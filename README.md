# Izin Takip

Personel izinlerini takip etmek icin hazirlanmis basit MVP uygulamasi.
FastAPI, SQLite ve server-rendered HTML kullanir.

## Ozellikler

- Personel ekleme, duzenleme ve sistemden silme.
- Personele izin kaydi ekleme.
- Yanlis girilen izin kaydini tek tek silme.
- Her tamamlanan calisma yili icin 14 gun izin hakki hesaplama.
- Kullanilan ve kalan izin gunlerini otomatik gosterme.
- PDF izin dilekcesi yukleme ve goruntuleme.
- Personel arama ve ozet rapor ekrani.
- Hizli kullanim icin klavye kisayollari.
- Windows icin tek tikla baslatma dosyasi.

## Hizli Baslatma

Windows'ta en kolay kullanim:

```powershell
start_leave_tracker.bat
```

Bu dosya ilk calistirmada sanal ortami ve paketleri hazirlar. Sonraki acilislarda uygulamayi daha hizli baslatir ve tarayicida su adresi acar:

```text
http://127.0.0.1:8000
```

## Manuel Kurulum

```powershell
git clone https://github.com/MeteHanYilmaz0/leave-tracker.git
cd leave-tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Tarayici:

```text
http://127.0.0.1:8000
```

## Giris Bilgileri

Varsayilan admin hesabi:

```text
Kullanici adi: admin
Sifre: admin123
```

Canli kullanimda varsayilan sifreyi degistirin:

```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="guclu-bir-sifre"
$env:SECRET_KEY="uzun-rastgele-bir-deger"
```

## Kullanim

1. Giris yapin.
2. `Yeni personel` ile personel ekleyin.
3. Personel detay sayfasindan izin gunu girin.
4. Gerekirse PDF dilekce yukleyin.
5. Yanlis girilen izinlerde sadece ilgili izin satirindaki `Sil` butonunu kullanin.
6. Personeli tamamen silmek icin personel detayindaki ust `Sil` butonunu kullanin.

## Kisayollar

- `/`: Personel arama kutusuna odaklanir.
- `Alt + N`: Yeni personel formunu acar.
- `Alt + L`: Personel detay sayfasinda izin gunu alanina odaklanir.

## Davranis

- Ilk yil dolmadan izin hakki 0 gundur.
- Her tamamlanan calisma yili icin 14 gun izin hakki eklenir.
- Kullanilan izin gunu manuel girilir.
- Bitis tarihi baslangic tarihinden once olan izin kayitlari kabul edilmez.
- Kalan haktan fazla izin girilemez.
- Personel silinirse o personele ait izin kayitlari da silinir.
- Tekil izin silme sadece secilen izin kaydini siler.

## Test

```powershell
python -m pytest
```
