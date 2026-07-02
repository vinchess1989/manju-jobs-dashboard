#!/usr/bin/env python3
"""
Agent-based job application form filler.

Claude (or a local vision/text LLM via LM Studio) controls a browser to fill
application forms. After every action the agent sees the current page state —
either as a screenshot (vision mode) or a DOM text snapshot (--no-vision mode).

Usage:
    python fill_agent.py --job-id ID              # Claude API, vision (default)
    python fill_agent.py --job-id ID --local      # LM Studio, vision model
    python fill_agent.py --job-id ID --local --no-vision  # LM Studio, text-only model
    python fill_agent.py --job-id ID --local --no-vision --model hermes-3-llama-3.1-8b

--no-vision replaces screenshots with a structured text dump of the form DOM,
suitable for models like Hermes 3 that don't support image inputs.

Requirements for --local:
    pip install openai
    A model loaded in LM Studio (vision for default, any for --no-vision).
"""

import ast
import json
import os
import re
import base64
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright


def _load_env(private_dir: Path) -> None:
    """
    Resolve Anthropic credentials in priority order:
      1. ANTHROPIC_API_KEY already in environment
      2. ANTHROPIC_AUTH_TOKEN already in environment
      3. PRIVATE/.env or ./.env containing ANTHROPIC_API_KEY
      4. ~/.claude/.credentials.json (Claude Code OAuth token)
    """
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return

    # .env files
    for candidate in [private_dir / ".env", Path(".env")]:
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY=") and "=" in line:
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        os.environ["ANTHROPIC_API_KEY"] = key
                        print(f"  [auth] loaded ANTHROPIC_API_KEY from {candidate}")
                        return

    # Claude Code OAuth credentials (~/.claude/.credentials.json)
    creds_file = Path.home() / ".claude" / ".credentials.json"
    if creds_file.exists():
        try:
            import json as _json, time as _time
            creds = _json.loads(creds_file.read_text(encoding="utf-8"))
            oauth  = creds.get("claudeAiOauth", {})
            token  = oauth.get("accessToken", "")
            expiry = oauth.get("expiresAt", 0)
            if token:
                if expiry and expiry / 1000 < _time.time():
                    print("  [auth] Claude Code OAuth token is expired — re-open Claude Code to refresh")
                else:
                    os.environ["ANTHROPIC_AUTH_TOKEN"] = token
                    print("  [auth] using Claude Code OAuth token from ~/.claude/.credentials.json")
                    return
        except Exception as e:
            print(f"  [auth] could not read credentials file: {e}")

# ── Text-to-tool-call parser (for models like Hermes 3 that output tool calls
#    as plain text instead of using the structured API) ────────────────────────

def parse_text_tool_calls(text: str) -> list:
    """
    Hermes 3 (and some other local models) ignores the OpenAI function-calling
    API and instead writes tool calls inline as:
        [tool_name {'key': 'value', ...}]
    This parser extracts those calls and returns them as (name, input, fake_id)
    tuples, matching the format returned by the structured API path.
    """
    tool_names = {t["name"] for t in TOOLS}
    # Build regex that anchors on known tool names to avoid false matches
    name_pat = "|".join(re.escape(n) for n in sorted(tool_names, key=len, reverse=True))
    start_re  = re.compile(r"\[(" + name_pat + r")\s+(\{)")

    calls = []
    for m in start_re.finditer(text):
        name      = m.group(1)
        brace_pos = m.start(2)

        # Walk forward tracking bracket depth, respecting string literals
        depth    = 0
        in_str   = False
        str_char = None
        i        = brace_pos
        end      = -1
        while i < len(text):
            ch = text[i]
            if in_str:
                if ch == "\\" :
                    i += 2          # skip escaped character
                    continue
                if ch == str_char:
                    in_str = False
            else:
                if ch in ('"', "'"):
                    in_str   = True
                    str_char = ch
                elif ch in ("{", "["):
                    depth += 1
                elif ch in ("}", "]"):
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            i += 1

        if end == -1:
            continue

        dict_str = text[brace_pos:end]
        try:
            inp = ast.literal_eval(dict_str)
            if isinstance(inp, dict):
                calls.append((name, inp, f"txt_{len(calls)}"))
        except Exception:
            pass

    return calls


