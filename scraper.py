import json
import time
import os
import subprocess
import threading
import hashlib
import argparse
from datetime import datetime, timedelta
from urllib.parse import urljoin, quote
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")
SEEN_URLS_FILE = os.path.join(BASE_DIR, "seen_urls.json")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "checkpoint.json")
REQ_FILE = os.path.join(BASE_DIR, "job_requirements.md")
DELETED_FILE = os.path.join(BASE_DIR, "deleted.json")
HISTORY_FILE = os.path.join(BASE_DIR, "jobs_history.json")

def clean_blocked_jobs():
    """Finds and moves blocked jobs (senior, director, manager, johtaja, päällikkö, or US residency) from jobs.json to deleted.json."""
    if not os.path.exists(JOBS_FILE):
        return

    try:
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
    except Exception as e:
        print(f"Error reading {JOBS_FILE} during cleanup: {e}")
        return

    deleted_jobs = []
    if os.path.exists(DELETED_FILE):
        try:
            with open(DELETED_FILE, 'r', encoding='utf-8') as f:
                deleted_jobs = json.load(f)
        except Exception:
            pass

    blocked_keywords = ['senior', 'director', 'manager', 'johtaja', 'päällikkö']
    cleaned_jobs = []
    moved_count = 0

    seen_deleted = {j.get('url') for j in deleted_jobs if j.get('url')}

    for job in jobs:
        title = job.get('title', '').lower()
        reason = job.get('reason', '').lower()
        
        is_blocked = False
        deletion_reason = ""

        # Check keywords
        for kw in blocked_keywords:
            if kw in title:
                is_blocked = True
                deletion_reason = f"Title contains blocked keyword '{kw}'"
                break

        # Check US residency
        if not is_blocked:
            if "us residency" in reason or "requires us" in reason or "united states residency" in reason:
                is_blocked = True
                deletion_reason = "Requires US residency"
                
        # Check expired deadline (> 2 days passed) and not reviewed by user
        if not is_blocked and job.get('user_review') != 'done':
            deadline_str = job.get('deadline', '')
            if deadline_str:
                import re
                if re.match(r'^\d{4}-\d{2}-\d{2}$', deadline_str):
                    try:
                        deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d")
                        if datetime.now() > deadline_date + timedelta(days=2):
                            is_blocked = True
                            deletion_reason = f"Deadline ({deadline_str}) passed by more than 2 days and unreviewed"
                    except ValueError:
                        pass

        if is_blocked:
            job['deletion_reason'] = deletion_reason
            if job.get('url') not in seen_deleted:
                deleted_jobs.append(job)
                seen_deleted.add(job.get('url'))
            moved_count += 1
        else:
            cleaned_jobs.append(job)

    if moved_count > 0:
        print(f"INFO: Moved {moved_count} blocked jobs (senior/director/manager/expired/US residency) to deleted.json.")
        try:
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(cleaned_jobs, f, indent=2)
            with open(DELETED_FILE, 'w', encoding='utf-8') as f:
                json.dump(deleted_jobs, f, indent=2)
        except Exception as e:
            print(f"Error saving files during cleanup: {e}")


SEARCH_SITES = [
    {"id": "linkedin_fin", "platform": "linkedin", "url": "https://www.linkedin.com/jobs/search?location=Finland&sortBy=DD"},
    {"id": "linkedin_ww", "platform": "linkedin", "url": "https://www.linkedin.com/jobs/search?location=Worldwide&f_WT=2&sortBy=DD"},
    {"id": "duunitori", "platform": "duunitori", "url": "https://duunitori.fi/tyopaikat?jarjestys=uusimmat"},
    {"id": "indeed", "platform": "indeed", "url": "https://fi.indeed.com/jobs?l=Finland&sort=date"},
    {"id": "oikotie", "platform": "oikotie", "url": "https://tyopaikat.oikotie.fi/tyopaikat?jarjestys=julkaisuaika"},
    {"id": "tyomarkkinatori", "platform": "tyomarkkinatori", "url": "https://tyomarkkinatori.fi/henkiloasiakkaat/avoimet-tyopaikat?sort=published,desc"},
    {"id": "jobly", "platform": "jobly", "url": "https://www.jobly.fi/tyopaikat"},
    {"id": "meetfrank", "platform": "meetfrank", "url": "https://meetfrank.com/jobs/"},
    {"id": "hub", "platform": "hub", "url": "https://hub.no/jobs"}
]

def generate_targets():
    targets = []
    for site in SEARCH_SITES:
        targets.append({
            "id": site["id"],
            "platform": site["platform"],
            "term": "All",
            "url": site["url"]
        })
    return targets

def parse_linkedin(soup):
    jobs = []
    for card in soup.find_all('div', class_='base-card'):
        title_elem = card.find('h3', class_='base-search-card__title')
        company_elem = card.find('h4', class_='base-search-card__subtitle')
        location_elem = card.find('span', class_='job-search-card__location')
        url_elem = card.find('a', class_='base-card__full-link')
        if title_elem and url_elem:
            title = title_elem.text.strip()
            if 'senior' in title.lower():
                continue
            jobs.append({
                "title": title,
                "company": company_elem.text.strip() if company_elem else "Unknown",
                "location": location_elem.text.strip() if location_elem else "Unknown",
                "url": url_elem['href'].split('?')[0],
                "visited": "no",
                "matches_requirements": "pending",
                "reason": ""
            })
    return jobs

