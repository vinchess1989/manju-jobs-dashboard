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

# Domains that are job listing aggregators (not the employer's own form).
# Only on these do we try to follow "Apply" links to the real form.
LISTING_DOMAINS = [
    "jobly.fi", "duunitori.fi", "indeed.com", "monster.com",
    "jobs.fi", "te-palvelut.fi", "tyomarkkinatori.fi", "mol.fi",
    "oikotie.fi", "rekrytointi.fi",
]

CRED_MAP = {
    "linkedin": ("LINKEDIN_EMAIL", "LINKEDIN_PASSWORD", "LinkedIn"),
    "indeed":   ("INDEED_EMAIL",   "INDEED_PASSWORD",   "Indeed"),
}

PLACEHOLDER_LABELS = {
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
    # Substring match — require at least 5 chars to avoid short Finnish words matching as suffixes
    for key, entry in answers_map.items():
        if key and len(key) >= 5 and len(norm) >= 5 and (key in norm or norm in key):
            return entry
    return None


# ── Field filling ─────────────────────────────────────────────────────────────

def jquery_set(page, field_id, answer_text, field_type):
    """Set a GravityForms field value via jQuery — the only approach GF reliably accepts."""
    safe = answer_text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    fid  = field_id.replace("'", "\\'")

    if field_type == "checkbox":
        page.evaluate(f"""
            (function() {{
                var $el = typeof jQuery !== 'undefined' ? jQuery('#{fid}') : null;
                if ($el && $el.length) {{ $el.prop('checked', true).trigger('change'); return; }}
                var el = document.getElementById('{fid}');
                if (el) {{ el.checked = true; el.dispatchEvent(new Event('change', {{bubbles:true}})); }}
            }})()
        """)
    elif field_type == "select":
        page.evaluate(f"""
            (function() {{
                var $el = typeof jQuery !== 'undefined' ? jQuery('#{fid}') : null;
                if ($el && $el.length) {{
                    $el.find('option').each(function() {{
                        if (jQuery(this).text().toLowerCase().indexOf('{safe.lower()}') !== -1) {{
                            jQuery(this).prop('selected', true);
                            $el.trigger('change');
                            return false;
                        }}
                    }});
                    return;
                }}
                var el = document.getElementById('{fid}');
                if (!el) return;
                for (var i = 0; i < el.options.length; i++) {{
                    if (el.options[i].text.toLowerCase().indexOf('{safe.lower()}') !== -1) {{
                        el.selectedIndex = i;
                        el.dispatchEvent(new Event('change', {{bubbles:true}}));
                        break;
                    }}
                }}
            }})()
        """)
    else:
        page.evaluate(f"""
            (function() {{
                if (typeof jQuery !== 'undefined') {{
                    jQuery('#{fid}').val('{safe}').trigger('input').trigger('change');
                    return;
                }}
                var el = document.getElementById('{fid}');
                if (!el) return;
                el.value = '{safe}';
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
            }})()
        """)


def fill_element(element, answer_text, field_type):
    """Playwright-level fallback fill — used for file inputs and fields without a known ID."""
    try:
        tag   = element.evaluate("el => el.tagName.toLowerCase()")
        itype = (element.get_attribute("type") or "text").lower()

        if tag == "select":
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
        elif itype == "file":
            paths    = [p.strip() for p in answer_text.split(",") if p.strip()]
            existing = [p for p in paths if Path(p).exists()]
            if existing:
                element.set_input_files(existing)
        elif tag == "textarea" or itype in ("text", "email", "url", "search", "tel", "number"):
            element.click()
            element.press("Control+a")
            element.press("Delete")
            element.press_sequentially(answer_text, delay=30)
            element.dispatch_event("input")
            element.dispatch_event("change")
        elif itype == "checkbox":
            if answer_text.lower() in ("yes", "true", "1", "kyllä"):
                element.check()
        elif itype == "radio":
            element.check()
    except Exception:
        pass


def fill_visible_fields(page, answers_map, skip_files=False):
    """Fill all visible labeled form fields on the current page state."""
    filled = []
    skipped = []

    all_labels = page.query_selector_all("label")
    print(f"  [fill] Found {len(all_labels)} <label> elements on page")

    for label_el in all_labels:
        label_text = label_el.inner_text().strip()
        if not label_text or len(label_text) > 300:
            continue

        if is_placeholder(label_text):
            print(f"  [fill]   SKIP (placeholder label): {label_text!r}")
            skipped.append(label_text)
            continue

        entry = find_answer(label_text, answers_map)
        if not entry or entry.get("is_placeholder"):
            print(f"  [fill]   SKIP (no answer match): {label_text!r}")
            skipped.append(label_text)
            continue

        answer_text = entry.get("answer", "").strip()
        if not answer_text:
            print(f"  [fill]   SKIP (empty answer): {label_text!r}")
            skipped.append(label_text)
            continue

        for_id = label_el.get_attribute("for")
        field = None

        if for_id:
            field = page.query_selector(f"#{for_id}")
            print(f"  [fill]   label={label_text!r}  for={for_id!r}  by-id={'FOUND' if field else 'MISS'}")
        else:
            print(f"  [fill]   label={label_text!r}  for=None  trying child/sibling...")

        if not field:
            # Try input nested inside the label (CF7 / WPForms style)
            try:
                field = label_el.query_selector("input:not([type='hidden']), select, textarea")
                if field:
                    print(f"  [fill]     -> found via child selector")
            except Exception as e:
                print(f"  [fill]     -> child selector error: {e}")
                field = None

        if not field:
            # Try next sibling input/select/textarea
            try:
                sib = label_el.evaluate_handle("el => el.nextElementSibling").as_element()
                if sib:
                    tag = sib.evaluate("el => el.tagName.toLowerCase()")
                    print(f"  [fill]     -> next sibling tag: {tag}")
                    if tag in ("input", "select", "textarea"):
                        field = sib
                    else:
                        print(f"  [fill]     -> sibling is <{tag}>, not an input — skipping")
                else:
                    print(f"  [fill]     -> no next sibling")
            except Exception as e:
                print(f"  [fill]     -> sibling error: {e}")
                field = None

        if not field:
            # Try sibling container that wraps the input (div.wpcf7-form-control-wrap etc.)
            try:
                parent = label_el.evaluate_handle("el => el.parentElement").as_element()
                if parent:
                    field = parent.query_selector("input:not([type='hidden']), select, textarea")
                    if field:
                        print(f"  [fill]     -> found via parent container")
                    else:
                        print(f"  [fill]     -> parent container has no matching input")
            except Exception as e:
                print(f"  [fill]     -> parent container error: {e}")
                field = None

        if field:
            ftype = entry.get("type", "text")
            if ftype == "file" and skip_files:
                print(f"  [fill]   SKIP (file, second pass): {label_text!r}")
                continue
            if ftype == "file":
                fill_element(field, answer_text, ftype)   # must use Playwright for files
            elif for_id:
                jquery_set(page, for_id, answer_text, ftype)  # jQuery for GF fields
            else:
                fill_element(field, answer_text, ftype)   # Playwright fallback (no ID)
            print(f"  [fill]   FILLED: {label_text!r} = {answer_text[:40]!r}")
            filled.append(label_text)
        else:
            print(f"  [fill]   NO FIELD FOUND for label: {label_text!r}")

    # Also handle aria-label / placeholder fields not covered by <label>
    for sel in ["textarea[aria-label]", "input[aria-label]"]:
        for el in page.query_selector_all(sel):
            aria = (el.get_attribute("aria-label") or "").strip()
            if not aria or is_placeholder(aria):
                continue
            entry = find_answer(aria, answers_map)
            if entry and not entry.get("is_placeholder") and entry.get("answer"):
                fill_element(el, entry["answer"], entry.get("type", "text"))
                print(f"  [fill]   FILLED (aria-label): {aria!r}")
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

def dismiss_chatbots(page):
    """Close common live-chat widgets that can steal focus. Best-effort."""
    selectors = [
        # Generic close buttons on chat widgets
        'button[aria-label="Close"]', 'button[aria-label="Sulje"]',
        'button[title="Close"]', 'button[title="Sulje"]',
        '[class*="chat"] button[class*="close"]',
        '[class*="chat"] button[class*="dismiss"]',
        '[id*="chat"] button[class*="close"]',
        # Common chat platforms
        '#hubspot-messages-iframe-container iframe',  # HubSpot (hide parent)
        '.intercom-lightweight-app-launcher',
        '[data-testid="close-button"]',
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                time.sleep(0.5)
        except Exception:
            pass
    # Also hide via JS as a fallback
    try:
        page.evaluate("""
            ['iframe[src*="chat"]','iframe[src*="hubspot"]','iframe[src*="intercom"]',
             '[class*="chat-widget"]','[class*="chatbot"]','[id*="chat-widget"]']
            .forEach(sel => document.querySelectorAll(sel)
                .forEach(el => el.style.display = 'none'));
        """)
    except Exception:
        pass


def accept_cookies(page):
    """Click the most common cookie-accept buttons. Best-effort, silent."""
    selectors = [
        # Generic English
        'button:has-text("Accept all")', 'button:has-text("Accept All")',
        'button:has-text("Accept cookies")', 'button:has-text("Allow all")',
        'button:has-text("Allow All")', 'button:has-text("I agree")',
        'button:has-text("OK")', 'button:has-text("Got it")',
        # Finnish
        'button:has-text("Hyväksy")', 'button:has-text("Hyväksy kaikki")',
        'button:has-text("Hyväksy evästeet")', 'button:has-text("Salli kaikki")',
        'button:has-text("Hyväksyn")', 'button:has-text("OK")',
        # Common cookie library patterns
        '#onetrust-accept-btn-handler',
        '.cc-accept', '.cc-btn.cc-allow',
        '[data-cookiebanner="accept_button"]',
        '[aria-label="Accept cookies"]',
        '[id*="accept"][id*="cookie"]',
        '[class*="accept"][class*="cookie"]',
    ]
    for sel in selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(0.8)
                return True
        except Exception:
            pass
    return False


def is_listing_page(url):
    return any(domain in url for domain in LISTING_DOMAINS)


def wait_for_gravityforms(page):
    """Wait for GravityForms to finish initializing, if present."""
    try:
        page.wait_for_function(
            "typeof jQuery !== 'undefined' && typeof gform !== 'undefined'",
            timeout=6000
        )
        # Wait for gform_post_render callbacks to finish
        page.wait_for_function(
            """() => {
                return new Promise(resolve => {
                    if (typeof jQuery === 'undefined') { resolve(true); return; }
                    jQuery(document).one('gform_post_render', () => resolve(true));
                    setTimeout(() => resolve(true), 2000);
                });
            }""",
            timeout=5000
        )
        print("  [fill] GravityForms ready")
    except Exception:
        time.sleep(2)


def fill_generic(page, apply_url, answers_map):
    page.goto(apply_url, wait_until="networkidle")
    time.sleep(2)
    accept_cookies(page)
    time.sleep(0.5)
    dismiss_chatbots(page)

    # Only follow "Apply" links when we're on a known job listing aggregator.
    # On the employer's own site the apply URL already points at the form.
    if is_listing_page(apply_url):
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

    # Wait for GravityForms to fully initialize before touching any fields
    wait_for_gravityforms(page)

    # Scroll to anchor fragment if present (e.g. #tyohakemus)
    fragment = apply_url.split("#")[-1] if "#" in apply_url else None
    if fragment:
        try:
            page.evaluate(f"""
                const el = document.getElementById('{fragment}');
                if (el) el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
            """)
            time.sleep(0.5)
        except Exception:
            pass

    # First fill pass
    filled, skipped = fill_visible_fields(page, answers_map)

    # Second fill pass — GravityForms sometimes re-renders and clears fields
    # after the first interaction; a second pass ensures values stick.
    # skip_files=True prevents uploading the same files twice.
    time.sleep(1.5)
    print("  [fill] Second pass to ensure values stuck after GravityForms re-render...")
    filled2, _ = fill_visible_fields(page, answers_map, skip_files=True)

    print(f"\n  Filled {len(filled)} field(s): {', '.join(filled[:6])}" +
          (f" + {len(filled)-6} more" if len(filled) > 6 else ""))
    if skipped:
        print(f"  Skipped {len(skipped)} (placeholder/unmatched): {', '.join(skipped[:4])}" +
              ("…" if len(skipped) > 4 else ""))

    # Scroll back to top of form so user can review from the beginning
    if fragment:
        try:
            page.evaluate(f"""
                const el = document.getElementById('{fragment}');
                if (el) el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
            """)
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("  REVIEW YOUR APPLICATION IN THE BROWSER")
    print("  Scroll down to find the submit button when ready.")
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
