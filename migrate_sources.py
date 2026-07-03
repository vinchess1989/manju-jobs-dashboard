import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")

def get_source_from_url(url):
    if not url:
        return "unknown"
    l_url = url.toLowerCase() if hasattr(url, 'toLowerCase') else url.lower()
    
    if "linkedin.com" in l_url:
        return "linkedin"
    if "duunitori.fi" in l_url:
        return "duunitori"
    if "indeed.com" in l_url:
        return "indeed"
    if "oikotie.fi" in l_url:
        return "oikotie"
    if "tyomarkkinatori.fi" in l_url:
        return "tyomarkkinatori"
    if "jobly.fi" in l_url:
        return "jobly"
    if "meetfrank.com" in l_url:
        return "meetfrank"
    if "hub.no" in l_url:
        return "hub"
        
    try:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname
        if hostname:
            return hostname.replace("www.", "")
    except Exception:
        pass
        
    return "unknown"

def main():
    if not os.path.exists(JOBS_FILE):
        print(f"Error: {JOBS_FILE} does not exist.")
        return
        
    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
        
    updated_count = 0
    for job in jobs:
        if "source" not in job or not job["source"]:
            job["source"] = get_source_from_url(job.get("url", ""))
            updated_count += 1
            
    if updated_count > 0:
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2)
        print(f"Successfully migrated {updated_count} jobs with source field.")
    else:
        print("No jobs needed migration.")

if __name__ == "__main__":
    main()
