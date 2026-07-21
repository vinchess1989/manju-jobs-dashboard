import json
import os
import re
from pathlib import Path

# 1. Update job_requirements.md
req_path = 'job_requirements.md'
with open(req_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace language line
old_lang = r'\* \*\*Languages:\*\* English \(C1 \/ Native-level\), Finnish \(B2 . Intermediate, actively improving\), Malayalam \(Native\).'
new_lang = '* **Languages:** English (C2 / Expert-level - won gold medal in essay competitions), Finnish (B2 – Intermediate, actively improving), Malayalam (Native).'
content = re.sub(old_lang, new_lang, content)

# Add explicit english note
if 'English Expertise' not in content:
    english_note = '\n* **English Expertise:** The candidate is an expert in the English language (highest level/C2) and has won a gold medal in essay competitions. Any roles requiring strong written English, English language expertise, or AI training for English should NOT be rejected based on language.'
    content = content.replace('**Language note:** Manju\'s Finnish is B2 (Intermediate). Roles requiring fluent Finnish (C1+) as a hard requirement should be marked "no". Roles where Finnish is preferred but not mandatory, or where English is the working language, are fine to match.', 
                            '**Language note:** Manju\'s Finnish is B2 (Intermediate). Roles requiring fluent Finnish (C1+) as a hard requirement should be marked "no". Roles where Finnish is preferred but not mandatory, or where English is the working language, are fine to match.' + english_note)

with open(req_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated job_requirements.md')

# 2. Reset jobs in jobs.json
jobs_path = 'jobs.json'
with open(jobs_path, 'r', encoding='utf-8') as f:
    jobs = json.load(f)

count = 0
for job in jobs:
    reason = job.get('ai_reason', '').lower()
    if 'english' in reason or 'englanti' in reason or 'englannin' in reason or 'mindrift' in reason or 'sme careers' in reason:
        if job.get('matches_requirements') == 'no':
            job['matches_requirements'] = 'pending'
            job['needs_re_review'] = True
            count += 1

with open(jobs_path, 'w', encoding='utf-8') as f:
    json.dump(jobs, f, indent=2, ensure_ascii=False)

print(f'Reset {count} jobs requiring English expertise to pending.')

# 3. Update tailoring scripts
scripts_to_update = ['tailor_with_local_llm.py', 'scratch/tailor_with_gemini.py', 'scratch/manage_tailor_queue.py']
for script_path in scripts_to_update:
    if not os.path.exists(script_path): continue
    with open(script_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Replace the exact template path
    code = code.replace('os.path.join(OUT_DIR, "f6aaa66f", "f6aaa66f_data.json")', 'os.path.join(PRIVATE_DIR, "Resumes", "Master", "master_data.json")')
    code = code.replace('os.path.join(RESUMES_DIR, "f6aaa66f", "f6aaa66f_data.json")', 'os.path.join(PRIVATE_DIR, "Resumes", "Master", "master_data.json")')
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print(f'Updated {script_path}')

