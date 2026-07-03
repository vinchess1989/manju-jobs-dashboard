import json
with open('jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)
for j in jobs:
    if j.get('id') in ['19e049c0', 'aa8961ac', '40143eb6', '5975bdd2']:
        print(f"ID: {j['id']} | Title: {j.get('title')} | Desc: {bool(j.get('description_file'))}")
