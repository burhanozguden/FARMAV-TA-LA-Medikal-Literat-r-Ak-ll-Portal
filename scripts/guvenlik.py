#!/usr/bin/env python3
"""Veriyi şifreler / çözer ve kullanıcı girişini hazırlar.

Komutlar:
  ac     data/veri.enc varsa çözüp data/yayinlar.json (ve rakipler.json) dosyalarını geçici olarak yazar.
  kapat  data/yayinlar.json + rakipler.json + sorgular.json dosyalarını data/veri.enc içine şifreler,
         data/giris.json (kullanıcı anahtarları) dosyasını yeniden üretir, açık dosyaları siler.

Ortam değişkenleri:
  YONETICI_SIFRE   (zorunlu) Yönetici şifresi; veri anahtarını açmak için. Uzun ve rastgele seçin.
  KULLANICILAR     (zorunlu: kapat) Her satır: "Ad Soyad" veya "Ad Soyad;şifre".
                   Kullanıcı adı = soyad hariç adlar, şifre = soyad (belirtilmezse).
  SERVIS_URL, SERVIS_ANAHTAR (opsiyonel) Favori/okunma servisi (şifreli pakete konur). Ayrıca kullanıcıların
                   siteden değiştirdiği şifreler (şifre kutuları) servisten alınıp data/giris.json'a işlenir.
  RAKIPLER_JSON    (opsiyonel) Doluysa rakipler verisi dosya yerine bundan alınır.
"""
import os, sys, json, base64, hashlib, re, unicodedata, secrets, urllib.request, urllib.parse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(KOK, "data")
GIRIS, VERI = os.path.join(D, "giris.json"), os.path.join(D, "veri.enc")
YAY, RAK, SOR = (os.path.join(D, f) for f in ("yayinlar.json", "rakipler.json", "sorgular.json"))
ITER = 600000
b64 = lambda b: base64.b64encode(b).decode()
unb64 = lambda s: base64.b64decode(s)

def norm(s):
    s = unicodedata.normalize("NFC", s).replace("İ", "i").replace("I", "ı").lower()
    s = s.translate(str.maketrans("çğıöşüâîû", "cgiosuaiu"))
    return re.sub(r"[^a-z0-9]", "", s)

def idhash(kid): return hashlib.sha256(("fv|" + norm(kid)).encode()).hexdigest()

def kdf(sifre, salt):
    return hashlib.pbkdf2_hmac("sha256", norm(sifre).encode(), salt, ITER, 32)

def sar(anahtar, sifre):
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    ct = AESGCM(kdf(sifre, salt)).encrypt(nonce, anahtar, b"fv1")
    return {"s": b64(salt), "w": b64(nonce + ct)}

def ac_anahtar(kayit, sifre):
    w = unb64(kayit["w"])
    return AESGCM(kdf(sifre, unb64(kayit["s"]))).decrypt(w[:12], w[12:], b"fv1")

def yonetici_anahtar():
    sifre = os.environ.get("YONETICI_SIFRE", "")
    if not sifre:
        sys.exit("HATA: YONETICI_SIFRE secret'ı tanımlı değil.")
    if os.path.exists(GIRIS):
        g = json.load(open(GIRIS, encoding="utf-8"))
        try:
            return ac_anahtar(g["kullanicilar"][idhash("_yonetici")], sifre), sifre
        except Exception:
            sys.exit("HATA: YONETICI_SIFRE mevcut data/giris.json ile uyuşmuyor. Şifreyi değiştirdiyseniz eski şifreyi geri yazın.")
    return None, sifre

def kullanicilari_oku():
    ham = os.environ.get("KULLANICILAR", "")
    liste, gorulen = [], set()
    for satir in ham.splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#"): continue
        ad, _, sif = satir.partition(";")
        kelimeler = ad.split()
        if len(kelimeler) < 2: sys.exit(f"HATA: 'Ad Soyad' biçiminde olmayan satır: {satir!r}")
        kid = norm(" ".join(kelimeler[:-1]))
        sifre = sif.strip() or kelimeler[-1]
        if kid in gorulen: sys.exit(f"HATA: Aynı kullanıcı adı iki kez: {kid}")
        gorulen.add(kid)
        liste.append((kid, " ".join(kelimeler), sifre))
    if not liste: sys.exit("HATA: KULLANICILAR secret'ı boş.")
    return liste

def kutu_gecerli(k):
    try:
        return (isinstance(k, dict) and len(unb64(k["s"])) == 16 and len(unb64(k["w"])) == 60)
    except Exception:
        return False

