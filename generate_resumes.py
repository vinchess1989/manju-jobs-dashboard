"""
generate_resumes.py  —  Generate tailored CVs + cover letters for filtered jobs.

Usage:
    python generate_resumes.py jobs_<timestamp>.json

Requires:
    ANTHROPIC_API_KEY set as environment variable, or placed in a .env file
    in the same directory as this script (key=value format).

Outputs:
    - Resumes/{job_id}_resume.md
    - Resumes/{job_id}_cover_letter.md
    saved to the Manju-jobs private repo, pushed after every 5 jobs.
    - jobs.json in public repo updated with resume_link / cover_letter_link.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent.parent
PRIVATE_REPO    = BASE_DIR / "Manju-jobs"
PUBLIC_REPO     = Path(__file__).parent
DESC_BASE_URL   = "https://vinchess1989.github.io/manju-jobs-dashboard/"
PRIVATE_URL_BASE = "https://github.com/munchnambiar/Manju-jobs/blob/main/Resumes"

# ── Base CV (Manju Krishna Haridas) ──────────────────────────────────────────
BASE_CV = """\
MANJU KRISHNA HARIDAS
Business and Corporate Law Specialist
Tuirantie 13 A22 Tuira, 90500 Oulu, Finland
+358 415765217 | munchnambiar@gmail.com | linkedin.com/in/manjukrishnaharidas

PROFESSIONAL PROFILE
A dedicated legal professional with a Master's degree in Business and Corporate Law.
Currently bridging international legal expertise with the Finnish system through
advanced university-level language and law studies. Recognised for academic excellence
and a proactive, community-oriented approach.

EXPERIENCE
Language Intern (Kieliharjoittelu) | Asianajajatoimisto Regelin Oy, Oulu | Apr–Jun 2026
• Completing a 2-month professional language placement as part of the Kohti Yliopistoa
  – Työelämä course.
• Mastering Finnish legal terminology and professional communication within a law firm.
• Observing Finnish legal practices to integrate international expertise with local requirements.

Intern | International House Oulu, Finland | Jan–Apr 2025 / Sep–Oct 2024
• Organised 14 community events, facilitating networking for an average of 25 participants.
• Supported 'OuluBot' deployment through data training and 100+ pilot user feedbacks.
• Produced social media content and reports in Finnish in a professional setting.

Legal Associate | Poise Legal, India | Oct 2021–May 2022
• Managed full contract lifecycle; drafted and negotiated 5–7 commercial agreements monthly.
• Conducted specialised research on company law for strategic corporate advice.

Junior Lawyer | Juris Nexus, India | Sep 2015–Jan 2016
• Researched 50+ case laws for civil and family trials, streamlining due diligence.
• Represented clients in court and drafted complex legal memoranda.

EDUCATION
Kohti Yliopistoa Program | University of Oulu (2025–2026)
Supplementary Law Studies (Finnish Bar Qualification) | University of Lapland (Ongoing)
  — OPH recognition decision received
Master's in Business and Corporate Law (Rank 1 / Top of Class) | Symbiosis International University
Bachelor of Laws (Top 3 Graduate) | University of Calicut
Integration Course | OSAO, Finland (2023–2024)

CORE COMPETENCIES
• Legal: Contract Law & Drafting, Corporate Governance, Legal Research & Analysis,
  Regulatory Compliance, Contract Lifecycle Management
• Coordination: Event Management (14+ events), Project Coordination, Document Management
• Digital: MS Office, Social Media Management, Digital Service Deployment (OuluBot)
• Languages: English (C1/Fluent), Finnish (B2/Developing), Malayalam (Native)
• Other: Valid driving licence; own vehicle available for work

REFERENCES
Marina Galanapoulou — Lawyer, Asianajajatoimisto Regelin Oy | +306945494407 | marina@regalin.fi
Jaana Liukkonen — Teacher, OSAO | +358 405707593 | jaana.liukkonen@osao.fi
Rikupekka Leinonen — Coordinator, International House Oulu | rikupekka.leinonen@ouka.fi
"""


def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def fetch_text(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        for enc in ("utf-8", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    except Exception:
        pass
    return None


def fetch_description(desc_link, job_url):
    if desc_link:
        text = fetch_text(DESC_BASE_URL + desc_link)
        if text:
            return text[:4000]
    if job_url:
        text = fetch_text(job_url)
        if text:
            # Strip HTML tags for a rough plain-text extract
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:4000]
    return None


def generate_for_job(job, client):
    desc = fetch_description(job.get("description_link"), job.get("job_link"))

    prompt = f"""You are helping Manju Krishna Haridas apply for a job. Produce a tailored one-page resume and a concise cover letter in Markdown.

BASE CV:
{BASE_CV}

TARGET JOB:
Title   : {job.get("job_title")}
Company : {job.get("company")}
Location: {job.get("location")}

JOB DESCRIPTION:
{desc if desc else "Not available — infer from title and company."}

