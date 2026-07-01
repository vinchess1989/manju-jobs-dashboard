#!/usr/bin/env python3
"""
Auto-fill a job application form using pre-generated answers, then pause for review.

Loads answers from JOB_ID_answers.json, opens the application in a visible browser,
fills all fields, navigates to the final review/submit screen, and waits.
Manju reviews and clicks Submit manually.

Usage:
    python fill_application.py --job-id ID --private-dir PATH
"""

import os
import json
import time
import getpass
import argparse
import re
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Paths ─────────────────────────────────────────────────────────────────────

PRIVATE_DIR = Path(r"C:\Users\vinee\Manju_jobs_private")
ENV_FILE    = PRIVATE_DIR / ".env"
SESSION_DIR = PRIVATE_DIR / "sessions"

PLATFORM_PATTERNS = {
    "linkedin":   ["linkedin.com"],
    "indeed":     ["indeed.com"],
    "duunitori":  ["duunitori.fi"],
    "greenhouse": ["boards.greenhouse.io", "boards.eu.greenhouse.io"],
    "lever":      ["jobs.lever.co"],
    "workday":    ["myworkdayjobs.com"],
}

CRED_MAP = {
    "linkedin": ("LINKEDIN_EMAIL", "LINKEDIN_PASSWORD", "LinkedIn"),
    "indeed":   ("INDEED_EMAIL",   "INDEED_PASSWORD",   "Indeed"),
}

PLACEHOLDER_LABELS = {
    "phone", "telephone", "mobile", "puhelin", "puhelinnumero",
    "salary", "palkka", "palkkatoive", "expected salary", "compensation",
}

# ── .env helpers ──────────────────────────────────────────────────────────────

def load_env_file():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def save_env_var(key, value):
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f'{key}="{value}"'
            updated = True
            break
    if not updated:
        lines.append(f'{key}="{value}"')
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def ensure_credentials(platform):
    if platform not in CRED_MAP:
        return None, None
    email_key, pass_key, label = CRED_MAP[platform]
    email    = os.environ.get(email_key)
    password = os.environ.get(pass_key)
    if not email or not password:
        print(f"\n[{label}] Credentials needed — saving to {ENV_FILE} for future runs.\n")
    if not email:
        email = input(f"  {label} email: ").strip()
        save_env_var(email_key, email)
    if not password:
        password = getpass.getpass(f"  {label} password: ")
        save_env_var(pass_key, password)
    return email, password


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_platform(url):
    for platform, patterns in PLATFORM_PATTERNS.items():
        for p in patterns:
            if p in url:
                return platform
    return "generic"


def session_file(platform):
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_DIR / f"{platform}_session.json"


def needs_relogin(page, platform):
    url = page.url
    if platform == "linkedin":
        return any(k in url for k in ("login", "authwall", "checkpoint", "uas/login"))
    if platform == "indeed":
        return "login" in url or "signin" in url
    return False


def normalize(text):
    """Lowercase, strip punctuation — for fuzzy label matching."""
    return re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()


def is_placeholder(label_text):
    norm = normalize(label_text)
    return any(kw in norm for kw in PLACEHOLDER_LABELS)


def build_answers_map(answers):
    """Return {normalized_label: entry} for fast fuzzy lookup."""
    return {normalize(a["label"]): a for a in answers}


def find_answer(label_text, answers_map):
    """Find the best matching answer entry for a given label text."""
    norm = normalize(label_text)
    if norm in answers_map:
        return answers_map[norm]
    # Substring match — label contains key or key contains label
    for key, entry in answers_map.items():
        if key and (key in norm or norm in key):
            return entry
    return None


# ── Field filling ─────────────────────────────────────────────────────────────