def parse_generic(soup, base_url):
    jobs = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Look for URL paths commonly associated with job postings
        if any(kw in href.lower() for kw in ['/tyopaikka', '/job', '/view', '/rc/clk', '/avoimet-tyopaikat']):
            # Skip search/list filter queries, sorting options, base list pages, and recruitment/pricing/advertising pages
            if any(skip in href.lower() for skip in [
                '?haku=', '?search=', '?q=', 'jarjestys=', '?sort=', 
                'tyopaikat.oikotie.fi/tyopaikat?', 'rekrytointi', 
                'tyopaikkailmoitus', '/tyonantajalle', '/yhteystiedot',
                '/palvelut/', '/hinnat', '/pricing', '/job-bookmarks-anon',
                'destination=search'
            ]):
                continue
            clean_path = href.lower().split('?')[0].rstrip('/')
            if clean_path.endswith('/tyopaikat') or clean_path.endswith('/avoimet-tyopaikat') or clean_path.endswith('/jobs'):
                continue
            title = a.text.strip()
            if 'senior' in title.lower():
                continue
            if 5 < len(title) < 100 and not any(skip in title.lower() for skip in ['read more', 'lue lisää', 'katso', 'show all']):
                raw_url = urljoin(base_url, href)
                # Normalize Indeed URLs to prevent duplicates
                if "indeed.com/rc/clk" in raw_url and "jk=" in raw_url:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(raw_url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if 'jk' in qs:
                        raw_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?jk={qs['jk'][0]}"
                        
                jobs.append({
                    "title": title.replace('\n', ' ').strip(),
                    "company": "Extract via OpenClaw",
                    "location": "Extract via OpenClaw",
                    "url": raw_url,
                    "visited": "no",
                    "matches_requirements": "pending",
                    "reason": ""
                })
    return jobs

def clean_old_backups(backup_dir):
    """Smart backup retention: keeps 1/hr for 24h, 1/day for 7d, 1/week for 4w."""
    if not os.path.exists(backup_dir):
        return
        
    import glob
    from datetime import datetime, timedelta
    
    now = datetime.now()
    files = glob.glob(os.path.join(backup_dir, "jobs_backup_*.json"))
    
    parsed_files = []
    for f in files:
        basename = os.path.basename(f)
        try:
            ts_str = basename.replace("jobs_backup_", "").replace(".json", "")
            file_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            parsed_files.append((f, file_time))
        except ValueError:
            continue
            
    # Sort files from newest to oldest
    parsed_files.sort(key=lambda x: x[1], reverse=True)
    
    keepers = set()
    seen_hours = set()
    seen_days = set()
    seen_weeks = set()
    
    for filepath, file_time in parsed_files:
        age = now - file_time
        
        # Keep latest backup unconditionally to never delete the one we just made
        if not keepers:
            keepers.add(filepath)
            continue
            
        if age <= timedelta(hours=24):
            hour_key = file_time.strftime("%Y%m%d_%H")
            if hour_key not in seen_hours:
                seen_hours.add(hour_key)
                keepers.add(filepath)
        elif age <= timedelta(days=8):
            day_key = file_time.strftime("%Y%m%d")
            if day_key not in seen_days:
                seen_days.add(day_key)
                keepers.add(filepath)
        elif age <= timedelta(days=36):
            week_key = f"{file_time.isocalendar()[0]}_{file_time.isocalendar()[1]}"
            if week_key not in seen_weeks:
                seen_weeks.add(week_key)
                keepers.add(filepath)

    deleted_count = 0
    for filepath, _ in parsed_files:
        if filepath not in keepers:
            try:
                os.remove(filepath)
                deleted_count += 1
            except Exception:
                pass
                
    if deleted_count > 0:
        print(f"INFO: Cleaned up {deleted_count} old backups (kept {len(keepers)}).")

def save_history_snapshot(jobs):
    """Append a count snapshot to jobs_history.json for trend tracking."""
    snapshot = {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "total": len(jobs),
        "yes": sum(1 for j in jobs if j.get('matches_requirements') == 'yes'),
        "no": sum(1 for j in jobs if j.get('matches_requirements') == 'no'),
        "maybe": sum(1 for j in jobs if j.get('matches_requirements') == 'maybe'),
        "pending": sum(1 for j in jobs if j.get('matches_requirements') == 'pending'),
    }
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(snapshot)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

def generate_history_from_backups():
    """One-time: build jobs_history.json from all existing backup files."""
    if os.path.exists(HISTORY_FILE):
        return  # Already generated
    import glob as _glob
    backup_dir = os.path.join(BASE_DIR, "backups")
    files = sorted(_glob.glob(os.path.join(backup_dir, "jobs_backup_*.json")))
    history = []
    for fpath in files:
        basename = os.path.basename(fpath)
        try:
            ts_str = basename.replace("jobs_backup_", "").replace(".json", "")
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            with open(fpath, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            history.append({
                "timestamp": ts.isoformat(timespec='seconds'),
                "total": len(jobs),
                "yes": sum(1 for j in jobs if j.get('matches_requirements') == 'yes'),
                "no": sum(1 for j in jobs if j.get('matches_requirements') == 'no'),
                "maybe": sum(1 for j in jobs if j.get('matches_requirements') == 'maybe'),
                "pending": sum(1 for j in jobs if j.get('matches_requirements') == 'pending'),
            })
        except Exception as e:
            print(f"WARN: Skipping {basename}: {e}")
    if history:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        print(f"INFO: Generated jobs_history.json with {len(history)} snapshots from backups.")

def scrape_all_jobs(max_jobs=200):
    seen_urls = set()
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, 'r', encoding='utf-8') as f:
                seen_urls = set(json.load(f))
        except Exception:
            pass

    checkpoint_idx = 0
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                checkpoint_idx = data.get("target_index", 0)
        except Exception:
            pass

    targets = generate_targets()
    if checkpoint_idx >= len(targets):
        print("Reached end of all targets. Resetting checkpoint to 0.")
        checkpoint_idx = 0

    all_extracted_jobs = []
    limit = max_jobs if max_jobs > 0 else float('inf')

    with sync_playwright() as p:
        print("Launching Playwright browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        current_idx = checkpoint_idx
        while current_idx < len(targets) and len(all_extracted_jobs) < limit:
            target = targets[current_idx]
            print(f"\nNavigating to {target['url']} (Term: {target['term']}, Site: {target['id']}) ...")
            try:
                page.goto(target['url'], timeout=30000)
                for _ in range(3):
                    page.mouse.wheel(0, 2000)
                    time.sleep(1.5)
                    
                soup = BeautifulSoup(page.content(), 'html.parser')
                
                if target['platform'] == 'linkedin':
                    jobs = parse_linkedin(soup)
                else:
                    jobs = parse_generic(soup, target['url'])
                    
                print(f"Found {len(jobs)} potential job links on {target['platform']}.")
                
                added = 0
                for job in jobs:
                    if len(all_extracted_jobs) >= limit:
                        break
                    if job['url'] not in seen_urls:
                        job['id'] = hashlib.md5(job['url'].encode('utf-8')).hexdigest()[:8]
                        job['source'] = target['id']
                        all_extracted_jobs.append(job)
                        seen_urls.add(job['url'])
                        added += 1
                        
                print(f"Added {added} new unseen jobs from this source.")
            except Exception as e:
                print(f"Failed to scrape {target['id']}: {e}")
                
            current_idx += 1
                
        browser.close()
        
    print(f"\nTotal new jobs fetched in this run: {len(all_extracted_jobs)}")
    print(f"Stopped at target index: {current_idx} out of {len(targets)}")
    
    # Read existing jobs so we can append rather than overwrite
    existing_jobs = []
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                existing_jobs = json.load(f)
        except Exception:
            pass

    combined_jobs = existing_jobs + all_extracted_jobs

    # Save combined jobs to jobs.json
    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(combined_jobs, f, indent=2)

    # Create a timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_file = os.path.join(backup_dir, f"jobs_backup_{timestamp}.json")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(combined_jobs, f, indent=2)

    print(f"Total jobs currently in jobs.json: {len(combined_jobs)}")
    print(f"Backup saved to: {backup_file}\n")

    # Append to history for trend chart
    save_history_snapshot(combined_jobs)

    # Run smart cleanup
    clean_old_backups(backup_dir)
        
    # Save updated seen urls history
    with open(SEEN_URLS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(seen_urls), f)
        
    # Save checkpoint
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump({"target_index": current_idx}, f, indent=2)
        
    return all_extracted_jobs

def get_file_hash(filepath):
    if not os.path.exists(filepath):
        return ""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def classify_requirements_change(old_content, new_content):
    """Ask the local LLM whether a requirements change exclusively adds constraints.
    Returns True if only new restrictions were added (stricter), False otherwise."""
    llm_endpoint = os.environ.get("LOCAL_LLM_ENDPOINT")
    llm_model = os.environ.get("LOCAL_LLM_MODEL")

    if not llm_endpoint or not llm_model:
        return False  # No LLM available — fall back to re-reviewing all jobs

    prompt = f"""You are analyzing changes to a job matching requirements document.

### OLD REQUIREMENTS:
{old_content}

### NEW REQUIREMENTS:
{new_content}

Determine whether the change ONLY adds new restrictions or exclusions (making requirements stricter), or whether it removes or relaxes any existing constraint.

Respond with ONLY a JSON object with one key:
- "only_adds_constraints": true if the change exclusively adds new hard rejections, exclusions, or restrictions without removing or relaxing any existing criteria; false if any existing constraint was removed, loosened, or if new positive/match criteria were added that could cause previously-rejected jobs to now match.

Example: {{"only_adds_constraints": true}}"""

    headers = {"Content-Type": "application/json"}
    llm_api_key = os.environ.get("LOCAL_LLM_API_KEY")
    if llm_api_key:
        headers["Authorization"] = f"Bearer {llm_api_key}"

    payload = {
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(llm_endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        result = extract_json_from_text(content)
        return bool(result.get("only_adds_constraints", False))
    except Exception as e:
        print(f"WARN: Could not classify requirements change via LLM ({e}). Will re-review all jobs.")
        return False


def check_requirements_update():
    """Check if job_requirements.md has changed, and flag jobs for re-evaluation if it has."""
    req_hash = get_file_hash(REQ_FILE)
    if not req_hash:
        return

    new_content = ""
    if os.path.exists(REQ_FILE):
        with open(REQ_FILE, 'r', encoding='utf-8') as f:
            new_content = f.read()

    checkpoint_data = {}
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
        except Exception:
            pass

    saved_hash = checkpoint_data.get("requirements_hash", "")
    if saved_hash and req_hash != saved_hash:
        print("INFO: job_requirements.md has changed! Analyzing the type of change...")
        old_content = checkpoint_data.get("requirements_content", "")

        only_adds_constraints = False
        if old_content:
            only_adds_constraints = classify_requirements_change(old_content, new_content)

        if only_adds_constraints:
            print("INFO: Change only adds constraints — re-reviewing only jobs previously marked 'yes' or 'maybe'.")
            status_filter = {'yes', 'maybe'}
        else:
            print("INFO: Change may loosen or alter constraints — re-reviewing all non-done jobs.")
            status_filter = None

        if os.path.exists(JOBS_FILE):
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            count = 0
            for job in jobs:
                if job.get('user_review') == 'done':
                    continue
                if job.get('applied') == 'yes':
                    continue
                if status_filter is None or job.get('matches_requirements') in status_filter:
                    job['needs_re_review'] = True
                    count += 1
            print(f"INFO: Flagged {count} jobs for re-review.")
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2)

    checkpoint_data["requirements_hash"] = req_hash
    checkpoint_data["requirements_content"] = new_content
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, indent=2)

def extract_json_from_text(text):
    """Finds and parses the first JSON object in a text block, handling markdown code fences."""
    text = text.strip()
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = text[start_idx:end_idx + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return json.loads(text)

def clean_page_text(text):
    """Strip cookie banners, navigation, and footer boilerplate from scraped job page text.
    
    This preprocessing improves LLM accuracy by removing noise that causes hallucinations
    (e.g., the LLM extracting 'Indeed' as company or confusing 'korkeakoulututkinto' with 'Oulu').
    """
    import re
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Common boilerplate patterns to skip (case-insensitive matching)
    skip_patterns = [
        # Cookie consent / GDPR banners
        'evästeasetukset', 'evästekäytäntö', 'hyväksy kaikki eväste',
        'hylkää kaikki', 'käytämme evästeitä',
        'cookie settings', 'accept all cookies', 'reject all',
        # Navigation / chrome
        'siirry sivun pääsisältöön', 'pääsisällön alku',
        'kirjaudu sisään', 'työnantajat / lähetä',
        'skip to main content', 'sign in',
        # Search UI
        'etsi työpaikkoja', 'find jobs', 'search jobs',
        # Footer
        '© 20', 'indeed ja saavutettavuus', 'tietosuojakeskus',
        'dsa-ilmoitukset', 'verkkoturvallisuussivu',
        'selaa työpaikkoja', 'maat',
        'privacy center', 'accessibility',
        # Action prompts
        'sinun on luotava indeed-tili', 'hae työpaikkaa yrityksen sivustolla',
        'tee ilmoitus työpaikasta',
        # Anti-bot
        'checking your browser', 'ddos-guard', 'please stand by',
        'please allow up to',
    ]
    
    # Single-word nav items to skip (exact match on stripped line)
    nav_words = {'koti', 'home', 'mitä', 'missä', 'about', 'ohje', 'ehdot'}
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        
        # Skip lines that match boilerplate patterns
        if any(pat in lower for pat in skip_patterns):
            continue
        
        # Skip single nav words
        if lower in nav_words:
            continue
        
        # Skip very short lines that are just UI labels (1-2 chars or just &nbsp;)
        if len(stripped) <= 2 or stripped == '&nbsp;':
            continue
        
        cleaned_lines.append(stripped)
    
    return '\n'.join(cleaned_lines)

def detect_finnish_text(text):
    """Check if text appears to be written in Finnish based on common Finnish words."""
    finnish_indicators = [
        'työpaikka', 'työnkuvaus', 'hakuaika', 'kelpoisuus', 'tehtävä',
        'työsuhde', 'vakituinen', 'palkkaus', 'työssä', 'hae työpaikka',
        'sijainti', 'arvostamme', 'edellyttää', 'yhteystiedot',
        'työpaikan tiedot', 'työnantaja', 'kokemus', 'koulutus'
    ]
    text_lower = text.lower()
    matches = sum(1 for word in finnish_indicators if word in text_lower)
    return matches >= 2

def standardize_date(date_str):
    """Standardizes various date formats into YYYY-MM-DD."""
    if not date_str: return 'N/A'
    date_str = str(date_str).strip().lower()
    if date_str in ['n/a', 'unknown', 'not specified', 'none', 'null']: return 'N/A'
    if 'open' in date_str: return 'Open until filled'
    
    import re
    from datetime import datetime, timedelta
    
    # Handle ranges like "15.6. - 21.6." by taking the end date
    if '-' in date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        parts = date_str.split('-')
        date_str = parts[-1].strip()
        
    # Standard YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
        
    # Finnish / European DD.MM.YYYY
    fi_match = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', date_str)
    if fi_match:
        return f"{int(fi_match.group(3)):04d}-{int(fi_match.group(2)):02d}-{int(fi_match.group(1)):02d}"
        
    # Incomplete DD.MM. (assume current year)
    fi_short = re.match(r'^(\d{1,2})\.(\d{1,2})\.?$', date_str)
    if fi_short:
        year = datetime.now().year
        return f"{year:04d}-{int(fi_short.group(2)):02d}-{int(fi_short.group(1)):02d}"
        
    try:
        if 't' in date_str:
            d = datetime.fromisoformat(date_str.split('t')[0])
            return d.strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    today = datetime.now()
    
    # "tänään", "eilen"
    if 'tänään' in date_str or 'today' in date_str:
        return today.strftime("%Y-%m-%d")
    if 'eilen' in date_str or 'yesterday' in date_str:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
    # Relative formats: "X päivä(ä) sitten", "X viikko(a) sitten", "X kuukausi(a) sitten"
    rel_match = re.search(r'(\d+)\s+(day|päivä|viikko|week|month|kuukaus|hour|tunti|min)', date_str)
    if rel_match:
        num = int(rel_match.group(1))
        unit = rel_match.group(2)
        if 'day' in unit or 'päivä' in unit:
            return (today - timedelta(days=num)).strftime("%Y-%m-%d")
        if 'week' in unit or 'viikko' in unit:
            return (today - timedelta(weeks=num)).strftime("%Y-%m-%d")
        if 'month' in unit or 'kuukaus' in unit:
            return (today - timedelta(days=num*30)).strftime("%Y-%m-%d")
        if 'hour' in unit or 'tunti' in unit or 'min' in unit:
            return today.strftime("%Y-%m-%d")
            
    # Also "X d ago", "X w ago"
    short_rel = re.search(r'(\d+)\s*(d|w|m)\s+ago', date_str)
    if short_rel:
        num = int(short_rel.group(1))
        unit = short_rel.group(2)
        if unit == 'd': return (today - timedelta(days=num)).strftime("%Y-%m-%d")
        if unit == 'w': return (today - timedelta(weeks=num)).strftime("%Y-%m-%d")
        if unit == 'm': return (today - timedelta(days=num*30)).strftime("%Y-%m-%d")
        
    try:
        months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        months_short = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        parts = date_str.replace(',', '').split()
        if len(parts) >= 3:
            year_part = [p for p in parts if p.isdigit() and len(p) == 4]
            day_part = [p for p in parts if p.isdigit() and len(p) <= 2]
            month_part = [p for p in parts if p in months or p in months_short]
            if year_part and day_part and month_part:
                m_str = month_part[0]
                m_idx = months.index(m_str) + 1 if m_str in months else months_short.index(m_str) + 1
                y = int(year_part[0])
                d = int(day_part[0])
                return f"{y:04d}-{m_idx:02d}-{d:02d}"
    except Exception:
        pass

    return date_str

def extract_location_from_text(text):
    """Extract location from job page text using regex patterns.
    
    Looks for Finnish postal codes (NNNNN CityName), 'Sijainti' headers, 
    and known Finnish city names. Returns the best match or None.
    """
    import re
    
    lines = text.split('\n')
    
    # Regional municipalities for standardization
    oulu_region = {'Oulu', 'Kempele', 'Liminka', 'Haukipudas', 'Oulunsalo', 'Kiiminki', 'Tyrnävä', 'Muhos', 'Lumijoki', 'Hailuoto'}
    helsinki_region = {'Helsinki', 'Espoo', 'Vantaa', 'Kauniainen', 'Kerava', 'Sipoo', 'Kirkkonummi', 'Tuusula', 'Järvenpää', 'Nurmijärvi', 'Vihti', 'Porvoo', 'Lohja', 'Hyvinkää', 'Mäntsälä'}
    turku_region = {'Turku', 'Kaarina', 'Raisio', 'Naantali', 'Lieto', 'Parainen', 'Paimio', 'Masku', 'Rusko', 'Nousiainen', 'Salo'}
    tampere_region = {'Tampere', 'Nokia', 'Ylöjärvi', 'Kangasala', 'Lempäälä', 'Pirkkala', 'Orivesi', 'Valkeakoski', 'Vesilahti', 'Hämeenkyrö'}
    jyvaskyla_region = {'Jyväskylä', 'Muurame', 'Laukaa', 'Äänekoski', 'Jämsä', 'Keuruu', 'Petäjävesi', 'Toivakka', 'Uurainen'}
    rovaniemi_region = {'Rovaniemi', 'Ranua', 'Pello', 'Ylitornio', 'Kemijärvi', 'Sodankylä'}
    
    def format_city(c):
        if c in oulu_region:
            return "Oulu Region, Finland"
        if c in helsinki_region:
            return "Helsinki Region, Finland"
        if c in turku_region:
            return "Turku Region, Finland"
        if c in tampere_region:
            return "Tampere Region, Finland"
        if c in jyvaskyla_region:
            return "Jyväskylä Region, Finland"
        if c in rovaniemi_region:
            return "Rovaniemi Region, Finland"
        return f"{c}, Finland"

    # Pattern 1: Finnish postal code format "NNNNN CityName"
    postal_pattern = re.compile(r'\b(\d{5})\s+([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)?)\b')
    for line in lines:
        match = postal_pattern.search(line.strip())
        if match:
            city = match.group(2).strip()
            return format_city(city)
    
    # Pattern 2: Line after "Sijainti" header
    for i, line in enumerate(lines):
        if line.strip().lower() == 'sijainti' and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and len(next_line) > 2:
                # If it's a postal code line, extract city
                match = postal_pattern.search(next_line)
                if match:
                    return format_city(match.group(2).strip())
                # Otherwise use the line as-is (might be a city name)
                if len(next_line) < 60:
                    return format_city(next_line)
    
    # Pattern 3: Known Finnish cities mentioned in text
    finnish_cities = [
        'Helsinki', 'Espoo', 'Tampere', 'Vantaa', 'Oulu', 'Turku',
        'Jyväskylä', 'Lahti', 'Kuopio', 'Pori', 'Kouvola', 'Joensuu',
        'Lappeenranta', 'Hämeenlinna', 'Vaasa', 'Seinäjoki', 'Rovaniemi',
        'Mikkeli', 'Kotka', 'Salo', 'Porvoo', 'Kokkola', 'Lohja',
        'Hyvinkää', 'Järvenpää', 'Rauma', 'Kajaani', 'Kerava', 'Savonlinna',
        'Nokia', 'Riihimäki', 'Kangasala', 'Lieto', 'Raisio', 'Kirkkonummi',
        'Ylöjärvi', 'Kaarina', 'Tornio', 'Siilinjärvi', 'Hollola', 'Sipoo',
        'Iisalmi', 'Naantali', 'Lempäälä', 'Heinola', 'Hausjärvi', 'Kiuruvesi'
    ]
    text_words = set(re.findall(r'\b[A-ZÄÖÅa-zäöå]+\b', text))
    for city in finnish_cities:
        if city in text_words or city.lower() in {w.lower() for w in text_words}:
            return format_city(city)
    
    return None

_LOCATION_REGIONS = {
    # city (lowercase) -> canonical region string
    **{c.lower(): "Oulu Region, Finland" for c in
       ['Oulu', 'Kempele', 'Liminka', 'Haukipudas', 'Oulunsalo', 'Kiiminki', 'Tyrnävä', 'Muhos', 'Lumijoki', 'Hailuoto']},
    **{c.lower(): "Helsinki Region, Finland" for c in
       ['Helsinki', 'Espoo', 'Vantaa', 'Kauniainen', 'Kerava', 'Sipoo', 'Kirkkonummi', 'Tuusula',
        'Järvenpää', 'Nurmijärvi', 'Vihti', 'Porvoo', 'Lohja', 'Hyvinkää', 'Mäntsälä']},
    **{c.lower(): "Turku Region, Finland" for c in
       ['Turku', 'Kaarina', 'Raisio', 'Naantali', 'Lieto', 'Parainen', 'Paimio', 'Masku', 'Rusko', 'Nousiainen', 'Salo']},
    **{c.lower(): "Tampere Region, Finland" for c in
       ['Tampere', 'Nokia', 'Ylöjärvi', 'Kangasala', 'Lempäälä', 'Pirkkala', 'Orivesi', 'Valkeakoski', 'Vesilahti', 'Hämeenkyrö']},
    **{c.lower(): "Jyväskylä Region, Finland" for c in
       ['Jyväskylä', 'Muurame', 'Laukaa', 'Äänekoski', 'Jämsä', 'Keuruu', 'Petäjävesi', 'Toivakka', 'Uurainen']},
    **{c.lower(): "Rovaniemi Region, Finland" for c in
       ['Rovaniemi', 'Ranua', 'Pello', 'Ylitornio', 'Kemijärvi', 'Sodankylä']},
}

def normalize_location(location_str):
    """Validate and correct an LLM-returned location string against known city→region mappings.

    Returns the corrected string, or the original if no known city is found in it.
    Prevents misclassification where e.g. 'Espoo' ends up tagged as 'Oulu Region'.
    """
    if not location_str or location_str == "N/A":
        return location_str
    lower = location_str.lower()
    # Scan for any known city name inside the string
    for city_lower, canonical in _LOCATION_REGIONS.items():
        if city_lower in lower:
            if location_str != canonical:
                print(f"INFO: Correcting location '{location_str}' → '{canonical}' (city: {city_lower})")
            return canonical
    return location_str


def extract_company_from_text(text, job_title):
    """Extract company name from job page text using structural patterns.
    
    Looks for the company name that typically appears right after or near the job title
    in Finnish job board pages.
    """
    lines = text.split('\n')
    
    # Pattern 1: Line immediately after the job title
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and job_title and stripped.lower() == job_title.lower():
            # The next non-empty line is typically the company name
            for j in range(i + 1, min(i + 3, len(lines))):
                next_line = lines[j].strip()
                if next_line and len(next_line) > 2 and len(next_line) < 80:
                    # Skip postal codes and known non-company lines
                    import re
                    if re.match(r'^\d{5}\s', next_line):
                        continue
                    if next_line.lower() in ['vakituinen', 'sijainti', 'työpaikan tiedot', 'työpaikan tyyppi']:
                        continue
                    return next_line
    
    # Pattern 2: Look for "kunta" (municipality), "Oy" (company), "kaupunki" (city govt) patterns  
    import re
    company_patterns = [
        re.compile(r'\b([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)*\s+(?:kunta|kaupunki|Oy|Ab|Oyj|ry))\b'),
        re.compile(r'\b([A-ZÄÖÅ][a-zäöå]+n\s+kaupunki)\b'),  # e.g., "Liedon kaupunki"
        re.compile(r'\b([A-ZÄÖÅ][a-zäöå]+n\s+kunta)\b'),  # e.g., "Hausjärven kunta"
    ]
    for pattern in company_patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    
    return None

def review_pending_jobs(specific_urls=None):
    """Visit URLs of pending jobs, extract description, and evaluate using a local LLM."""
    if not os.path.exists(JOBS_FILE):
        return
        
    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
        
    def _is_reviewable(j):
        if j.get('user_review') == 'done':
            return False
        if j.get('applied') == 'yes':
            return False
        return j.get('matches_requirements') == 'pending' or j.get('needs_re_review') == True

    if specific_urls is not None:
        pending_jobs = [j for j in jobs if _is_reviewable(j) and j['url'] in specific_urls]
    else:
        pending_jobs = [j for j in jobs if _is_reviewable(j)]
        
    if not pending_jobs:
        return
        
    llm_endpoint = os.environ.get("LOCAL_LLM_ENDPOINT")
    llm_model = os.environ.get("LOCAL_LLM_MODEL")

    if not llm_endpoint or not llm_model:
        print("ERROR: LOCAL_LLM_ENDPOINT and LOCAL_LLM_MODEL environment variables must be set to use a local LLM. Skipping review.")
        print("INFO: Examples to set variables:")
        print("      Bash (Linux/WSL):    export LOCAL_LLM_ENDPOINT='http://localhost:11434/v1/chat/completions'")
        print("                           export LOCAL_LLM_MODEL='llama3'")
        print("      PowerShell (Windows):$env:LOCAL_LLM_ENDPOINT='http://localhost:11434/v1/chat/completions'")
        print("                           $env:LOCAL_LLM_MODEL='llama3'")
        print("      CMD (Windows):       set LOCAL_LLM_ENDPOINT=http://localhost:11434/v1/chat/completions")
        print("                           set LOCAL_LLM_MODEL=llama3")
        return

    print(f"\nEvaluating {len(pending_jobs)} pending jobs using local LLM at {llm_endpoint} with model {llm_model}...")
    
    requirements_text = ""
    if os.path.exists(REQ_FILE):
        with open(REQ_FILE, 'r') as f:
            requirements_text = f.read()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        for job in pending_jobs:
            if stop_event.is_set():
                break
            print(f"Reviewing: {job['title']} at {job['url']}")
            try:
                page.goto(job['url'], timeout=30000)
                
                # Smart wait: detect DDoS guard / anti-bot pages and retry
                text = ""
                ddos_keywords = ['ddos-guard', 'checking your browser', 'please stand by', 'please allow up to']
                max_retries = 4
                for attempt in range(max_retries):
                    wait_time = 1.5 if attempt == 0 else 3.0
                    time.sleep(wait_time)
                    try:
                        text = page.locator('body').inner_text()
                    except Exception:
                        text = ""
                    
                    text_lower = text.lower().strip()
                    # Check if the page is still showing a DDoS guard / anti-bot interstitial
                    if any(kw in text_lower for kw in ddos_keywords) and len(text) < 1500:
                        print(f"  [Attempt {attempt + 1}/{max_retries}] Anti-bot page detected, waiting longer...")
                        continue
                    else:
                        break
                
                posted_date = "N/A"
                deadline = "N/A"

                # Sanity check: if text is empty or still a DDoS guard page, treat as error
                text_lower_check = text.lower().strip()
                is_ddos_page = any(kw in text_lower_check for kw in ddos_keywords) and len(text) < 1500
                if not text.strip() or is_ddos_page:
                    match, reason = "error", "Could not extract text from page (anti-bot protection or empty page)."
                else:
                    # Clean page text to remove cookie banners, nav, footers
                    cleaned_text = clean_page_text(text)
                    is_finnish = detect_finnish_text(cleaned_text)
                    
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    prompt = f"""Please act as an expert job reviewer. Read the following job description and evaluate it against the requirements.
        
        Important Date Vocabulary for Finnish Jobs:
        - "Julkaistu" means Posted Date.
        - "Haku päättyy", "Hakuaika päättyy", or "Viimeinen hakupäivä" means Deadline Date.
        Do NOT confuse the posted date with the deadline date!

        Respond ONLY with a valid JSON object matching this exact structure:

### Job Requirements:
{requirements_text}

### Job Details:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
URL: {job['url']}

### Job Description:
{cleaned_text[:15000]}

### Instructions:
Return a JSON object with exactly six keys:
- "match": a string, either "yes", "maybe", or "no".
- "reason": a short 1-sentence explanation of your decision.
- "posted_date": a string, the date the job was posted formatted strictly as YYYY-MM-DD (e.g. '2026-06-12'). If a relative date like '3 days ago' is mentioned, calculate it relative to today's date ({today_str}). If not found, return 'N/A'.
- "deadline": a string, the deadline for applying formatted strictly as YYYY-MM-DD (e.g. '2026-06-30'). Ignore any times (e.g. if deadline is 15.6.2026 23:59, return '2026-06-15'). If it is open-ended or 'open until filled', return 'Open until filled'. If not found, return 'N/A'.
- "company": a string, the name of the hiring company as stated in the job posting (e.g. 'Wolt' or 'N/A' if not found). Do NOT use the job board name (e.g. do NOT return 'Indeed' or 'LinkedIn').
- "location": a string, the PRIMARY work location of the job. Map it to EXACTLY one of the strings below based on the city — do NOT mix up regions:
  * 'Oulu Region, Finland' — if city is one of: Oulu, Kempele, Liminka, Haukipudas, Oulunsalo, Kiiminki, Tyrnävä, Muhos, Lumijoki, Hailuoto
  * 'Helsinki Region, Finland' — if city is one of: Helsinki, Espoo, Vantaa, Kauniainen, Kerava, Sipoo, Kirkkonummi, Tuusula, Järvenpää, Nurmijärvi, Vihti, Porvoo, Lohja, Hyvinkää, Mäntsälä
  * 'Turku Region, Finland' — if city is one of: Turku, Kaarina, Raisio, Naantali, Lieto, Parainen, Paimio, Masku, Rusko, Nousiainen, Salo
  * 'Tampere Region, Finland' — if city is one of: Tampere, Nokia, Ylöjärvi, Kangasala, Lempäälä, Pirkkala, Orivesi, Valkeakoski, Vesilahti, Hämeenkyrö
  * 'Jyväskylä Region, Finland' — if city is one of: Jyväskylä, Muurame, Laukaa, Äänekoski, Jämsä, Keuruu, Petäjävesi, Toivakka, Uurainen
  * 'Rovaniemi Region, Finland' — if city is one of: Rovaniemi, Ranua, Pello, Ylitornio, Kemijärvi, Sodankylä
  * For any other Finnish city, return 'CityName, Finland'. Return 'N/A' only if truly unknown.
  IMPORTANT: Use only the PRIMARY work location. Ignore offices mentioned in passing. Espoo and Vantaa are Helsinki Region — NEVER Oulu Region.

IMPORTANT: Extract company and location ONLY from information explicitly stated in the job description text. Do NOT guess or hallucinate values.
Do not include any conversational intro/outro or explanations outside the JSON object.
"""
                    headers = {"Content-Type": "application/json"}
                    llm_api_key = os.environ.get("LOCAL_LLM_API_KEY")
                    if llm_api_key:
                        headers["Authorization"] = f"Bearer {llm_api_key}"

                    payload = {
                        "model": llm_model,
                        "messages": [{"role": "user", "content": prompt}]
                    }

                    try:
                        response = requests.post(llm_endpoint, headers=headers, json=payload, timeout=120)
                        response.raise_for_status()
                        
                        response_json = response.json()
                        content = response_json['choices'][0]['message']['content']
                        
                        # Use robust JSON extraction
                        result = extract_json_from_text(content)
                        match = str(result.get("match", "no")).lower()
                        reason = str(result.get("reason", "No reason provided by LLM."))
                        
                        # Only accept AI dates if we don't already have a valid one
                        import re
                        ai_posted = standardize_date(result.get("posted_date", "N/A"))
                        current_posted = job.get("posted_date", "N/A")
                        if current_posted == "N/A" or not re.match(r'^\d{4}-\d{2}-\d{2}$', str(current_posted)):
                            posted_date = ai_posted
                        else:
                            posted_date = current_posted
                            
                        ai_deadline = standardize_date(result.get("deadline", "N/A"))
                        current_deadline = job.get("deadline", "N/A")
                        if current_deadline == "N/A" or (not re.match(r'^\d{4}-\d{2}-\d{2}$', str(current_deadline)) and 'open' not in str(current_deadline).lower()):
                            deadline = ai_deadline
                        else:
                            deadline = current_deadline
                        
                        # Extract company and location from LLM if scraper had placeholder/unknown
                        ai_company = str(result.get("company", "N/A"))
                        ai_location = normalize_location(str(result.get("location", "N/A")))

                        if ai_company != "N/A" and (job.get('company') in ["Extract via OpenClaw", "Unknown", "", None]):
                            job['company'] = ai_company
                        if ai_location != "N/A" and (job.get('location') in ["Extract via OpenClaw", "Unknown", "", None]):
                            job['location'] = ai_location
                        # Normalize the existing location to fix any historical misclassifications
                        elif job.get('location'):
                            job['location'] = normalize_location(job['location'])
                        
                        # Regex-based extraction: more reliable than LLM for structured Finnish data
                        regex_location = extract_location_from_text(cleaned_text)
                        regex_company = extract_company_from_text(cleaned_text, job.get('title', ''))
                        
                        # Override with regex results if LLM failed or returned placeholder
                        if regex_location and (job.get('location') in ["Extract via OpenClaw", "Unknown", "", None, "N/A"]):
                            job['location'] = regex_location
                        if regex_company and (job.get('company') in ["Extract via OpenClaw", "Unknown", "", None, "N/A"]):
                            job['company'] = regex_company
                        
                        # Final fallback: if location is still unknown but text is Finnish, infer Finland
                        if job.get('location') in ["Extract via OpenClaw", "Unknown", "", None, "N/A"] and is_finnish:
                            job['location'] = "Finland"
                            
                        if match not in ["yes", "maybe", "no"]:
                            match = "no"
                    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, IndexError) as llm_err:
                        match = "error"
                        reason = f"Failed to get or parse local LLM response: {llm_err}"

                # Update job dictionary in-place
                job['visited'] = "yes"
                job['matches_requirements'] = match
                job['reason'] = reason
                job['posted_date'] = posted_date
                job['deadline'] = deadline
                job.pop('needs_re_review', None)
                
                # If a posting matches requirements, save job description text to a file inside job_descriptions/
                if match == 'yes':
                    import re
                    clean_title = re.sub(r'[^a-zA-Z0-9]', '_', job['title'].lower())[:30]
                    clean_company = re.sub(r'[^a-zA-Z0-9]', '_', job['company'].lower())[:20]
                    url_hash = hashlib.md5(job['url'].encode('utf-8')).hexdigest()[:8]
                    desc_filename = f"{clean_company}_{clean_title}_{url_hash}.txt"
                    
                    desc_dir = os.path.join(BASE_DIR, "job_descriptions")
                    os.makedirs(desc_dir, exist_ok=True)
                    desc_path = os.path.join(desc_dir, desc_filename)
                    try:
                        with open(desc_path, 'w', encoding='utf-8') as f_desc:
                            f_desc.write(f"Title: {job['title']}\n")
                            f_desc.write(f"Company: {job['company']}\n")
                            f_desc.write(f"Location: {job['location']}\n")
                            f_desc.write(f"URL: {job['url']}\n")
                            f_desc.write(f"Posted: {posted_date}\n")
                            f_desc.write(f"Deadline: {deadline}\n")
                            f_desc.write(f"Reason: {reason}\n")
                            f_desc.write("\n" + "="*40 + "\n")
                            f_desc.write("JOB DESCRIPTION:\n")
                            f_desc.write("="*40 + "\n\n")
                            f_desc.write(text)
                        job['description_file'] = f"job_descriptions/{desc_filename}"
                    except Exception as e_desc:
                        print(f"Error writing description file: {e_desc}")
                        job['description_file'] = None
                else:
                    job['description_file'] = None

                print(f" -> {match.upper()}: {reason} (Posted: {posted_date}, Deadline: {deadline}, Company: {job['company']}, Location: {job['location']})")
                
            except Exception as e:
                print(f" -> ERROR: Failed to evaluate ({e})")
                job['visited'] = "yes"
                job['matches_requirements'] = "error"
                job['reason'] = "Page load or parsing error."
                job['posted_date'] = "N/A"
                job['deadline'] = "N/A"
                job['description_file'] = None
                
            # Save aggressively after each evaluation
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2)
                
        browser.close()

def update_git():
    print("\nUpdating GitHub repository...")
    try:
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Clean up the environment to prevent VS Code's git helper from causing socket errors
        env = os.environ.copy()
        env.pop("GIT_ASKPASS", None)
        env["GIT_TERMINAL_PROMPT"] = "0"

        # Check if the folder is inside a Git repository
        is_git = False
        check_path = repo_dir
        while True:
            if os.path.exists(os.path.join(check_path, ".git")):
                is_git = True
                break
            parent = os.path.dirname(check_path)
            if parent == check_path:
                break
            check_path = parent

        if not is_git:
            print("INFO: Directory is not a Git repository. Skipping Git update.")
            return

        # Add updated files (including dashboard HTML and scraper changes)
        subprocess.run(["git", "add", "jobs.json", "seen_urls.json", "checkpoint.json", "dashboard.html",
                        "job_descriptions", "job_requirements.md",
                        "firebase_app/index.html", "scraper.py", "jobs_history.json"], cwd=repo_dir, check=True, env=env)
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True, env=env)
        if status.stdout.strip():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"Auto-update scraped jobs: {timestamp}"
            subprocess.run(["git", "commit", "-m", commit_message], cwd=repo_dir, check=True, env=env)
            
            # Check for GitHub token in environment variables
            push_cmd = ["git", "push"]
            github_token = os.environ.get("GITHUB_TOKEN")
            if github_token:
                remote_result = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=repo_dir, capture_output=True, text=True)
                remote_url = remote_result.stdout.strip()
                if remote_url.startswith("https://"):
                    auth_url = remote_url.replace("https://", f"https://{github_token}@")
                    push_cmd = ["git", "push", auth_url]

            try:
                subprocess.run(push_cmd, cwd=repo_dir, check=True, env=env)
                print("Successfully pushed updates to GitHub!")
                # Deploy dashboard to Firebase Hosting if the CLI is available
                firebase_app_dir = os.path.join(repo_dir, "firebase_app")
                if os.path.exists(os.path.join(firebase_app_dir, "firebase.json")):
                    try:
                        subprocess.run(["firebase", "deploy", "--only", "hosting", "--non-interactive"],
                                       cwd=firebase_app_dir, check=True, env=env, timeout=120)
                        print("Successfully deployed dashboard to Firebase Hosting.")
                    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as fe:
                        print(f"Firebase deploy skipped or failed (run 'firebase deploy' manually if needed): {fe}")
            except subprocess.CalledProcessError:
                print("Failed to push to GitHub (Check your GITHUB_TOKEN or internet connection).")
        else:
            print("No changes to commit. GitHub is already up to date.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to update Git: {e}")

