# Farmavita Portal — Kurulum

Dosya yerleşimi (depo kökü): `index.html`, `README.md`, `.gitignore`, `data/`, `scripts/`, `.github/workflows/pubmed-aylik.yml`

## Secrets (Settings > Secrets and variables > Actions)
- `YONETICI_SIFRE` (zorunlu): uzun, rastgele bir şifre (en az 16 karakter). Kimseyle paylaşmayın.
- `KULLANICILAR` (zorunlu): her satıra bir kişi: `Ad Soyad` ya da `Ad Soyad;şifre`.
  Kullanıcı adı = soyad hariç adlar, şifre = soyad (şifre yazılmadıysa). Büyük/küçük harf ve Türkçe karakter önemsizdir.
- Çeviri için biri yeterli: `GEMINI_API_KEY`, `NVIDIA_API_KEY` veya `ANTHROPIC_API_KEY`.
- `NCBI_API_KEY`, `NCBI_EMAIL` (opsiyonel)
- `RAKIPLER_JSON` (opsiyonel): doluysa rakip verisi dosya yerine buradan okunur.

## Çalıştırma
Actions > "PubMed aylık güncelleme" > Run workflow. Kullanıcı eklemek/çıkarmak/şifre değiştirmek için `KULLANICILAR` secret'ını düzenleyip iş akışını yeniden çalıştırın.

## Notlar
- Yayınlar ve rakip verisi `data/veri.enc` içinde şifreli durur; `data/giris.json` kullanıcıların anahtar kutularıdır.
- `data/yayinlar.json` ve `data/rakipler.json` açık hâlde depoda tutulmaz. İlk çalıştırmada şifrelenir ve repodan kaldırılır.
- `YONETICI_SIFRE`'yi değiştirmek isterseniz önce eski şifreyle bir çalıştırma yapıp sonra değiştirmeyin: şifreyi değiştirirseniz veri açılamaz. Değişiklik gerekirse bana yazın.