def fill_element(element, answer_text, field_type):
    """Fill a single form element with the answer."""
    try:
        tag = element.evaluate("el => el.tagName.toLowerCase()")
        itype = (element.get_attribute("type") or "text").lower()

        if tag == "select":
            # Try exact option text first, then partial
            opts = element.query_selector_all("option")
            best = None
            for opt in opts:
                opt_text = opt.inner_text().strip()
                if normalize(opt_text) == normalize(answer_text):
                    best = opt_text
                    break
            if not best:
                for opt in opts:
                    opt_text = opt.inner_text().strip()
                    if normalize(answer_text) in normalize(opt_text):
                        best = opt_text
                        break
            if best:
                element.select_option(label=best)
        elif tag == "textarea" or itype in ("text", "email", "url", "search"):
            element.triple_click()
            element.fill(answer_text)
        elif itype == "tel":
            element.triple_click()
            element.fill(answer_text)
        elif itype == "number":
            digits = re.sub(r"[^\d]", "", answer_text)
            if digits:
                element.triple_click()
                element.fill(digits)
        elif itype == "checkbox":
            if answer_text.lower() in ("yes", "true", "1", "kyllä"):
                element.check()
        elif itype == "radio":
            element.check()
    except Exception as e:
        pass  # Best-effort — don't crash on one bad field


def fill_visible_fields(page, answers_map):
    """Fill all visible labeled form fields on the current page state."""
    filled = []
    skipped = []

    for label_el in page.query_selector_all("label"):
        label_text = label_el.inner_text().strip()
        if not label_text or len(label_text) > 300:
            continue

        if is_placeholder(label_text):
            skipped.append(label_text)
            continue

        entry = find_answer(label_text, answers_map)
        if not entry or entry.get("is_placeholder"):
            skipped.append(label_text)
            continue

        answer_text = entry.get("answer", "").strip()
        if not answer_text:
            skipped.append(label_text)
            continue

        for_id = label_el.get_attribute("for")
        field = None
        if for_id:
            field = page.query_selector(f"#{for_id}")
        if not field:
            # Try next sibling input/select/textarea
            try:
                field = label_el.evaluate_handle(
                    "el => el.nextElementSibling"
                ).as_element()
                if field:
                    tag = field.evaluate("el => el.tagName.toLowerCase()")
                    if tag not in ("input", "select", "textarea"):
                        field = None
            except Exception:
                field = None

        if field:
            fill_element(field, answer_text, entry.get("type", "text"))
            filled.append(label_text)

    # Also handle aria-label / placeholder fields not covered by <label>
    for sel in ["textarea[aria-label]", "input[aria-label]"]:
        for el in page.query_selector_all(sel):
            aria = (el.get_attribute("aria-label") or "").strip()
            if not aria or is_placeholder(aria):
                continue
            entry = find_answer(aria, answers_map)
            if entry and not entry.get("is_placeholder") and entry.get("answer"):
                fill_element(el, entry["answer"], entry.get("type", "text"))
                filled.append(aria)

    return filled, skipped


# ── LinkedIn login ────────────────────────────────────────────────────────────

