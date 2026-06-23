import os
import json

PUBLIC_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\manju-jobs-dashboard"

curated_path = os.path.join(PUBLIC_DIR, "curated_jobs.json")
with open(curated_path, "r", encoding="utf-8") as f:
    jobs = json.load(f)

valid_jobs = []
blocked_jobs = []

for job in jobs:
    desc_file = job.get("description_link")
    if not desc_file:
        blocked_jobs.append((job, "No local description link"))
        continue
    
    desc_path = os.path.join(PUBLIC_DIR, desc_file)
    if not os.path.exists(desc_path):
        blocked_jobs.append((job, "Local description file missing"))
        continue
        
    with open(desc_path, "r", encoding="utf-8") as f_desc:
        content = f_desc.read()
        
    # Check for Cloudflare / Ray ID / short descriptions
    if "cloudflare" in content.lower() or "ray id" in content.lower() or "additional verification required" in content.lower():
        blocked_jobs.append((job, "Cloudflare blocked file"))
    elif len(content.strip().split()) < 50:
        blocked_jobs.append((job, "Description too short (<50 words)"))
    else:
        valid_jobs.append(job)

print(f"Total curated jobs: {len(jobs)}")
print(f"Valid jobs (ready to process): {len(valid_jobs)}")
print(f"Blocked or incomplete jobs: {len(blocked_jobs)}")

# Print first 10 valid jobs
print("\nFirst 10 valid jobs:")
for idx, job in enumerate(valid_jobs[:10], 1):
    print(f"{idx:2d}. ID: {job['job_id']} | Co: {job['company']} | Title: {job['job_title']} | Loc: {job['location']}")

# Save valid jobs to a separate JSON file
valid_path = os.path.join(PUBLIC_DIR, "valid_jobs.json")
with open(valid_path, "w", encoding="utf-8") as f:
    json.dump(valid_jobs, f, indent=2, ensure_ascii=False)
print(f"\nSaved valid jobs list to {valid_path}")