Rules:
- Resume: keep to one page equivalent, highlight most relevant experience and skills first, use the same contact details from the base CV.
- Cover letter: under 350 words, addressed to the hiring manager at {job.get("company")}, specific to this role, warm and professional tone. Do NOT invent facts not in the base CV.
- Do NOT include a photo or personal photo note.
- Output EXACTLY in this format (no extra headings):

## RESUME
<resume content>

## COVER LETTER
<cover letter content>
"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text

    resume_match = re.search(r"## RESUME\s*(.*?)(?=## COVER LETTER|$)", text, re.DOTALL)
    cover_match  = re.search(r"## COVER LETTER\s*(.*?)$", text, re.DOTALL)

    resume       = resume_match.group(1).strip() if resume_match else text
    cover_letter = cover_match.group(1).strip()  if cover_match  else ""
    return resume, cover_letter


def git(args, cwd):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def ensure_private_repo_ready():
    git(["config", "user.email", "munchnambiar@gmail.com"], PRIVATE_REPO)
    git(["config", "user.name",  "munchnambiar"],            PRIVATE_REPO)
    (PRIVATE_REPO / "Resumes").mkdir(exist_ok=True)
    # Create README on first run if repo is empty
    readme = PRIVATE_REPO / "README.md"
    if not readme.exists():
        readme.write_text("# Manju-jobs\nTailored resumes and cover letters.\n")
        git(["add", "README.md"],               PRIVATE_REPO)
        git(["commit", "-m", "Initial commit"], PRIVATE_REPO)
        git(["push", "-u", "origin", "main"],   PRIVATE_REPO)


def push_private_batch(batch_num, job_ids):
    git(["add", "Resumes/"], PRIVATE_REPO)
    msg = f"Add resumes batch {batch_num}: {', '.join(job_ids)}"
    git(["commit", "-m", msg], PRIVATE_REPO)
    try:
        git(["push", "origin", "main"], PRIVATE_REPO)
    except RuntimeError:
        git(["push", "-u", "origin", "main"], PRIVATE_REPO)


def update_public_jobs_json(processed):
    jobs_path = PUBLIC_REPO / "jobs.json"
    with open(jobs_path, encoding="utf-8") as f:
        all_jobs = json.load(f)

    links = {p["job_id"]: p for p in processed}
    for job in all_jobs:
        jid = job.get("id")
        if jid in links:
            job["resume_link"]       = links[jid]["resume_link"]
            job["cover_letter_link"] = links[jid]["cover_letter_link"]

    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_resumes.py jobs_<timestamp>.json")
        sys.exit(1)

    api_key = load_api_key()
    if not api_key:
        print(
            "ERROR: ANTHROPIC_API_KEY not found.\n"
            "Set it as an environment variable, or add it to a .env file:\n"
            "  ANTHROPIC_API_KEY=sk-ant-..."
        )
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    jobs_file = Path(sys.argv[1])
    if not jobs_file.is_absolute():
        jobs_file = PUBLIC_REPO / jobs_file
    with open(jobs_file, encoding="utf-8") as f:
        jobs = json.load(f)

    print(f"Loaded {len(jobs)} jobs from {jobs_file.name}")
    print(f"Private repo : {PRIVATE_REPO}")
    print(f"Batches      : {(len(jobs) + 4) // 5} x 5\n")

    ensure_private_repo_ready()

    processed   = []
    resumes_dir = PRIVATE_REPO / "Resumes"
    batch_size  = 5

    for batch_start in range(0, len(jobs), batch_size):
        batch     = jobs[batch_start : batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total     = (len(jobs) + batch_size - 1) // batch_size
        print(f"=== Batch {batch_num}/{total} ===")

        batch_ids = []
        for job in batch:
            job_id  = job["job_id"]
            title   = job["job_title"]
            company = job["company"]
            print(f"  [{job_id}] {title} @ {company}")

            try:
                resume, cover = generate_for_job(job, client)
                (resumes_dir / f"{job_id}_resume.md").write_text(resume, encoding="utf-8")
                (resumes_dir / f"{job_id}_cover_letter.md").write_text(cover, encoding="utf-8")

                job["resume_link"]       = f"{PRIVATE_URL_BASE}/{job_id}_resume.md"
                job["cover_letter_link"] = f"{PRIVATE_URL_BASE}/{job_id}_cover_letter.md"
                processed.append(job)
                batch_ids.append(job_id)
                print(f"    OK")
            except Exception as e:
                print(f"    FAILED: {e}")

            time.sleep(0.5)   # brief pause between API calls

        if batch_ids:
            print(f"  Pushing batch {batch_num} to private repo...")
            try:
                push_private_batch(batch_num, batch_ids)
                print(f"  Pushed OK")
            except Exception as e:
                print(f"  Push failed: {e}")

        print()

    print(f"Generated {len(processed)}/{len(jobs)} resumes.")

    if processed:
        print("Updating public jobs.json with resume links...")
        update_public_jobs_json(processed)
        print("Done. Next: commit + push public repo, then firebase deploy.")


if __name__ == "__main__":
    main()
