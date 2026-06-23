import os
import json

PUBLIC_DIR = r"C:\Users\vinee\Documents\manju jobs dashboard\manju-jobs-dashboard"

valid_path = os.path.join(PUBLIC_DIR, "valid_jobs.json")
with open(valid_path, "r", encoding="utf-8") as f:
    valid_jobs = json.load(f)

legal_keywords = ["juristi", "legal", "compliance", "lawyer", "counsel", "sopimus", "hankinta", "contract", "tender", "kilpailutus"]

prioritized = []
others = []

for job in valid_jobs:
    title = (job.get("job_title") or "").lower()
    if any(kw in title for kw in legal_keywords):
        prioritized.append(job)
    else:
        others.append(job)

print(f"Total valid jobs: {len(valid_jobs)}")
print(f"Prioritized legal/contract jobs: {len(prioritized)}")

print("\nPrioritized list:")
for idx, job in enumerate(prioritized, 1):
    print(f"{idx:2d}. ID: {job['job_id']} | Co: {job['company']} | Title: {job['job_title']} | Loc: {job['location']}")

print("\nOther valid jobs (first 10):")
for idx, job in enumerate(others[:10], 1):
    print(f"{idx:2d}. ID: {job['job_id']} | Co: {job['company']} | Title: {job['job_title']} | Loc: {job['location']}")

# Save prioritized list
prio_path = os.path.join(PUBLIC_DIR, "prioritized_jobs.json")
with open(prio_path, "w", encoding="utf-8") as f:
    json.dump(prioritized + others, f, indent=2, ensure_ascii=False)
print(f"\nSaved combined prioritized list to {prio_path}")
