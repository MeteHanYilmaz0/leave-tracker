import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
    import app as app_module

    app_module = importlib.reload(app_module)
    app_module.init_database()
    with TestClient(app_module.app) as test_client:
        yield test_client, app_module


def login(client):
    return client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)


def create_employee(client, first_name="Ada", last_name="Lovelace", hire_date="2023-04-01"):
    response = client.post(
        "/employees",
        data={
            "first_name": first_name,
            "last_name": last_name,
            "hire_date": hire_date,
            "is_active": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return int(response.headers["location"].rstrip("/").split("/")[-1])


def test_leave_entitlement_calculation(client):
    _, app_module = client
    as_of = app_module.date(2026, 5, 11)

    assert app_module.total_entitlement_days(app_module.date(2025, 6, 11), as_of) == 0
    assert app_module.total_entitlement_days(app_module.date(2025, 5, 11), as_of) == 14
    assert app_module.total_entitlement_days(app_module.date(2023, 4, 11), as_of) == 42


def test_auth_required_for_employee_list(client):
    test_client, _ = client
    response = test_client.get("/employees", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_and_create_employee(client):
    test_client, _ = client
    response = login(test_client)

    assert response.status_code == 303
    assert response.headers["location"] == "/employees"

    employee_id = create_employee(test_client, hire_date="2023-04-11")
    detail = test_client.get(f"/employees/{employee_id}")

    assert detail.status_code == 200
    assert "Ada Lovelace" in detail.text


def test_leave_entry_reduces_remaining_days(client):
    test_client, _ = client
    login(test_client)
    employee_id = create_employee(test_client, hire_date="2023-04-11")

    response = test_client.post(
        f"/employees/{employee_id}/leaves",
        data={"days_used": "12", "start_date": "2026-05-01", "end_date": "2026-05-12", "note": "Yillik izin"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = test_client.get(f"/employees/{employee_id}")
    assert ">30<" in detail.text


def test_leave_entry_cannot_exceed_remaining_days(client):
    test_client, _ = client
    login(test_client)
    employee_id = create_employee(test_client, hire_date="2023-04-11")

    response = test_client.post(
        f"/employees/{employee_id}/leaves",
        data={"days_used": "99", "start_date": "", "end_date": "", "note": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    detail = test_client.get(f"/employees/{employee_id}")
    assert "Kalan izin hakki yetersiz" in detail.text


def test_pdf_upload_and_download(client):
    test_client, _ = client
    login(test_client)
    employee_id = create_employee(test_client, hire_date="2023-04-11")
    pdf_bytes = b"%PDF-1.4\n%test\n"

    response = test_client.post(
        f"/employees/{employee_id}/leaves",
        data={"days_used": "1", "start_date": "", "end_date": "", "note": "Dilekce var"},
        files={"document": ("dilekce.pdf", pdf_bytes, "application/pdf")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    document = test_client.get("/leaves/1/document")
    assert document.status_code == 200
    assert document.headers["content-type"] == "application/pdf"
    assert document.content == pdf_bytes


def test_leave_delete_removes_only_selected_leave_and_document(client):
    test_client, app_module = client
    login(test_client)
    employee_id = create_employee(test_client, hire_date="2023-04-11")

    test_client.post(
        f"/employees/{employee_id}/leaves",
        data={"days_used": "4", "start_date": "", "end_date": "", "note": "Kalacak"},
        follow_redirects=False,
    )
    test_client.post(
        f"/employees/{employee_id}/leaves",
        data={"days_used": "6", "start_date": "", "end_date": "", "note": "Silinecek"},
        files={"document": ("dilekce.pdf", b"%PDF-1.4\n%test\n", "application/pdf")},
        follow_redirects=False,
    )

    response = test_client.post(f"/employees/{employee_id}/leaves/2/delete", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/employees/{employee_id}"
    with app_module.db_connection() as db:
        leaves = db.execute("SELECT days_used, note FROM leave_records ORDER BY id").fetchall()
        documents = db.execute("SELECT id FROM leave_documents").fetchall()
    assert len(leaves) == 1
    assert leaves[0]["days_used"] == 4
    assert leaves[0]["note"] == "Kalacak"
    assert documents == []


def test_employee_edit_updates_hire_date_and_entitlement(client):
    test_client, _ = client
    login(test_client)
    employee_id = create_employee(test_client, hire_date="2023-04-11")

    response = test_client.post(
        f"/employees/{employee_id}",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "hire_date": "2022-04-11",
            "is_active": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    detail = test_client.get(f"/employees/{employee_id}")
    assert "Toplam hak" in detail.text
    assert ">56<" in detail.text


def test_employee_delete_removes_employee_and_related_leave(client):
    test_client, _ = client
    login(test_client)
    employee_id = create_employee(test_client, hire_date="2023-04-11")
    test_client.post(
        f"/employees/{employee_id}/leaves",
        data={"days_used": "1", "start_date": "", "end_date": "", "note": "Silinecek"},
        follow_redirects=False,
    )

    response = test_client.post(f"/employees/{employee_id}/delete", follow_redirects=False)

    assert response.status_code == 303
    detail = test_client.get(f"/employees/{employee_id}")
    assert detail.status_code == 404
