#!/usr/bin/env python3
"""
Scrape job application form questions from a job listing URL.

First run per platform: prompts for credentials interactively, saves to PRIVATE/.env,
saves Playwright session cookies. All subsequent runs are fully automatic.

Usage:
    python scrape_application.py --job-url URL --job-id ID --out-dir DIR

Output:
    {out-dir}/{job_id}_questions.json
"""

import os
import sys
import json
import time
import getpass
import argparse
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Paths (defaults; overridden by --private-dir at runtime) ──────────────────

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
    print(f"  Saved {key} to {ENV_FILE}")


# ── Credential prompting ───────────────────────────────────────────────────────

def ensure_credentials(platform):
    """Return (email, password). Prompts and saves if not already set."""
    if platform not in CRED_MAP:
        return None, None
    email_key, pass_key, label = CRED_MAP[platform]
    email = os.environ.get(email_key)
    password = os.environ.get(pass_key)
    if not email or not password:
        print(f"\n[{label}] First-time setup — credentials saved to {ENV_FILE}")
        print("  They won't be asked again after this.\n")
    if not email:
        email = input(f"  {label} email: ").strip()
        save_env_var(email_key, email)
    if not password:
        password = getpass.getpass(f"  {label} password: ")
        save_env_var(pass_key, password)
    return email, password


# ── Platform detection ─────────────────────────────────────────────────────────

def detect_platform(url):
    for platform, patterns in PLATFORM_PATTERNS.items():
        for p in patterns:
            if p in url:
                return platform
    return "generic"


# ── Session management ─────────────────────────────────────────────────────────

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


# ── Form extraction helpers ───────────────────────────────────────────────────

def extract_form_fields(page):
    """Extract all visible form questions from the current page state."""
    seen = set()
    questions = []

    def add(label, ftype, options=None, required=False):
        label = label.strip()
        if not label or label in seen or len(label) > 400:
            return
        seen.add(label)
        questions.append({
            "label": label,
            "type": ftype,
            "options": options or [],
            "required": required,
        })

    # Labels → associated fields
    for label_el in page.query_selector_all("label"):
        text = label_el.inner_text().strip()
        for_id = label_el.get_attribute("for")
        ftype = "text"
        options = []
        required = False

        if for_id:
            field = page.query_selector(f"#{for_id}")
            if field:
                tag = field.evaluate("el => el.tagName.toLowerCase()")
                req = field.get_attribute("required")
                required = req is not None
                if tag == "select":
                    ftype = "select"
                    options = [
                        o.inner_text().strip()
                        for o in page.query_selector_all(f"#{for_id} option")
                        if o.inner_text().strip()
                    ]
                elif tag == "textarea":
                    ftype = "textarea"
                else:
                    ftype = field.get_attribute("type") or "text"

        add(text, ftype, options, required)

    # Standalone inputs/textareas with aria-label or placeholder
    for sel in ["textarea", "input[aria-label]", "input[placeholder]"]:
        for el in page.query_selector_all(sel):
            text = (el.get_attribute("aria-label") or el.get_attribute("placeholder") or "").strip()
            tag = el.evaluate("el => el.tagName.toLowerCase()")
            ftype = "textarea" if tag == "textarea" else (el.get_attribute("type") or "text")
            add(text, ftype)

    return questions


def fill_required_dummy(page):
    """Fill required empty fields with placeholder values so 'Next' is clickable."""
    for inp in page.query_selector_all("input[required]:not([type='hidden'])"):
        try:
            if not inp.input_value():
                itype = inp.get_attribute("type") or "text"
                if itype in ("text", "search"):
                    inp.fill("N/A")
                elif itype == "email":
                    inp.fill("test@example.com")
                elif itype == "tel":
                    inp.fill("+358000000000")
                elif itype == "number":
                    inp.fill("1")
                elif itype == "checkbox":
                    inp.check()
        except Exception:
            pass
    for ta in page.query_selector_all("textarea[required]"):
        try:
            if not ta.input_value():
                ta.fill("N/A")
        except Exception:
            pass


# ── LinkedIn scraper ───────────────────────────────────────────────────────────

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
        print("  LinkedIn is asking for verification (email/phone/captcha).")
        print("  Complete it in the browser window, then press Enter here.")
        input("  Press Enter when you have verified and can see your LinkedIn feed: ")


