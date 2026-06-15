import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")

def main():
    if not os.path.exists(JOBS_FILE):
        print("ERROR: jobs.json not found.")
        return

    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    cleaned_jobs = []
    removed_count = 0

    # Define patterns that identify a listing/search/bookmark page rather than a single job post
    bad_patterns = [
        '?search=',
        '?haku=',
        '/tyopaikat/',
        '/job-bookmarks-anon',
        'destination=search',
        '?jarjestys=',
        'tyopaikat.oikotie.fi/tyopaikat',
        'duunitori.fi/tyopaikat',
        'indeed.com/jobs'
    ]

    for job in jobs:
        url = job.get('url', '').lower()
        is_bad = False
        
        # Check if the URL matches any bad patterns
        for pattern in bad_patterns:
            if pattern in url:
                is_bad = True
                break
                
        # Also double check title anomalies (e.g. category filter links like "Uusimaa (20)")
        title = job.get('title', '')
        if '(' in title and ')' in title and any(char.isdigit() for char in title):
            # Titles like "Etätyö (10)", "Uusimaa (20)", "Vakituinen (22)" are listing indicators
            is_bad = True

        if is_bad:
            removed_count += 1
            # Delete description file if it exists
            desc_file = job.get('description_file')
            if desc_file:
                desc_path = os.path.join(BASE_DIR, desc_file)
                if os.path.exists(desc_path):
                    try:
                        os.remove(desc_path)
                        print(f"Removed description file: {desc_file}")
                    except Exception as e:
                        print(f"Error removing {desc_file}: {e}")
        else:
            cleaned_jobs.append(job)

    if removed_count > 0:
        print(f"SUCCESS: Removed {removed_count} listing/search/bookmark pages from jobs.json.")
        with open(JOBS_FILE, 'w', encoding='utf-8') as f_out:
            json.dump(cleaned_jobs, f_out, indent=2)
    else:
        print("INFO: No bad listing/search pages found in jobs.json.")

if __name__ == "__main__":
    main()
