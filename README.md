# Izin Takip

Basit personel izin takip uygulamasi. FastAPI, SQLite ve server-rendered HTML kullanir.

## Kurulum

```powershell
cd C:\Users\mete_\Desktop\leave-tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Tarayici: http://127.0.0.1:8000

Varsayilan admin hesabi:

```text
Kullanici adi: admin
Sifre: admin123
```

Canli kullanimda asagidaki ortam degiskenlerini verin:

```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="guclu-bir-sifre"
$env:SECRET_KEY="uzun-rastgele-bir-deger"
```

## Davranis

- Her tamamlanan calisma yili icin 14 gun izin hakki hesaplanir.
- Ilk yil dolmadan izin hakki 0 gundur.
- Kullanilan izin gunu manuel girilir.
- PDF dilekceler SQLite veritabaninda saklanir.

## Test

```powershell
pytest
```
