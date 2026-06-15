import os
import json
import time
import hashlib
import re
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")
DESC_DIR = os.path.join(BASE_DIR, "job_descriptions")
os.makedirs(DESC_DIR, exist_ok=True)

def main():
    if not os.path.exists(JOBS_FILE):
        print("ERROR: jobs.json not found.")
        return

    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    # Find jobs that matched requirements but don't have description_file set or file doesn't exist
    matched_jobs = []
    for job in jobs:
        if job.get('matches_requirements') == 'yes':
            desc_file = job.get('description_file')
            if not desc_file or not os.path.exists(os.path.join(BASE_DIR, desc_file)):
                matched_jobs.append(job)

    if not matched_jobs:
        print("INFO: No matched jobs are missing descriptions.")
        return

    print(f"INFO: Found {len(matched_jobs)} matched jobs missing descriptions. Starting extraction...")

    with sync_playwright() as p:
        print("Launching Playwright browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for idx, job in enumerate(matched_jobs):
            print(f"[{idx+1}/{len(matched_jobs)}] Fetching description for: {job['title']} at {job['company']}")
            try:
                page.goto(job['url'], timeout=30000)
                time.sleep(1.5) # Wait for page to render

                try:
                    text = page.locator('body').inner_text()
                except Exception:
                    text = ""

                if not text.strip():
                    print("  -> ERROR: Could not extract text from page.")
                    continue

                clean_title = re.sub(r'[^a-zA-Z0-9]', '_', job['title'].lower())[:30]
                clean_company = re.sub(r'[^a-zA-Z0-9]', '_', job['company'].lower())[:20]
                url_hash = hashlib.md5(job['url'].encode('utf-8')).hexdigest()[:8]
                desc_filename = f"{clean_company}_{clean_title}_{url_hash}.txt"
                desc_path = os.path.join(DESC_DIR, desc_filename)

                with open(desc_path, 'w', encoding='utf-8') as f_desc:
                    f_desc.write(f"Title: {job['title']}\n")
                    f_desc.write(f"Company: {job['company']}\n")
                    f_desc.write(f"Location: {job['location']}\n")
                    f_desc.write(f"URL: {job['url']}\n")
                    f_desc.write(f"Posted: {job.get('posted_date', 'N/A')}\n")
                    f_desc.write(f"Deadline: {job.get('deadline', 'N/A')}\n")
                    f_desc.write(f"Reason: {job.get('reason', '')}\n")
                    f_desc.write("\n" + "="*40 + "\n")
                    f_desc.write("JOB DESCRIPTION:\n")
                    f_desc.write("="*40 + "\n\n")
                    f_desc.write(text)

                job['description_file'] = f"job_descriptions/{desc_filename}"
                print(f"  -> SUCCESS: Saved to {job['description_file']}")

                # Save jobs.json in-place after each success
                with open(JOBS_FILE, 'w', encoding='utf-8') as f_out:
                    json.dump(jobs, f_out, indent=2)

            except Exception as e:
                print(f"  -> ERROR: Failed to fetch ({e})")

        browser.close()
    print("INFO: Completed description extraction for matched jobs.")

if __name__ == "__main__":
    main()
