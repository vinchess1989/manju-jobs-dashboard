import json
import os
import shutil
from filelock import FileLock, Timeout

JOBS_FILE = os.path.join(os.path.dirname(__file__), 'jobs.json')
LOCK_FILE = JOBS_FILE + '.lock'

# 10 seconds timeout
LOCK_TIMEOUT = 10

def load_jobs():
    """Acquires the lock, reads jobs.json, and returns the list of jobs."""
    lock = FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT)
    with lock:
        if not os.path.exists(JOBS_FILE):
            return []
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

def save_jobs(jobs):
    """Writes the updated list to jobs.json, creates a backup, and releases the lock."""
    lock = FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT)
    with lock:
        # Create a backup just in case
        if os.path.exists(JOBS_FILE):
            shutil.copy2(JOBS_FILE, JOBS_FILE + '.bak')
            
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2)

def update_job(job_id, updates):
    """A helper that safely loads, modifies, and saves a single job atomically.
    updates should be a dictionary of key-value pairs to update.
    Returns True if job was found and updated, False otherwise.
    """
    lock = FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT)
    with lock:
        if not os.path.exists(JOBS_FILE):
            return False
        
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            try:
                jobs = json.load(f)
            except json.JSONDecodeError:
                jobs = []
                
        updated = False
        for job in jobs:
            if job.get('id') == job_id or job.get('job_id') == job_id:
                for k, v in updates.items():
                    job[k] = v
                updated = True
                break
                
        if updated:
            if os.path.exists(JOBS_FILE):
                shutil.copy2(JOBS_FILE, JOBS_FILE + '.bak')
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2)
                
        return updated