# ── Constants ─────────────────────────────────────────────────────────────────

PRIVATE_DIR  = Path(r"C:\Users\vinee\Manju_jobs_private")
CLAUDE_MODEL = "claude-sonnet-4-6"
LOCAL_URL    = "http://localhost:1234/v1"
MAX_STEPS    = 50
VIEWPORT     = {"width": 1280, "height": 900}

# ── Tool definitions (Anthropic format — converted for OpenAI in LocalBackend) ─

TOOLS = [
    {
        "name": "screenshot",
        "description": "Refresh the current page state (screenshot or DOM dump).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "click",
        "description": "Click at pixel coordinates (x, y) on the page.",
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
        "description": "Click an element by CSS selector (useful when coordinates are unknown).",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "type",
        "description": "Type text into the currently focused element.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "clear_and_type",
        "description": "Select all text in the focused field and replace it with new text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "fill_field",
        "description": (
            "Set a field's value by CSS selector using jQuery (works for GravityForms). "
            "Use this when type/clear_and_type leaves the field empty."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector, e.g. #input_1_3"},
                "value":    {"type": "string"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "select_option",
        "description": "Choose an option in a <select> element by visible text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text":     {"type": "string", "description": "Visible option text to select"},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "check",
        "description": "Tick a checkbox by CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "key",
        "description": "Press a key or combination, e.g. Tab, Enter, Escape, Control+a.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the page up or down.",
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
        "name": "upload_files",
        "description": "Attach files to a file-input field by CSS selector or coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the file input (preferred)"},
                "x":        {"type": "number", "description": "Fallback: x coordinate near the input"},
                "y":        {"type": "number", "description": "Fallback: y coordinate near the input"},
                "paths":    {
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
            "Call when the form is fully filled and ready for human review. "
            "Do NOT submit — leave that to the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary":  {"type": "string"},
                "unfilled": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields intentionally left blank (placeholders)",
                },
            },
            "required": ["summary"],
        },
    },
]

# ── Page capture helpers ──────────────────────────────────────────────────────

def snap(page) -> str:
    """Base64-encoded PNG of the current viewport."""
    return base64.standard_b64encode(page.screenshot()).decode("utf-8")


