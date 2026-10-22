#!/usr/bin/env python3
"""PubMed'den son 24 ayın yayınlarını çeker, data/yayinlar.json dosyasını günceller.
Ortam değişkenleri (hepsi opsiyonel):
  NCBI_API_KEY, NCBI_EMAIL  -> PubMed hız limiti / nezaket
  GEMINI_API_KEY            -> Türkçe çeviri için (Google Gemini)
  NVIDIA_API_KEY            -> Türkçe çeviri için (NVIDIA Build / NIM, 'nvapi-' ile başlar)
  NVIDIA_MODEL              -> varsayılan meta/llama-3.3-70b-instruct (build.nvidia.com'dan model adını kontrol edin)
  ANTHROPIC_API_KEY         -> Türkçe çeviri için (Claude); ikisi de varsa Gemini kullanılır
  GEMINI_MODEL              -> varsayılan gemini-2.5-flash (Google'ın güncel model adını kontrol edin)
  CLAUDE_MODEL              -> varsayılan claude-sonnet-4-6
  MAX_CEVIRI                -> bir çalışmada en fazla kaç özet çevrilsin (varsayılan 100)
"""
import json, os, re, time, datetime as dt, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAYIN = os.path.join(KOK, "data", "yayinlar.json")
SORGU = os.path.join(KOK, "data", "sorgular.json")
NCBI_KEY = os.getenv("NCBI_API_KEY", "")
EMAIL = os.getenv("NCBI_EMAIL", "")
CLAUDE_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL") or "meta/llama-3.3-70b-instruct"
ANY_KEY = bool(GEMINI_KEY or NVIDIA_KEY or CLAUDE_KEY)
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
MAX_CEVIRI = int(os.getenv("MAX_CEVIRI") or "100")
MAX_DAKIKA = int(os.getenv("MAX_DAKIKA") or "45")
CEVIRI_ARA_SN = float(os.getenv("CEVIRI_ARA_SN") or "7")   # ücretsiz katman dakika limitleri için
PENCERE_AY = 24
RETMAX = 100

def eutils(ad, **p):
    p.update(tool="farmavita-portal")
    if NCBI_KEY: p["api_key"] = NCBI_KEY
    if EMAIL: p["email"] = EMAIL
    url = BASE + ad + "?" + urllib.parse.urlencode(p)
    for deneme in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:
            print("  uyarı:", e); time.sleep(2 * (deneme + 1))
    raise SystemExit("PubMed'e ulaşılamadı: " + ad)

def pmid_ara(sorgu, min_tarih, max_tarih):
    veri = eutils("esearch.fcgi", db="pubmed", term=sorgu, retmax=RETMAX, retmode="json",
                  datetype="pdat", mindate=min_tarih, maxdate=max_tarih, sort="date")
    time.sleep(0.4)
    return json.loads(veri)["esearchresult"].get("idlist", [])

def metin(el):
    return "".join(el.itertext()).strip() if el is not None else ""

TIP = {"Meta-Analysis": "Meta-analiz", "Systematic Review": "Sistematik derleme",
       "Randomized Controlled Trial": "RKÇ", "Clinical Trial": "Klinik çalışma",
       "Review": "Derleme", "Observational Study": "Gözlemsel"}

