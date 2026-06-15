import json
import time
import os
import subprocess
import threading
import hashlib
import argparse
from datetime import datetime
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

SEARCH_SITES = [
    {"id": "linkedin_fin", "platform": "linkedin", "url": "https://www.linkedin.com/jobs/search?location=Finland&sortBy=DD"},
    {"id": "linkedin_ww", "platform": "linkedin", "url": "https://www.linkedin.com/jobs/search?location=Worldwide&f_WT=2&sortBy=DD"},
    {"id": "duunitori", "platform": "duunitori", "url": "https://duunitori.fi/tyopaikat?jarjestys=uusimmat"},
    {"id": "indeed", "platform": "indeed", "url": "https://fi.indeed.com/jobs?l=Finland&sort=date"},
    {"id": "oikotie", "platform": "oikotie", "url": "https://tyopaikat.oikotie.fi/tyopaikat?jarjestys=julkaisuaika"},
    {"id": "tyomarkkinatori", "platform": "tyomarkkinatori", "url": "https://tyomarkkinatori.fi/henkiloasiakkaat/tyopaikat?sort=published,desc"},
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
                '/palvelut/', '/hinnat', '/pricing'
            ]):
                continue
            clean_path = href.lower().split('?')[0].rstrip('/')
            if clean_path.endswith('/tyopaikat') or clean_path.endswith('/avoimet-tyopaikat') or clean_path.endswith('/jobs'):
                continue
            title = a.text.strip()
            if 'senior' in title.lower():
                continue
            # Exclude navigation links like "Read more" or "Show all"
            if 5 < len(title) < 100 and not any(skip in title.lower() for skip in ['read more', 'lue lisää', 'katso', 'show all']):
                jobs.append({
                    "title": title.replace('\n', ' ').strip(),
                    "company": "Extract via OpenClaw",
                    "location": "Extract via OpenClaw",
                    "url": urljoin(base_url, href),
                    "visited": "no",
                    "matches_requirements": "pending",
                    "reason": ""
                })
    return jobs

def scrape_all_jobs(max_jobs=200):
    seen_urls = set()
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, 'r') as f:
                seen_urls = set(json.load(f))
        except Exception:
            pass

    checkpoint_idx = 0
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
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
            with open(JOBS_FILE, 'r') as f:
                existing_jobs = json.load(f)
        except Exception:
            pass

    combined_jobs = existing_jobs + all_extracted_jobs

    # Save combined jobs to jobs.json
    with open(JOBS_FILE, 'w') as f:
        json.dump(combined_jobs, f, indent=2)

    # Create a timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_file = os.path.join(backup_dir, f"jobs_backup_{timestamp}.json")
    with open(backup_file, 'w') as f:
        json.dump(combined_jobs, f, indent=2)

    print(f"Total jobs currently in jobs.json: {len(combined_jobs)}")
    print(f"Backup saved to: {backup_file}\n")
        
    # Save updated seen urls history
    with open(SEEN_URLS_FILE, 'w') as f:
        json.dump(list(seen_urls), f)
        
    # Save checkpoint
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({"target_index": current_idx}, f, indent=2)
        
    return all_extracted_jobs

def get_file_hash(filepath):
    if not os.path.exists(filepath):
        return ""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def check_requirements_update():
    """Check if job_requirements.md has changed, and flag jobs for re-evaluation if it has."""
    req_hash = get_file_hash(REQ_FILE)
    if not req_hash:
        return

    checkpoint_data = {}
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                checkpoint_data = json.load(f)
        except Exception:
            pass
    
    saved_hash = checkpoint_data.get("requirements_hash", "")
    if saved_hash and req_hash != saved_hash:
        print("INFO: job_requirements.md has changed! Resetting evaluation status for existing jobs...")
        if os.path.exists(JOBS_FILE):
            with open(JOBS_FILE, 'r') as f:
                jobs = json.load(f)
            for job in jobs:
                job['visited'] = 'no'
                job['matches_requirements'] = 'pending'
                job['reason'] = ''
            with open(JOBS_FILE, 'w') as f:
                json.dump(jobs, f, indent=2)
        
    checkpoint_data["requirements_hash"] = req_hash
    with open(CHECKPOINT_FILE, 'w') as f:
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

