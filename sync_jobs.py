import requests, json

url = 'https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents/shared_state/job_status'
r = requests.get(url)
data = r.json()
fields = data.get('fields', {})

applied_map = {}
for job_url, job_data in fields.items():
    job_fields = job_data.get('mapValue', {}).get('fields', {})
    if 'applied' in job_fields:
        applied_val = job_fields['applied'].get('stringValue')
        applied_map[job_url] = applied_val

count = len([k for k,v in applied_map.items() if v == 'yes'])
print(f'Found {count} jobs marked as applied=yes in Firebase shared_state.')

with open('jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)

changed = False
for j in jobs:
    if j['url'] in applied_map:
        if j.get('applied') != applied_map[j['url']]:
            j['applied'] = applied_map[j['url']]
            changed = True

if changed:
    with open('jobs.json', 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2)
    print('Updated jobs.json with correct applied statuses.')
else:
    print('No changes needed in jobs.json.')