def dom_snapshot(page) -> str:
    """
    Structured text dump of the page — for text-only LLMs.
    Includes: page title, visible overlays/modals, buttons, and form fields.
    """
    try:
        data = page.evaluate("""() => {
            function center(el) {
                const r = el.getBoundingClientRect();
                return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
            }
            function isVisible(el) {
                if (!el.offsetParent) return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            }
            function labelOf(el) {
                if (el.id) {
                    const lbl = document.querySelector('label[for="' + el.id + '"]');
                    if (lbl) return lbl.innerText.replace(/\\s+/g,' ').trim();
                }
                return el.getAttribute('aria-label')
                    || el.getAttribute('placeholder')
                    || el.getAttribute('name')
                    || '';
            }

            // ── Overlays / modals ────────────────────────────────────────────
            const overlaySelectors = [
                '[class*="cookie"]','[id*="cookie"]',
                '[class*="consent"]','[id*="consent"]',
                '[class*="modal"]','[id*="modal"]',
                '[class*="overlay"]','[id*="overlay"]',
                '[class*="banner"]','[id*="banner"]',
                '[role="dialog"]','[aria-modal="true"]',
            ];
            const overlayEls = new Set();
            for (const sel of overlaySelectors) {
                for (const el of document.querySelectorAll(sel)) {
                    if (isVisible(el)) overlayEls.add(el);
                }
            }
            const overlays = [];
            for (const el of overlayEls) {
                const text = el.innerText.replace(/\\s+/g,' ').trim().slice(0, 120);
                // collect clickable children
                const btns = [];
                for (const b of el.querySelectorAll('button,a,[role="button"]')) {
                    if (!isVisible(b)) continue;
                    const {x,y} = center(b);
                    const sel = b.id ? '#'+b.id : b.className ? '.'+b.className.trim().split(/\\s+/)[0] : b.tagName.toLowerCase();
                    btns.push({text: b.innerText.trim().slice(0,60), sel, x, y});
                }
                overlays.push({text, buttons: btns});
            }

            // ── Buttons (outside overlays, near top of page) ─────────────────
            const topButtons = [];
            for (const el of document.querySelectorAll('button,[role="button"]')) {
                if (!isVisible(el)) continue;
                const r = el.getBoundingClientRect();
                if (r.top > 600) continue;          // only above-the-fold buttons
                if (overlayEls.has(el.closest('[class*="cookie"],[id*="cookie"],[role="dialog"]'))) continue;
                const {x,y} = center(el);
                const sel = el.id ? '#'+el.id : el.tagName.toLowerCase();
                topButtons.push({text: el.innerText.trim().slice(0,60), sel, x, y});
            }

            // ── Form fields ───────────────────────────────────────────────────
            const fields = [];
            for (const el of document.querySelectorAll(
                'input:not([type="hidden"]), select, textarea'
            )) {
                if (!isVisible(el)) continue;
                const {x,y} = center(el);
                const base = {
                    id: el.id||'', name: el.name||'',
                    label: labelOf(el), x, y,
                };
                if (el.tagName === 'SELECT') {
                    const opts = Array.from(el.options).map(o=>o.text.trim());
                    fields.push({...base, tag:'select', value:el.value, options:opts});
                } else if (el.type==='checkbox'||el.type==='radio') {
                    fields.push({...base, tag:'input', type:el.type,
                                 value:el.checked?'CHECKED':'unchecked'});
                } else if (el.type==='file') {
                    const names = Array.from(el.files||[]).map(f=>f.name);
                    fields.push({...base, tag:'input', type:'file',
                                 value:names.join(', ')||''});
                } else {
                    fields.push({...base, tag:el.tagName.toLowerCase(),
                                 type:el.type||'', value:el.value||''});
                }
            }

            return {
                title: document.title,
                url: location.href,
                overlays,
                topButtons,
                fields,
            };
        }""")
    except Exception as e:
        return f"[dom_snapshot error: {e}]"

    lines = [f"[page: {data['title']!r}  url={data['url']}]"]

    # Overlays / cookie walls
    if data["overlays"]:
        lines.append("\n[overlays / popups detected]")
        for ov in data["overlays"]:
            lines.append(f"  text: {ov['text']!r}")
            for b in ov["buttons"]:
                lines.append(f"    button  sel={b['sel']!r}  text={b['text']!r}  @({b['x']},{b['y']})")

    # Top-of-page buttons (nav, cookie accept outside overlay, etc.)
    if data["topButtons"]:
        lines.append("\n[buttons (above fold)]")
        for b in data["topButtons"]:
            lines.append(f"  button  sel={b['sel']!r}  text={b['text']!r}  @({b['x']},{b['y']})")

    # Form fields
    lines.append("\n[form fields]")
    for f in data["fields"]:
        sel   = f"#{f['id']}" if f["id"] else f"[name={f['name']!r}]" if f["name"] else "?"
        label = f["label"][:60]
        val   = f["value"][:80]
        pos   = f"@({f['x']},{f['y']})"
        if f.get("options"):
            opts = " | ".join(f["options"][:10])
            lines.append(f"  select{sel}  label={label!r}  value={val!r}  options=[{opts}]  {pos}")
        else:
            typ = f.get("type", "")
            lines.append(f"  {f['tag']}{sel}  type={typ}  label={label!r}  value={val!r}  {pos}")

    if not data["fields"]:
        lines.append("  (no visible form fields)")

    return "\n".join(lines)


# ── Playwright tool executor ──────────────────────────────────────────────────

