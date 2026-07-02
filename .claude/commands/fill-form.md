Fill one or more job application forms using a freshly generated Claude vision agent.

Job IDs to process: **$ARGUMENTS**

Parse `$ARGUMENTS` as a space-separated list of job IDs. Process each one sequentially.

---

## Path resolution (do once before the loop)

**`PRIVATE`** — resolve in order, stop at first hit:
1. `$env:MANJU_PRIVATE_DIR` if set
2. A sibling of the current directory whose name contains "private" (case-insensitive):
   ```powershell
   $parent  = Split-Path (Get-Location).Path -Parent
   $PRIVATE = Get-ChildItem $parent -Directory |
              Where-Object { $_.Name -match 'private' } |
              Select-Object -First 1 -ExpandProperty FullName
   ```

Print: `PRIVATE : <resolved path>`

---

## Loop — for each JOB_ID

### Step 1 — Read the answers file

Read `PRIVATE\Resumes\JOB_ID\JOB_ID_answers.json`.

If the file does not exist, print:
```
SKIP JOB_ID — no answers file found. Run /tailor-resume first.
```
and continue to the next job ID.

Extract:
- `APPLY_URL`  — `apply_url` field (fall back to `job_url` if absent)
- `ANSWERS`    — the `answers` array (list of objects with label/type/answer/is_placeholder)

If `APPLY_URL` is empty or `ANSWERS` is empty, print an error and skip.

---

### Step 2 — Write the agent script

Write the following Python script to `PRIVATE\Resumes\JOB_ID\fill_JOB_ID.py`.

Substitute:
- `<<<JOB_ID>>>` → the actual job ID string
- `<<<APPLY_URL>>>` → the actual apply URL string
- `<<<ANSWERS_JSON>>>` → the answers array serialised as a compact JSON literal (use `json.dumps(answers_list)`)