def scrape_linkedin(page, job_url, context, email, password):
    spath = session_file("linkedin")

    page.goto(job_url, wait_until="networkidle")
    time.sleep(2)

    if needs_relogin(page, "linkedin"):
        login_linkedin(page, email, password)
        context.storage_state(path=str(spath))
        print(f"  Session saved → {spath}")
        page.goto(job_url, wait_until="networkidle")
        time.sleep(2)

    # Find Easy Apply button
    easy_apply = None
    for sel in [
        'button[data-control-name="jobdetails_topcard_inapply"]',
        'button.jobs-apply-button',
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
        return [], page.url

    easy_apply.click()
    time.sleep(2)

    all_questions = []
    step = 0

    while step < 15:
        step += 1
        time.sleep(1.2)
        step_questions = extract_form_fields(page)
        for q in step_questions:
            if q["label"] not in [x["label"] for x in all_questions]:
                q["step"] = step
                all_questions.append(q)

        # Check if we're on the review/submit step
        review_btn = page.query_selector(
            'button[aria-label="Review your application"], button:has-text("Review"), button:has-text("Tarkista")'
        )
        submit_btn = page.query_selector(
            'button[aria-label="Submit application"], button:has-text("Submit application")'
        )
        if submit_btn:
            print(f"  Reached submit step — NOT submitting. Collected {len(all_questions)} questions.")
            break

        next_btn = page.query_selector(
            'button[aria-label="Continue to next step"], button:has-text("Next"), '
            'button:has-text("Seuraava"), button:has-text("Continue")'
        )
        if review_btn:
            review_btn.click()
            time.sleep(1.2)
            continue
        if next_btn:
            fill_required_dummy(page)
            next_btn.click()
            time.sleep(1.5)
        else:
            break

    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    return all_questions, page.url


# ── Generic / Duunitori / Greenhouse / Lever scraper ─────────────────────────

def scrape_generic(page, job_url):
    page.goto(job_url, wait_until="networkidle")
    time.sleep(2)

    apply_url = job_url

    # Try to find and follow an Apply link
    for sel in [
        'a:has-text("Apply now")', 'a:has-text("Apply")',
        'a:has-text("Hae nyt")', 'a:has-text("Hae paikkaa")', 'a:has-text("Hae")',
        'a[href*="apply"]', 'a[href*="application"]',
        'button:has-text("Apply")', 'button:has-text("Hae")',
    ]:
        try:
            el = page.query_selector(sel)
            if el:
                href = el.get_attribute("href")
                if href:
                    apply_url = href if href.startswith("http") else urljoin(job_url, href)
                    page.goto(apply_url, wait_until="networkidle")
                    time.sleep(2)
                else:
                    el.click()
                    page.wait_for_load_state("networkidle")
                    apply_url = page.url
                    time.sleep(2)
                break
        except Exception:
            pass

    questions = extract_form_fields(page)
    return questions, apply_url


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global PRIVATE_DIR, ENV_FILE, SESSION_DIR

    parser = argparse.ArgumentParser(description="Scrape job application form questions.")
    parser.add_argument("--job-url",     required=True, help="Job listing URL")
    parser.add_argument("--job-id",      required=True, help="Job ID")
    parser.add_argument("--out-dir",     required=True, help="Output directory")
    parser.add_argument("--private-dir", default=str(PRIVATE_DIR),
                        help="Path to private repo (for .env and sessions)")
    args = parser.parse_args()

    PRIVATE_DIR = Path(args.private_dir)
    ENV_FILE    = PRIVATE_DIR / ".env"
    SESSION_DIR = PRIVATE_DIR / "sessions"

    load_env_file()

    platform = detect_platform(args.job_url)
    print(f"Detected platform: {platform}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.job_id}_questions.json"

    spath = session_file(platform)
    has_session = platform in CRED_MAP and spath.exists()

    # Browser is visible if this is a first-time login (user may need to verify)
    headless = has_session

    email, password = ensure_credentials(platform)

    questions = []
    apply_url = args.job_url

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
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
        page = context.new_page()

        try:
            if platform == "linkedin":
                questions, apply_url = scrape_linkedin(page, args.job_url, context, email, password)
                # Save session after first-time login
                if not has_session:
                    context.storage_state(path=str(spath))
                    print(f"  Session saved → {spath}")
            else:
                questions, apply_url = scrape_generic(page, args.job_url)

        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
        finally:
            browser.close()

    result = {
        "job_id":         args.job_id,
        "job_url":        args.job_url,
        "apply_url":      apply_url,
        "platform":       platform,
        "question_count": len(questions),
        "questions":      questions,
    }

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(questions)} questions → {out_path}")

    if questions:
        print("\nQuestions found:")
        for i, q in enumerate(questions, 1):
            opts = f" [{', '.join(q['options'][:3])}{'…' if len(q['options']) > 3 else ''}]" if q.get("options") else ""
            step = f" (step {q['step']})" if "step" in q else ""
            print(f"  {i}. [{q['type']}] {q['label']}{opts}{step}")
    else:
        print("  No questions extracted (login wall, no Easy Apply, or unsupported ATS).")
        sys.exit(1)


if __name__ == "__main__":
    main()
