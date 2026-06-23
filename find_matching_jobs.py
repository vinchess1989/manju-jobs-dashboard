import argparse
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

JOBS_URL = "https://vinchess1989.github.io/manju-jobs-dashboard/jobs.json"


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
    """Return days from today until date_str, or None if unparseable."""
    parsed = parse_date(date_str)
    if parsed is None:
        return None
    delta = parsed - datetime.now(timezone.utc)
    return delta.days


def days_since_posted(date_str):
    """Return days since posted, or None if unparseable."""
    parsed = parse_date(date_str)
    if parsed is None:
        return None
    delta = datetime.now(timezone.utc) - parsed
    return delta.days


def apply_filters(jobs, args):
    results = []
    for job in jobs:
        # --- matches_requirements filter ---
        if args.matching is not None:
            val = (job.get("matches_requirements") or "").lower()
            if args.matching and val != "yes":
                continue
            if not args.matching and val == "yes":
                continue

        # --- applied / user_review filter ---
        if args.applied is not None:
            review = (job.get("user_review") or "").lower()
            is_applied = review in ("applied", "done")
            if args.applied and not is_applied:
                continue
            if not args.applied and is_applied:
                continue

        # --- posted-days / deadline-days: OR or AND depending on --date-logic ---
        if args.posted_days is not None or args.deadline_days is not None:
            passes_posted = False
            passes_deadline = False

            if args.posted_days is not None:
                age = days_since_posted(job.get("posted_date", ""))
                passes_posted = age is not None and age <= args.posted_days

            if args.deadline_days is not None:
                remaining = days_until(job.get("deadline", ""))
                # Unparseable deadline (N/A, open-ended) treated as always valid
                passes_deadline = remaining is None or remaining >= args.deadline_days

            use_or = args.date_logic == "or"
            if use_or:
                if not (passes_posted or passes_deadline):
                    continue
            else:
                if args.posted_days is not None and not passes_posted:
                    continue
                if args.deadline_days is not None and not passes_deadline:
                    continue

        # --- location regex filter ---
        if args.location:
            location = job.get("location") or ""
            if not re.search(args.location, location, re.IGNORECASE):
                continue

        results.append(job)

    return results


def build_filter_summary(args):
    parts = []
    if args.matching is not None:
        parts.append(f"matching={'yes' if args.matching else 'no'}")
    if args.applied is not None:
        parts.append(f"applied={'yes' if args.applied else 'no'}")
    if args.posted_days is not None and args.deadline_days is not None:
        logic = args.date_logic.upper()
        parts.append(f"(posted within {args.posted_days}d {logic} deadline >={args.deadline_days}d away)")
    elif args.posted_days is not None:
        parts.append(f"posted within {args.posted_days}d")
    elif args.deadline_days is not None:
        parts.append(f"deadline >={args.deadline_days}d away")
    if args.location:
        parts.append(f"location~/{args.location}/")
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
        epilog="""
Examples:
  # Matching, not applied, posted in last 3 days (original behaviour)
  python find_matching_jobs.py --matching --no-applied --posted-days 3

  # Any job in Finland posted within 7 days with deadline at least 5 days away
  python find_matching_jobs.py --posted-days 7 --deadline-days 5 --location Finland

  # Show all applied jobs regardless of match
  python find_matching_jobs.py --applied

  # Non-matching jobs in Helsinki posted this week
  python find_matching_jobs.py --no-matching --posted-days 7 --location Helsinki
        """,
    )

    match_group = parser.add_mutually_exclusive_group()
    match_group.add_argument(
        "--matching", dest="matching", action="store_true", default=None,
        help="Only show jobs where matches_requirements=yes",
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
        help="Only show jobs whose deadline is at least N days away (jobs with no parseable deadline are always kept)",
    )
    parser.add_argument(
        "--location", metavar="REGEX", default=None,
        help="Only show jobs whose location matches this regex (case-insensitive)",
    )
    parser.add_argument(
        "--date-logic", choices=["or", "and"], default="or",
        help="When both --posted-days and --deadline-days are given, combine them with OR (default) or AND",
    )

    args = parser.parse_args()

    # argparse stores False for store_false even when not provided; fix that
    # by relying on default=None and the mutually exclusive group
    # (store_true/store_false always write a value, so we need a workaround)
    # Re-parse defaults properly using sys.argv inspection:
    import sys
    matching_flags = {"--matching", "--no-matching"}
    applied_flags  = {"--applied", "--no-applied"}
    if not matching_flags.intersection(sys.argv):
        args.matching = True   # default: only matching jobs
    if not applied_flags.intersection(sys.argv):
        args.applied = False   # default: only not-applied jobs

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
