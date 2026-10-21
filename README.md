# Farmavita Portal — Kurulum

1. Bu klasördeki **tüm dosyaları** (`.github` gizli klasörü dahil) GitHub reposunun köküne yükleyin.
2. Repo > Settings > Pages: Branch `main`, klasör `/ (root)`.
3. Repo > Settings > Secrets and variables > Actions > New repository secret:
   - `ANTHROPIC_API_KEY` (Türkçe çeviri için; yoksa özetler İngilizce kalır)
   - `NCBI_API_KEY` (opsiyonel, PubMed hız limitini artırır)
   - `NCBI_EMAIL` (opsiyonel)
4. Settings > Actions > General > Workflow permissions: **Read and write permissions**.
5. Actions sekmesi > "PubMed aylık güncelleme" > Run workflow (ilk dolum). Sonra her ayın 1'inde otomatik çalışır.

Elle düzenlenecek dosyalar:
- `data/rakipler.json`: ürün ve rakip bilgileri (DOLDURUN yazan yerler)
- `data/sorgular.json`: yeni suş/form eklemek için PubMed sorguları
- `data/yayinlar.json` içindeki `saha_notu`: her yayına kendi saha notunuzu yazın (güncellemede silinmez)
