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
        print(f"Failed to get git date for {job_id}: {e}")
    return datetime.now()

def standardize_date(date_str, ref_date):
    if not date_str: return 'N/A'
    date_str = str(date_str).strip().lower()
    if date_str in ['n/a', 'unknown', 'not specified', 'none', 'null']: return 'N/A'
    if 'open' in date_str: return 'Open until filled'
    if 'jatkuva' in date_str: return 'Open until filled'

    if '-' in date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        parts = date_str.split('-')
        date_str = parts[-1].strip()

    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str

    fi_match = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', date_str)
    if fi_match:
        d, m, y = fi_match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    fi_short = re.match(r'^(\d{1,2})\.(\d{1,2})\.?$', date_str)
    if fi_short:
        d, m = fi_short.groups()
        year = ref_date.year
        return f"{year}-{int(m):02d}-{int(d):02d}"

    if 't' in date_str:
        try:
            d = datetime.fromisoformat(date_str.split('t')[0])
            return d.strftime('%Y-%m-%d')
        except ValueError:
            pass

    if 'tänään' in date_str or 'today' in date_str:
        return ref_date.strftime("%Y-%m-%d")

    if 'eilen' in date_str or 'yesterday' in date_str:
        return (ref_date - timedelta(days=1)).strftime("%Y-%m-%d")

    rel_match = re.search(r'(\d+)\s+(day|päivä|viikko|week|month|kuukaus|hour|tunti|min)', date_str)
    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit in ['day', 'päivä']:
            d = ref_date - timedelta(days=val)
        elif unit in ['viikko', 'week']:
            d = ref_date - timedelta(weeks=val)
        elif unit in ['month', 'kuukaus']:
            d = ref_date - timedelta(days=val * 30)
        else:
            d = ref_date
        return d.strftime("%Y-%m-%d")

    short_rel = re.search(r'(\d+)\s*(d|w|m)\s+ago', date_str)
    if short_rel:
        val = int(short_rel.group(1))
        unit = short_rel.group(2)
        if unit == 'd':
            d = ref_date - timedelta(days=val)
        elif unit == 'w':
            d = ref_date - timedelta(weeks=val)
        elif unit == 'm':
            d = ref_date - timedelta(days=val * 30)
        return d.strftime("%Y-%m-%d")

    return date_str

def fix_jobs(folder):
    jobs_file = os.path.join(folder, 'jobs.json')
    if not os.path.exists(jobs_file): return
    with open(jobs_file, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    jobs_to_process = [j for j in jobs if j.get('matches_requirements') in ['yes', 'maybe'] and j.get('description_file')]
    print(f"[{folder}] Processing {len(jobs_to_process)} jobs...")

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

            title = job.get('title', '').lower()
            title_pos = raw_text.find(title)
            if title_pos != -1:
                search_text = raw_text[title_pos:]
            else:
                search_text = raw_text

            patterns = [
                r'(\d+\s+(?:day|päivä|viikko|week|month|kuukaus|hour|tunti|min)s?\s+ago)',
                r'(\d+\s*[dwm]\s*ago)',
                r'\b(today|tänään|yesterday|eilen)\b',
                r'posted:\s*(\d{4}-\d{2}-\d{2})',
                r'posted\s*(\d+\s+(?:day|päivä|viikko|week|month|kuukaus)s?\s+ago)'
            ]
            
            found_date_str = None
            for p in patterns:
                m = re.search(p, search_text)
                if m:
                    found_date_str = m.group(1)
                    break
            
            if found_date_str:
                new_date = standardize_date(found_date_str, ref_date)
                if new_date and new_date != job.get('posted_date'):
                    new_content = re.sub(r'Posted: .*\n', f'Posted: {new_date}\n', content)
                    with open(desc_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    print(f"[{folder}] Updated {job['id']}: {job.get('posted_date')} -> {new_date} (found '{found_date_str}' rel to {ref_date.strftime('%Y-%m-%d')})")
                    job['posted_date'] = new_date
                    updated += 1

    if updated > 0:
        with open(jobs_file, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        print(f"[{folder}] Updated {updated} jobs in jobs.json")

if __name__ == '__main__':
    fix_jobs(r'c:\Users\vinee\manju_jobs')
    fix_jobs(r'c:\Users\vinee\vineeth_jobs')
