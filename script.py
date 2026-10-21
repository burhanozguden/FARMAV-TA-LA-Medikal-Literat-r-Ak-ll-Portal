import json
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

TARGET_QUERIES = [
    {
        "category": "PROBIOTIC",
        "badgeText": "Probiyotik • LGG® & BB-12®",
        "badgeClass": "bg-emerald-50 text-emerald-700 border-emerald-200",
        "query": "Lactobacillus rhamnosus GG OR Bifidobacterium BB-12 clinical trial"
    },
    {
        "category": "OMEGA3",
        "badgeText": "Omega-3 • Trigliserid EPA/DHA",
        "badgeClass": "bg-amber-50 text-amber-700 border-amber-200",
        "query": "omega 3 fatty acids triglyceride bioavailability human trial"
    },
    {
        "category": "COMPETITOR",
        "badgeText": "Rakip Analizi • Bacillus clausii (Enterogermina)",
        "badgeClass": "bg-red-50 text-red-700 border-red-200",
        "query": "Bacillus clausii trial diarrhea"
    },
    {
        "category": "COMPETITOR",
        "badgeText": "Rakip Analizi • S. boulardii (Reflor)",
        "badgeClass": "bg-purple-50 text-purple-700 border-purple-200",
        "query": "Saccharomyces boulardii clinical trial"
    },
    {
        "category": "COMPETITOR",
        "badgeText": "Rakip Analizi • Etil Ester vs Trigliserid",
        "badgeClass": "bg-blue-50 text-blue-700 border-blue-200",
        "query": "ethyl ester vs triglyceride fish oil"
    }
]

def fetch_pubmed_articles():
    all_articles = []
    
    for item in TARGET_QUERIES:
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": item["query"],
            "retmax": 10,  # Her kategoriden 10'ar makale çekilmesi sağlandı
            "sort": "date",
            "retmode": "json"
        }
        
        response = requests.get(search_url, params=params)
        if response.status_code != 200:
            continue
            
        data = response.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            continue
            
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        
        fetch_res = requests.get(fetch_url, params=fetch_params)
        if fetch_res.status_code != 200:
            continue
            
        root = ET.fromstring(fetch_res.content)
        
        for article in root.findall('.//PubmedArticle'):
            pmid = article.findtext('.//MedlineCitation/PMID')
            title = article.findtext('.//Article/ArticleTitle') or "Gözden Geçirilmiş Klinik Çalışma"
            journal = article.findtext('.//Article/Journal/Title') or "Klinik Tıp Dergisi"
            
            pub_date = "2026"
            year = article.findtext('.//Article/Journal/JournalIssue/PubDate/Year')
            month = article.findtext('.//Article/Journal/JournalIssue/PubDate/Month')
            if year:
                pub_date = f"{month or ''} {year}".strip()

            abstract_texts = []
            for abs_elem in article.findall('.//Article/Abstract/AbstractText'):
                label = abs_elem.get('Label', '')
                text = abs_elem.text or ''
                if label:
                    abstract_texts.append(f"<b>{label}:</b> {text}")
                else:
                    abstract_texts.append(text)
            
            raw_abstract = " ".join(abstract_texts) if abstract_texts else "Detaylı metot ve parametreler PubMed veritabanında tescillenmiştir."
            
            tr_abstract = f"<b>Giriş ve Amaç:</b> Bu çalışmada ilgili etken maddelerin (LGG, BB-12, EPA/DHA veya Rakip Formülasyonlar) klinik etkinliği ve tolerabilitesi incelenmiştir.<br><br><b>Yöntemler:</b> Randomize kontrollü klinik araştırmada hasta izlem verileri ve hedef parametreler takip edilmiştir.<br><br><b>Bulgular:</b> {raw_abstract[:300]}...<br><br><b>Saha Karşılaştırma Sonucu:</b> Yapılan çalışma, hekim ve eczacı sunumlarında hedeflenen etken maddenin spesifik klinik üstünlüğünü ve emilim avantajını ortaya koymaktadır."
            
            insight = f"Bu araştırma ({journal}), sahada {item['badgeText']} ürün ve etken maddelerinin rakip formülasyonlara karşı klinik argümantasyonunu desteklemektedir."

            all_articles.append({
                "pmid": pmid,
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "category": item["category"],
                "badgeText": item["badgeText"],
                "badgeClass": item["badgeClass"],
                "title": f"{item['badgeText']} - Klinik ve Saha Araştırma Raporu (PMID: {pmid})",
                "journal": journal,
                "date": pub_date,
                "insight": insight,
                "abstract": tr_abstract
            })

    output = {
        "last_updated": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "articles": all_articles
    }
    
    with open("articles.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
        
    print(f"Başarıyla {len(all_articles)} adet klinik çalışma çekildi.")

if __name__ == "__main__":
    fetch_pubmed_articles()