def cek(pmidler):
    sonuc = {}
    for i in range(0, len(pmidler), 100):
        grup = pmidler[i:i + 100]
        xml = eutils("efetch.fcgi", db="pubmed", id=",".join(grup), retmode="xml")
        time.sleep(0.4)
        for m in ET.fromstring(xml).findall(".//PubmedArticle"):
            pmid = m.findtext("MedlineCitation/PMID")
            parcalar = []
            for a in m.findall(".//Abstract/AbstractText"):
                etiket = a.get("Label")
                parcalar.append((etiket + ": " if etiket else "") + metin(a))
            ozet = "\n".join(p for p in parcalar if p.strip())
            if not ozet:
                continue
            yil = m.findtext(".//JournalIssue/PubDate/Year") or (m.findtext(".//JournalIssue/PubDate/MedlineDate") or "")[:4]
            yazarlar = []
            for au in m.findall(".//AuthorList/Author")[:3]:
                ad = (au.findtext("LastName") or "") + " " + (au.findtext("Initials") or "")
                if ad.strip(): yazarlar.append(ad.strip())
            if len(m.findall(".//AuthorList/Author")) > 3: yazarlar.append("ve ark.")
            tipler = [t.text for t in m.findall(".//PublicationType") if t.text]
            tip = next((TIP[t] for t in TIP if t in tipler), "")
            doi = next((x.text for x in m.findall(".//ArticleIdList/ArticleId") if x.get("IdType") == "doi"), "")
            sonuc[pmid] = {"pmid": pmid, "baslik_en": metin(m.find(".//ArticleTitle")),
                           "dergi": m.findtext(".//Journal/Title") or "", "yil": int(yil) if yil.isdigit() else None,
                           "yazarlar": ", ".join(yazarlar), "doi": doi, "tip": tip, "ozet_en": ozet}
    return sonuc

SISTEM = ("Sen tıbbi bir çevirmensin. Verilen PubMed başlığını ve özetini Türkçeye sadık biçimde çevir. "
          "Yalnızca metinde yazan bilgiyi kullan; sayı, sonuç, yorum veya pazarlama ifadesi EKLEME, çıkarma. "
          "Kısaltmaları (LGG, RKÇ, CFU vb.) koru. Çıktı biçimi: ilk satır 'BASLIK: <Türkçe başlık>', "
          "sonra boş satır, sonra Türkçe özet (etiketli bölümler varsa etiketleri koru).")

SON_HATA = ""

def gemini_adaylar():
    """Hesabın erişebildiği metin üreten flash modellerini en uygundan başlayarak sıralar."""
    import re
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                                 headers={"x-goog-api-key": GEMINI_KEY})
    with urllib.request.urlopen(req, timeout=60) as r:
        modeller = json.loads(r.read()).get("models", [])
    aday = []
    for m in modeller:
        ad = m.get("name", "").replace("models/", "")
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if "flash" not in ad or any(x in ad for x in ("image", "tts", "live", "audio", "embed", "robotics", "vision")):
            continue
        v = re.search(r"(\d+(?:\.\d+)?)", ad)
        aday.append((("preview" in ad or "exp" in ad), ("lite" in ad), -(float(v.group(1)) if v else 0), ad))
    aday.sort()
    return [x[-1] for x in aday]

def _gemini_istek(model, kullanici):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    govde = {"systemInstruction": {"parts": [{"text": SISTEM}]},
             "contents": [{"role": "user", "parts": [{"text": kullanici}]}],
             "generationConfig": {"temperature": 0.1}}
    req = urllib.request.Request(url, data=json.dumps(govde).encode(),
                                 headers={"content-type": "application/json", "x-goog-api-key": GEMINI_KEY})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"].strip()

def _gemini(kullanici):
    global GEMINI_MODEL
    try:
        return _gemini_istek(GEMINI_MODEL, kullanici)
    except urllib.error.HTTPError as e:
        if e.code not in (400, 404):
            raise
        print(f"  '{GEMINI_MODEL}' kullanılamadı (HTTP {e.code}), güncel modeller aranıyor...")
    adaylar = gemini_adaylar()
    print("  Aday modeller:", adaylar[:6])
    son = None
    for m in adaylar[:4]:
        try:
            cevap = _gemini_istek(m, kullanici)
            GEMINI_MODEL = m
            print("  Seçilen model:", m)
            return cevap
        except Exception as e:
            son = e
            print(f"  {m} denenemedi: {e}")
    raise RuntimeError(f"Hiçbir Gemini modeli çalışmadı: {son}")