def review_pending_jobs(specific_urls=None):
    """Visit URLs of pending jobs, extract description, and evaluate using a local LLM."""
    if not os.path.exists(JOBS_FILE):
        return
        
    with open(JOBS_FILE, 'r') as f:
        jobs = json.load(f)
        
    if specific_urls is not None:
        pending_jobs = [j for j in jobs if j.get('matches_requirements') == 'pending' and j['url'] in specific_urls]
    else:
        pending_jobs = [j for j in jobs if j.get('matches_requirements') == 'pending']
        
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
        page = context.new_page()
        
        for job in pending_jobs:
            if stop_event.is_set():
                break
            print(f"Reviewing: {job['title']} at {job['url']}")
            try:
                page.goto(job['url'], timeout=30000)
                time.sleep(1.5) # Wait for page to render
                
                try:
                    text = page.locator('body').inner_text()
                except Exception:
                    text = ""
                
                posted_date = "N/A"
                deadline = "N/A"

                if not text.strip():
                    match, reason = "error", "Could not extract text from page."
                else:
                    prompt = f"""Evaluate the following job posting against the candidate's requirements.

### Job Requirements:
{requirements_text}

### Job Details:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
URL: {job['url']}

### Job Description:
{text[:15000]}

### Instructions:
Return a JSON object with exactly six keys:
- "match": a string, either "yes" or "no".
- "reason": a short 1-sentence explanation of your decision.
- "posted_date": a string, the date the job was posted formatted strictly as YYYY-MM-DD (e.g. '2026-06-12'). If a relative date like '3 days ago' is mentioned, calculate it relative to today's date (2026-06-15). If not found, return 'N/A'.
- "deadline": a string, the deadline for applying formatted strictly as YYYY-MM-DD (e.g. '2026-06-30'). Ignore any times (e.g. if deadline is 15.6.2026 23:59, return '2026-06-15'). If it is open-ended or 'open until filled', return 'Open until filled'. If not found, return 'N/A'.
- "company": a string, the name of the hiring company (e.g. 'Wolt' or 'N/A' if not found).
- "location": a string, the city and country of the job (e.g. 'Helsinki, Finland' or 'N/A' if not found).

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
                        posted_date = str(result.get("posted_date", "N/A"))
                        deadline = str(result.get("deadline", "N/A"))
                        
                        # Extract company and location from LLM if scraper had placeholder/unknown
                        ai_company = str(result.get("company", "N/A"))
                        ai_location = str(result.get("location", "N/A"))
                        
                        if ai_company != "N/A" and (job.get('company') in ["Extract via OpenClaw", "Unknown", "", None]):
                            job['company'] = ai_company
                        if ai_location != "N/A" and (job.get('location') in ["Extract via OpenClaw", "Unknown", "", None]):
                            job['location'] = ai_location
                            
                        if match not in ["yes", "no"]:
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
            with open(JOBS_FILE, 'w') as f:
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

        # Add updated files
        subprocess.run(["git", "add", "jobs.json", "seen_urls.json", "checkpoint.json", "dashboard.html", "job_descriptions"], cwd=repo_dir, check=True, env=env)
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

def main():
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
            
            pending_urls = [j['url'] for j in jobs if j.get('matches_requirements') == 'pending']
            if not pending_urls:
                print("INFO: No more pending jobs to review.")
                break
                
            batch_urls = pending_urls[:15]
            print(f"\nINFO: Reviewing batch of {len(batch_urls)} pending jobs (Remaining pending: {len(pending_urls)})...")
            review_pending_jobs(specific_urls=set(batch_urls))
            
            update_git()
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
                    with open(CHECKPOINT_FILE, 'r') as f:
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
                    with open(CHECKPOINT_FILE, 'r') as f:
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
                    
            update_git()
            
            if not new_jobs and new_checkpoint_idx == checkpoint_idx:
                print("INFO: No progress made, stopping scrape loop.")
                break
                
            time.sleep(1)
        return

    print("INFO: Scraper script starting execution loop...")
    # Start the background thread to listen for user input
    input_thread = threading.Thread(target=listen_for_input, daemon=True)
    input_thread.start()

    while not stop_event.is_set():
        try:
            check_requirements_update()
        except Exception as e:
            print(f"An error occurred checking requirements: {e}")
            
        quota = 15
        new_jobs = []
        
        try:
            print(f"\nINFO: Scanning for up to {quota} new unseen jobs...")
            new_jobs = scrape_all_jobs(max_jobs=quota)
        except Exception as e:
            print(f"An error occurred during scraping: {e}")
            
        # Collect URLs to review
        urls_to_review = [j['url'] for j in new_jobs]
        
        if len(urls_to_review) < quota:
            remaining_slots = quota - len(urls_to_review)
            try:
                if os.path.exists(JOBS_FILE):
                    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                        current_jobs = json.load(f)
                    
                    already_collected = set(urls_to_review)
                    for j in current_jobs:
                        if j.get('matches_requirements') == 'pending' and j['url'] not in already_collected:
                            urls_to_review.append(j['url'])
                            if len(urls_to_review) >= quota:
                                break
            except Exception as e:
                print(f"An error occurred reading pending jobs for review quota: {e}")
                
        if urls_to_review:
            print(f"INFO: Reviewing {len(urls_to_review)} jobs in this batch (New: {len(new_jobs)}, Existing Pending: {len(urls_to_review) - len(new_jobs)})")
            try:
                review_pending_jobs(specific_urls=set(urls_to_review))
            except Exception as e:
                print(f"An error occurred during reviewing: {e}")
        else:
            print("INFO: No jobs found to review in this iteration.")
            
        try:
            update_git()
        except Exception as e:
            print(f"An error occurred during Git update: {e}")
        
        print("\nWaiting 5 seconds before the next run. Press [Enter] to stop...")
        
        # This will wait for up to 5 seconds.
        if stop_event.wait(timeout=5):
            print("Stopping the scraper...")
            break

if __name__ == "__main__":
    main()