def execute(page, name: str, inp: dict) -> tuple[bool, str]:
    """
    Run one tool call.  Returns (keep_going, status_message).
    keep_going=False signals the agent is done.
    """
    try:
        if name == "screenshot":
            return True, "page state refreshed"

        elif name == "click":
            page.mouse.click(inp["x"], inp["y"])
            time.sleep(0.6)
            return True, f"clicked ({inp['x']:.0f}, {inp['y']:.0f})"

        elif name == "click_selector":
            sel = inp["selector"]
            el  = page.query_selector(sel)
            if el:
                el.scroll_into_view_if_needed()
                el.click()
                time.sleep(0.6)
                return True, f"clicked {sel}"
            return True, f"selector not found: {sel}"

        elif name == "type":
            page.keyboard.type(inp["text"], delay=35)
            time.sleep(0.3)
            return True, f"typed {inp['text'][:50]!r}"

        elif name == "clear_and_type":
            page.keyboard.press("Control+a")
            time.sleep(0.1)
            page.keyboard.press("Delete")
            time.sleep(0.1)
            page.keyboard.type(inp["text"], delay=35)
            time.sleep(0.3)
            return True, f"cleared and typed {inp['text'][:50]!r}"

        elif name == "fill_field":
            sel  = inp["selector"].replace("'", "\\'")
            val  = inp["value"].replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            page.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{sel}');
                    if (!el) return;
                    if (window.jQuery) {{
                        jQuery(el).val('{val}').trigger('input').trigger('change');
                    }} else {{
                        el.value = '{val}';
                        el.dispatchEvent(new Event('input',  {{bubbles:true}}));
                        el.dispatchEvent(new Event('change', {{bubbles:true}}));
                    }}
                }})()
            """)
            time.sleep(0.3)
            return True, f"fill_field {inp['selector']} = {inp['value'][:50]!r}"

        elif name == "select_option":
            sel  = inp["selector"]
            text = inp["text"]
            el   = page.query_selector(sel)
            if el:
                el.select_option(label=text)
                time.sleep(0.4)
                return True, f"selected {text!r} in {sel}"
            return True, f"select not found: {sel}"

        elif name == "check":
            sel = inp["selector"]
            el  = page.query_selector(sel)
            if el:
                if not el.is_checked():
                    el.check()
                    time.sleep(0.3)
                return True, f"checked {sel}"
            # jQuery fallback
            safe = sel.replace("'", "\\'")
            page.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{safe}');
                    if (!el) return;
                    if (window.jQuery) {{
                        jQuery(el).prop('checked', true).trigger('change');
                    }} else {{
                        el.checked = true;
                        el.dispatchEvent(new Event('change', {{bubbles:true}}));
                    }}
                }})()
            """)
            time.sleep(0.3)
            return True, f"checked (jQuery fallback) {sel}"

        elif name == "key":
            page.keyboard.press(inp["key"])
            time.sleep(0.4)
            return True, f"pressed {inp['key']}"

        elif name == "scroll":
            px = inp["pixels"] * (-1 if inp["direction"] == "up" else 1)
            page.evaluate(f"window.scrollBy(0, {px})")
            time.sleep(0.3)
            return True, f"scrolled {inp['direction']} {inp['pixels']}px"

        elif name == "upload_files":
            paths = [p for p in inp.get("paths", []) if Path(p).exists()]
            if not paths:
                return True, "upload_files: no valid paths provided"

            # Try CSS selector first
            sel = inp.get("selector", "")
            file_input = page.query_selector(sel) if sel else None

            # Fallback: elementFromPoint
            if not file_input and "x" in inp and "y" in inp:
                x, y = inp["x"], inp["y"]
                file_input = page.evaluate_handle(f"""
                    (function() {{
                        var el = document.elementFromPoint({x}, {y});
                        for (var i = 0; i < 6 && el; i++) {{
                            if (el.tagName === 'INPUT' && el.type === 'file') return el;
                            el = el.parentElement;
                        }}
                        return null;
                    }})()
                """).as_element()

            # Last resort: first file input on page
            if not file_input:
                file_input = page.query_selector('input[type="file"]')

            if file_input:
                file_input.set_input_files(paths)
                time.sleep(0.6)
                return True, f"uploaded {len(paths)} file(s): {[Path(p).name for p in paths]}"
            return True, "upload_files: no file input found"

        elif name == "done":
            return False, inp.get("summary", "done")

    except Exception as e:
        return True, f"ERROR in {name}: {e}"

    return True, f"unknown tool: {name}"


# ── Backend: Anthropic ────────────────────────────────────────────────────────

