#!/usr/bin/env python3
"""PubMed'den son 24 ayın yayınlarını çeker, data/yayinlar.json dosyasını günceller.
Ortam değişkenleri (hepsi opsiyonel):
  NCBI_API_KEY, NCBI_EMAIL  -> PubMed hız limiti / nezaket
  ANTHROPIC_API_KEY         -> Türkçe çeviri için (yoksa çeviri yapılmaz)
  CLAUDE_MODEL              -> varsayılan claude-sonnet-4-6
  MAX_CEVIRI                -> bir çalışmada en fazla kaç özet çevrilsin (varsayılan 40)
"""
import json, os, time, datetime as dt, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAYIN = os.path.join(KOK, "data", "yayinlar.json")
SORGU = os.path.join(KOK, "data", "sorgular.json")
NCBI_KEY = os.getenv("NCBI_API_KEY", "")
EMAIL = os.getenv("NCBI_EMAIL", "")
CLAUDE_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_CEVIRI = int(os.getenv("MAX_CEVIRI", "40"))
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

def cevir(baslik, ozet):
    if not CLAUDE_KEY:
        return None
    istek = {"model": MODEL, "max_tokens": 1800,
             "system": ("Sen tıbbi bir çevirmensin. Verilen PubMed başlığını ve özetini Türkçeye sadık biçimde çevir. "
                        "Yalnızca metinde yazan bilgiyi kullan; sayı, sonuç, yorum veya pazarlama ifadesi EKLEME, çıkarma. "
                        "Kısaltmaları (LGG, RKÇ, CFU vb.) koru. Çıktı biçimi: ilk satır 'BASLIK: <Türkçe başlık>', "
                        "sonra boş satır, sonra Türkçe özet (etiketli bölümler varsa etiketleri koru)."),
             "messages": [{"role": "user", "content": f"Başlık: {baslik}\n\nÖzet:\n{ozet}"}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(istek).encode(),
                                 headers={"content-type": "application/json", "x-api-key": CLAUDE_KEY,
                                          "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            cevap = json.loads(r.read())["content"][0]["text"].strip()
    except Exception as e:
        print("  çeviri hatası:", e); return None
    baslik_tr, _, govde = cevap.partition("\n")
    return baslik_tr.replace("BASLIK:", "").strip(), govde.strip()

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

    cevrilen = 0
    for y in sorted(mevcut.values(), key=lambda x: x.get("yil") or 0, reverse=True):
        if y.get("ozet_tr") or cevrilen >= MAX_CEVIRI or not CLAUDE_KEY:
            continue
        sonuc = cevir(y["baslik_en"], y["ozet_en"])
        if sonuc:
            y["baslik_tr"], y["ozet_tr"], y["ceviri"] = sonuc[0], sonuc[1], "yapay-zeka"
            cevrilen += 1
        time.sleep(0.5)

    alt_yil = bugun.year - 2
    liste = [y for y in mevcut.values() if (y.get("yil") or 0) >= alt_yil]
    liste.sort(key=lambda y: (y.get("yil") or 0, y["pmid"]), reverse=True)
    json.dump({"son_guncelleme": bugun.isoformat(), "toplam": len(liste), "yayinlar": liste},
              open(YAYIN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Kaydedildi: {len(liste)} yayın, {cevrilen} yeni çeviri.")

if __name__ == "__main__":
    main()
