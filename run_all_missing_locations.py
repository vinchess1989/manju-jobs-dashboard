import os
import json
import scraper

JOBS_FILE = "jobs.json"

def main():
    if not os.path.exists(JOBS_FILE):
        print("jobs.json not found")
        return
        
    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    missing_locs = [
        'Extract via OpenClaw', 'Unknown', 'N/A', '', 'None', 
        'Extract via Openclaw', 'extract via openclaw', 'n/a', None,
        'Finland', 'finland'
    ]
    
    urls_to_review = []
    
    # 1. Flag all missing location jobs to pending
    for j in jobs:
        if j.get('location') in missing_locs or not j.get('location'):
            j['visited'] = 'no'
            j['matches_requirements'] = 'pending'
            j['reason'] = ''
            urls_to_review.append(j['url'])
            
    print(f"Found {len(urls_to_review)} jobs missing a location.")
    
    # Save the pending statuses
    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2)
        
    if not urls_to_review:
        print("Nothing to review.")
        return
        
    # 2. Review all of them in a single batch
    print(f"Starting review of all {len(urls_to_review)} jobs in a single shot...")
    try:
        scraper.review_pending_jobs(specific_urls=set(urls_to_review))
    except Exception as e:
        print(f"Error during review: {e}")
        
    # 3. Clean blocked jobs
    print("Cleaning blocked jobs...")
    scraper.clean_blocked_jobs()
    
    # 4. Update git at the very end
    print("Pushing all changes to Git...")
    scraper.update_git()
    
    print("Done!")

if __name__ == "__main__":
    main()
