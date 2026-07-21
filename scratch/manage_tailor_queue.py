import json
import os
import sys

PUBLIC_DIR = r"C:\Users\vinee\manju_jobs"
PRIVATE_DIR = r"C:\Users\vinee\Manju_jobs_private"
RESUMES_DIR = os.path.join(PRIVATE_DIR, "Resumes")
JOBS_FILE = os.path.join(PUBLIC_DIR, "jobs.json")
TEMPLATE_PATH = os.path.join(PRIVATE_DIR, "Resumes", "Master", "master_data.json")

def get_job_description(job):
    desc_text = job.get("description")
    if not desc_text:
        desc_link = job.get("description_link", job.get("description_file"))
        if desc_link:
            path = os.path.join(PUBLIC_DIR, desc_link)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
    return desc_text or ""

def main():
    max_jobs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    if PUBLIC_DIR not in sys.path:
        sys.path.append(PUBLIC_DIR)
    import db_utils
    jobs = db_utils.load_jobs()
        
    yes_queue = []
    maybe_queue = []
    
    LOCAL_LLM_VALUES = {"local llm", "llm", "local", "hermes-3-llama-3.1-8b", "hermes-3-llama-3.1-8b:2"}

    for j in jobs:
        job_id = j.get("id")
        if not job_id: continue

        # Skip jobs that have already been applied to
        if str(j.get("applied", "")).lower() == "yes":
            continue

        data_path = os.path.join(RESUMES_DIR, job_id, f"{job_id}_data.json")
        docs_exist = os.path.exists(data_path)

        # Read tailor_model from the actual data file (more reliable than jobs.json
        # which can be overwritten by the scraper's git pull)
        if docs_exist:
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    doc_data = json.load(f)
                file_tailor_model = str(doc_data.get("tailor_model", "")).strip().lower()
            except Exception:
                file_tailor_model = ""
            # If the file was tailored by a real AI (not local LLM), skip it
            if file_tailor_model and file_tailor_model not in LOCAL_LLM_VALUES:
                continue

        # Also check jobs.json tailor_model as a fallback
        tailor_model = str(j.get("tailor_model", "")).strip()
        if docs_exist and tailor_model.lower() not in LOCAL_LLM_VALUES:
            continue

        req = str(j.get("matches_requirements")).lower()
        if req == "yes":
            yes_queue.append(j)
        elif req == "maybe":
            maybe_queue.append(j)
            
    from datetime import datetime, timedelta
    today_str = datetime.now().strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    def priority_key(x):
        d = x.get('posted_date', '')
        posted_val = '' if d == 'NA' else d
        deadline = x.get('deadline', '')
        is_urgent = 1 if deadline in (today_str, tomorrow_str) else 0
        return (is_urgent, posted_val)
        
    yes_queue.sort(key=priority_key, reverse=True)
    maybe_queue.sort(key=priority_key, reverse=True)
    
    print(f"Queue Status: {len(yes_queue)} YES jobs, {len(maybe_queue)} MAYBE jobs remaining.")
    
    batch = yes_queue[:max_jobs]
    if len(batch) < max_jobs:
        batch.extend(maybe_queue[:max_jobs - len(batch)])
        
    if not batch:
        print("QUEUE_EMPTY")
        return
        
    batch_data = []
    for j in batch:
        desc = get_job_description(j)
        batch_data.append({
            "job_id": j.get("id"),
            "company": j.get("company"),
            "title": j.get("title"),
            "location": j.get("location"),
            "description": desc
        })
        
    out_path = os.path.join(PUBLIC_DIR, "scratch", "agent_batch.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(batch_data, f, indent=2, ensure_ascii=False)
        
    print(f"BATCH_READY: Saved {len(batch_data)} jobs to {out_path}")

if __name__ == "__main__":
    main()
