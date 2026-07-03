import json
with open(r'C:\Users\vinee\Manju_jobs_private\Resumes\f6aaa66f\f6aaa66f_data.json', 'r', encoding='utf-8') as f:
    template_data = json.load(f)
template_str = json.dumps(template_data, indent=2)
comp_name = 'EXL'
job_title = 'Executive Assistant'
template_str = template_str.replace("Hiab's Legal and Compliance team", f"{comp_name}'s team")
template_str = template_str.replace("Hiab", comp_name)
template_str = template_str.replace("Legal Trainee", job_title)
print('Hiab' in template_str)