```python
#!/usr/bin/env python3
"""Claude vision agent — form filler for <<<JOB_ID>>>"""

import base64, json, os, time
from pathlib import Path
from playwright.sync_api import sync_playwright

# ── Answers baked in ───────────────────────────────────────────────────────────
APPLY_URL = "<<<APPLY_URL>>>"
ANSWERS   = <<<ANSWERS_JSON>>>

MAX_STEPS = 50
VIEWPORT  = {"width": 1280, "height": 900}
MODEL     = "claude-sonnet-4-6"

# ── Auth ───────────────────────────────────────────────────────────────────────

def _load_auth() -> None:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return
    # Try .env files
    for candidate in [
        Path(__file__).parent.parent.parent / ".env",   # PRIVATE/.env
        Path(".env"),
    ]:
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY=") and "=" in line:
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        os.environ["ANTHROPIC_API_KEY"] = key
                        print(f"  [auth] ANTHROPIC_API_KEY loaded from {candidate}")
                        return
    # Try Claude Code OAuth token
    creds_file = Path.home() / ".claude" / ".credentials.json"
    if creds_file.exists():
        try:
            creds = json.loads(creds_file.read_text(encoding="utf-8"))
            oauth = creds.get("claudeAiOauth", {})
            token = oauth.get("accessToken", "")
            if token:
                os.environ["ANTHROPIC_AUTH_TOKEN"] = token
                print("  [auth] using Claude Code OAuth token")
                return
        except Exception as e:
            print(f"  [auth] could not read credentials: {e}")
    raise RuntimeError("No Anthropic credentials found. Set ANTHROPIC_API_KEY or open Claude Code.")


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "screenshot",
        "description": "Capture the current browser viewport as a PNG and return it.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "click",
        "description": "Click at pixel coordinates (x, y).",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "click_selector",
        "description": "Click an element by CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "type_text",
        "description": "Type text into the currently focused element (preserves existing content).",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "replace_text",
        "description": "Select all content in the focused field and replace it with new text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "set_field",
        "description": (
            "Set a field value by CSS selector via jQuery/DOM events. "
            "Reliable for GravityForms fields that ignore keyboard events."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "value":    {"type": "string"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "choose_option",
        "description": "Select a <select> dropdown option by its visible text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text":     {"type": "string"},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "tick_checkbox",
        "description": "Check a checkbox by CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "press_key",
        "description": "Press a keyboard key or combination, e.g. Tab, Enter, Control+a.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "scroll_page",
        "description": "Scroll the page up or down by a given number of pixels.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["down", "up"]},
                "pixels":    {"type": "number"},
            },
            "required": ["direction", "pixels"],
        },
    },
    {
        "name": "attach_files",
        "description": "Attach one or more files to a file-input element.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the file input (preferred over coordinates)",
                },
                "x": {"type": "number", "description": "Fallback x coordinate near the input"},
                "y": {"type": "number", "description": "Fallback y coordinate near the input"},
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Absolute file paths to attach",
                },
            },
            "required": ["paths"],
        },
    },
    {
        "name": "done",
        "description": (
            "Call when every field is filled and the form is ready for human review. "
            "Do NOT click Submit — the user does that manually."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary":  {"type": "string", "description": "Brief description of what was filled"},
                "skipped":  {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields deliberately left blank (placeholders, salary, etc.)",
                },
            },
            "required": ["summary"],
        },
    },
]


# ── Browser tool executor ──────────────────────────────────────────────────────

def run_tool(page, name: str, inp: dict) -> tuple[bool, str]:
    """Execute a tool call. Returns (keep_going, status_text)."""
    try:
        if name == "screenshot":
            return True, "page refreshed"

        elif name == "click":
            page.mouse.click(inp["x"], inp["y"])
            time.sleep(0.7)
            return True, f"clicked ({inp['x']:.0f}, {inp['y']:.0f})"

        elif name == "click_selector":
            el = page.query_selector(inp["selector"])
            if el:
                el.scroll_into_view_if_needed()
                el.click()
                time.sleep(0.7)
                return True, f"clicked {inp['selector']}"
            return True, f"selector not found: {inp['selector']}"

        elif name == "type_text":
            page.keyboard.type(inp["text"], delay=40)
            time.sleep(0.3)
            return True, f"typed {inp['text'][:60]!r}"

        elif name == "replace_text":
            page.keyboard.press("Control+a")
            time.sleep(0.1)
            page.keyboard.press("Delete")
            time.sleep(0.1)
            page.keyboard.type(inp["text"], delay=40)
            time.sleep(0.3)
            return True, f"replaced with {inp['text'][:60]!r}"

        elif name == "set_field":
            sel = inp["selector"].replace("'", "\\'")
            val = inp["value"].replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            page.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{sel}');
                    if (!el) return;
                    if (window.jQuery) {{
                        jQuery(el).val('{val}').trigger('input').trigger('change');
                    }} else {{
                        el.value = '{val}';
                        el.dispatchEvent(new Event('input',  {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                }})()
            """)
            time.sleep(0.3)
            return True, f"set_field {inp['selector']} = {inp['value'][:60]!r}"

        elif name == "choose_option":
            el = page.query_selector(inp["selector"])
            if el:
                el.select_option(label=inp["text"])
                time.sleep(0.4)
                return True, f"selected {inp['text']!r} in {inp['selector']}"
            return True, f"select not found: {inp['selector']}"

        elif name == "tick_checkbox":
            el = page.query_selector(inp["selector"])
            if el:
                if not el.is_checked():
                    el.check()
                time.sleep(0.3)
                return True, f"ticked {inp['selector']}"
            # jQuery fallback
            safe = inp["selector"].replace("'", "\\'")
            page.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{safe}');
                    if (!el) return;
                    if (window.jQuery) {{
                        jQuery(el).prop('checked', true).trigger('change');
                    }} else {{
                        el.checked = true;
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                }})()
            """)
            time.sleep(0.3)
            return True, f"ticked (jQuery) {inp['selector']}"

        elif name == "press_key":
            page.keyboard.press(inp["key"])
            time.sleep(0.4)
            return True, f"pressed {inp['key']}"

        elif name == "scroll_page":
            px = inp["pixels"] * (-1 if inp["direction"] == "up" else 1)
            page.evaluate(f"window.scrollBy(0, {px})")
            time.sleep(0.3)
            return True, f"scrolled {inp['direction']} {inp['pixels']}px"

        elif name == "attach_files":
            paths = [p for p in inp.get("paths", []) if Path(p).exists()]
            if not paths:
                return True, "attach_files: none of the paths exist on disk"
            file_input = None
            sel = inp.get("selector", "")
            if sel:
                file_input = page.query_selector(sel)
            if not file_input and "x" in inp and "y" in inp:
                file_input = page.evaluate_handle(f"""
                    (function() {{
                        var el = document.elementFromPoint({inp['x']}, {inp['y']});
                        for (var i = 0; i < 6 && el; i++) {{
                            if (el.tagName === 'INPUT' && el.type === 'file') return el;
                            el = el.parentElement;
                        }}
                        return null;
                    }})()
                """).as_element()
            if not file_input:
                file_input = page.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(paths)
                time.sleep(0.7)
                return True, f"attached {[Path(p).name for p in paths]}"
            return True, "attach_files: no file input found"

        elif name == "done":
            return False, inp.get("summary", "done")

    except Exception as e:
        return True, f"ERROR in {name}: {e}"

    return True, f"unknown tool: {name}"


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM = f"""You are filling a job application form on behalf of Manju Krishna Haridas.

TARGET URL: {APPLY_URL}

ANSWERS TO USE:
{json.dumps(ANSWERS, indent=2, ensure_ascii=False)}

HOW TO WORK:
1. After every action you receive a fresh screenshot. Use it to verify the action worked and find the next field.
2. If a cookie/consent banner is visible, dismiss it first (click its Accept/Hyväksy button).
3. Ignore live-chat widgets — they do not block the form.
4. For text, email, tel, textarea fields: click the field, then use replace_text to set the value. After typing, take a screenshot to confirm the value is visible. If GravityForms cleared it, use set_field with the element's CSS selector.
5. For <select> dropdowns: use choose_option with the selector and visible option text.
6. For checkboxes: use tick_checkbox.
7. For file uploads: use attach_files with the absolute paths from the answers JSON.
8. Skip any field where is_placeholder is true.
9. When all non-placeholder fields are filled, call done(). Do NOT click Submit.
10. The form may be in Finnish — match fields by meaning, not exact wording.
"""

NUDGE = (
    "You must call a tool to continue filling the form. "
    "Do not respond with plain text. "
    "Use replace_text, set_field, choose_option, tick_checkbox, attach_files, or done. "
    "Here is the current page:"
)


# ── Agent loop ─────────────────────────────────────────────────────────────────

def run_agent(page, client) -> bool:
    import anthropic

    def snap() -> str:
        return base64.standard_b64encode(page.screenshot()).decode()

    def img(b64: str) -> dict:
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}

    messages = [
        {
            "role": "user",
            "content": [img(snap()), {"type": "text", "text": "Here is the form. Please fill it in now."}],
        }
    ]

    nudge_count = 0
    max_nudges  = 3

    for step in range(1, MAX_STEPS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [(b.name, b.input, b.id) for b in response.content if b.type == "tool_use"]
        text_out   = " ".join(b.text for b in response.content if b.type == "text")

        if not tool_calls:
            if text_out:
                print(f"  [step {step}] model said: {text_out[:200]}")
            if nudge_count < max_nudges:
                nudge_count += 1
                print(f"  [nudge {nudge_count}/{max_nudges}]")
                messages.append({
                    "role": "user",
                    "content": [img(snap()), {"type": "text", "text": NUDGE}],
                })
                continue
            print("  Agent stopped calling tools — giving up.")
            return False

        nudge_count = 0
        results     = []
        keep_going  = True

        for name, inp, call_id in tool_calls:
            print(f"  [step {step}] {name}({str(inp)[:80]})")
            keep_going, msg = run_tool(page, name, inp)
            print(f"             → {msg}")
            current_snap = snap()
            results.append((call_id, msg, current_snap))
            if not keep_going:
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call_id,
                            "content": [{"type": "text", "text": msg}, img(current_snap)],
                        }
                    ],
                })
                return True

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": [{"type": "text", "text": msg}, img(snap_b64)],
                }
                for call_id, msg, snap_b64 in results
            ],
        })

    print(f"  Reached {MAX_STEPS}-step limit.")
    return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    _load_auth()
    import anthropic
    client = anthropic.Anthropic()

    print(f"\n{'=' * 60}")
    print(f"  Job  : <<<JOB_ID>>>")
    print(f"  URL  : {APPLY_URL}")
    print(f"  Model: {MODEL}")
    print(f"  Fields: {len(ANSWERS)}")
    print(f"{'=' * 60}\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            viewport=VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(APPLY_URL, wait_until="networkidle")
        time.sleep(2)

        success = run_agent(page, client)

        if success:
            print("\n" + "=" * 60)
            print("  FORM FILLED — review everything in the browser, then click Submit.")
            print("=" * 60)
        else:
            print("\n  Agent could not complete the form — check the browser and fill any remaining fields manually.")

        input("\n  Press Enter when you are done (browser will close): ")
        browser.close()


if __name__ == "__main__":
    main()
```

---

### Step 3 — Run the script

```powershell
python "PRIVATE\Resumes\JOB_ID\fill_JOB_ID.py"
```

Wait for it to complete before moving to the next job ID. The browser stays open until the user presses Enter.

---

## End of loop

After all jobs are processed, print a summary:

| Job ID | Status |
|--------|--------|
| abc123 | done   |
| def456 | skipped — no answers file |
