import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

JOBS_URL = "https://vinchess1989.github.io/manju-jobs-dashboard/jobs.json"

VALID_CONDITIONS = ("matching", "applied", "posted-days", "deadline-days", "location")


def fetch_jobs(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def parse_date(date_str):
    if not date_str or date_str in ("N/A", "Open until filled", ""):
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def days_until(date_str):
    parsed = parse_date(date_str)
    if parsed is None:
        return None
    return (parsed - datetime.now(timezone.utc)).days


def days_since_posted(date_str):
    parsed = parse_date(date_str)
    if parsed is None:
        return None
    return (datetime.now(timezone.utc) - parsed).days


def evaluate_condition(job, cond, args):
    """Return True/False if condition is active, None if not specified by user."""
    if cond == "matching":
        if args.matching is None:
            return None
        val = (job.get("matches_requirements") or "").lower()
        return val in ("yes", "maybe") if args.matching else val not in ("yes", "maybe")
    if cond == "applied":
        if args.applied is None:
            return None
        is_applied = (job.get("user_review") or "").lower() in ("applied", "done")
        return is_applied if args.applied else not is_applied
    if cond == "posted-days":
        if args.posted_days is None:
            return None
        age = days_since_posted(job.get("posted_date", ""))
        return age is not None and age <= args.posted_days
    if cond == "deadline-days":
        if args.deadline_days is None:
            return None
        remaining = days_until(job.get("deadline", ""))
        # Unparseable deadline (N/A, open-ended) treated as always valid
        return remaining is None or remaining >= args.deadline_days
    if cond == "location":
        if not args.location:
            return None
        return bool(re.search(args.location, job.get("location") or "", re.IGNORECASE))
    return None


def apply_filters(jobs, args):
    or_pairs = args.or_pairs or []
    or_grouped = {cond for pair in or_pairs for cond in pair}
    standalone = [c for c in VALID_CONDITIONS if c not in or_grouped]

    results = []
    for job in jobs:
        # AND: every standalone condition must pass
        if any(evaluate_condition(job, c, args) is False for c in standalone):
            continue

        # OR groups: within each group, at least one active condition must pass
        failed_group = False
        for pair in or_pairs:
            active = [evaluate_condition(job, c, args) for c in pair]
            active = [r for r in active if r is not None]
            if active and not any(active):
                failed_group = True
                break
        if failed_group:
            continue

        results.append(job)

    return results


def condition_label(cond, args):
    """Human-readable label for a condition, or None if not active."""
    if cond == "matching":
        return f"matching={'yes/maybe' if args.matching else 'no'}" if args.matching is not None else None
    if cond == "applied":
        return f"applied={'yes' if args.applied else 'no'}" if args.applied is not None else None
    if cond == "posted-days":
        return f"posted within {args.posted_days}d" if args.posted_days is not None else None
    if cond == "deadline-days":
        return f"deadline >={args.deadline_days}d away" if args.deadline_days is not None else None
    if cond == "location":
        return f"location~/{args.location}/" if args.location else None
    return None


def build_filter_summary(args):
    or_pairs = args.or_pairs or []
    or_grouped = {cond for pair in or_pairs for cond in pair}

    parts = []
    for cond in VALID_CONDITIONS:
        if cond not in or_grouped:
            label = condition_label(cond, args)
            if label:
                parts.append(label)

    for pair in or_pairs:
        labels = [condition_label(c, args) or c for c in pair]
        parts.append(f"({' OR '.join(labels)})")

    return "  |  ".join(parts) if parts else "none"


DESCRIPTION_BASE_URL = "https://vinchess1989.github.io/manju-jobs-dashboard/"


def generate_combined_prompt(jobs_filename, jobs):
    job_lines = []
    for i, job in enumerate(jobs, 1):
        desc_link = job.get("description_link")
        desc_url = (DESCRIPTION_BASE_URL + desc_link) if desc_link else "N/A"
        job_lines.append(
            f"  {i}. Job ID: {job.get('job_id')}\n"
            f"     Company    : {job.get('company')}\n"
            f"     Job Title  : {job.get('job_title')}\n"
            f"     Location   : {job.get('location')}\n"
            f"     Posted     : {job.get('posted_date')}\n"
            f"     Deadline   : {job.get('deadline_date')}\n"
            f"     Job Link   : {job.get('job_link')}\n"
            f"     Description: {desc_url}"
        )
    jobs_block = "\n\n".join(job_lines)

    return f"""Hi Claude, I would like you to tailor my resume and cover letter for each of the following jobs.

The full list of jobs is available in this local JSON file: {jobs_filename}

For each job below, fetch and read its full job description from the URL listed under "Description", \
then generate a tailored resume matching the job's focus areas and a compelling cover letter \
highlighting why my background and skills are a strong fit for that specific role.

Jobs ({len(jobs)} total):

{jobs_block}

Please process each job one by one, clearly labelling each resume and cover letter with the Job ID, \
company name, and job title.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Filter jobs from the Manju jobs dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Condition names for --or: {', '.join(VALID_CONDITIONS)}

Examples:
  # Matching, not applied, posted in last 3 days (default AND behaviour)
  python find_matching_jobs.py --matching --no-applied --posted-days 3

  # Jobs posted within 7 days OR with deadline >=5 days away, in Finland
  python find_matching_jobs.py --posted-days 7 --deadline-days 5 --location Finland --or posted-days deadline-days

  # Show all applied jobs regardless of match
  python find_matching_jobs.py --applied

  # Non-matching jobs: recently posted OR deadline soon, in Helsinki
  python find_matching_jobs.py --no-matching --posted-days 7 --deadline-days 3 --location Helsinki --or posted-days deadline-days
        """,
    )

    match_group = parser.add_mutually_exclusive_group()
    match_group.add_argument(
        "--matching", dest="matching", action="store_true", default=None,
        help="Only show jobs where matches_requirements=yes or maybe",
    )
    match_group.add_argument(
        "--no-matching", dest="matching", action="store_false",
        help="Only show jobs where matches_requirements != yes",
    )

    apply_group = parser.add_mutually_exclusive_group()
    apply_group.add_argument(
        "--applied", dest="applied", action="store_true", default=None,
        help="Only show jobs already applied/done",
    )
    apply_group.add_argument(
        "--no-applied", dest="applied", action="store_false",
        help="Only show jobs NOT yet applied/done",
    )

    parser.add_argument(
        "--posted-days", type=int, metavar="N", default=None,
        help="Only show jobs posted within the last N days",
    )
    parser.add_argument(
        "--deadline-days", type=int, metavar="N", default=None,
        help="Only show jobs whose deadline is at least N days away (unparseable deadlines always pass)",
    )
    parser.add_argument(
        "--location", metavar="REGEX", default=None,
        help="Only show jobs whose location matches this regex (case-insensitive)",
    )
    parser.add_argument(
        "--or", dest="or_pairs", nargs=2, action="append", metavar="COND",
        help=(
            "OR two conditions instead of AND-ing them "
            f"({', '.join(VALID_CONDITIONS)}). Repeatable for multiple OR pairs."
        ),
    )

    args = parser.parse_args()

    # store_true/store_false always write a value; restore None when flag absent
    if not {"--matching", "--no-matching"}.intersection(sys.argv):
        args.matching = True   # default: only matching jobs
    if not {"--applied", "--no-applied"}.intersection(sys.argv):
        args.applied = False   # default: only not-applied jobs

    # Validate --or condition names
    for pair in (args.or_pairs or []):
        for cond in pair:
            if cond not in VALID_CONDITIONS:
                parser.error(f"--or: unknown condition '{cond}'. Valid: {', '.join(VALID_CONDITIONS)}")

    print(f"Fetching jobs from {JOBS_URL} ...")
    jobs = fetch_jobs(JOBS_URL)

    results = apply_filters(jobs, args)

    today = datetime.now(timezone.utc).date()
    filters = build_filter_summary(args)
    print(f"\nDate   : {today}")
    print(f"Filters: {filters}")
    print(f"Total  : {len(jobs)} jobs  ->  {len(results)} matched\n")

    if not results:
        print("No jobs found matching the given filters.")
        return

    output = [
        {
            "job_id":           job.get("id"),
            "company":          job.get("company"),
            "job_title":        job.get("title"),
            "location":         job.get("location"),
            "description_link": job.get("description_file"),
            "job_link":         job.get("url"),
            "matching_status":  job.get("matches_requirements"),
            "applied_status":   job.get("user_review"),
            "posted_date":      job.get("posted_date"),
            "deadline_date":    job.get("deadline"),
        }
        for job in results
    ]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"jobs_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(output)} jobs to {filename}")

    prompts_filename = f"resume_prompts_{timestamp}.txt"
    with open(prompts_filename, "w", encoding="utf-8") as f:
        f.write(generate_combined_prompt(filename, output))
    print(f"Saved resume prompt to {prompts_filename}")


if __name__ == "__main__":
    main()
