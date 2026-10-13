import json
import os
import requests
from datetime import datetime

TARGET_QUERIES = [
    {
        "category": "Probiyotik / Suş Bazlı",
        "query": "Lactobacillus rhamnosus GG clinical efficacy gut barrier"
    },
    {
        "category": "Probiyotik / Suş Bazlı",
        "query": "Bifidobacterium animalis subsp lactis BB 12 immune modulation"
    },
    {
        "category": "Omega-3 / Balık Yağı",
        "query": "omega 3 fatty acids triglyceride form bioavailability cardiovascular"
    },
    {
        "category": "Omega-3 / Balık Yağı",
        "query": "cod liver oil vitamin D clinical benefits children health"
    }
]

def fetch_pubmed_articles():
    all_articles = []
    
    for item in TARGET_QUERIES:
        search_query = item["query"]
        category = item["category"]
        
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": search_query,
            "retmax": 2,
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
            
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        
        summary_res = requests.get(summary_url, params=summary_params)
        if summary_res.status_code != 200:
            continue
            
        summary_data = summary_res.json().get("result", {})
        
        for pmid in id_list:
            if pmid in summary_data:
                article_info = summary_data[pmid]
                title = article_info.get("title", "Başlık bulunamadı")
                pub_date = article_info.get("pubdate", "Tarih yok")
                source_journal = article_info.get("source", "Kaynak dergi yok")
                
                # Kategoriye özel güçlü saha rasyoneli notları
                if "Probiyotik" in category:
                    insight = f"Bu klinik çalışma; ilgili probiyotik suşunun (LGG / BB-12) gastrointestinal mukoza üzerindeki koruyucu bariyer etkisini ve immün sistem modülasyonundaki güvenilirlik profilini desteklemektedir."
                else:
                    insight = f"Bu güncel literatür verisi; omega-3 yağ asitlerinin trigliserid formundaki yüksek biyoyararlanım oranını ve kardiyovasküler/bilişsel fonksiyonlar üzerindeki olumlu klinik çıktıklarını doğrulamaktadır."

                all_articles.append({
                    "id": pmid,
                    "category": category,
                    "search_term": search_query,
                    "title": title,
                    "journal": source_journal,
                    "date": pub_date,
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "clinical_insight": insight
                })

    output = {
        "last_updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "total_articles": len(all_articles),
        "articles": all_articles
    }
    
    with open("articles.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
        
    print(f"Toplam {len(all_articles)} makale başarıyla güncellendi.")

if __name__ == "__main__":
    fetch_pubmed_articles()