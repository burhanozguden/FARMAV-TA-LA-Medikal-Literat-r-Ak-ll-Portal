/**
 * Farmavita Portal servisi: favoriler (kullanıcıya özel) ve okunma sayacı (toplam).
 * Kurulum için README.md'deki "Servis kurulumu" bölümüne bakın.
 */

// Tabloyu bulur. olustur=true ise (yalnızca kurulumda) bağlı tablo yoksa yeni bir tablo oluşturur.
function tablo_(olustur) {
  const ozellik = PropertiesService.getScriptProperties();
  const id = ozellik.getProperty("TABLO_ID");
  if (id) return SpreadsheetApp.openById(id);
  let aktif = null;
  try { aktif = SpreadsheetApp.getActiveSpreadsheet(); } catch (e) {}
  if (aktif) { ozellik.setProperty("TABLO_ID", aktif.getId()); return aktif; }
  if (!olustur) throw new Error("Tablo bulunamadı: Apps Script'te 'kurulum' fonksiyonunu çalıştırın.");
  const yeni = SpreadsheetApp.create("Farmavita Portal Servis");
  ozellik.setProperty("TABLO_ID", yeni.getId());
  return yeni;
}

// 1) Elle çalıştırın (tekrar çalıştırmak güvenlidir; mevcut anahtarı DEĞİŞTİRMEZ).
function kurulum() {
  const ozellik = PropertiesService.getScriptProperties();
  let anahtar = ozellik.getProperty("ANAHTAR");
  if (!anahtar) {
    anahtar = Utilities.getUuid() + Utilities.getUuid();
    ozellik.setProperty("ANAHTAR", anahtar);
    Logger.log("Yeni anahtar üretildi.");
  }
  const tablo = tablo_(true);
  sayfa_("Favoriler", ["kullanici", "pmid"], true);
  sayfa_("Okunma", ["pmid", "sayi"], true);
  Logger.log("SERVIS_ANAHTAR: " + anahtar);
  Logger.log("Tablo adresi: " + tablo.getUrl());
}

// Yalnızca anahtarı yenilemek isterseniz (sonra GitHub'daki SERVIS_ANAHTAR secret'ını da güncelleyin).
function anahtarYenile() {
  const anahtar = Utilities.getUuid() + Utilities.getUuid();
  PropertiesService.getScriptProperties().setProperty("ANAHTAR", anahtar);
  Logger.log("SERVIS_ANAHTAR: " + anahtar);
}

function sayfa_(ad, baslik, olustur) {
  const ss = tablo_(!!olustur);
  let s = ss.getSheetByName(ad);
  if (!s) {
    s = ss.insertSheet(ad);
    s.getRange("A:B").setNumberFormat("@");
    s.appendRow(baslik);
  }
  return s;
}

function satirlar_(s) {
  const son = s.getLastRow();
  return son > 1 ? s.getRange(2, 1, son - 1, 2).getValues() : [];
}

function cevap_(nesne) {
  return ContentService.createTextOutput(JSON.stringify(nesne)).setMimeType(ContentService.MimeType.JSON);
}

// Tarayıcıdan adresi açınca durum bilgisi verir (gizli bilgi içermez).
function doGet() {
  let anahtar = false, tablo = false;
  try {
    const o = PropertiesService.getScriptProperties();
    anahtar = !!o.getProperty("ANAHTAR");
    tablo = !!o.getProperty("TABLO_ID");
    if (!tablo) { try { tablo = !!SpreadsheetApp.getActiveSpreadsheet(); } catch (e) {} }
  } catch (e) {}
  return cevap_({ servis: "calisiyor", anahtar: anahtar, tablo: tablo });
}

function doPost(e) {
  const kilit = LockService.getScriptLock();
  kilit.waitLock(20000);
  let yetkili = false;
  try {
    const d = JSON.parse(e.postData.contents);
    const anahtar = PropertiesService.getScriptProperties().getProperty("ANAHTAR");
    if (!anahtar || d.k !== anahtar) return cevap_({ hata: "yetki" });
    yetkili = true;
    const u = String(d.u || "");
    if (!/^[0-9a-f]{64}$/.test(u)) return cevap_({ hata: "kullanici" });
    const p = String(d.p || "").replace(/\D/g, "").slice(0, 12);
    const fav = sayfa_("Favoriler", ["kullanici", "pmid"]);
    const say = sayfa_("Okunma", ["pmid", "sayi"]);

    if (d.a === "durum") {
      const favoriler = satirlar_(fav).filter(function (r) { return String(r[0]) === u; }).map(function (r) { return String(r[1]); });
      const sayac = {};
      satirlar_(say).forEach(function (r) { sayac[String(r[0])] = Number(r[1]) || 0; });
      return cevap_({ fav: favoriler, sayac: sayac });
    }
    if (!p) return cevap_({ hata: "pmid" });

    if (d.a === "fav") {
      const rows = satirlar_(fav);
      let idx = -1;
      for (let i = 0; i < rows.length; i++) {
        if (String(rows[i][0]) === u && String(rows[i][1]) === p) { idx = i; break; }
      }
      if (d.on && idx < 0) fav.appendRow([u, p]);
      if (!d.on && idx >= 0) fav.deleteRow(idx + 2);
      return cevap_({ tamam: true });
    }
    if (d.a === "oku") {
      const rows = satirlar_(say);
      for (let i = 0; i < rows.length; i++) {
        if (String(rows[i][0]) === p) {
          say.getRange(i + 2, 2).setValue(String((Number(rows[i][1]) || 0) + 1));
          return cevap_({ tamam: true });
        }
      }
      say.appendRow([p, "1"]);
      return cevap_({ tamam: true });
    }
    return cevap_({ hata: "islem" });
  } catch (err) {
    return cevap_(yetkili ? { hata: "sunucu", ayrinti: String(err && err.message || err) } : { hata: "sunucu" });
  } finally {
    kilit.releaseLock();
  }
}
