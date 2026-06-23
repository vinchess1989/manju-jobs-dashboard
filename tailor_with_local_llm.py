import os
import sys
import json
import re
import requests
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

PUBLIC_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\manju-jobs-dashboard"
load_env_manual()
PRIVATE_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\Manju-jobs"
DESC_DIR = os.path.join(PUBLIC_DIR, "job_descriptions")
OUT_DIR = os.path.join(PRIVATE_DIR, "Resumes")
TEMPLATE_PATH = os.path.join(OUT_DIR, "f6aaa66f", "f6aaa66f_data.json")

# Local LLM configuration from environment (with defaults)
LLM_ENDPOINT = os.environ.get("LOCAL_LLM_ENDPOINT", "http://localhost:11434/v1/chat/completions")
LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "llama3")
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
    """Find job info in curated_jobs.json or valid_jobs.json."""
    for fn in ["valid_jobs.json", "curated_jobs.json"]:
        path = os.path.join(PUBLIC_DIR, fn)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                jobs = json.load(f)
                for j in jobs:
                    if j.get("job_id") == job_id:
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
        
    desc_text = read_job_description(job.get("description_link"))
    if not desc_text:
        print(f"ERROR: No description found for Job ID {job_id}.")
        return False
        
    print(f"Tailoring resume for: {job['job_title']} at {job['company']} (ID: {job_id})")
    
    # Determine job language
    # Simple check: if description contains typical Finnish words, language is Finnish
    is_finnish = any(word in desc_text.lower() for word in ["tehtävä", "hakemus", "edellytämme", "tarjoamme", "osaamista", "työkokemusta"])
    lang_label = "Finnish" if is_finnish else "English"
    print(f"Detected job posting language: {lang_label}")
    
    # Load structural template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template_data = json.load(f)
        
    # Construct LLM prompt
    prompt = f"""You are a professional resume writer. Your task is to tailor a resume and write a cover letter based on the provided candidate profile, job description, and a JSON template.

Candidate Profile:
{MANJU_PROFILE_RAW}

Job Description:
{desc_text}

JSON Structural Template (fill this structure exactly):
{json.dumps(template_data, indent=2)}

Instructions for Tailoring:
1. Match the exact structure and keys of the template JSON.
2. The output MUST be a single raw JSON object only. No preamble, no explanation, no markdown wrappers (other than code block if needed).
3. "job_id": Use "{job_id}".
4. "job_title": Use "{job.get('job_title')}".
5. "company": Use "{job.get('company')}".
6. "resume" -> "role": Set to "{job.get('job_title')} Candidate".
7. "resume" -> "profile": 2-3 sentences in English. Refer to "{job.get('company')}" and the role specifically, highlighting the most relevant aspects of Manju's background.
8. "resume" -> "experience": Keep all 4 entries (Regelin, International House Oulu, Poise Legal, Juris Nexus). Adjust or reorder their "bullets" to highlight skills most relevant to this job. Keep the dates and company names exactly as they are.
9. "resume" -> "education": Keep all entries.
10. "resume" -> "languages_html": If the job language is Finnish, put Finnish first:
    "<span class=\\"skill-cat\\">Finnish</span> B2 (professional working proficiency) &nbsp;|&nbsp; <span class=\\"skill-cat\\">English</span> C1 / Fluent &nbsp;|&nbsp; <span class=\\"skill-cat\\">Malayalam</span> Native<br>..."
    Otherwise, keep English first.
11. "resume" -> "competencies_html": Reorder/reword the HTML competencies to lead with what matters most for this role. Use '<span class=\\"skill-cat\\">Category:</span> description...' format.
12. "cover_letter":
    - If the job language is Finnish, the cover letter paragraphs MUST be written in Finnish. Otherwise, write them in English.
    - Date: Use "23 June 2026".
    - Recipient company: "{job.get('company')}". Recipient city: "{job.get('location')}".
    - Write 4-5 compelling paragraphs detailing hook -> relevant experience -> integration in Finland -> why this company -> close.
    - Keep sign_off: "Ystävällisin terveisin" for Finnish, "Yours sincerely" for English.

Ensure the final JSON is completely valid, has escaped double-quotes in HTML fields, and matches the template structure. Output only the JSON."""

    # Call local LLM
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
        
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4000
    }
    
    try:
        print(f"Sending request to local LLM ({LLM_MODEL}) at {LLM_ENDPOINT}...")
        response = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        res_json = response.json()
        raw_text = res_json['choices'][0]['message']['content'].strip()
        
        # Parse JSON
        tailored_data = extract_json(raw_text)
        
        # Save output file
        job_dir = os.path.join(OUT_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        out_path = os.path.join(job_dir, f"{job_id}_data.json")
        with open(out_path, "w", encoding="utf-8") as f_out:
            json.dump(tailored_data, f_out, indent=2, ensure_ascii=False)
            
        print(f"SUCCESS: Tailored data JSON saved to {out_path}")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to run local LLM tailoring: {e}")
        if 'raw_text' in locals():
            print(f"Raw Response: {raw_text[:1000]}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tailor_with_local_llm.py <job_id>")
        sys.exit(1)
    tailor_job(sys.argv[1])
