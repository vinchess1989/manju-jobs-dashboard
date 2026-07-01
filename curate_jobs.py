import os
import json
import re
import sys

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PUBLIC_DIR = r"C:\Users\vinee\manju_jobs"
PRIVATE_DIR = r"C:\Users\vinee\Manju_jobs_private"
RESUMES_DIR = os.path.join(PRIVATE_DIR, "Resumes")

JOBS_FILE = os.path.join(PUBLIC_DIR, "jobs.json")
json_path = JOBS_FILE
print(f"Reading from jobs file: {json_path}")

with open(json_path, "r", encoding="utf-8") as f:
    jobs = json.load(f)

# Get existing resume folder names (job IDs)
existing_ids = set()
if os.path.exists(RESUMES_DIR):
    existing_ids = {name for name in os.listdir(RESUMES_DIR) if os.path.isdir(os.path.join(RESUMES_DIR, name))}

print(f"Total jobs in {json_path}: {len(jobs)}")
print(f"Already completed folders found: {len(existing_ids)}")

# Finnish city/region list to verify location is in Finland
FINNISH_LOCATIONS = [
    "finland", "suomi", "oulu", "helsinki", "tampere", "turku", "espoo", "vantaa",
    "lahti", "kuopio", "pori", "joensuu", "lappeenranta", "vaasa", "rovaniemi",
    "seinäjoki", "kajaani", "sastamala", "kemi", "tornio", "inari", "hanko",
    "porvoo", "kokkola", "rauma", "kerava", "nokia", "salo", "imatra", "riihimäki",
    "jyväskylä", "mikkeli", "kotka", "lohja", "hyvinkää", "järvenpää", "tuusula"
]

IRRELEVANT_KEYWORDS = [
    "siivo", "cleaner", "housekeeper", "siivous",
    "kuljettaja", "driver", "delivery", "jakelu",
    "varasto", "warehouse",
    "kokki", "keitti", "cook", "chef", "baker", "kitchen", "ravintola", "tarjoil", "waiter", "baarimikko", "aamupala",
    "lähihoitaja", "sairaanhoitaja", "nurse", "caregiver", "hoitaja", "hoitoavustaja", "henkilökohtainen", "ohjaaja", "kouluttaja",
    "sähköasentaja", "asentaja", "mechanic", "electrician", "plumber", "putkiasentaja", "timpuri", "rakentaja", "eristäjä", "kirvesmies",
    "kokoon", "assembler", "prosessit", "tuotantot", "tuotanto", "rakennus", "carpenter",
    "kassan", "cashier", "myy", "myyn", "sales associate", "asiakashankkija", "telemarketer", "puhelinmyyjä",
    "trimmaaja", "seurakuntamestari", "ajojärjestelijä", "huoltopäivystäjä", "maatilaneuvoja", "opiskelija", "oppisopimus", "kaupan alan"
]

curated = []
skipped_processed = 0
skipped_location = 0
skipped_type = 0

for job in jobs:
    job_id = job.get("id", job.get("job_id"))
    title = (job.get("title", job.get("job_title")) or "").lower()
    location = (job.get("location") or "").lower()

    # 1. Filter out already processed
    if job_id in existing_ids:
        skipped_processed += 1
        continue

    # 2. Filter out non-Finland locations (unless explicitly remote with no country mentioned or Finland remote)
    is_in_finland = any(loc in location for loc in FINNISH_LOCATIONS)
    # Check if it is a completely foreign country
    is_foreign = any(country in location for country in ["united states", "usa", "brazil", "peru", "malta", "philippines", "netherlands", "india", "germany", "france", "uk", "london", "canada", "spain"])
    
    if is_foreign or (not is_in_finland and "remote" not in location):
        skipped_location += 1
        continue

    # 3. Filter out irrelevant titles
    is_irrelevant = False
    for kw in IRRELEVANT_KEYWORDS:
        # Avoid matching legal/admin positions that contain substring keywords (e.g. "sales manager" vs "sales associate")
        # "myyjä" / "sales associate" / "cashier" are filtered out, but "legal" / "coordinator" / "admin" are unconditionally kept
        if kw in title:
            # Let's unconditionally keep legal/trainee/coordinator/assistant/HR/comms
            keep_keywords = ["legal", "compliance", "paralegal", "juristi", "trainee", "coordinator", "assistant", "hr", "comms", "event", "hallinto", "assistentti", "koordinaattori", "sihteeri"]
            if any(k in title for k in keep_keywords):
                continue
            is_irrelevant = True
            break
            
    if is_irrelevant:
        skipped_type += 1
        continue

    curated.append(job)

print(f"Skipped already processed: {skipped_processed}")
print(f"Skipped foreign/non-Finland locations: {skipped_location}")
print(f"Skipped irrelevant job types: {skipped_type}")
print(f"Curated jobs remaining: {len(curated)}")

curated_path = os.path.join(PUBLIC_DIR, "curated_jobs.json")
with open(curated_path, "w", encoding="utf-8") as f:
    json.dump(curated, f, indent=2, ensure_ascii=False)
print(f"Saved curated list to {curated_path}")

# Print curated jobs list
for idx, job in enumerate(curated, 1):
    j_id = job.get('id', job.get('job_id', 'N/A'))
    j_title = job.get('title', job.get('job_title', 'N/A'))
    print(f"{idx:3d}. ID: {j_id} | Co: {job.get('company', 'N/A')} | Title: {j_title} | Loc: {job.get('location', 'N/A')}")
