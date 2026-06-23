import os
import json

PUBLIC_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\manju-jobs-dashboard"
PRIVATE_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\Manju-jobs"
RESUMES_DIR = os.path.join(PRIVATE_DIR, "Resumes")

# Find the latest jobs_<timestamp>.json in the public directory (ignoring jobs_history.json)
json_files = [f for f in os.listdir(PUBLIC_DIR) if f.startswith("jobs_") and f.endswith(".json") and f != "jobs_history.json"]
if not json_files:
    print("No jobs_*.json files found!")
    exit(1)

latest_json = sorted(json_files)[-1]
json_path = os.path.join(PUBLIC_DIR, latest_json)
print(f"Reading from latest file: {latest_json}")

with open(json_path, "r", encoding="utf-8") as f:
    jobs = json.load(f)

# Get existing resume folder names (job IDs)
existing_ids = set()
if os.path.exists(RESUMES_DIR):
    existing_ids = {name for name in os.listdir(RESUMES_DIR) if os.path.isdir(os.path.join(RESUMES_DIR, name))}

print(f"Total jobs in {latest_json}: {len(jobs)}")
print(f"Already completed folders found: {len(existing_ids)}")

unprocessed = []
for job in jobs:
    job_id = job.get("job_id")
    if job_id not in existing_ids:
        unprocessed.append(job)

print(f"Unprocessed jobs count: {len(unprocessed)}")

# Save unprocessed list
unprocessed_path = os.path.join(PUBLIC_DIR, "unprocessed_jobs.json")
with open(unprocessed_path, "w", encoding="utf-8") as f:
    json.dump(unprocessed, f, indent=2, ensure_ascii=False)
print(f"Saved unprocessed list to {unprocessed_path}")

# Print summary of unprocessed jobs
for idx, job in enumerate(unprocessed, 1):
    print(f"{idx:3d}. ID: {job['job_id']} | Co: {job['company']} | Title: {job['job_title']} | Loc: {job['location']}")
