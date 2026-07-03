"""Append a single manually-specified job URL to jobs.json as a pending entry.

Used by the /add-job-link skill to hand-add a job the scraper didn't find on
its own. The new entry flows through the normal pipeline afterwards via
`scraper.py --review-urls`.
"""
import argparse
import hashlib
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")
DELETED_FILE = os.path.join(BASE_DIR, "deleted.json")


def main():
    parser = argparse.ArgumentParser(description="Manually add a job URL to jobs.json for review.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--company", default="")
    parser.add_argument("--location", default="")
    args = parser.parse_args()

    job_id = hashlib.md5(args.url.encode("utf-8")).hexdigest()[:8]

    jobs = []
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            jobs = json.load(f)

    for j in jobs:
        if j.get("url") == args.url or j.get("id") == job_id:
            print(f"SKIP: Already tracked as {j.get('id')} (matches_requirements={j.get('matches_requirements')})")
            sys.exit(0)

    if os.path.exists(DELETED_FILE):
        with open(DELETED_FILE, "r", encoding="utf-8") as f:
            deleted = json.load(f)
        for j in deleted:
            if j.get("url") == args.url:
                print(f"WARN: This URL was previously deleted ({j.get('deletion_reason', 'unknown reason')}). Re-adding as a fresh pending job.")
                break

    jobs.append({
        "title": args.title,
        "company": args.company,
        "location": args.location,
        "url": args.url,
        "visited": "no",
        "matches_requirements": "pending",
        "reason": "",
        "id": job_id,
        "source": "manual",
    })
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)

    print(f"ADDED: {job_id} - {args.title or '(title pending review)'} @ {args.company or '?'}")


if __name__ == "__main__":
    main()
