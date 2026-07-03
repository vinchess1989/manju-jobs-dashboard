import json
import os

def fix_missing():
    with open('jobs.json', 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    count = 0
    for j in jobs:
        # Check both 'yes' and 'maybe' matches that have no description file
        if j.get('matches_requirements') in ['yes', 'maybe'] and (not j.get('description_file') or j.get('description_file') == 'None'):
            j['visited'] = 'no'
            j['matches_requirements'] = 'pending'
            j['reason'] = ''
            j['description_file'] = None
            j['ai_evaluated'] = 'no'
            count += 1
                
    with open('jobs.json', 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
        
    print(f"Reset {count} error jobs back to pending!")

if __name__ == '__main__':
    fix_missing()
