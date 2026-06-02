import json
import urllib.request
import urllib.error
import time
import sys
import os
import random
import concurrent.futures
import itertools
import glob
from urllib.parse import urlparse

# === 1. API Keys ===
API_KEYS = [
    'f66e92dc93db3243b8111adc15e3be9aab7082d8',
    'e8c7bae643789205a636d2e8967ba9f0338cfd6d',
    'a367c545383e1c02dd4fd31e5ffc3c4ded5ad5d2',
    '7357f22a4928a46e508233ce2bfc2c877a722060',
    '931aff7b7867b1d4e2015fdb1c10e82e1e4bd153'
]

BASE_URL = 'https://google.serper.dev/search'
STATE_FILE = 'state_advanced.json'
NEGATIVE_DORKS = "-site:facebook.com -site:youtube.com -site:twitter.com -site:instagram.com -site:linkedin.com -site:github.com -site:stackoverflow.com"
THREADS = 5
dead_keys = set()
saved_urls = set() # Bach n3arfo chno sejelna w man3awdohch

# === 2. Mega Banka (Universal Italian Keywords) ===
KEYWORDS_BANK = [
    "carrello", "accedi", "registrati", "fattura", "preventivo", "catalogo",
    "cerca", "profilo", "dettaglio", "scheda", "notizie", "articoli", "azienda",
    "servizi", "contatti", "ordini", "abbonamento", "spedizione", "pagamento",
    "codice fiscale", "partita iva", "carrello acquisti", "chi siamo", "lavora con noi",
    "amministrazione trasparente", "diritto recesso", "informativa privacy",
    "condizioni generali", "note legali", "area riservata", "recupero password",
    "assistenza clienti", "metodi pagamento", "dati personali", "sede legale",
    "ragione sociale", "il mio account", "metti nel carrello", "iscriviti alla newsletter",
    "termini e condizioni", "servizio clienti", "ufficio stampa", "mappa del sito",
    "domande frequenti", "aggiungi al carrello", "procedi all'acquisto", "conferma ordine"
]

# === 3. Variable Bank (Rotation) ===
VARIABLES_BANK = ["id", "cat", "p", "prod", "item", "category", "article", "id_prod", "item_id", "uid", "s", "page", "view"]
var_cycle = itertools.cycle(VARIABLES_BANK)

# === 4. TLDs & Extensions (JDID) ===
TLDS_BANK = ["it", "com", "net", "org", "eu", "info", "biz"]
tld_cycle = itertools.cycle(TLDS_BANK)

EXTENSIONS_BANK = ["php", "asp", "aspx", "jsp", "cfm", "html"]

def load_saved_urls():
    """Kijbed les URLs li fayt sejelna bach may3awdhomch"""
    # Load from the main file
    if os.path.exists("results_advanced.txt"):
        try:
            with open("results_advanced.txt", 'r', encoding='utf-8') as f:
                for line in f:
                    saved_urls.add(line.strip())
        except: pass
    # Load from any legacy result files
    for file in glob.glob("result_*.txt"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    saved_urls.add(line.strip())
        except:
            pass

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {"kw_idx": 0, "id_idx": 1}

def save_state(kw_idx, id_idx):
    with open(STATE_FILE, 'w') as f:
        json.dump({"kw_idx": kw_idx, "id_idx": id_idx}, f)

def get_key():
    working = [k for k in API_KEYS if k not in dead_keys]
    if not working: return None
    return random.choice(working)

def clean_url(url):
    """Kina9i l-URL w kaykhelli ghir l-asass"""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{parsed.query}"
    except:
        return url

def search_serper(query, page=1):
    key = get_key()
    if not key: return "STOP"
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    # gl="it" katkhli search i-viser Google Italia, hl="it" katfered l-lugha l-italiya
    payload = json.dumps({
        "q": query, 
        "gl": "it", 
        "hl": "it",
        "num": 10, 
        "tbs": "qdr:m", 
        "page": page
    }).encode("utf-8")
    req = urllib.request.Request(BASE_URL, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403: 
            dead_keys.add(key)
            return search_serper(query, page) # Jereb b key akhor
        else:
            sys.stderr.write(f"⚠️ API Error {e.code}: {e.read().decode('utf-8')}\n")
    except Exception as err:
        sys.stderr.write(f"⚠️ Connection Error: {err}\n")
    return None

def process_single_request(dork_data):
    dork, kw_idx, current_id, keyword = dork_data
    
    all_found_links = []
    # Pagination: njebdo page 1 tal 3 (300 résultats max par dork)
    for page in range(1, 4):
        data = search_serper(dork, page)
        if data == "STOP": return "STOP_API"
        
        found_links = []
        if data and data.get('organic'):
            for item in data['organic']:
                url = item.get('link')
                if url and '?' in url and '=' in url:
                    clean = clean_url(url)
                    if clean not in saved_urls:
                        found_links.append(clean)
                        saved_urls.add(clean)
            all_found_links.extend(found_links)
        else:
            break # Ila makaynch résultats f had l-page, n7ebso l-pagination l had dork
            
    return (all_found_links, keyword)

def main():
    load_saved_urls() # Jbed URLs lqdam
    state = load_state()
    kw_idx = state["kw_idx"]
    current_id = state["id_idx"]
    
    sys.stderr.write(f"🚀 Advanced Dorker Started (Multi-TLD | Anti-Duplicate)\n")
    sys.stderr.write(f"📁 URLs in Database: {len(saved_urls)}\n")

    if kw_idx >= len(KEYWORDS_BANK):
        kw_idx = 0

    try:
        while kw_idx < len(KEYWORDS_BANK):
            keyword = KEYWORDS_BANK[kw_idx]
            sys.stderr.write(f"\n🔥 CURRENT KEYWORD: [{keyword}] (Active for 60s)\n")
            
            kw_timer = time.time()
            
            while (time.time() - kw_timer) < 60:
                batch = []
                for _ in range(THREADS):
                    var = next(var_cycle)
                    tld = next(tld_cycle)
                    ext = random.choice(EXTENSIONS_BANK)
                    
                    # ID random kbir mais sghir kfaya bach ykon f google (1-1500)
                    current_id = random.randint(1, 1500)
                    
                    # Dork jdid motawar fih TLD motaghayir w negative dorks (bla quotes f inurl w bla dot f site)
                    dork = f'inurl:{ext}?{var}={current_id} "{keyword}" site:{tld} {NEGATIVE_DORKS}'
                    batch.append((dork, kw_idx, current_id, keyword))
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
                    results = list(executor.map(process_single_request, batch))
                
                for res in results:
                    if res == "STOP_API":
                        print("\n❌ API SALAT (Kolchi tbedel/Mata). Saving state...")
                        save_state(kw_idx, current_id)
                        sys.exit(0)
                    
                    if isinstance(res, tuple):
                        links, kw = res
                        if links:
                            filename = "results_advanced.txt"
                            with open(filename, "a", encoding="utf-8") as f:
                                for link in links:
                                    f.write(link + "\n")
                                    print(link)
                
                save_state(kw_idx, current_id)
                time.sleep(0.5)

            kw_idx += 1
            if kw_idx >= len(KEYWORDS_BANK): kw_idx = 0 

    except KeyboardInterrupt:
        print("\n🛑 Stopped by User. Saving state...")
        save_state(kw_idx, current_id)
        sys.exit()

if __name__ == "__main__":
    main()
