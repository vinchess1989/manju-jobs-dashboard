"""
check_expired.py — Batch-check all active jobs for expired/removed listings.

Visits every job in jobs.json with matches_requirements in (yes, maybe, error)
that isn't already applied, checks for expired-listing signals, and moves
expired ones to deleted.json.

Usage:
    python check_expired.py
    python check_expired.py --dry-run       # report without moving
    python check_expired.py --yes-only      # only check matches_requirements=yes
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
JOBS_FILE    = BASE_DIR / "jobs.json"
DELETED_FILE = BASE_DIR / "deleted.json"

EXPIRED_SIGNALS = [
    "tämä työpaikkailmoitus indeedissä on vanhentunut",
    "tämä ilmoitus on vanhentunut",
    "ilmoitus on poistettu",
    "this job listing has expired",
    "this indeed job listing has expired",
    "this job is no longer available",
    "job posting is no longer available",
    "this job posting on indeed is outdated",
    "job posting is outdated",
    "is no longer accepting job applications",
    "not currently actively recruiting",
    "posting has been removed",
]

# DOM selectors that directly flag expiry (faster than full-text scan)
EXPIRED_SELECTORS = [
    '[data-testid="outdated-job-alert"]',
    '[class*="expired"]',
    '[class*="outdated"]',
]


def load_json(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_json(path: Path, data: list):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_indeed_url(url: str) -> bool:
    return "indeed.com" in url.lower()


def check_page_expired(page, url: str) -> bool:
    """
    Return True if the current page shows an expired/removed listing.
    Checks Indeed redirect, DOM selectors, and page text.
    """
    current_url = page.url.lower()

    # Indeed: redirect away from the job detail page means expired/removed
    if is_indeed_url(url):
        if ("viewjob" not in current_url and
                "/rc/clk" not in current_url and
                "jk=" not in current_url):
            return True

    # DOM selectors (fast)
    for sel in EXPIRED_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True
        except Exception:
            pass

    # Full-text scan
    try:
        text = (page.evaluate("() => document.body.innerText") or "").lower()
        if any(s in text for s in EXPIRED_SIGNALS):
            return True
    except Exception:
        pass

    return False


def move_to_deleted(jobs: list, deleted: list, job: dict, reason: str) -> tuple:
    """Remove job from jobs list, add to deleted list. Returns (jobs, deleted)."""
    job["deletion_reason"] = reason
    url = job.get("url")
    seen = {j.get("url") for j in deleted}
    if url not in seen:
        deleted.append(job)
    jobs = [j for j in jobs if j.get("url") != url]
    return jobs, deleted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",  action="store_true", help="Report only, don't modify files")
    parser.add_argument("--yes-only", action="store_true", help="Only check matches_requirements=yes jobs")
    args = parser.parse_args()

    jobs    = load_json(JOBS_FILE)
    deleted = load_json(DELETED_FILE)

    deleted_urls = {j.get("url") for j in deleted}

    statuses = {"yes", "maybe", "error"} if not args.yes_only else {"yes"}
    candidates = [
        j for j in jobs
        if j.get("matches_requirements") in statuses
        and j.get("applied") != "yes"
        and j.get("url") not in deleted_urls
    ]

    total = len(candidates)
    print(f"Jobs to check: {total}  (dry_run={args.dry_run}, yes_only={args.yes_only})")
    if total == 0:
        print("Nothing to check.")
        return

    expired_list  = []
    skipped_list  = []
    checked_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = ctx.new_page()

        for i, job in enumerate(candidates, 1):
            url   = job.get("url", "")
            title = job.get("title", "?")
            co    = job.get("company", "?")
            mr    = job.get("matches_requirements", "?")
            prefix = f"[{i}/{total}] {title} @ {co} ({mr})"

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(1.5)
            except Exception as e:
                print(f"  {prefix} — SKIP (timeout/error: {e})")
                skipped_list.append(url)
                checked_count += 1
                continue

            if check_page_expired(page, url):
                print(f"  {prefix} — EXPIRED")
                expired_list.append(job)
                checked_count += 1
                if not args.dry_run:
                    jobs, deleted = move_to_deleted(
                        jobs, deleted, job,
                        "Expired job listing (batch check)"
                    )
                    # Save after each expired job so progress survives interruption
                    save_json(JOBS_FILE, jobs)
                    save_json(DELETED_FILE, deleted)
            else:
                print(f"  {prefix} — ok")
                checked_count += 1

        browser.close()

    print()
    print("=" * 60)
    print(f"Checked : {checked_count} / {total}")
    print(f"Expired : {len(expired_list)}")
    print(f"Skipped : {len(skipped_list)}")

    if expired_list:
        print("\nExpired jobs:")
        for j in expired_list:
            tag = "(not moved — dry run)" if args.dry_run else "(moved to deleted.json)"
            print(f"  [{j.get('matches_requirements')}] {j.get('title')} @ {j.get('company')} {tag}")

    if skipped_list:
        print("\nSkipped (timeout/error):")
        for u in skipped_list:
            print(f"  {u}")

    if not args.dry_run and expired_list:
        print(f"\njobs.json updated: {len(jobs)} remaining jobs")
        print(f"deleted.json updated: {len(deleted)} total deleted")


if __name__ == "__main__":
    main()
