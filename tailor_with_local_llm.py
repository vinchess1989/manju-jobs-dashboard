import os
import sys
import json
import re
import requests
import random
import time

# Manual dotenv loading to avoid external dependency
def load_env_manual():
    env_path = os.path.join(PUBLIC_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

PUBLIC_DIR = r"C:\Users\vinee\manju_jobs"
load_env_manual()
PRIVATE_DIR = r"C:\Users\vinee\Manju_jobs_private"
DESC_DIR = os.path.join(PUBLIC_DIR, "job_descriptions")
OUT_DIR = os.path.join(PRIVATE_DIR, "Resumes")
SAMPLES_DIR = os.path.join(PUBLIC_DIR, "samples_for_review")
TEMPLATE_PATH = os.path.join(OUT_DIR, "f6aaa66f", "f6aaa66f_data.json")

# Local LLM configuration from environment (with defaults)
LLM_ENDPOINT = os.environ.get("LOCAL_LLM_ENDPOINT", "http://localhost:11434/v1/chat/completions")

def get_active_model(endpoint):
    """Query /v1/models to dynamically find the active loaded model."""
    try:
        base_url = endpoint.rsplit("/chat/completions", 1)[0]
        models_url = f"{base_url}/models"
        resp = requests.get(models_url, timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            chat_models = [m["id"] for m in models if "embed" not in m["id"].lower()]
            if chat_models:
                return chat_models[0]
            elif models:
                return models[0]["id"]
    except Exception as e:
        print(f"Warning: Could not fetch active model from {endpoint}: {e}")
    return os.environ.get("LOCAL_LLM_MODEL", "llama3")

LLM_MODEL = get_active_model(LLM_ENDPOINT)
print(f"Dynamically selected active tailoring model: {LLM_MODEL}")
LLM_API_KEY = os.environ.get("LOCAL_LLM_API_KEY", "")

# Manju's profile details
MANJU_PROFILE_RAW = """
- LL.M. Business & Corporate Law, First Rank — Symbiosis International University (2020–21)
- LL.B. First Class Honours, Top 3 — University of Calicut (2009–14)
- Finnish Supplementary Law Studies (OPH bar path) — University of Lapland (2025–present)
- Kohti Yliopistoa — University of Oulu (2025–26)
- Language placement: Asianajajatoimisto Regelin Oy, Oulu (Apr–Jun 2026)
- Intern: International House Oulu — 14 events, OuluBot (Jan–Apr 2025, Sep–Oct 2024)
- Legal Associate: Poise Legal India (Oct 2021–May 2022) — 5–7 contracts/month
- Junior Lawyer: Juris Nexus India (Sep 2015–Jan 2016) — family & civil law
- Finnish B2, English C1, Malayalam native. Based in Oulu. Available Sep 2026.
"""

def extract_json(text):
    """Clean markdown code block wrappers from response and parse JSON."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse valid JSON from response: {text[:500]}...")

def get_job_info(job_id):
    """Find job info in jobs.json, valid_jobs.json, or curated_jobs.json."""
    for fn in ["jobs.json", "valid_jobs.json", "curated_jobs.json"]:
        path = os.path.join(PUBLIC_DIR, fn)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                jobs = json.load(f)
                for j in jobs:
                    if j.get("id", j.get("job_id")) == job_id:
                        return j
    return None

def read_job_description(job_desc_link):
    """Read the scraped job description text."""
    if not job_desc_link:
        return ""
    path = os.path.join(PUBLIC_DIR, job_desc_link)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def tailor_job(job_id):
    job = get_job_info(job_id)
    if not job:
        print(f"ERROR: Job ID {job_id} not found in lists.")
        return False
        
    desc_text = job.get("description")
    if not desc_text:
        desc_link = job.get("description_link", job.get("description_file"))
        if desc_link:
            desc_text = read_job_description(desc_link)
            
    if not desc_text:
        print(f"ERROR: No description found for Job ID {job_id}.")
        return False
        
    print(f"Tailoring resume for: {job.get('title')} at {job['company']} (ID: {job_id})")
    
    # Determine job language by checking for Finnish-specific letters (ä, ö) or relative counts of common words
    english_common = ["the", "and", "to", "of", "in", "for", "with", "on", "our", "your", "experience", "skills", "company"]
    finnish_common = ["ja", "on", "että", "se", "joka", "mukana", "oleva", "kanssa", "työ", "tehtävä", "hakemus", "edellytämme", "tarjoamme", "osaamista", "työkokemusta", "tai"]
    
    en_count = sum(len(re.findall(rf"\b{w}\b", desc_text.lower())) for w in english_common)
    fi_count = sum(len(re.findall(rf"\b{w}\b", desc_text.lower())) for w in finnish_common)
    
    # Check for specific Finnish characters ä (code point 228 or \u00e4) and ö (code point 246 or \u00f6)
    has_fi_chars = "\u00e4" in desc_text.lower() or "\u00f6" in desc_text.lower()
    
    # Classify as Finnish if Finnish words are significantly present, or if FI chars are present AND FI words aren't drowned out by EN words
    is_finnish = (fi_count > (en_count * 0.2)) or (has_fi_chars and fi_count > 2 and fi_count > (en_count * 0.05))
    lang_label = "Finnish" if is_finnish else "English"
    print(f"Detected job posting language: {lang_label} (EN common: {en_count}, FI common: {fi_count}, has_fi_chars: {has_fi_chars})")
    
    # Load structural template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template_data = json.load(f)
        
    # Sanitize the template string to absolutely prevent leakage
    comp_name = job.get('company', 'Company')
    job_title = job.get('title', 'Role')
    template_str = json.dumps(template_data, indent=2)
    template_str = template_str.replace("Hiab's Legal and Compliance team", f"{comp_name}'s team")
    template_str = template_str.replace("Hiab", comp_name)
    template_str = template_str.replace("Legal Trainee", job_title)
    
    sign_off_str = "Yst\u00e4v\u00e4llisin terveisin" if lang_label == 'Finnish' else "Yours sincerely"
    
    system_prompt = f"""You are an elite, professional executive resume writer. Your task is to tailor a resume and write a cover letter based on the provided candidate profile, job description, and a JSON template.

CRITICAL LANGUAGE & TRANSLATION RULES:
1. Cover Letter Language: The job description language is determined as: {lang_label}. 
   - If {lang_label} is Finnish, the ENTIRE cover letter (recipient team/title/city, paragraphs, and sign_off) MUST be written in natural, fluent, grammatically correct Finnish. 
   - If {lang_label} is English, the ENTIRE cover letter MUST be written in fluent, professional English.
2. Sign Off Language:
   - The "sign_off" key MUST be exactly "{sign_off_str}".
3. Resume Profile & Resume content:
   - The candidate's resume (profile, experiences, education, competencies) MUST ALWAYS be in English.

Instructions for tailoring each section:
1. Match the exact structure and keys of the template JSON.
2. The output MUST be a single raw JSON object only. No preamble, no explanation.
3. "job_id": Use "{job_id}".
4. "job_title": Use "{job_title}".
5. "company": Use "{comp_name}".
6. "resume" -> "role": Set to "{job_title} Candidate".
7. "resume" -> "profile": 2-3 sentences in English. Make this HIGHLY tailored to "{job_title}" and "{comp_name}".
8. "resume" -> "experience": Keep all entries, REORDER them so the most relevant experience for this specific job appears FIRST. Rewrite bullets to highlight the exact skills needed. Keep the dates and company names exactly as they are.
9. "resume" -> "languages_html": If {lang_label} is Finnish, put Finnish first:
   "<span class=\\"skill-cat\\">Finnish</span> B2 (professional working proficiency) &nbsp;|&nbsp; <span class=\\"skill-cat\\">English</span> C1 / Fluent &nbsp;|&nbsp; <span class=\\"skill-cat\\">Malayalam</span> Native<br>..."
   Otherwise, keep English first.
10. "resume" -> "competencies_html": Rewrite these HTML competencies to match the key requirements in the Job Description. Use '<span class=\\"skill-cat\\">Category:</span> description...' format.
11. "cover_letter":
   - Date: Use "23 June 2026".
   - Recipient: Update recipient company to "{comp_name}" and recipient city to "{job.get('location', '')}".
   - Write 4-5 highly persuasive paragraphs in the correct language ({lang_label}).

Ensure the final JSON is completely valid, has escaped double-quotes in HTML fields, and matches the template structure. Output only the JSON. Do not include any text, notes or markdown wrapper outside of the JSON block."""

    user_prompt = f"""Candidate Profile:
{MANJU_PROFILE_RAW}

Job Description:
{desc_text}

JSON Structural Template (fill this structure exactly):
{template_str}"""

    # Call local LLM
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
        
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4000
    }
    
    try:
        print(f"Sending request to local LLM ({LLM_MODEL}) at {LLM_ENDPOINT}...")
        response = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        res_json = response.json()
        response_text = res_json['choices'][0]['message']['content'].strip()
        
        # Parse JSON
        tailored_data = extract_json(response_text)
        
        # Sanity Check for data leakage
        resume_html = str(tailored_data).lower()
        if "hiab" in resume_html and "hiab" not in comp_name.lower():
            raise ValueError("Sanity Check Failed: Output contained leaked 'Hiab' data.")
        if "legal trainee" in resume_html and "legal trainee" not in job_title.lower():
            raise ValueError("Sanity Check Failed: Output contained leaked 'Legal Trainee' data.")
        
        # Inject the tailoring model for transparency
        tailored_data['tailor_model'] = LLM_MODEL
        # Enforce correct job ID (LLM sometimes copies the template's ID)
        tailored_data['job_id'] = job_id
        
        # Save output file
        job_dir = os.path.join(OUT_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        out_path = os.path.join(job_dir, f"{job_id}_data.json")
        with open(out_path, "w", encoding="utf-8") as f_out:
            json.dump(tailored_data, f_out, indent=2, ensure_ascii=False)
            
        # Dynamically update jobs.json with tailor_model
        jobs_json_path = os.path.join(os.path.dirname(__file__), 'jobs.json')
        if os.path.exists(jobs_json_path):
            with open(jobs_json_path, 'r', encoding='utf-8') as f:
                all_jobs = json.load(f)
            updated = False
            for j in all_jobs:
                if j.get('id') == job_id:
                    j['tailor_model'] = "Local LLM"
                    updated = True
                    break
            if updated:
                with open(jobs_json_path, 'w', encoding='utf-8') as f:
                    json.dump(all_jobs, f, indent=2, ensure_ascii=False)
            
        # Print a detailed summary for the orchestrator log
        resume_title = tailored_data.get('job_title', tailored_data.get('title', 'Unknown Title'))
        cl_data = tailored_data.get('cover_letter', {})
        sign_off = cl_data.get('sign_off', '')
        lang_label = "Finnish" if "ystävällisin" in sign_off.lower() else "English"
        paragraphs = cl_data.get('paragraphs', [])
        cover_letter_len = sum(len(p) for p in paragraphs) if isinstance(paragraphs, list) else 0
        print(f"SUCCESS: Tailored resume for '{resume_title}' ({lang_label}). Cover letter length: {cover_letter_len} chars. Saved to {out_path}")
        # 10% SAMPLING LOGIC FOR PROMPT IMPROVEMENT
        if random.random() < 0.1:
            os.makedirs(SAMPLES_DIR, exist_ok=True)
            sample_data = {
                "job_id": job_id,
                "type": "tailoring",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "job_title": job.get('job_title'),
                "prompt_used": system_prompt + "\n\n" + user_prompt,
                "llm_raw_response": response_text,
                "parsed_output": tailored_data
            }
            sample_file = os.path.join(SAMPLES_DIR, f"sample_tailor_{job_id}_{int(time.time())}.json")
            with open(sample_file, "w", encoding="utf-8") as sf:
                json.dump(sample_data, sf, indent=2, ensure_ascii=False)
            print(f"  [SAMPLING] Saved tailoring sample for review.")
            
        return True
        
    except requests.exceptions.RequestException as e:
        error_msg = f"ERROR: Failed to run local LLM tailoring: {e}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"\nResponse text: {e.response.text}"
        print(error_msg)
        return False

if __name__ == "__main__":
    import sys
    # Force stdout to utf-8 to avoid cp1252 charmap errors
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2:
        print("Usage: python tailor_with_local_llm.py <job_id>")
        sys.exit(1)
    try:
        tailor_job(sys.argv[1])
    except Exception as e:
        print(f"ERROR: Unhandled exception processing {sys.argv[1]}: {e}")
        # Don't exit with code 1 so the pipeline continues
