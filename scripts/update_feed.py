import os
import sys
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time

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
        raise e

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
        raise e

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

def generate_fallback(article, existing_untranslated=None):
    if existing_untranslated:
        # Keep existing untranslated structure to avoid unnecessary data modifications
        print(f"Preserving existing untranslated entry for PMID {article['pmid']}.")
        return existing_untranslated
        
    category = classify_fallback(article['title'], article['abstract'])
    print(f"Generating fallback entry for PMID {article['pmid']}")
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

def process_with_gemini_api(article, api_key):
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    genai.configure(api_key=api_key)
    
    prompt = f"""
    あなたは精神科看護学の卓越した研究エージェントです。以下の英語論文のタイトルとアブストラクトを日本語でニュース風に要約・翻訳してください。
    
    【論文タイトル】: {article['title']}
    【アブストラクト】: {article['abstract']}
    【ジャーナル】: {article['journal']}
    【出版年】: {article['pubdate']}
    
    以下のJSONフォーマット of オブジェクトを厳格に返してください。マークダウンの ```json コードブロック表記を含めずに、純粋なプレーンテキストのJSONデータだけを出力してください。
    
    {{
      "title": "惹きつける日本語のニュース風タイトル",
      "category": "以下のうち最も適合する1つ: 'Coercion & Ethics', 'Psychiatric Nursing', 'General Medical Science', 'Research Methods'",
      "methodology": "使用されている研究手法（例: '質的研究（半構造化面接）', 'ランダム化比較試験(RCT)', '文献レビュー' など）",
      "summary": "ニュース風の簡潔な2-3文の日本語要約",
      "clinicalImplication": "臨床（看護実践、病棟運営、患者との関係性）における重要性や示唆（日本語で2-3文）",
      "researchImplication": "研究における意義（概念定義、尺度開発、今後の研究への示唆など）（日本語で2-3文）"
    }}
    """
    
    # Disable safety filters for academic research summaries to prevent blocking words like "suicide" or "death"
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Retry mechanism for robust API calls
    max_retries = 2
    text = ""
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt, safety_settings=safety_settings)
            text = response.text.strip()
            break
        except Exception as api_err:
            if attempt < max_retries - 1:
                print(f"Gemini API attempt {attempt + 1} failed: {api_err}. Waiting 6 seconds before retrying...")
                time.sleep(6.0)
            else:
                raise api_err
    
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