# Event flag to signal when the user wants to stop
stop_event = threading.Event()

def listen_for_input():
    """Background task waiting for the user to press Enter."""
    try:
        input()
        stop_event.set()
    except EOFError:
        pass

def print_job_summary():
    """Reads jobs.json and prints a summary of job statuses."""
    if not os.path.exists(JOBS_FILE):
        print("\nStats - No jobs.json file found.")
        return
        
    try:
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)
            total_jobs = len(jobs_data)
            matching_jobs = sum(1 for j in jobs_data if j.get('matches_requirements') == 'yes')
            maybe_jobs = sum(1 for j in jobs_data if j.get('matches_requirements') == 'maybe')
            no_jobs = sum(1 for j in jobs_data if j.get('matches_requirements') == 'no')
            pending_jobs = sum(1 for j in jobs_data if j.get('matches_requirements') == 'pending')
            
        print(f"\nStats - Total jobs: {total_jobs} | Yes Match: {matching_jobs} | Maybe Match: {maybe_jobs} | No Match: {no_jobs} | Pending: {pending_jobs}")
    except Exception as e:
        print(f"Error reading jobs file for status display: {e}")

def self_heal_locations():
    """One-time pass: normalize every job's location field against the known city→region map."""
    if not os.path.exists(JOBS_FILE):
        return
    try:
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
        changed = False
        for job in jobs:
            loc = job.get('location', '')
            fixed = normalize_location(loc)
            if fixed and fixed != loc:
                job['location'] = fixed
                changed = True
        if changed:
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2)
            print("INFO: self_heal_locations: corrected location misclassifications in jobs.json.")
    except Exception as e:
        print(f"Error during self_heal_locations: {e}")


