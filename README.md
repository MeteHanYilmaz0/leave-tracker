# Izin Takip

Basit personel izin takip uygulamasi. FastAPI, SQLite ve server-rendered HTML kullanir.

## Kurulum

```powershell
git clone https://github.com/MeteHanYilmaz0/leave-tracker.git
cd leave-tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Tarayici: http://127.0.0.1:8000

Windows'ta hizli baslatmak icin proje klasorundeki `start_leave_tracker.bat` dosyasini calistirabilirsiniz. Ilk calistirmada sanal ortam ve paketler hazirlanir, sonraki acilislarda uygulama daha hizli baslar.

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
- Bitis tarihi baslangic tarihinden once olan izin kayitlari kabul edilmez.
- Yanlis girilen izin kayitlari personel detay sayfasindan tek tek silinebilir.
- PDF dilekceler SQLite veritabaninda saklanir.

## Kisayollar

- `/`: Personel arama kutusuna odaklanir.
- `Alt + N`: Yeni personel formunu acar.
- `Alt + L`: Personel detay sayfasinda izin gunu alanina odaklanir.

## Test

```powershell
python -m pytest
```
