import os
import subprocess
import json
import sys

class TeeLogger:
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        
    def write(self, message):
        try:
            self.terminal.write(message)
        except UnicodeEncodeError:
            clean_msg = message.encode(self.terminal.encoding or 'ascii', errors='replace').decode(self.terminal.encoding or 'ascii', errors='replace')
            self.terminal.write(clean_msg)
        self.log_file.write(message)
        self.flush()
        
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

sys.stdout = TeeLogger("orchestrator.log")
sys.stderr = sys.stdout

PUBLIC_DIR = r"C:\Users\vinee\manju_jobs"
PRIVATE_DIR = r"C:\Users\vinee\Manju_jobs_private"
JOBS_FILE = os.path.join(PUBLIC_DIR, "jobs.json")
RESUMES_DIR = os.path.join(PRIVATE_DIR, "Resumes")

def run_script(script_name):
    print(f"\n{'='*50}\nRunning {script_name}...\n{'='*50}")
    # Using python executable from venv
    python_exe = os.path.join(PUBLIC_DIR, "venv", "Scripts", "python.exe")
    
    # Force UTF-8 encoding to prevent Windows charmap print errors (like the arrow -> symbol)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    # Stream the output line-by-line so it hits the TeeLogger and gets instantly written to the file
    process = subprocess.Popen([python_exe, "-u", script_name], cwd=PUBLIC_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    for line in process.stdout:
        print(line, end='')
        
    process.wait()
    if process.returncode != 0:
        print(f"ERROR: {script_name} failed with return code {process.returncode}")
        return False
    return True

def main():
    print("Starting Autonomous Local LLM Pipeline Orchestrator...")
    
    # Step 1: Scrape new jobs
    if not run_script("scraper.py"): return
    
    # Step 2: Curate jobs (Basic string/location filters)
    if not run_script("curate_jobs.py"): return
    
    # Step 3: Evaluate jobs with local LLM
    if not run_script("evaluate_with_local_llm.py"): return
    
    # Step 4: Find newly approved jobs that need resumes
    print(f"\n{'='*50}\nFinding approved jobs for resume generation...\n{'='*50}")
    if not os.path.exists(JOBS_FILE):
        print("No jobs.json found!")
        return
        
    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f)
        
    approved_jobs = []
    for job in jobs:
        matches = job.get("matches_requirements")
        if matches in ["yes", "maybe"]:
            job_id = job.get("id")
            # Check if resume folder already exists
            resume_path = os.path.join(RESUMES_DIR, job_id)
            if not os.path.exists(resume_path):
                approved_jobs.append(job_id)
                
    if not approved_jobs:
        print("No new approved jobs found to process. Pipeline finished.")
        return
        
    print(f"Found {len(approved_jobs)} new approved jobs: {', '.join(approved_jobs)}")
    
    # Step 5: Run the Resume Pipeline (DISABLED)
    # The user requested to skip tailoring resumes via local LLM during orchestration.
    if approved_jobs:
        print(f"\nFound {len(approved_jobs)} approved jobs. Skipping automatic resume generation as per user request.")
        print("Orchestrator finished successfully!")

if __name__ == "__main__":
    main()