def main():
    try:
        # Ensure data directory exists
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        # Load existing articles
        existing_articles = []
        existing_ids = set()
        all_existing_ids = set()
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    existing_articles = json.load(f)
                    
                    # [未翻訳] となっている論文は、APIキー設定後に再翻訳できるように既存IDから除外する
                    existing_ids = {
                        art['id'].replace('pmid_', '') 
                        for art in existing_articles 
                        if "[未翻訳]" not in art.get('title', '')
                    }
                    # 翻訳済み・未翻訳を問わず、データベースに存在するすべてのIDを取得
                    all_existing_ids = {
                        art['id'].replace('pmid_', '') 
                        for art in existing_articles
                    }
            except Exception as e:
                print(f"Error loading existing database: {e}. Starting fresh...")
        
        # Define categories, queries and limits
        CATEGORIES_QUERIES = [
            {
                "name": "Coercion & Ethics",
                "query": '("informal coercion" OR "perceived coercion" OR "coercion psychiatry" OR "coercive measures psychiatry")',
                "limit": 25
            },
            {
                "name": "Psychiatric Nursing",
                "query": '("psychiatric nursing" OR "mental health nursing" OR "psychiatric care")',
                "limit": 10
            },
            {
                "name": "Research Methods",
                "query": '("research methods" OR "methodology" OR "qualitative research" OR "randomized controlled trial") AND ("psychiatric nursing" OR "nursing" OR "psychiatry")',
                "limit": 8
            },
            {
                "name": "AI & Technology",
                "query": '"nursing" AND ("artificial intelligence" OR "AI" OR "large language model" OR "chatgpt" OR "digital technology")',
                "limit": 7
            }
        ]
        
        # Fetch and merge PMIDs from all categories, removing duplicates
        pmids = []
        seen_pmids = set()
        for idx, cat in enumerate(CATEGORIES_QUERIES):
            if idx > 0:
                print("Waiting 1.5 seconds to avoid PubMed API rate limits...")
                time.sleep(1.5)  # Rate limit safety interval
            cat_pmids = search_pubmed(cat["query"], cat["limit"])
            added_count = 0
            for pmid in cat_pmids:
                if pmid not in seen_pmids:
                    pmids.append(pmid)
                    seen_pmids.add(pmid)
                    added_count += 1
            print(f"Category '{cat['name']}': Added {added_count} unique PMIDs (out of {len(cat_pmids)} found).")

        print(f"Total merged PMIDs from recent search: {len(pmids)}")
        
        # Filter new ones (PMIDs completely absent from database)
        new_pmids = [pmid for pmid in pmids if pmid not in all_existing_ids]
        
        # Past Article Backfill: If there are fewer than 8 truly new articles,
        # automatically query deeper into PubMed history to pull older articles that haven't been fetched yet.
        MIN_NEW_ARTICLES = 8
        if len(new_pmids) < MIN_NEW_ARTICLES:
            shortage = MIN_NEW_ARTICLES - len(new_pmids)
            print(f"New articles count ({len(new_pmids)}) is less than minimum required ({MIN_NEW_ARTICLES}).")
            print(f"Triggering backfill to fetch {shortage} past articles...")
            
            backfill_queries = [
                {
                    "name": "Coercion & Ethics (Backfill)",
                    "query": '("informal coercion" OR "perceived coercion" OR "coercion psychiatry" OR "coercive measures psychiatry")',
                    "limit": 80
                },
                {
                    "name": "Psychiatric Nursing (Backfill)",
                    "query": '("psychiatric nursing" OR "mental health nursing" OR "psychiatric care")',
                    "limit": 30
                },
                {
                    "name": "Research Methods (Backfill)",
                    "query": '("research methods" OR "methodology" OR "qualitative research" OR "randomized controlled trial") AND ("psychiatric nursing" OR "nursing" OR "psychiatry")',
                    "limit": 25
                },
                {
                    "name": "AI & Technology (Backfill)",
                    "query": '"nursing" AND ("artificial intelligence" OR "AI" OR "large language model" OR "chatgpt" OR "digital technology")',
                    "limit": 20
                }
            ]
            
            backfill_pmids = []
            seen_backfill = set(seen_pmids)
            for idx, cat in enumerate(backfill_queries):
                if idx > 0:
                    time.sleep(1.5)
                cat_pmids = search_pubmed(cat["query"], cat["limit"])
                added = 0
                for pmid in cat_pmids:
                    if pmid not in seen_backfill:
                        backfill_pmids.append(pmid)
                        seen_backfill.add(pmid)
                        added += 1
            
            # Filter past articles that are completely absent from database
            past_new_pmids = [pmid for pmid in backfill_pmids if pmid not in all_existing_ids]
            print(f"Found {len(past_new_pmids)} past candidate articles for backfill.")
            
            added_backfill = past_new_pmids[:shortage]
            new_pmids.extend(added_backfill)
            print(f"Successfully backfilled {len(added_backfill)} past articles: {added_backfill}")
        
        # Extract PMIDs of already saved "[未翻訳]" articles to re-process them
        retranslate_pmids = [
            art['id'].replace('pmid_', '') 
            for art in existing_articles 
            if "[未翻訳]" in art.get('title', '')
        ]
        
        # Combine new PMIDs and untranslated PMIDs, removing duplicates
        combined_pmids = list(set(new_pmids) | set(retranslate_pmids))
        
        if not combined_pmids:
            print("No new or untranslated articles found. Database is up to date.")
            return
            
        print(f"Found {len(new_pmids)} new/backfilled articles and {len(retranslate_pmids)} untranslated articles to process. Total: {len(combined_pmids)}")
        
        # Fetch details
        print("Waiting 1.5 seconds before fetching abstracts...")
        time.sleep(1.5)
        raw_articles = fetch_abstracts(combined_pmids)
        
        # Process translations incrementally to respect strict Gemini API quotas (e.g., 20 requests per day)
        processed_new = []
        api_key = os.environ.get("GEMINI_API_KEY")
        
        # Maximum number of API translations to perform in a single workflow run
        MAX_GEMINI_CALLS = 100
        gemini_call_count = 0
        
        for idx, raw in enumerate(raw_articles):
            # Locate existing untranslated entry if it exists to preserve its properties
            existing_untranslated = next(
                (art for art in existing_articles if art['id'] == f"pmid_{raw['pmid']}"), 
                None
            )
            
            if api_key and gemini_call_count < MAX_GEMINI_CALLS:
                if gemini_call_count > 0:
                    # Respect RPM (Requests Per Minute) free-tier limit of 15 RPM
                    print("Waiting 4.2 seconds to avoid Gemini API rate limits (15 RPM)...")
                    time.sleep(4.2)
                try:
                    print(f"[{gemini_call_count + 1}/{MAX_GEMINI_CALLS}] Processing PMID {raw['pmid']} with Gemini...")
                    rich = process_with_gemini_api(raw, api_key)
                    processed_new.append(rich)
                    gemini_call_count += 1
                except Exception as api_err:
                    print(f"Failed to process with Gemini for PMID {raw['pmid']}: {api_err}")
                    # If quota is exhausted or an error happens, stop calling the API in this run
                    gemini_call_count = MAX_GEMINI_CALLS
                    # Fallback to local translation (retains prior un-translated entry if available)
                    rich = generate_fallback(raw, existing_untranslated)
                    processed_new.append(rich)
            else:
                # Quota budget reached for this run, or API key not present. Generate local fallback.
                if api_key:
                    print(f"Gemini API limit reached ({MAX_GEMINI_CALLS} calls). Postponing translation for PMID {raw['pmid']}.")
                rich = generate_fallback(raw, existing_untranslated)
                processed_new.append(rich)
            
        # Remove duplicates of re-translated articles or old fallback articles
        new_ids_set = {art['id'] for art in processed_new}
        cleaned_existing = [
            art for art in existing_articles 
            if art['id'] not in new_ids_set and "[未翻訳]" not in art.get('title', '')
        ]
        
        # Merge and Save (put new ones at the beginning)
        updated_list = processed_new + cleaned_existing
        
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(updated_list, f, ensure_ascii=False, indent=2)
            print(f"Database successfully updated. Added {len(processed_new)} articles.")
        except Exception as e:
            print(f"Error writing updated database: {e}")
            raise e
            
    except Exception as e:
        print(f"FATAL ERROR in main update thread: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