def kutulari_al():
    """Kullanıcıların siteden değiştirdiği şifre kutuları: {kimlik: {s,w}}. Servise ulaşılamazsa None."""
    url, anahtar = os.environ.get("SERVIS_URL", "").strip(), os.environ.get("SERVIS_ANAHTAR", "").strip()
    if not url or not anahtar: return None
    try:
        q = urllib.parse.quote(json.dumps({"k": anahtar, "u": "0" * 64, "a": "kutular"}))
        with urllib.request.urlopen(url + ("&" if "?" in url else "?") + "q=" + q, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
        if "liste" not in j: raise ValueError(j.get("hata", "beklenmeyen yanıt"))
        sonuc = {}
        for satir in j["liste"]:
            try: k = json.loads(satir["kutu"])
            except Exception: continue
            if re.fullmatch(r"[0-9a-f]{64}", str(satir.get("u", ""))) and kutu_gecerli(k):
                sonuc[satir["u"]] = {"s": k["s"], "w": k["w"]}
        return sonuc
    except Exception as e:
        print(f"UYARI: şifre kutuları servisten alınamadı ({e}); mevcut kullanıcı kayıtları korunuyor.")
        return None

def sifrele(anahtar, nesne):
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(anahtar).encrypt(nonce, json.dumps(nesne, ensure_ascii=False).encode(), b"fv-veri")

def ac():
    anahtar, _ = yonetici_anahtar()
    if not os.path.exists(VERI):
        print("data/veri.enc yok: ilk kurulum, açık dosyalar kullanılacak."); return
    if anahtar is None: sys.exit("HATA: veri.enc var ama giris.json yok.")
    ham = open(VERI, "rb").read()
    b = json.loads(AESGCM(anahtar).decrypt(ham[:12], ham[12:], b"fv-veri"))
    json.dump(b["yayinlar"], open(YAY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not os.environ.get("RAKIPLER_JSON") and not os.path.exists(RAK):
        json.dump(b["rakipler"], open(RAK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Şifreli veri çözüldü.")

def kapat():
    anahtar, ysifre = yonetici_anahtar()
    if anahtar is None:
        anahtar = secrets.token_bytes(32); print("Yeni veri anahtarı üretildi.")
    kullanicilar = kullanicilari_oku()
    rak = json.loads(os.environ["RAKIPLER_JSON"]) if os.environ.get("RAKIPLER_JSON") else json.load(open(RAK, encoding="utf-8"))
    bundle = {"yayinlar": json.load(open(YAY, encoding="utf-8")), "rakipler": rak,
              "sorgular": json.load(open(SOR, encoding="utf-8")),
              "adlar": {idhash(k): ad for k, ad, _ in kullanicilar}}
    if os.environ.get("SERVIS_URL") and os.environ.get("SERVIS_ANAHTAR"):
        bundle["servis"] = {"url": os.environ["SERVIS_URL"].strip(), "anahtar": os.environ["SERVIS_ANAHTAR"].strip()}
        print("Servis bilgisi pakete eklendi.")
    else:
        print("UYARI: SERVIS_URL / SERVIS_ANAHTAR secret'ları tanımlı değil; servis pakete EKLENMEDİ (favoriler yalnızca cihazda kalır).")
    open(VERI, "wb").write(sifrele(anahtar, bundle))
    giris = {"v": 1, "iter": ITER, "kullanicilar": {idhash("_yonetici"): sar(anahtar, ysifre)}}
    if os.environ.get("SERVIS_URL"): giris["servis_url"] = os.environ["SERVIS_URL"].strip()
    kutular = kutulari_al()
    eski = {}
    if os.path.exists(GIRIS):
        try: eski = json.load(open(GIRIS, encoding="utf-8")).get("kullanicilar", {})
        except Exception: eski = {}
    kutulu = korunan = 0
    for kid, ad, sifre in kullanicilar:
        h = idhash(kid)
        if kutular is not None and h in kutular:      # kullanıcı şifresini siteden değiştirmiş
            giris["kullanicilar"][h] = kutular[h]; kutulu += 1
        elif kutular is None and os.environ.get("SERVIS_URL") and h in eski and kutu_gecerli(eski[h]):
            giris["kullanicilar"][h] = eski[h]; korunan += 1   # servis yok: mevcut kaydı bozma
        else:
            giris["kullanicilar"][h] = sar(anahtar, sifre)
            if len(norm(sifre)) < 8: print(f"  uyarı: '{kid}' şifresi kısa (kolay tahmin edilir)")
    if kutulu: print(f"{kutulu} kullanıcının siteden değiştirdiği şifre işlendi.")
    if korunan: print(f"{korunan} kullanıcının mevcut kaydı korundu.")
    json.dump(giris, open(GIRIS, "w", encoding="utf-8"), indent=1)
    for f in (YAY, RAK):
        if os.path.exists(f): os.remove(f)
    print(f"Şifrelendi: {len(kullanicilar)} kullanıcı, veri.enc {os.path.getsize(VERI)} bayt.")

if __name__ == "__main__":
    {"ac": ac, "kapat": kapat}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
