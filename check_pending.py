import json
with open('jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)
pending = [j for j in jobs if j.get('matches_requirements') == 'pending']
print(f"Pending jobs: {len(pending)}")
