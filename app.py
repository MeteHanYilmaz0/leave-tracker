from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "leave_tracker.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-secret-change-me")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SESSION_COOKIE = "leave_tracker_session"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
ANNUAL_LEAVE_DAYS = 14

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(title="Izin Takip", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def parse_optional_date(value: str | None) -> str | None:
    if not value:
        return None
    date.fromisoformat(value)
    return value


def validate_leave_dates(start_date: str | None, end_date: str | None) -> tuple[str | None, str | None]:
    parsed_start = parse_optional_date(start_date)
    parsed_end = parse_optional_date(end_date)
    if parsed_start and parsed_end and date.fromisoformat(parsed_end) < date.fromisoformat(parsed_start):
        raise ValueError("end_before_start")
    return parsed_start, parsed_end


def completed_years(hire_date: date, as_of: date | None = None) -> int:
    current = as_of or today_utc()
    years = current.year - hire_date.year
    if (current.month, current.day) < (hire_date.month, hire_date.day):
        years -= 1
    return max(years, 0)


def total_entitlement_days(hire_date: date, as_of: date | None = None) -> int:
    return completed_years(hire_date, as_of) * ANNUAL_LEAVE_DAYS


def anniversary_date(hire_date: date, years: int) -> date:
    try:
        return hire_date.replace(year=hire_date.year + years)
    except ValueError:
        return hire_date.replace(year=hire_date.year + years, day=28)


def make_password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = make_password_hash(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, password_hash)


def sign_session(username: str, issued_at: int) -> str:
    payload = f"{username}|{issued_at}"
    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}|{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(token).decode("ascii")


def verify_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, issued_at_raw, signature = decoded.split("|", 2)
        issued_at = int(issued_at_raw)
    except (ValueError, TypeError):
        return None
    expected = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{username}|{issued_at}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    now = int(datetime.now(timezone.utc).timestamp())
    if now - issued_at > SESSION_MAX_AGE_SECONDS:
        return None
    return username


@contextmanager
def db_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_database() -> None:
    with db_connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                hire_date TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS leave_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                start_date TEXT,
                end_date TEXT,
                days_used REAL NOT NULL CHECK (days_used > 0),
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS leave_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                leave_record_id INTEGER NOT NULL UNIQUE REFERENCES leave_records(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_bytes BLOB NOT NULL,
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        existing = db.execute("SELECT id FROM admin_users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        if existing is None:
            db.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                (ADMIN_USERNAME, make_password_hash(ADMIN_PASSWORD)),
            )


def current_admin(request: Request) -> str | None:
    return verify_session(request.cookies.get(SESSION_COOKIE))


def auth_redirect(request: Request) -> RedirectResponse | None:
    if current_admin(request):
        return None
    return RedirectResponse(url="/login", status_code=303)


def employee_stats(row: sqlite3.Row, as_of: date | None = None) -> dict[str, Any]:
    hire = date.fromisoformat(row["hire_date"])
    used = float(row["used_days"] or 0)
    year_count = completed_years(hire, as_of)
    entitlement = total_entitlement_days(hire, as_of)
    next_anniversary = anniversary_date(hire, year_count + 1)
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "full_name": f"{row['first_name']} {row['last_name']}",
        "hire_date": row["hire_date"],
        "is_active": bool(row["is_active"]),
        "completed_years": year_count,
        "entitlement_days": entitlement,
        "used_days": used,
        "remaining_days": entitlement - used,
        "next_anniversary": next_anniversary.isoformat(),
        "next_entitlement_days": entitlement + ANNUAL_LEAVE_DAYS,
    }


def get_employee(employee_id: int) -> sqlite3.Row | None:
    with db_connection() as db:
        return db.execute(
            """
            SELECT e.*, COALESCE(SUM(l.days_used), 0) AS used_days
            FROM employees e
            LEFT JOIN leave_records l ON l.employee_id = e.id
            WHERE e.id = ?
            GROUP BY e.id
            """,
            (employee_id,),
        ).fetchone()


def list_employee_stats(search: str = "") -> list[dict[str, Any]]:
    term = f"%{search.strip()}%"
    with db_connection() as db:
        rows = db.execute(
            """
            SELECT e.*, COALESCE(SUM(l.days_used), 0) AS used_days
            FROM employees e
            LEFT JOIN leave_records l ON l.employee_id = e.id
            WHERE ? = '%%' OR e.first_name LIKE ? OR e.last_name LIKE ?
            GROUP BY e.id
            ORDER BY e.is_active DESC, e.last_name COLLATE NOCASE, e.first_name COLLATE NOCASE
            """,
            (term, term, term),
        ).fetchall()
    return [employee_stats(row) for row in rows]


def flash_redirect(url: str, message: str, level: str = "ok") -> RedirectResponse:
    response = RedirectResponse(url=url, status_code=303)
    response.set_cookie("flash", message, max_age=10, httponly=True, samesite="lax")
    response.set_cookie("flash_level", level, max_age=10, httponly=True, samesite="lax")
    return response


def render(request: Request, template_name: str, context: dict[str, Any], status_code: int = 200) -> HTMLResponse:
    flash = request.cookies.get("flash")
    flash_level = request.cookies.get("flash_level", "ok")
    response = templates.TemplateResponse(
        request,
        template_name,
        {
            **context,
            "admin": current_admin(request),
            "flash": flash,
            "flash_level": flash_level,
        },
        status_code=status_code,
    )
    if flash:
        response.delete_cookie("flash")
        response.delete_cookie("flash_level")
    return response


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> Response:
    if not current_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/employees", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    if current_admin(request):
        return RedirectResponse(url="/employees", status_code=303)
    return render(request, "login.html", {"error": ""})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)) -> Response:
    with db_connection() as db:
        user = db.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
    if user is None or not verify_password(password, user["password_hash"]):
        return render(request, "login.html", {"error": "Kullanici adi veya sifre hatali."}, status_code=401)
    issued_at = int(datetime.now(timezone.utc).timestamp())
    response = RedirectResponse(url="/employees", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(username, issued_at),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/employees", response_class=HTMLResponse)
def employees(request: Request, q: str = "") -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    people = list_employee_stats(q)
    totals = {
        "entitlement_days": sum(item["entitlement_days"] for item in people),
        "used_days": sum(item["used_days"] for item in people),
        "remaining_days": sum(item["remaining_days"] for item in people),
    }
    return render(request, "employees.html", {"employees": people, "totals": totals, "q": q})


@app.get("/employees/new", response_class=HTMLResponse)
def new_employee_page(request: Request) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    return render(request, "employee_form.html", {"error": "", "form": {}})


@app.post("/employees")
def create_employee(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    hire_date: str = Form(...),
    is_active: str | None = Form(None),
) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    form = {"first_name": first_name, "last_name": last_name, "hire_date": hire_date, "is_active": is_active}
    try:
        date.fromisoformat(hire_date)
    except ValueError:
        return render(request, "employee_form.html", {"error": "Ise baslama tarihi gecersiz.", "form": form}, 400)
    if not first_name.strip() or not last_name.strip():
        return render(request, "employee_form.html", {"error": "Ad ve soyad zorunludur.", "form": form}, 400)
    with db_connection() as db:
        cursor = db.execute(
            """
            INSERT INTO employees (first_name, last_name, hire_date, is_active)
            VALUES (?, ?, ?, ?)
            """,
            (first_name.strip(), last_name.strip(), hire_date, 1 if is_active else 0),
        )
        employee_id = cursor.lastrowid
    return flash_redirect(f"/employees/{employee_id}", "Personel kaydi olusturuldu.")


@app.get("/employees/{employee_id}/edit", response_class=HTMLResponse)
def edit_employee_page(request: Request, employee_id: int) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    row = get_employee(employee_id)
    if row is None:
        return render(request, "not_found.html", {"title": "Personel bulunamadi"}, 404)
    return render(request, "employee_form.html", {"error": "", "form": dict(row), "employee_id": employee_id})


@app.post("/employees/{employee_id}")
def update_employee(
    request: Request,
    employee_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    hire_date: str = Form(...),
    is_active: str | None = Form(None),
) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    row = get_employee(employee_id)
    if row is None:
        return render(request, "not_found.html", {"title": "Personel bulunamadi"}, 404)
    form = {"first_name": first_name, "last_name": last_name, "hire_date": hire_date, "is_active": is_active}
    try:
        date.fromisoformat(hire_date)
    except ValueError:
        return render(
            request,
            "employee_form.html",
            {"error": "Ise baslama tarihi gecersiz.", "form": form, "employee_id": employee_id},
            400,
        )
    if not first_name.strip() or not last_name.strip():
        return render(
            request,
            "employee_form.html",
            {"error": "Ad ve soyad zorunludur.", "form": form, "employee_id": employee_id},
            400,
        )
    with db_connection() as db:
        db.execute(
            """
            UPDATE employees
            SET first_name = ?, last_name = ?, hire_date = ?, is_active = ?
            WHERE id = ?
            """,
            (first_name.strip(), last_name.strip(), hire_date, 1 if is_active else 0, employee_id),
        )
    return flash_redirect(f"/employees/{employee_id}", "Personel bilgileri guncellendi.")


@app.post("/employees/{employee_id}/delete")
def delete_employee(request: Request, employee_id: int) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    row = get_employee(employee_id)
    if row is None:
        return render(request, "not_found.html", {"title": "Personel bulunamadi"}, 404)
    with db_connection() as db:
        db.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    return flash_redirect("/employees", "Personel ve ilgili izin kayitlari silindi.")


@app.get("/employees/{employee_id}", response_class=HTMLResponse)
def employee_detail(request: Request, employee_id: int) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    row = get_employee(employee_id)
    if row is None:
        return render(request, "not_found.html", {"title": "Personel bulunamadi"}, 404)
    stats = employee_stats(row)
    with db_connection() as db:
        leaves = db.execute(
            """
            SELECT l.*, d.id AS document_id, d.filename
            FROM leave_records l
            LEFT JOIN leave_documents d ON d.leave_record_id = l.id
            WHERE l.employee_id = ?
            ORDER BY l.created_at DESC, l.id DESC
            """,
            (employee_id,),
        ).fetchall()
    return render(request, "employee_detail.html", {"employee": stats, "leaves": leaves, "error": ""})


@app.post("/employees/{employee_id}/leaves")
async def create_leave(
    request: Request,
    employee_id: int,
    start_date: str | None = Form(None),
    end_date: str | None = Form(None),
    days_used: float = Form(...),
    note: str = Form(""),
    document: UploadFile | None = File(None),
) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    row = get_employee(employee_id)
    if row is None:
        return render(request, "not_found.html", {"title": "Personel bulunamadi"}, 404)
    stats = employee_stats(row)
    try:
        parsed_start, parsed_end = validate_leave_dates(start_date, end_date)
    except ValueError:
        return flash_redirect(
            f"/employees/{employee_id}",
            "Izin tarihi gecersiz. Bitis tarihi baslangictan once olamaz.",
            "error",
        )
    if days_used <= 0:
        return flash_redirect(f"/employees/{employee_id}", "Kullanilan izin gunu 0'dan buyuk olmali.", "error")
    if days_used > stats["remaining_days"]:
        return flash_redirect(
            f"/employees/{employee_id}",
            f"Kalan izin hakki yetersiz. Kalan: {stats['remaining_days']:g} gun.",
            "error",
        )
    file_bytes = b""
    filename = ""
    content_type = ""
    if document and document.filename:
        if document.content_type != "application/pdf":
            return flash_redirect(f"/employees/{employee_id}", "Sadece PDF dilekce yuklenebilir.", "error")
        file_bytes = await document.read()
        if not file_bytes.startswith(b"%PDF"):
            return flash_redirect(f"/employees/{employee_id}", "Yuklenen dosya gecerli bir PDF degil.", "error")
        filename = Path(document.filename).name
        content_type = document.content_type
    with db_connection() as db:
        cursor = db.execute(
            """
            INSERT INTO leave_records (employee_id, start_date, end_date, days_used, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (employee_id, parsed_start, parsed_end, days_used, note.strip()),
        )
        leave_id = cursor.lastrowid
        if file_bytes:
            db.execute(
                """
                INSERT INTO leave_documents (leave_record_id, filename, content_type, file_bytes)
                VALUES (?, ?, ?, ?)
                """,
                (leave_id, filename, content_type, file_bytes),
            )
    return flash_redirect(f"/employees/{employee_id}", "Izin kaydi olusturuldu.")


@app.post("/employees/{employee_id}/leaves/{leave_id}/delete")
def delete_leave(request: Request, employee_id: int, leave_id: int) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    row = get_employee(employee_id)
    if row is None:
        return render(request, "not_found.html", {"title": "Personel bulunamadi"}, 404)
    with db_connection() as db:
        leave = db.execute(
            "SELECT id FROM leave_records WHERE id = ? AND employee_id = ?",
            (leave_id, employee_id),
        ).fetchone()
        if leave is None:
            return render(request, "not_found.html", {"title": "Izin kaydi bulunamadi"}, 404)
        db.execute("DELETE FROM leave_records WHERE id = ?", (leave_id,))
    return flash_redirect(f"/employees/{employee_id}", "Izin kaydi silindi.")


@app.get("/leaves/{leave_id}/document")
def leave_document(request: Request, leave_id: int) -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    with db_connection() as db:
        document = db.execute(
            """
            SELECT filename, content_type, file_bytes
            FROM leave_documents
            WHERE leave_record_id = ?
            """,
            (leave_id,),
        ).fetchone()
    if document is None:
        return Response("Dosya bulunamadi.", status_code=404)
    headers = {"Content-Disposition": f'inline; filename="{document["filename"]}"'}
    return Response(content=document["file_bytes"], media_type=document["content_type"], headers=headers)


@app.get("/reports/summary", response_class=HTMLResponse)
def summary_report(request: Request, q: str = "") -> Response:
    redirect = auth_redirect(request)
    if redirect:
        return redirect
    people = list_employee_stats(q)
    return render(request, "summary.html", {"employees": people, "q": q})