def login_linkedin(page, email, password):
    print("  Logging in to LinkedIn...")
    page.goto("https://www.linkedin.com/login", wait_until="networkidle")
    time.sleep(1)
    page.fill("#username", email)
    page.fill("#password", password)
    page.click('[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    if any(k in page.url for k in ("checkpoint", "challenge", "verification")):
        print()
        print("  LinkedIn requires verification. Complete it in the browser, then press Enter here.")
        input("  Press Enter when verified: ")


# ── LinkedIn Easy Apply filler ────────────────────────────────────────────────

def fill_linkedin(page, job_url, context, email, password, answers_map):
    spath = session_file("linkedin")

    page.goto(job_url, wait_until="networkidle")
    time.sleep(2)

    if needs_relogin(page, "linkedin"):
        login_linkedin(page, email, password)
        context.storage_state(path=str(spath))
        page.goto(job_url, wait_until="networkidle")
        time.sleep(2)

    # Click Easy Apply
    easy_apply = None
    for sel in [
        'button.jobs-apply-button',
        'button[data-control-name="jobdetails_topcard_inapply"]',
        'button:has-text("Easy Apply")',
        'button:has-text("Hae helposti")',
    ]:
        try:
            easy_apply = page.query_selector(sel)
            if easy_apply:
                break
        except Exception:
            pass

    if not easy_apply:
        print("  No Easy Apply button found on this listing.")
        return False

    easy_apply.click()
    time.sleep(2)

    step = 0
    total_filled = []

    while step < 15:
        step += 1
        time.sleep(1.2)

        # Check for submit button — we're at the review step, stop here
        submit_btn = page.query_selector(
            'button[aria-label="Submit application"], '
            'button:has-text("Submit application"), '
            'button:has-text("Lähetä hakemus")'
        )
        if submit_btn:
            print(f"\n  Reached review step after {step} steps. {len(total_filled)} fields filled.")
            print("\n" + "=" * 60)
            print("  REVIEW YOUR APPLICATION IN THE BROWSER")
            print("  When satisfied, click 'Submit application'.")
            print("=" * 60)
            if total_filled:
                print(f"\n  Auto-filled: {', '.join(total_filled[:8])}" +
                      (f" + {len(total_filled)-8} more" if len(total_filled) > 8 else ""))
            return True

        # Fill visible fields on this step
        filled, skipped = fill_visible_fields(page, answers_map)
        total_filled.extend(filled)
        if filled:
            print(f"  Step {step}: filled {len(filled)} field(s): {', '.join(filled[:4])}" +
                  ("…" if len(filled) > 4 else ""))
        if skipped:
            print(f"           skipped {len(skipped)} (placeholder/unmatched): {', '.join(skipped[:3])}" +
                  ("…" if len(skipped) > 3 else ""))

        # Navigate to next step
        review_btn = page.query_selector(
            'button[aria-label="Review your application"], '
            'button:has-text("Review"), button:has-text("Tarkista")'
        )
        next_btn = page.query_selector(
            'button[aria-label="Continue to next step"], '
            'button:has-text("Next"), button:has-text("Seuraava"), '
            'button:has-text("Continue")'
        )

        if review_btn:
            review_btn.click()
        elif next_btn:
            next_btn.click()
        else:
            print(f"  No Next/Review button found at step {step} — stopping.")
            print("\n  Browser left open. Check the current state and submit manually.")
            return True

    print("  Reached step limit — stopping.")
    return True


# ── Generic form filler ───────────────────────────────────────────────────────

def fill_generic(page, apply_url, answers_map):
    page.goto(apply_url, wait_until="networkidle")
    time.sleep(2)

    # If still on a listing page, try to follow the Apply button
    if apply_url == page.url or "apply" not in page.url.lower():
        for sel in [
            'a:has-text("Apply now")', 'a:has-text("Apply")',
            'a:has-text("Hae nyt")', 'a:has-text("Hae paikkaa")',
            'a[href*="apply"]',
        ]:
            try:
                el = page.query_selector(sel)
                if el:
                    href = el.get_attribute("href")
                    if href:
                        dest = href if href.startswith("http") else urljoin(apply_url, href)
                        page.goto(dest, wait_until="networkidle")
                        time.sleep(2)
                    break
            except Exception:
                pass

    filled, skipped = fill_visible_fields(page, answers_map)

    print(f"\n  Filled {len(filled)} field(s): {', '.join(filled[:6])}" +
          (f" + {len(filled)-6} more" if len(filled) > 6 else ""))
    if skipped:
        print(f"  Skipped {len(skipped)} (placeholder/unmatched): {', '.join(skipped[:4])}" +
              ("…" if len(skipped) > 4 else ""))

    # Find submit button — scroll to it so it's visible, but don't click
    submit_btn = None
    for sel in [
        'button[type="submit"]', 'input[type="submit"]',
        'button:has-text("Submit")', 'button:has-text("Send")',
        'button:has-text("Lähetä")', 'button:has-text("Hae")',
    ]:
        try:
            submit_btn = page.query_selector(sel)
            if submit_btn:
                submit_btn.scroll_into_view_if_needed()
                break
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("  REVIEW YOUR APPLICATION IN THE BROWSER")
    if submit_btn:
        print("  Submit button is visible — click it when ready.")
    else:
        print("  Locate the submit button and click when ready.")
    print("=" * 60)

    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global PRIVATE_DIR, ENV_FILE, SESSION_DIR

    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id",      nargs="+", required=True,
                        help="One or more job IDs to fill sequentially")
    parser.add_argument("--private-dir", default=str(PRIVATE_DIR))
    args = parser.parse_args()

    PRIVATE_DIR = Path(args.private_dir)
    ENV_FILE    = PRIVATE_DIR / ".env"
    SESSION_DIR = PRIVATE_DIR / "sessions"

    load_env_file()

    job_ids = args.job_id
    total   = len(job_ids)
    results = []  # (job_id, status, note)

    # Prompt for credentials once upfront (saved on first use, silent after)
    # Detect if any job needs LinkedIn/Indeed so we prompt before opening browsers
    platforms_needed = set()
    for job_id in job_ids:
        f = PRIVATE_DIR / "Resumes" / job_id / f"{job_id}_answers.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            platforms_needed.add(d.get("platform", "generic"))
    for platform in platforms_needed:
        ensure_credentials(platform)

    for idx, job_id in enumerate(job_ids, 1):
        print(f"\n{'=' * 60}")
        print(f"  Job {idx} of {total}  —  {job_id}")
        print(f"{'=' * 60}")

        answers_file = PRIVATE_DIR / "Resumes" / job_id / f"{job_id}_answers.json"
        if not answers_file.exists():
            print(f"  SKIP: {answers_file} not found — run /tailor-resume first.")
            results.append((job_id, "skipped", "no answers file"))
            continue

        data      = json.loads(answers_file.read_text(encoding="utf-8"))
        apply_url = data.get("apply_url") or data.get("job_url", "")
        platform  = data.get("platform", detect_platform(apply_url))
        answers   = data.get("answers", [])

        if not answers:
            print(f"  SKIP: Answers file is empty — re-run /tailor-resume.")
            results.append((job_id, "skipped", "empty answers"))
            continue

        print(f"  Platform : {platform}")
        print(f"  Answers  : {len(answers)} fields")
        print(f"  URL      : {apply_url}")

        answers_map = build_answers_map(answers)
        spath       = session_file(platform)
        has_session = platform in CRED_MAP and spath.exists()
        email, password = (os.environ.get(CRED_MAP[platform][0]),
                           os.environ.get(CRED_MAP[platform][1])) \
                          if platform in CRED_MAP else (None, None)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                ctx_opts = dict(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                if has_session:
                    ctx_opts["storage_state"] = str(spath)

                context = browser.new_context(**ctx_opts)
                page    = context.new_page()

                try:
                    if platform == "linkedin":
                        fill_linkedin(page, apply_url, context, email, password, answers_map)
                    else:
                        fill_generic(page, apply_url, answers_map)

                    print()
                    remaining = total - idx
                    if remaining > 0:
                        prompt = (f"  Submit in the browser, then press Enter to open "
                                  f"Job {idx + 1} of {total}  (or type 's' to skip this one): ")
                    else:
                        prompt = "  Submit in the browser, then press Enter to finish: "

                    response = input(prompt).strip().lower()
                    status   = "skipped" if response == "s" else "submitted"

                except KeyboardInterrupt:
                    print("\n  Interrupted.")
                    status = "interrupted"
                finally:
                    browser.close()

        except Exception as e:
            print(f"  ERROR: {e}")
            status = "error"
            results.append((job_id, status, str(e)))
            continue

        results.append((job_id, status, ""))

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  Done — {total} job(s) processed")
    print(f"{'=' * 60}")
    for job_id, status, note in results:
        icon = "✓" if status == "submitted" else ("–" if status == "skipped" else "✗")
        print(f"  {icon}  {job_id}  {status}" + (f"  ({note})" if note else ""))


if __name__ == "__main__":
    main()