class AnthropicBackend:
    def __init__(self, system: str):
        import anthropic
        self.client   = anthropic.Anthropic()
        self.system   = system
        self.messages = []
        print(f"  [backend] Anthropic — {CLAUDE_MODEL} (vision)")

    def _img(self, b64: str) -> dict:
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}

    def add_user(self, text: str, snap: str):
        self.messages.append({
            "role": "user",
            "content": [self._img(snap), {"type": "text", "text": text}],
        })

    def add_tool_results(self, results: list):
        """results: [(call_id, msg, snap_b64)]"""
        self.messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": [
                        {"type": "text", "text": msg},
                        self._img(snap_b64),
                    ],
                }
                for call_id, msg, snap_b64 in results
            ],
        })

    def chat(self) -> tuple[list, str, str]:
        """Returns ([(name, input, id)], stop_reason, text_content)."""
        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=self.system,
            tools=TOOLS,
            messages=self.messages,
        )
        self.messages.append({"role": "assistant", "content": response.content})
        calls    = [(b.name, b.input, b.id) for b in response.content if b.type == "tool_use"]
        text_out = " ".join(b.text for b in response.content if b.type == "text")
        return calls, response.stop_reason, text_out


# ── Backend: Local LLM via LM Studio ─────────────────────────────────────────

class LocalBackend:
    def __init__(self, system: str, model: str = None, no_vision: bool = False):
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package required for --local: pip install openai")

        self.client    = OpenAI(base_url=LOCAL_URL, api_key="lm-studio")
        self.model     = model or self._detect_model()
        self.system    = system
        self.no_vision = no_vision
        self.messages  = []
        self.oai_tools = [self._to_oai(t) for t in TOOLS]
        mode = "text/DOM" if no_vision else "vision"
        print(f"  [backend] LM Studio — {self.model} ({mode})")

    def _detect_model(self) -> str:
        try:
            models = self.client.models.list()
            if models.data:
                return models.data[0].id
        except Exception:
            pass
        raise RuntimeError(
            "Could not detect a loaded model from LM Studio.\n"
            "Load a model first, or pass --model <name> explicitly."
        )

    def _to_oai(self, tool: dict) -> dict:
        return {
            "type": "function",
            "function": {
                "name":        tool["name"],
                "description": tool.get("description", ""),
                "parameters":  tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        }

    def _img(self, b64: str) -> dict:
        return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}

    def add_user(self, text: str, snap: str):
        if self.no_vision:
            # snap is DOM text
            content = [
                {"type": "text", "text": snap},
                {"type": "text", "text": text},
            ]
        else:
            # snap is b64 image
            content = [self._img(snap), {"type": "text", "text": text}]
        self.messages.append({"role": "user", "content": content})

    def add_tool_results(self, results: list):
        """Route to the correct results path based on how the last chat() call worked."""
        if getattr(self, "_text_parsed", False):
            self._add_text_results(results)
        else:
            self._add_api_results(results)

    def _add_api_results(self, results: list):
        """Standard OpenAI path: role=tool messages matched by tool_call_id."""
        for call_id, msg, _ in results:
            self.messages.append({
                "role":         "tool",
                "tool_call_id": call_id,
                "content":      msg,
            })
        snaps = [s for _, _, s in results if s]
        if not snaps:
            return
        if self.no_vision:
            self.messages.append({
                "role":    "user",
                "content": [{"type": "text", "text": f"Updated form state:\n{snaps[-1]}"}],
            })
        else:
            content = [self._img(s) for s in snaps]
            content.append({"type": "text", "text": "Updated browser state after the above actions."})
            self.messages.append({"role": "user", "content": content})

    def _add_text_results(self, results: list):
        """Fallback path: model output was plain-text tool calls, send results as user msg."""
        lines = ["Tool execution results:"]
        for _, msg, _ in results:
            lines.append(f"  {msg}")
        content = [{"type": "text", "text": "\n".join(lines)}]
        snaps = [s for _, _, s in results if s]
        if snaps:
            if self.no_vision:
                content.append({"type": "text", "text": f"Updated form state:\n{snaps[-1]}"})
            else:
                content = [self._img(s) for s in snaps] + content
        self.messages.append({"role": "user", "content": content})

    def chat(self) -> tuple[list, str, str]:
        """Returns ([(name, input, id)], stop_reason, text_content)."""
        full_messages = [{"role": "system", "content": self.system}] + self.messages
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=2048,
            tools=self.oai_tools,
            messages=full_messages,
        )
        msg         = response.choices[0].message
        stop_reason = response.choices[0].finish_reason
        text_out    = msg.content or ""

        self.messages.append({
            "role":       "assistant",
            "content":    msg.content,
            "tool_calls": msg.tool_calls or [],
        })

        # Primary path: structured API tool calls
        calls = []
        for tc in (msg.tool_calls or []):
            try:
                inp = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                inp = {}
            calls.append((tc.function.name, inp, tc.id))

        # Fallback: Hermes 3 writes tool calls as plain text
        self._text_parsed = False
        if not calls and text_out:
            parsed = parse_text_tool_calls(text_out)
            if parsed:
                calls = parsed
                self._text_parsed = True
                print(f"  [local] parsed {len(parsed)} tool call(s) from text output")

        return calls, stop_reason, text_out