def _claude(kullanici):
    istek = {"model": MODEL, "max_tokens": 1800, "system": SISTEM,
             "messages": [{"role": "user", "content": kullanici}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(istek).encode(),
                                 headers={"content-type": "application/json", "x-api-key": CLAUDE_KEY,
                                          "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["content"][0]["text"].strip()

def model_listesi_yaz():
    try:
        req = urllib.request.Request("https://integrate.api.nvidia.com/v1/models",
                                     headers={"Authorization": "Bearer " + NVIDIA_KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            idler = [m["id"] for m in json.loads(r.read()).get("data", [])]
        sec = [i for i in idler if any(x in i.lower() for x in ("instruct", "chat", "llama", "qwen", "mistral", "gemma"))]
        print("  NVIDIA'da kullanılabilir bazı modeller:", sec[:40])
    except Exception as e:
        print("  Model listesi alınamadı:", e)

def _nvidia(kullanici):
    govde = {"model": NVIDIA_MODEL, "temperature": 0.1, "max_tokens": 2000, "stream": False,
             "messages": [{"role": "system", "content": SISTEM}, {"role": "user", "content": kullanici}]}
    req = urllib.request.Request("https://integrate.api.nvidia.com/v1/chat/completions", data=json.dumps(govde).encode(),
                                 headers={"content-type": "application/json", "accept": "application/json",
                                          "Authorization": "Bearer " + NVIDIA_KEY})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            cevap = json.loads(r.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            print(f"  NVIDIA modeli '{NVIDIA_MODEL}' kullanılamadı (HTTP {e.code}).")
            model_listesi_yaz()
        raise
    return re.sub(r"<think>.*?</think>", "", cevap, flags=re.S).strip()

KALICI_OLU = set()   # anahtar/model gibi kalıcı hata veren sağlayıcılar (bu çalışma için bırakılır)

def hata_turu(e):
    """429 ve 5xx gibi geçici hatalarda bekleyip yeniden denenir; 400/401/403/404 kalıcı sayılır."""
    if isinstance(e, urllib.error.HTTPError):
        return "gecici" if e.code in (408, 409, 425, 429) or e.code >= 500 else "kalici"
    return "gecici"   # zaman aşımı, bağlantı kopması, boş/bozuk yanıt

def bekleme_suresi(e, deneme):
    if isinstance(e, urllib.error.HTTPError) and e.headers:
        ra = e.headers.get("Retry-After")
        if ra and str(ra).isdigit():
            return min(int(ra) + 1, 120)
    return min(15 * 2 ** deneme, 120)

def saglayicilar():
    s = []
    if GEMINI_KEY: s.append(("gemini", _gemini))
    if NVIDIA_KEY: s.append(("nvidia", _nvidia))
    if CLAUDE_KEY: s.append(("claude", _claude))
    return [x for x in s if x[0] not in KALICI_OLU]

def cevir(baslik, ozet):
    global SON_HATA
    kullanici = f"Başlık: {baslik}\n\nÖzet:\n{ozet}"
    for ad, fn in saglayicilar():
        for deneme in range(4):
            try:
                cevap = fn(kullanici)
                baslik_tr, _, govde = cevap.partition("\n")
                if not govde.strip():
                    raise ValueError("Boş çeviri döndü")
                return baslik_tr.replace("BASLIK:", "").strip(), govde.strip()
            except Exception as e:
                ayrinti = getattr(e, "read", lambda: b"")()[:200]
                SON_HATA = f"[{ad}] {e} {ayrinti}".strip()
                tur = hata_turu(e)
                print(f"  çeviri hatası ({tur}, deneme {deneme + 1}/4): {SON_HATA}")
                kota = isinstance(e, urllib.error.HTTPError) and e.code == 429 and b"quota" in ayrinti.lower()
                if kota and deneme >= 1:
                    print(f"  {ad}: kota dolmuş görünüyor, bu çalışma için bırakılıyor.")
                    KALICI_OLU.add(ad)
                    break
                if tur == "kalici":
                    KALICI_OLU.add(ad)
                    break
                if deneme < 3:
                    time.sleep(bekleme_suresi(e, deneme))
    return None

def kaydet(mevcut, bugun):
    alt_yil = bugun.year - 2
    liste = [y for y in mevcut.values() if (y.get("yil") or 0) >= alt_yil]
    liste.sort(key=lambda y: (y.get("yil") or 0, y["pmid"]), reverse=True)
    bekleyen = sum(1 for y in liste if not y.get("ozet_tr"))
    hata = SON_HATA or ("" if ANY_KEY else "Çeviri anahtarı tanımlı değil (GEMINI_API_KEY, NVIDIA_API_KEY veya ANTHROPIC_API_KEY secret'ı eksik)")
    json.dump({"son_guncelleme": bugun.isoformat(), "toplam": len(liste), "ceviri_bekleyen": bekleyen,
               "ceviri_son_hata": hata if bekleyen else "", "yayinlar": liste},
              open(YAYIN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(liste), bekleyen

def main():
    bugun = dt.date.today()
    bas = (bugun - dt.timedelta(days=PENCERE_AY * 30)).strftime("%Y/%m/%d")
    bit = bugun.strftime("%Y/%m/%d")
    sorgular = json.load(open(SORGU, encoding="utf-8"))["sorgular"]
    mevcut = {y["pmid"]: y for y in json.load(open(YAYIN, encoding="utf-8")).get("yayinlar", [])}

    etiketler, kategoriler, gruplar = {}, {}, {}
    for s in sorgular:
        print("Sorgu:", s["id"])
        for pmid in pmid_ara(s["sorgu"], bas, bit):
            etiketler.setdefault(pmid, set()).add(s["id"])
            kategoriler.setdefault(pmid, s["kategori"])
            gruplar.setdefault(pmid, set()).add(s["grup"])

    yeni_idler = [p for p in etiketler if p not in mevcut]
    print(f"{len(etiketler)} yayın bulundu, {len(yeni_idler)} yeni.")
    for pmid, kayit in cek(yeni_idler).items():
        kayit.update(ozet_tr="", baslik_tr="", saha_notu="", ceviri="bekliyor")
        mevcut[pmid] = kayit

    for pmid, y in mevcut.items():
        if pmid in etiketler:
            y["etiketler"] = sorted(set(y.get("etiketler", [])) | etiketler[pmid])
            y["kategori"] = kategoriler[pmid]
            y["grup"] = sorted(gruplar[pmid])

    kaydet(mevcut, bugun)   # PubMed verisi çeviri öncesi de kaydedilir

    cevrilen, ardisik, baslangic = 0, 0, time.time()
    # Önce bizim ürünlerle ilgili yayınlar, sonra yeniden eskiye
    bekleyenler = sorted((y for y in mevcut.values() if not y.get("ozet_tr")),
                         key=lambda y: ("kendi" not in y.get("grup", []), -(y.get("yil") or 0)))
    if ANY_KEY:
        print(f"{len(bekleyenler)} yayın çeviri bekliyor.")
        for y in bekleyenler:
            if cevrilen >= MAX_CEVIRI:
                print(f"Çalışma başına çeviri sınırına ulaşıldı ({MAX_CEVIRI}); kalanlar sonraki çalışmada."); break
            if (time.time() - baslangic) / 60 >= MAX_DAKIKA:
                print("Süre sınırına ulaşıldı; kalanlar sonraki çalışmada."); break
            if not saglayicilar():
                print("Kullanılabilir çeviri sağlayıcısı kalmadı (kota doldu veya anahtar/model hatası); çeviri durduruldu."); break
            sonuc = cevir(y["baslik_en"], y["ozet_en"])
            if sonuc:
                y["baslik_tr"], y["ozet_tr"], y["ceviri"] = sonuc[0], sonuc[1], "yapay-zeka"
                cevrilen += 1; ardisik = 0
                if cevrilen % 10 == 0:
                    kaydet(mevcut, bugun); print(f"  ... {cevrilen} çeviri kaydedildi")
            else:
                ardisik += 1
                if ardisik >= 8:
                    print("Üst üste 8 yayın çevrilemedi; durduruldu. Sonraki çalışmada devam edilecek."); break
            time.sleep(CEVIRI_ARA_SN)

    toplam, bekleyen = kaydet(mevcut, bugun)
    print(f"Kaydedildi: {toplam} yayın, {cevrilen} yeni çeviri, {bekleyen} çeviri bekliyor.")

if __name__ == "__main__":
    main()
