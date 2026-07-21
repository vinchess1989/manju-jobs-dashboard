import os
import sys
import json
import re
import time
import random
import google.generativeai as genai

PUBLIC_DIR = r"C:\Users\vinee\manju_jobs"
PRIVATE_DIR = r"C:\Users\vinee\Manju_jobs_private"
DESC_DIR = os.path.join(PUBLIC_DIR, "job_descriptions")
OUT_DIR = os.path.join(PRIVATE_DIR, "Resumes")
SAMPLES_DIR = os.path.join(PUBLIC_DIR, "samples_for_review")
TEMPLATE_PATH = os.path.join(PRIVATE_DIR, "Resumes", "Master", "master_data.json")

# Configure Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable not found.")
    sys.exit(1)

genai.configure(api_key=API_KEY)
LLM_MODEL = "gemini-2.5-flash"

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
    
    # Determine language
    english_common = ["the", "and", "to", "of", "in", "for", "with", "on", "our", "your", "experience", "skills", "company"]
    finnish_common = ["ja", "on", "että", "se", "joka", "mukana", "oleva", "kanssa", "työ", "tehtävä", "hakemus", "edellytämme", "tarjoamme", "osaamista", "työkokemusta", "tai"]
    
    en_count = sum(len(re.findall(rf"\b{w}\b", desc_text.lower())) for w in english_common)
    fi_count = sum(len(re.findall(rf"\b{w}\b", desc_text.lower())) for w in finnish_common)
    has_fi_chars = "\u00e4" in desc_text.lower() or "\u00f6" in desc_text.lower()
    is_finnish = (fi_count > (en_count * 0.2)) or (has_fi_chars and fi_count > 2 and fi_count > (en_count * 0.05))
    lang_label = "Finnish" if is_finnish else "English"
    
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template_data = json.load(f)
        
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
   - The candidate's resume MUST ALWAYS be in English.

Instructions for tailoring each section:
1. Match the exact structure and keys of the template JSON.
2. The output MUST be a single raw JSON object only. No preamble, no markdown wrapper!
3. "job_id": Use "{job_id}".
4. "job_title": Use "{job_title}".
5. "company": Use "{comp_name}".
6. "resume" -> "role": Set to "{job_title} Candidate".
7. "resume" -> "profile": 2-3 sentences in English. Make this HIGHLY tailored to "{job_title}" and "{comp_name}".
8. "resume" -> "experience": Keep all entries, REORDER them so the most relevant experience appears FIRST. Rewrite bullets to highlight exact skills.
9. "resume" -> "languages_html": If {lang_label} is Finnish, put Finnish first. Otherwise, keep English first.
10. "resume" -> "competencies_html": Rewrite these HTML competencies to match the key requirements.
11. "cover_letter":
   - Date: Use current date.
   - Recipient: Update recipient company to "{comp_name}" and city to "{job.get('location', '')}".
   - Write 4-5 highly persuasive paragraphs in the correct language ({lang_label}).

Ensure the final JSON is valid and matches the template structure. OUTPUT ONLY JSON."""

    user_prompt = f"""Candidate Profile:
{MANJU_PROFILE_RAW}

Job Description:
{desc_text}

JSON Structural Template (fill this structure exactly):
{template_str}"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(
                model_name=LLM_MODEL,
                system_instruction=system_prompt,
                generation_config={"temperature": 0.2, "response_mime_type": "application/json"}
            )
            print(f"Sending request to Gemini API ({LLM_MODEL})...")
            response = model.generate_content(user_prompt)
            response_text = response.text.strip()
            
            tailored_data = extract_json(response_text)
            
            # Sanity Check
            resume_html = str(tailored_data).lower()
            if "hiab" in resume_html and "hiab" not in comp_name.lower():
                raise ValueError("Sanity Check Failed: Output contained leaked 'Hiab' data.")
                
            tailored_data['tailor_model'] = LLM_MODEL
            tailored_data['job_id'] = job_id
            
            job_dir = os.path.join(OUT_DIR, job_id)
            os.makedirs(job_dir, exist_ok=True)
            out_path = os.path.join(job_dir, f"{job_id}_data.json")
            with open(out_path, "w", encoding="utf-8") as f_out:
                json.dump(tailored_data, f_out, indent=2, ensure_ascii=False)
                
            # Update jobs.json
            jobs_json_path = os.path.join(PUBLIC_DIR, 'jobs.json')
            if os.path.exists(jobs_json_path):
                with open(jobs_json_path, 'r', encoding='utf-8') as f:
                    all_jobs = json.load(f)
                updated = False
                for j in all_jobs:
                    if j.get('id') == job_id:
                        j['tailor_model'] = LLM_MODEL
                        updated = True
                        break
                if updated:
                    with open(jobs_json_path, 'w', encoding='utf-8') as f:
                        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
                        
            print(f"SUCCESS: Tailored resume for '{job_title}' ({lang_label}). Saved to {out_path}")
            return True
            
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and attempt < max_retries - 1:
                print(f"Rate limit hit (429). Retrying in 65 seconds... (Attempt {attempt+1}/{max_retries})")
                time.sleep(65)
                continue
            else:
                print(f"ERROR: Failed to run Gemini API tailoring: {e}")
                return False

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2:
        print("Usage: python tailor_with_gemini.py <job_id>")
        sys.exit(1)
    success = tailor_job(sys.argv[1])
    sys.exit(0 if success else 1)
