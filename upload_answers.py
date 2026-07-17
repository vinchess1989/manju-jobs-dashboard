#!/usr/bin/env python3
"""
Upload a job's pre-generated application answers to Firestore so they can be
fetched by job_id (e.g. by a browser extension) without opening the private repo.

Usage:
    python upload_answers.py --job-id abc12345                 # upload one job
    python upload_answers.py --job-id abc12345 def67890         # upload several
    python upload_answers.py --all                              # rescan and upload every *_answers.json found

Reads PRIVATE\\Resumes\\JOB_ID\\JOB_ID_answers.json and writes it to the
Firestore collection `application_answers`, one document per job_id.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import requests

PROJECT_ID = "manju-jobs-dashboard"
FIRESTORE_BASE = (
    f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
    f"/databases/(default)/documents"
)
COLLECTION = "application_answers"

PRIVATE_SLUG = "munchnambiar/Manju-jobs"
GITHUB_BLOB_BASE = f"https://github.com/{PRIVATE_SLUG}/blob/main/Resumes"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{PRIVATE_SLUG}/main/Resumes"


def find_documents(job_dir: Path) -> dict:
    """Find the resume/cover-letter PDFs for a job and build blob + raw GitHub URLs."""
    job_id = job_dir.name
    pdfs = list(job_dir.glob("*.pdf"))
    resume_file = next((p for p in pdfs if p.name.endswith("_resume.pdf")), None)
    letter_file = next((p for p in pdfs if p.name.endswith("_cover_letter.pdf")), None)

    docs = {}
    if resume_file:
        docs["resume_url"] = f"{GITHUB_BLOB_BASE}/{job_id}/{resume_file.name}"
        docs["resume_raw_url"] = f"{GITHUB_RAW_BASE}/{job_id}/{resume_file.name}"
    if letter_file:
        docs["cover_letter_url"] = f"{GITHUB_BLOB_BASE}/{job_id}/{letter_file.name}"
        docs["cover_letter_raw_url"] = f"{GITHUB_RAW_BASE}/{job_id}/{letter_file.name}"
    return docs


def find_private_repo() -> Path:
    script = Path(__file__).parent / "find_repos.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print("ERROR: find_repos.py failed:", result.stderr)
        sys.exit(1)
    data = json.loads(result.stdout)
    private = data.get("private")
    if not private:
        print("ERROR: Could not locate private repo. Make sure it is cloned.")
        sys.exit(1)
    return Path(private)


def _serialize_value(val):
    if val is None:
        return {"nullValue": None}
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, dict):
        return {"mapValue": {"fields": {k: _serialize_value(v) for k, v in val.items()}}}
    if isinstance(val, list):
        return {"arrayValue": {"values": [_serialize_value(v) for v in val]}}
    return {"stringValue": str(val)}


def _serialize_doc(data: dict) -> dict:
    return {"fields": {k: _serialize_value(v) for k, v in data.items()}}


def find_answer_files(private_repo: Path, job_ids: list[str] | None) -> list[Path]:
    resumes_dir = private_repo / "Resumes"
    if job_ids:
        files = []
        for job_id in job_ids:
            f = resumes_dir / job_id / f"{job_id}_answers.json"
            if f.exists():
                files.append(f)
            else:
                print(f"WARN: no answers file for job_id '{job_id}' at {f} — skipping.")
        return files
    return sorted(resumes_dir.glob("*/*_answers.json"))


def upload_one(answers_path: Path) -> str:
    with open(answers_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    job_id = payload.get("job_id") or answers_path.parent.name
    doc_url = f"{FIRESTORE_BASE}/{COLLECTION}/{job_id}"

    body = {
        "job_id": job_id,
        "job_url": payload.get("job_url", ""),
        "apply_url": payload.get("apply_url", ""),
        "platform": payload.get("platform", ""),
        "answers": payload.get("answers", []),
    }
    body.update(find_documents(answers_path.parent))

    resp = requests.patch(doc_url, json=_serialize_doc(body), timeout=30)
    resp.raise_for_status()
    return job_id


def main():
    parser = argparse.ArgumentParser(description="Upload application answers to Firestore.")
    parser.add_argument("--job-id", nargs="+", help="One or more job IDs to upload")
    parser.add_argument("--all", action="store_true", help="Upload every *_answers.json found in the private repo")
    args = parser.parse_args()

    if not args.job_id and not args.all:
        parser.error("Provide --job-id <id...> or --all")

    private_repo = find_private_repo()
    print(f"Private repo: {private_repo}")

    files = find_answer_files(private_repo, args.job_id if not args.all else None)
    if not files:
        print("No answers files found to upload.")
        return

    print(f"Uploading {len(files)} answers file(s) to Firestore collection '{COLLECTION}'...")
    for f in files:
        try:
            job_id = upload_one(f)
            print(f"  OK  {job_id}  <-  {f}")
        except Exception as e:
            print(f"  FAIL  {f}: {e}")

    print("\nDone. Fetch a job's answers with:")
    print(f"  {FIRESTORE_BASE}/{COLLECTION}/<job_id>")


if __name__ == "__main__":
    main()
