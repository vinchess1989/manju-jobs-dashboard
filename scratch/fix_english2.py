import json

jobs_path = 'jobs.json'
with open(jobs_path, 'r', encoding='utf-8') as f:
    jobs = json.load(f)

count = 0
for job in jobs:
    if job.get('matches_requirements') == 'no':
        reason = str(job.get('ai_reason', '')).lower()
        title = str(job.get('job_title', '')).lower()
        company = str(job.get('company', '')).lower()
        
        if any(keyword in reason or keyword in title or keyword in company for keyword in ['english', 'englanti', 'englannin', 'mindrift', 'sme careers']):
            job['matches_requirements'] = 'pending'
            job['needs_re_review'] = True
            count += 1

with open(jobs_path, 'w', encoding='utf-8') as f:
    json.dump(jobs, f, indent=2, ensure_ascii=False)

print(f'Reset {count} jobs requiring English expertise to pending.')