def self_heal_dates():
    """Run through existing jobs in jobs.json and standardize their dates using the native scraper logic."""
    if not os.path.exists(JOBS_FILE):
        return
    try:
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
            
        changed = False
        for job in jobs:
            p = str(job.get('posted_date', ''))
            d = str(job.get('deadline', ''))
            
            new_p = standardize_date(p)
            new_d = standardize_date(d)
            
            if new_p != p:
                job['posted_date'] = new_p
                changed = True
            if new_d != d:
                job['deadline'] = new_d
                changed = True
                
        if changed:
            print("INFO: Natively standardized messy dates in jobs.json!")
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2)
    except Exception as e:
        print(f"Error self-healing dates: {e}")

def is_meaningful_reason(reason):
    """Returns True if reason is substantive enough to add to job requirements."""
    stripped = reason.strip().lower()
    if len(stripped.split()) < 3:
        return False
    test_words = ('test', 'testing', 'try', 'trying', 'debug', 'hello', 'foo', 'bar', 'abc', 'asdf', 'sample', 'check', 'again')
    if stripped.split()[0] in test_words:
        return False
    return True


def send_email_notification(subject, body):
    """Send an email via Gmail SMTP. Requires GMAIL_SENDER and GMAIL_APP_PASSWORD env vars."""
    import smtplib
    from email.mime.text import MIMEText
    sender = os.environ.get("GMAIL_SENDER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("NOTIFICATION_EMAIL", sender)
    if not sender or not app_password:
        print("INFO: Email notification skipped (GMAIL_SENDER / GMAIL_APP_PASSWORD not set).")
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.sendmail(sender, [recipient], msg.as_string())
        print(f"INFO: Email notification sent to {recipient}.")
    except Exception as e:
        print(f"WARN: Failed to send email notification: {e}")


def poll_firebase_feedback():
    """Polls the Firebase Firestore REST API for user feedback, updates requirements, and deletes them."""
    url = "https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents/user_feedback"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return # Database not created, or empty, or permission denied
            
        data = response.json()
        documents = data.get("documents", [])
        if not documents:
            return
            
        print(f"\nINFO: Found {len(documents)} new feedback items from the cloud dashboard!")
        
        new_positive_rules = []
        new_negative_rules = []
        user_review_updates = {}
        match_updates = {}
        processed_urls = set()
        
        for doc in documents:
            doc_name = doc.get("name")
            fields = doc.get("fields", {})
            status = fields.get("status", {}).get("stringValue", "unread")
            
            if status == "read":
                continue
                
            feedback_type = fields.get("type", {}).get("stringValue", "negative")
            url_field = fields.get("url", {}).get("stringValue", "")
            if url_field:
                processed_urls.add(url_field)
            
            if feedback_type == "user_review_update":
                new_status = fields.get("user_review", {}).get("stringValue", "pending")
                url_field = fields.get("url", {}).get("stringValue", "")
                if url_field:
                    user_review_updates[url_field] = new_status
                
                # Update status to "read"
                if doc_name:
                    update_url = f"https://firestore.googleapis.com/v1/{doc_name}?updateMask.fieldPaths=status"
                    payload = {"fields": {"status": {"stringValue": "read"}}}
                    requests.patch(update_url, json=payload, timeout=10)
                continue
                

            if feedback_type == "applied_update":
                new_status = fields.get("applied", {}).get("stringValue", "no")
                url_field = fields.get("url", {}).get("stringValue", "")
                if url_field:
                    if 'applied_updates' not in locals():
                        applied_updates = {}
                    applied_updates[url_field] = new_status
                
                # Update status to "read"
                if doc_name:
                    update_url = f"https://firestore.googleapis.com/v1/{doc_name}?updateMask.fieldPaths=status"
                    payload = {"fields": {"status": {"stringValue": "read"}}}
                    requests.patch(update_url, json=payload, timeout=10)
                continue

            reason = fields.get("reason", {}).get("stringValue", "")

            if feedback_type == "positive":
                if url_field:
                    match_updates[url_field] = ("yes", reason.strip())
            else:
                if url_field:
                    match_updates[url_field] = ("no", reason.strip())

            if reason and reason.strip():
                if is_meaningful_reason(reason.strip()):
                    if feedback_type == "positive":
                        new_positive_rules.append(reason.strip())
                    else:
                        new_negative_rules.append(reason.strip())
                else:
                    print(f"INFO: Skipping low-quality reason (not added to requirements): '{reason.strip()}'")
                
            # Update the document status to "read" so we keep a history in the cloud
            if doc_name:
                update_url = f"https://firestore.googleapis.com/v1/{doc_name}?updateMask.fieldPaths=status"
                payload = {"fields": {"status": {"stringValue": "read"}}}
                requests.patch(update_url, json=payload, timeout=10)
                
        if new_positive_rules or new_negative_rules:
            with open(REQ_FILE, 'a', encoding='utf-8') as f:
                if new_negative_rules:
                    f.write("\n\n### Automatically Added Negative Constraints (from UI Rejections):\n")
                    for rule in new_negative_rules:
                        f.write(f"- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: '{rule}'. Do NOT match jobs that have this issue.\n")
                if new_positive_rules:
                    f.write("\n\n### Automatically Added Positive Constraints (from UI Approvals):\n")
                    for rule in new_positive_rules:
                        f.write(f"- POSITIVE CONSTRAINT: The user explicitly approved a previous job because: '{rule}'. Make sure to MATCH jobs that have this characteristic.\n")
            print(f"INFO: Successfully updated job_requirements.md with {len(new_positive_rules)} positive and {len(new_negative_rules)} negative rules!")
            

        if locals().get('applied_updates'):
            try:
                if os.path.exists(JOBS_FILE):
                    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                        jobs = json.load(f)
                    changed = False
                    for j in jobs:
                        if j.get('url') in applied_updates:
                            j['applied'] = applied_updates[j['url']]
                            changed = True
                    if changed:
                        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                            json.dump(jobs, f, indent=2)
                    print(f"INFO: Successfully synced applied status for {len(applied_updates)} jobs from the cloud.")
            except Exception as e:
                print(f"Error syncing applied status: {e}")

        if user_review_updates:
            try:
                if os.path.exists(JOBS_FILE):
                    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                        jobs = json.load(f)
                    changed = False
                    for j in jobs:
                        if j.get('url') in user_review_updates:
                            j['user_review'] = user_review_updates[j['url']]
                            changed = True
                    if changed:
                        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                            json.dump(jobs, f, indent=2)
                    print(f"INFO: Successfully synced user_review status for {len(user_review_updates)} jobs from the cloud.")
            except Exception as e:
                print(f"Error syncing user review status: {e}")
            
    
        if match_updates:
            try:
                if os.path.exists(JOBS_FILE):
                    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                        jobs = json.load(f)
                    changed = False
                    for j in jobs:
                        if j.get('url') in match_updates:
                            new_status, user_reason = match_updates[j['url']]
                            j['matches_requirements'] = new_status
                            # Always overwrite user_reason so stale reasons are cleared when no reason is given
                            j['user_reason'] = user_reason
                            changed = True
                    if changed:
                        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                            json.dump(jobs, f, indent=2)
                    print(f"INFO: Successfully synced matches_requirements for {len(match_updates)} jobs from the cloud.")
            except Exception as e:
                print(f"Error syncing match updates: {e}")
        
        # Wipe shared_state since all updates are now safely in jobs.json
        if locals().get('applied_updates') or user_review_updates or match_updates:
            try:
                wipe_url = url.replace('user_feedback', 'shared_state/job_status')
                requests.delete(wipe_url, timeout=10)
                print("INFO: Cleared shared_state temporary queue.")
            except Exception as e:
                print(f"Error clearing shared_state: {e}")

                
    except Exception as e:
        print(f"Error polling Firebase feedback: {e}")

FIRESTORE_BASE = "https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents"


def poll_re_review_request():
    """Check Firebase for a user-triggered re-review request and run it synchronously."""
    doc_url = f"{FIRESTORE_BASE}/shared_state/re_review_request"
    try:
        response = requests.get(doc_url, timeout=10)
        if response.status_code != 200:
            print(f"INFO: poll_re_review: Firestore GET returned {response.status_code} — skipping.")
            return
        data = response.json()
        fields = data.get("fields", {})
        status = fields.get("status", {}).get("stringValue", "")
        print(f"INFO: poll_re_review: status='{status}'")
        if status != "requested":
            return

        print("INFO: " + "=" * 60)
        print("INFO: RE-REVIEW TRIGGERED BY USER (dashboard button)")
        requests.patch(
            f"{doc_url}?updateMask.fieldPaths=status",
            json={"fields": {"status": {"stringValue": "in_progress"}}},
            timeout=10
        )

        by_status = {}
        skip_done = 0
        skip_applied = 0
        eligible = {'yes', 'maybe', 'pending', 'error'}

        if os.path.exists(JOBS_FILE):
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            for job in jobs:
                if job.get('user_review') == 'done':
                    skip_done += 1
                    continue
                if job.get('applied') == 'yes':
                    skip_applied += 1
                    continue
                s = job.get('matches_requirements', '')
                if s in eligible:
                    job['needs_re_review'] = True
                    by_status[s] = by_status.get(s, 0) + 1
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2)

        total = sum(by_status.values())
        scope_parts = [f"{s}={n}" for s, n in sorted(by_status.items())]
        print(f"INFO: Scope     : {' | '.join(scope_parts) if scope_parts else 'nothing to review'} → {total} job(s) queued")
        print(f"INFO: Skipping  : user_review=done ({skip_done})  applied=yes ({skip_applied})")
        print("INFO: " + "=" * 60)

        while not stop_event.is_set():
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            batch = [j for j in jobs if j.get('needs_re_review') == True]
            if not batch:
                break
            review_pending_jobs(specific_urls={j['url'] for j in batch[:15]})

        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        requests.patch(
            f"{doc_url}?updateMask.fieldPaths=status&updateMask.fieldPaths=completedAt",
            json={"fields": {
                "status": {"stringValue": "completed"},
                "completedAt": {"stringValue": completed_at}
            }},
            timeout=10
        )
        print("INFO: " + "=" * 60)
        print(f"INFO: RE-REVIEW COMPLETE at {completed_at}  ({total} job(s) reviewed)")
        print("INFO: " + "=" * 60)
        send_email_notification(
            "Re-review complete — Manju Job Dashboard",
            f"The re-review of matching jobs finished at {completed_at}.\nCheck the dashboard for updated results."
        )
    except Exception as e:
        print(f"Error handling re-review request: {e}")