# ── Agent loop ────────────────────────────────────────────────────────────────

MAX_NO_TOOL_NUDGES = 3   # how many times to nudge the model before giving up

NUDGE_MSG = (
    "You must use the provided tools to fill the form — do not respond with plain text. "
    "Call fill_field, click_selector, select_option, check, or upload_files for each field, "
    "then call done() when finished. Here is the current page state:"
)


def dismiss_chat_widgets(page) -> None:
    """Close live-chat support popups before the agent starts."""
    chat_close_selectors = [
        # Common chat widget close / minimize buttons
        'button[aria-label*="close" i]',
        'button[aria-label*="sulje" i]',
        'button[aria-label*="minimize" i]',
        '[class*="chat"] button[class*="close"]',
        '[class*="chat"] button[class*="minimiz"]',
        '[id*="chat"] button[class*="close"]',
        '.crisp-close', '.intercom-launcher-close',
        '#chat-close', '.chat-close',
    ]
    for sel in chat_close_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                time.sleep(0.4)
                print(f"  [setup] closed chat widget via {sel}")
        except Exception:
            pass


def build_system(apply_url: str, answers: list, no_vision: bool) -> str:
    answers_text = json.dumps(answers, indent=2, ensure_ascii=False)

    if no_vision:
        # ── Local text-only model (e.g. Hermes 3) ────────────────────────────
        # Gets DOM snapshots with selectors — use selector-based tools.
        return f"""You are filling a Finnish job application form on behalf of Manju Krishna Haridas.

APPLY URL: {apply_url}

ANSWERS TO USE:
{answers_text}

After each action you receive a [form state] DOM snapshot listing every visible field
with its CSS selector, label, and current value. Coordinates @(x,y) are also shown.

INSTRUCTIONS — you MUST output tool calls only, no plain text:
- Check the [overlays / popups detected] section first.
  - Dismiss ONLY real cookie banners (text about 'evästeet', 'cookies', 'tietosuoja').
  - IGNORE live-chat widgets ('Miten voimme auttaa', 'Aloita keskustelu') — they are not blocking.
- For each field in [form fields] where is_placeholder is false:
  - text/email/tel/textarea → fill_field with the selector from the DOM snapshot
  - select → select_option with selector and the matching Finnish option text
  - checkbox → check with the selector
  - file → upload_files with selector and paths from answers JSON
- Skip fields where is_placeholder is true.
- After filling all fields, call done(). Do NOT submit.
- The form is in Finnish — match by label meaning.
- Call screenshot() to refresh the DOM snapshot if needed.
"""

    else:
        # ── Claude vision mode ────────────────────────────────────────────────
        # Gets screenshots — use coordinate-based tools (click + type).
        # fill_field requires known DOM selectors which aren't visible in screenshots.
        return f"""You are filling a Finnish job application form on behalf of Manju Krishna Haridas.

APPLY URL: {apply_url}

ANSWERS TO USE:
{answers_text}

After each action you receive a screenshot. Use it to verify that values were accepted
and to find where to click next.

INSTRUCTIONS:
- If a cookie consent banner is visible, click its accept/hyväksy button first.
  Ignore live-chat support widgets — they are not blocking the form.
- To fill a text field: click on it, then use type or clear_and_type.
  After typing, take a screenshot to verify the value appears.
  If the field is empty after typing (GravityForms re-render), use clear_and_type again.
- For dropdowns: click the <select> element, then use key("ArrowDown") or click the option.
- For checkboxes: click directly on the checkbox element.
- For file uploads: use upload_files with the file paths from the answers JSON.
  Pass x/y coordinates from where you see the upload button in the screenshot.
- Skip fields where is_placeholder is true.
- When all fields are filled and verified, call done(). Do NOT click submit.
- The form is in Finnish — match fields by label meaning, not exact wording.
"""


