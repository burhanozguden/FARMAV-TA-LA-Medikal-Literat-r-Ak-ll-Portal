import json
import os
import requests
from datetime import datetime

TARGET_QUERIES = [
    {
        "category": "CULTURELLE",
        "badgeText": "Culturelle® • LGG® & BB-12®",
        "badgeClass": "bg-emerald-50 text-emerald-700 border-emerald-200",
        "query": "Lactobacillus rhamnosus GG clinical efficacy gut barrier"
    },
    {
        "category": "MOLLERS",
        "badgeText": "Möller's • Trigliserid Omega-3",
        "badgeClass": "bg-amber-50 text-amber-700 border-amber-200",
        "query": "omega 3 fatty acids triglyceride form bioavailability"
    },
    {
        "category": "GUT_BRAIN",
        "badgeText": "Bağırsak-Beyin Ekseni",
        "badgeClass": "bg-blue-50 text-blue-700 border-blue-200",
        "query": "microbiome gut brain axis probiotic omega 3"
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
                pub_date = article_info.get("pubdate", "Güncel")
                source_journal = article_info.get("source", "PubMed Dergisi")
                
                all_articles.append({
                    "pmid": pmid,
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "category": category,
                    "badgeText": item["badgeText"],
                    "badgeClass": item["badgeClass"],
                    "title": title,
                    "journal": source_journal,
                    "date": pub_date,
                    "insight": "Bu güncel PubMed literatür verisi, saha çalışmalarında ürün rasyonelini destekleyen klinik bulgular sunmaktadır.",
                    "abstract": f"PubMed üzerinden otomatik olarak çekilen bu makale ({title}), ilgili suş ve omega-3 parametrelerinin klinik etkinlik, biyoyararlanım ve güvenilirlik profillerini incelemektedir."
                })

    output = {
        "last_updated": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "articles": all_articles
    }
    
    with open("articles.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
        
    print(f"Toplam {len(all_articles)} makale işlendi.")

if __name__ == "__main__":
    fetch_pubmed_articles()