def main():
    generate_history_from_backups()
    self_heal_dates()
    self_heal_locations()
    parser = argparse.ArgumentParser(description="Job Scraper and Reviewer")
    parser.add_argument("--git-only", action="store_true", help="Only run the Git commit and push step, then exit.")
    parser.add_argument("--review-only", action="store_true", help="Only run the local LLM review step on pending jobs, then exit.")
    parser.add_argument("--scrape-only", action="store_true", help="Only run the scraping step, then exit.")
    parser.add_argument("--max-jobs", type=int, default=200, help="Maximum number of new jobs to fetch in this run (default 200). Use 0 for unlimited.")
    args = parser.parse_args()

    if args.git_only:
        update_git()
        return

    if args.review_only:
        check_requirements_update()
        while True:
            if not os.path.exists(JOBS_FILE):
                break
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            
            pending_urls = [j['url'] for j in jobs if j.get('matches_requirements') == 'pending' or j.get('needs_re_review') == True]
            if not pending_urls:
                print("INFO: No more pending jobs to review.")
                break
                
            batch_urls = pending_urls[:15]
            print(f"\nINFO: Reviewing batch of {len(batch_urls)} pending jobs (Remaining pending: {len(pending_urls)})...")
            review_pending_jobs(specific_urls=set(batch_urls))
            
            clean_blocked_jobs()
            update_git()
            print_job_summary()
            time.sleep(1)
        return

    if args.scrape_only:
        check_requirements_update()
        targets = generate_targets()
        total_targets = len(targets)
        visited_indices = set()
        
        while len(visited_indices) < total_targets:
            checkpoint_idx = 0
            if os.path.exists(CHECKPOINT_FILE):
                try:
                    with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                        checkpoint_idx = json.load(f).get("target_index", 0)
                except Exception:
                    pass
            
            if checkpoint_idx >= total_targets or checkpoint_idx < 0:
                checkpoint_idx = 0
                
            print(f"\nINFO: Scraping batch of up to 15 jobs (Starting target index: {checkpoint_idx}/{total_targets})...")
            new_jobs = scrape_all_jobs(max_jobs=15)
            
            new_checkpoint_idx = 0
            if os.path.exists(CHECKPOINT_FILE):
                try:
                    with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                        new_checkpoint_idx = json.load(f).get("target_index", 0)
                except Exception:
                    pass
            
            if new_checkpoint_idx > checkpoint_idx:
                for i in range(checkpoint_idx, new_checkpoint_idx):
                    visited_indices.add(i)
            else:
                for i in range(checkpoint_idx, total_targets):
                    visited_indices.add(i)
                for i in range(0, new_checkpoint_idx):
                    visited_indices.add(i)
                    
            clean_blocked_jobs()
            update_git()
            
            if not new_jobs and new_checkpoint_idx == checkpoint_idx:
                print("INFO: No progress made, stopping scrape loop.")
                break
                
            time.sleep(1)
        return

    # Self-heal dates and locations before main loop
    self_heal_dates()
    self_heal_locations()

    print("INFO: Scraper script starting execution loop...")
    # Start the background thread to listen for user input
    input_thread = threading.Thread(target=listen_for_input, daemon=True)
    input_thread.start()

    while not stop_event.is_set():
        try:
            poll_firebase_feedback()
        except Exception as e:
            print(f"Error polling firebase: {e}")

        try:
            poll_re_review_request()
        except Exception as e:
            print(f"Error handling re-review request: {e}")

        try:
            check_requirements_update()
        except Exception as e:
            print(f"An error occurred checking requirements: {e}")
            
        # 1. Gather all pending jobs
        pending_jobs = []
        if os.path.exists(JOBS_FILE):
            try:
                with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                    jobs_data = json.load(f)
                    pending_jobs = [j for j in jobs_data if j.get('matches_requirements') == 'pending' or j.get('needs_re_review') == True]
            except Exception as e:
                print(f"Error reading jobs file: {e}")
        
        if pending_jobs:
            # We have pending jobs, flush a batch of them first
            print(f"\nINFO: Flushing pending jobs first. {len(pending_jobs)} pending jobs remaining.")
            batch_urls = [j['url'] for j in pending_jobs[:15]]
            try:
                review_pending_jobs(specific_urls=set(batch_urls))
            except Exception as e:
                print(f"An error occurred during reviewing: {e}")
                
            try:
                clean_blocked_jobs()
                update_git()
            except Exception as e:
                print(f"An error occurred during Git update: {e}")
                
            print_job_summary()
            print("Waiting 5 seconds before moving to scrape new jobs. Press [Enter] or Ctrl+C to stop...")
            
            slept = 0
            while slept < 5 and not stop_event.is_set():
                time.sleep(0.5)
                slept += 0.5
                
            if stop_event.is_set():
                print("Stopping the scraper...")
                break
            continue
            
        quota = 15
        new_jobs = []
        
        try:
            print(f"\nINFO: Scanning for up to {quota} new unseen jobs...")
            new_jobs = scrape_all_jobs(max_jobs=quota)
        except Exception as e:
            print(f"An error occurred during scraping: {e}")
            
        # Collect URLs to review
        urls_to_review = [j['url'] for j in new_jobs]
        
        if urls_to_review:
            print(f"INFO: Reviewing {len(urls_to_review)} jobs in this batch (New: {len(new_jobs)}, Existing Pending: {len(urls_to_review) - len(new_jobs)})")
            try:
                review_pending_jobs(specific_urls=set(urls_to_review))
            except Exception as e:
                print(f"An error occurred during reviewing: {e}")
        else:
            print("INFO: No jobs found to review in this iteration.")
            
        try:
            clean_blocked_jobs()
            update_git()
        except Exception as e:
            print(f"An error occurred during Git update: {e}")
        
        print_job_summary()

        # Determine wait time
        wait_time = 5
        if not new_jobs:
            wait_time = 600
            print(f"\nINFO: No new unseen jobs found in this iteration. Increasing wait time to {wait_time} seconds (10 mins).")
        
        print(f"Waiting {wait_time} seconds before the next run. Press [Enter] or Ctrl+C to stop...")
        
        # This loop waits in small increments so KeyboardInterrupt can be caught immediately on Windows.
        # Also polls Firestore every 15 s so a Re-Review request wakes the scraper immediately.
        slept = 0
        next_firebase_poll = 15.0
        while slept < wait_time and not stop_event.is_set():
            time.sleep(0.5)
            slept += 0.5
            if slept >= next_firebase_poll:
                next_firebase_poll += 15.0
                try:
                    doc_url = f"{FIRESTORE_BASE}/shared_state/re_review_request"
                    resp = requests.get(doc_url, timeout=5)
                    if resp.status_code == 200:
                        status = resp.json().get("fields", {}).get("status", {}).get("stringValue", "")
                        if status == "requested":
                            print("INFO: Re-review request detected during wait — waking up early.")
                            break
                except Exception:
                    pass
            
        if stop_event.is_set():
            print("Stopping the scraper...")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nINFO: Scraper stopped by user (Ctrl+C).")
        stop_event.set()