def fill_with_agent(job_id: str, private_dir: Path, use_local: bool,
                    local_model: str, no_vision: bool) -> bool:
    answers_file = private_dir / "Resumes" / job_id / f"{job_id}_answers.json"
    if not answers_file.exists():
        print(f"  No answers file: {answers_file}")
        return False

    data      = json.loads(answers_file.read_text(encoding="utf-8"))
    apply_url = data.get("apply_url") or data.get("job_url", "")
    answers   = data.get("answers", [])

    if not apply_url or not answers:
        print("  answers.json is missing apply_url or answers list")
        return False

    print(f"  Job ID  : {job_id}")
    print(f"  URL     : {apply_url}")
    print(f"  Answers : {len(answers)} fields")

    system = build_system(apply_url, answers, no_vision)

    _load_env(private_dir)

    if use_local:
        backend = LocalBackend(system, local_model, no_vision=no_vision)
        capture = dom_snapshot if no_vision else snap
    else:
        backend = AnthropicBackend(system)
        capture = snap

    success     = False
    nudge_count = 0

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
        page.goto(apply_url, wait_until="networkidle")
        time.sleep(2)

        # Close any live-chat popups before the agent sees the page
        dismiss_chat_widgets(page)

        backend.add_user(text="Here is the form. Please fill it in now.", snap=capture(page))

        for step in range(1, MAX_STEPS + 1):
            tool_calls, stop_reason, text_out = backend.chat()

            if not tool_calls:
                if text_out:
                    print(f"  [agent step {step}] Model text (no tool calls): {text_out[:300]}")
                else:
                    print(f"  [agent step {step}] No tool calls, no text — stop_reason={stop_reason}")

                if nudge_count < MAX_NO_TOOL_NUDGES:
                    nudge_count += 1
                    print(f"  [nudge {nudge_count}/{MAX_NO_TOOL_NUDGES}] Reminding model to use tools...")
                    backend.add_user(text=NUDGE_MSG, snap=capture(page))
                    continue

                print("  Agent gave no tool calls after nudges — giving up.")
                break

            nudge_count = 0   # reset once the model starts calling tools
            results    = []
            keep_going = True

            for name, inp, call_id in tool_calls:
                print(f"  [agent step {step}] {name}({str(inp)[:80]})")
                keep_going, msg = execute(page, name, inp)
                print(f"             → {msg}")
                results.append((call_id, msg, capture(page)))
                if not keep_going:
                    success = True
                    break

            backend.add_tool_results(results)

            if not keep_going:
                break

        if success:
            print("\n" + "=" * 60)
            print("  FORM FILLED — review in the browser and click Submit.")
            print("=" * 60)
        else:
            print(f"\n  Agent did not complete the form — check the browser manually.")

        input("\n  Press Enter when done (browser will close): ")
        browser.close()

    return success


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Agent-based form filler.")
    parser.add_argument("--job-id",      nargs="+", required=True)
    parser.add_argument("--private-dir", default=str(PRIVATE_DIR))
    parser.add_argument("--local",       action="store_true",
                        help="Use LM Studio local model instead of Claude API")
    parser.add_argument("--no-vision",   action="store_true",
                        help="Replace screenshots with DOM text snapshots (for text-only models)")
    parser.add_argument("--model",       default=None,
                        help="Override model name (local mode only; default: auto-detect from LM Studio)")
    args = parser.parse_args()

    if args.no_vision and not args.local:
        parser.error("--no-vision requires --local")

    private_dir = Path(args.private_dir)
    results     = []

    for job_id in args.job_id:
        print(f"\n{'=' * 60}")
        print(f"  Filling: {job_id}")
        print(f"{'=' * 60}")
        ok = fill_with_agent(job_id, private_dir, args.local, args.model, args.no_vision)
        results.append((job_id, "done" if ok else "incomplete"))

    print(f"\n{'=' * 60}  Summary")
    for job_id, status in results:
        mark = "v" if status == "done" else "?"
        print(f"  {mark}  {job_id}  {status}")


if __name__ == "__main__":
    main()
