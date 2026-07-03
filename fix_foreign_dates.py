import json
import os
import re
import subprocess
from datetime import datetime, timedelta

def get_original_scrape_date(folder, job_id):
    try:
        cmd = ['git', 'log', '-S', job_id, '--format=%cd', '--date=short', '--reverse', 'jobs.json']
        result = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
        lines = result.stdout.strip().split('\n')
        if lines and lines[0]:
            return datetime.strptime(lines[0], '%Y-%m-%d')
    except Exception as e:
        pass
    return datetime.now()

def standardize_foreign_date(val, unit_str, ref_date):
    unit = unit_str.lower()
    # Days
    if unit in ['dia', 'dias', 'día', 'días', 'jour', 'jours', 'tag', 'tagen']:
        d = ref_date - timedelta(days=val)
    # Weeks
    elif unit in ['semana', 'semanas', 'semaine', 'semaines', 'woche', 'wochen']:
        d = ref_date - timedelta(weeks=val)
    # Months
    elif unit in ['mês', 'mes', 'meses', 'mois', 'monat', 'monaten']:
        d = ref_date - timedelta(days=val * 30)
    # Hours (same day)
    elif unit in ['hora', 'horas', 'heure', 'heures', 'stunde', 'stunden']:
        d = ref_date
    else:
        d = ref_date
    return d.strftime("%Y-%m-%d")

def fix_foreign_jobs(folder):
    jobs_file = os.path.join(folder, 'jobs.json')
    if not os.path.exists(jobs_file): return
    with open(jobs_file, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    # Only process jobs that still have today's date (or ones we missed)
    jobs_to_process = [j for j in jobs if j.get('matches_requirements') in ['yes', 'maybe'] and j.get('description_file')]
    print(f"[{folder}] Checking {len(jobs_to_process)} jobs for foreign dates...")

    updated = 0
    for job in jobs_to_process:
        desc_file = os.path.join(folder, job.get('description_file'))
        if not os.path.exists(desc_file): continue
        
        ref_date = get_original_scrape_date(folder, job['id'])

        with open(desc_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        parts = content.split('JOB DESCRIPTION:\n========================================')
        if len(parts) > 1:
            raw_text = parts[1][:1500].lower()

            patterns = [
                r'h[áa]\s+(\d+)\s+(hora|dia|d[íi]a|semana|m[êe]s|meses|ano)s?', # Portuguese/Spanish
                r'hace\s+(\d+)\s+(hora|d[íi]a|semana|mes|a[ñn]o)s?', # Spanish
                r'il\s+y\s+a\s+(\d+)\s+(heure|jour|semaine|mois|an)s?', # French
                r'vor\s+(\d+)\s+(stunde|tag|woche|monat|jahr)(?:en|n|e)?' # German
            ]
            
            found_val = None
            found_unit = None
            found_str = None
            for p in patterns:
                m = re.search(p, raw_text)
                if m:
                    found_val = int(m.group(1))
                    found_unit = m.group(2)
                    found_str = m.group(0)
                    break
            
            if found_val is not None:
                new_date = standardize_foreign_date(found_val, found_unit, ref_date)
                if new_date and new_date != job.get('posted_date'):
                    new_content = re.sub(r'Posted: .*\n', f'Posted: {new_date}\n', content)
                    with open(desc_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    print(f"[{folder}] Updated {job['id']}: {job.get('posted_date')} -> {new_date} (found '{found_str}' rel to {ref_date.strftime('%Y-%m-%d')})")
                    job['posted_date'] = new_date
                    updated += 1

    if updated > 0:
        with open(jobs_file, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        print(f"[{folder}] Updated {updated} jobs in jobs.json")

if __name__ == '__main__':
    fix_foreign_jobs(r'c:\Users\vinee\manju_jobs')
    fix_foreign_jobs(r'c:\Users\vinee\vineeth_jobs')
