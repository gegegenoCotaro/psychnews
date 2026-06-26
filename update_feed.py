import os
import sys
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# Configuration
SEARCH_QUERY = '("informal coercion" OR "perceived coercion" OR "coercion psychiatry" OR "psychiatric nursing")'
MAX_RESULTS = 50
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(WORKSPACE_DIR, 'src', 'data', 'articles.json')
TEMP_DIR = os.path.join(WORKSPACE_DIR, 'tmp_research')

# Fallback images matching categories
CATEGORIES_IMAGES = {
    "Coercion & Ethics": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=800",
    "Psychiatric Nursing": "https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?w=800",
    "General Medical Science": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800",
    "Research Methods": "https://images.unsplash.com/photo-1478737270239-2f02b77fc618?w=800"
}

def get_fallback_image(category):
    return CATEGORIES_IMAGES.get(category, "https://images.unsplash.com/photo-1527689368864-3a821dbccc34?w=800")

def search_pubmed(query, max_results=8):
    print(f"Searching PubMed for query: {query}")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={urllib.parse.quote(query)}&retmode=json&retmax={max_results}&sort=most_recent"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'PsychNewsAgent/1.0'})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            pmids = data.get('esearchresult', {}).get('idlist', [])
            print(f"Found {len(pmids)} matching PMIDs.")
            return pmids
    except Exception as e:
        print(f"Error querying PubMed: {e}")
        return []

def fetch_abstracts(pmids):
    if not pmids:
        return []
    print(f"Fetching details for {len(pmids)} PMIDs...")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(pmids)}&retmode=xml"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'PsychNewsAgent/1.0'})
        with urllib.request.urlopen(req) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            articles = []
            for art in root.findall('.//PubmedArticle'):
                pmid = art.find('.//PMID').text
                title = art.find('.//ArticleTitle')
                title_text = "".join(title.itertext()) if title is not None else "No Title"
                
                journal = art.find('.//Journal/Title')
                journal_text = journal.text if journal is not None else "Unknown Journal"
                
                year = art.find('.//JournalIssue/PubDate/Year')
                month = art.find('.//JournalIssue/PubDate/Month')
                day = art.find('.//JournalIssue/PubDate/Day')
                pubdate = f"{year.text if year is not None else '2026'} {month.text if month is not None else ''} {day.text if day is not None else ''}".strip()
                
                abstract_text = ""
                abstract = art.find('.//Abstract')
                if abstract is not None:
                    abstract_text = "\n".join(["".join(el.itertext()) for el in abstract.findall('.//AbstractText')])
                
                articles.append({
                    'pmid': pmid,
                    'title': title_text,
                    'journal': journal_text,
                    'pubdate': pubdate,
                    'abstract': abstract_text
                })
            return articles
    except Exception as e:
        print(f"Error fetching abstracts: {e}")
        return []

def classify_fallback(title, abstract):
    text = (title + " " + abstract).lower()
    if "coercion" in text or "forced" in text or "compulsory" in text or "involuntary" in text:
        return "Coercion & Ethics"
    elif "nurse" in text or "nursing" in text or "care" in text:
        return "Psychiatric Nursing"
    elif "method" in text or "qualitative" in text or "interview" in text or "approach" in text:
        return "Research Methods"
    else:
        return "General Medical Science"

def process_with_gemini(article):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Fallback to local heuristic parsing
        category = classify_fallback(article['title'], article['abstract'])
        print(f"No GEMINI_API_KEY found. Generating fallback entry for PMID {article['pmid']}")
        return {
            "id": f"pmid_{article['pmid']}",
            "title": f"[未翻訳] {article['title']}",
            "originalTitle": article['title'],
            "source": article['journal'],
            "published": article['pubdate'],
            "methodology": "文献データベースより取得",
            "summary": article['abstract'][:300] + "..." if article['abstract'] else "抄録データなし。",
            "clinicalImplication": "Gemini APIキーを有効にすると、臨床への意義が自動翻訳・要約されます。",
            "researchImplication": "Gemini APIキーを有効にすると、研究への意義が自動翻訳・要約されます。",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/",
            "imageUrl": get_fallback_image(category),
            "category": category
        }
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        prompt = f"""
        あなたは精神科看護学の卓越した研究エージェントです。以下の英語論文のタイトルとアブストラクトを日本語でニュース風に要約・翻訳してください。
        
        【論文タイトル】: {article['title']}
        【アブストラクト】: {article['abstract']}
        【ジャーナル】: {article['journal']}
        【出版年】: {article['pubdate']}
        
        以下のJSONフォーマットのオブジェクトを厳格に返してください。マークダウンの ```json コードブロック表記を含めずに、純粋なプレーンテキストのJSONデータだけを出力してください。
        
        {{
          "title": "惹きつける日本語のニュース風タイトル",
          "category": "以下のうち最も適合する1つ: 'Coercion & Ethics', 'Psychiatric Nursing', 'General Medical Science', 'Research Methods'",
          "methodology": "使用されている研究手法（例: '質的研究（半構造化面接）', 'ランダム化比較試験(RCT)', '文献レビュー' など）",
          "summary": "ニュース風の簡潔な2-3文の日本語要約",
          "clinicalImplication": "臨床（看護実践、病棟運営、患者との関係性）における重要性や示唆（日本語で2-3文）",
          "researchImplication": "研究における意義（概念定義、尺度開発、今後の研究への示唆など）（日本語で2-3文）"
        }}
        """
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Strip code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        
        parsed = json.loads(text)
        category = parsed.get("category", "General Medical Science")
        
        return {
            "id": f"pmid_{article['pmid']}",
            "title": parsed.get("title", article['title']),
            "originalTitle": article['title'],
            "source": article['journal'],
            "published": article['pubdate'],
            "methodology": parsed.get("methodology", "文献レビュー"),
            "summary": parsed.get("summary", ""),
            "clinicalImplication": parsed.get("clinicalImplication", ""),
            "researchImplication": parsed.get("researchImplication", ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/",
            "imageUrl": get_fallback_image(category),
            "category": category
        }
    except Exception as e:
        print(f"Failed to process with Gemini: {e}")
        # Fallback to local heuristic
        category = classify_fallback(article['title'], article['abstract'])
        return {
            "id": f"pmid_{article['pmid']}",
            "title": f"[未翻訳] {article['title']}",
            "originalTitle": article['title'],
            "source": article['journal'],
            "published": article['pubdate'],
            "methodology": "文献データベースより取得 (解析エラー)",
            "summary": article['abstract'][:300] + "...",
            "clinicalImplication": "Gemini APIの実行エラーにより翻訳できませんでした。",
            "researchImplication": "Gemini APIの実行エラーにより翻訳できませんでした。",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/",
            "imageUrl": get_fallback_image(category),
            "category": category
        }

def main():
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    
    # Load existing articles
    existing_articles = []
    existing_ids = set()
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                existing_articles = json.load(f)
                existing_ids = {art['id'].replace('pmid_', '') for art in existing_articles}
        except Exception as e:
            print(f"Error loading existing database: {e}. Starting fresh...")
    
    # Search and Fetch
    pmids = search_pubmed(SEARCH_QUERY, MAX_RESULTS)
    
    # Filter new ones
    new_pmids = [pmid for pmid in pmids if pmid not in existing_ids]
    if not new_pmids:
        print("No new articles found. Database is up to date.")
        return
        
    print(f"Found {len(new_pmids)} new articles to translate and add.")
    
    # Fetch details
    raw_articles = fetch_abstracts(new_pmids)
    
    # Process
    processed_new = []
    for raw in raw_articles:
        rich = process_with_gemini(raw)
        processed_new.append(rich)
        
    # Merge and Save (put new ones at the beginning)
    updated_list = processed_new + existing_articles
    
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_list, f, ensure_ascii=False, indent=2)
        print(f"Database successfully updated. Added {len(processed_new)} articles.")
    except Exception as e:
        print(f"Error writing updated database: {e}")

if __name__ == "__main__":
    main()
