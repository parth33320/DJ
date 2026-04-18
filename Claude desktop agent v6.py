"""
Claude Desktop Agent v6 - Self-Improving Loop
==============================================
WHAT THIS DOES:
  1. Bundles the entire project into a repomix-style .txt file
  2. Opens a FRESH Claude Desktop chat for every iteration
  3. Uploads the bundle and asks Claude to suggest code fixes/improvements
  4. Pastes Claude's response back into the Antigravity chat (via file handoff)
  5. Triggers Antigravity agents to apply the changes and push to GitHub
  6. Re-bundles the updated project and loops until Claude says "no changes needed"
  7. If the app crashes mid-loop, asks Claude to fix the specific error, then continues

HOW TO RUN:
  python scratch/claude_desktop_agent_v6.py

DEPENDENCIES (pip install):
  pyautogui pygetwindow pyperclip subprocess hashlib

CONFIG (edit the constants below to match your screen layout):
  CLAUDE_WINDOW_TITLE   - Window title to find Claude Desktop
  ANTIGRAVITY_CHAT_FILE - Shared file path used to hand off Claude's response
                          to the Antigravity agents
  BUNDLE_SCRIPT         - Path to your repomix / bundler script
  BUNDLE_OUTPUT         - The .txt file repomix produces
  MAX_ITERATIONS        - Safety cap on the loop
  CLAUDE_RESPONSE_WAIT  - Seconds to wait for Claude to finish responding
  PLUS_MENU_WAIT        - Seconds to wait after clicking the + button
  UPLOAD_WAIT           - Seconds to wait for file to upload
"""

import os
import sys
import time
import hashlib
import subprocess
import pyautogui
import pygetwindow as gw
import pyperclip

# ─────────────────────────── CONFIG ───────────────────────────────────────────

CLAUDE_WINDOW_TITLE   = "Claude"           # Substring of Claude Desktop window title
BUNDLE_SCRIPT         = "scratch/bundler.py"  # Repomix / bundler script (produces the .txt)
BUNDLE_OUTPUT         = "project_bundle.txt"  # The file we upload to Claude
ANTIGRAVITY_CHAT_FILE = "data/logs/claude_suggestions_pending.txt"  # Shared handoff file
APPLY_SIGNAL_FILE     = "data/logs/apply_done.txt"   # Antigravity writes this when done
ERROR_LOG_FILE        = "data/logs/error_log.txt"    # Healing agent watches this

MAX_ITERATIONS        = 12   # Safety cap
CLAUDE_RESPONSE_WAIT  = 90   # seconds to wait for Claude to finish
PLUS_MENU_WAIT        = 2    # seconds after clicking +
UPLOAD_WAIT           = 12   # seconds after file dialog
APPLY_WAIT_TIMEOUT    = 300  # max seconds to wait for agents to apply changes

# Prompt sent to Claude each iteration
REVIEW_PROMPT = (
    "You are a senior Python engineer reviewing the Antigravity DJ project. "
    "Analyze every file in the uploaded bundle. "
    "Identify bugs, broken imports, missing error handling, and any improvement opportunities. "
    "For EACH change, output a fenced code block with the FULL updated file content prefixed by "
    "a comment line: # FILE: <relative/path/to/file.py>\n"
    "If no changes are needed, reply with exactly: NO_CHANGES_NEEDED\n"
    "Do not include any explanation outside the code blocks. Be precise."
)

# Prompt sent when a runtime error is detected
ERROR_PROMPT_TEMPLATE = (
    "The Antigravity DJ project crashed with the following error:\n\n"
    "{error}\n\n"
    "Analyze the uploaded project bundle and provide a fix. "
    "Output a fenced code block for every file that needs to change, prefixed by: "
    "# FILE: <relative/path/to/file.py>\n"
    "If no code change is needed (e.g. missing data file), explain in plain text."
)

# ──────────────────────────────────────────────────────────────────────────────

pyautogui.FAILSAFE = False


# ─────────────────── HELPERS ──────────────────────────────────────────────────

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def file_hash(path: str) -> str:
    """SHA-256 of a file, used to detect whether Claude changed anything."""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def bundle_project() -> bool:
    """Re-run the bundler so the .txt reflects the latest code."""
    log("📦 Re-bundling project...")
    try:
        result = subprocess.run(
            [sys.executable, BUNDLE_SCRIPT],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            log(f"✅ Bundle ready: {BUNDLE_OUTPUT}")
            return True
        else:
            log(f"❌ Bundle failed:\n{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log("❌ Bundle timed out.")
        return False
    except Exception as e:
        log(f"❌ Bundle error: {e}")
        return False


def get_claude_window():
    """Find and activate the Claude Desktop window."""
    wins = [w for w in gw.getAllWindows() if CLAUDE_WINDOW_TITLE in w.title]
    if not wins:
        log(f"❌ No window containing '{CLAUDE_WINDOW_TITLE}' found.")
        return None
    return wins[0]


def open_new_chat(win) -> bool:
    """
    Click 'New Chat' in Claude Desktop.
    Coordinates are relative to the window — adjust if your layout differs.
    """
    try:
        win.activate()
        win.restore()
    except Exception:
        pass
    time.sleep(1.5)

    left, top, width, height = win.left, win.top, win.width, win.height

    # "New Chat" button is typically top-left of the sidebar
    new_chat_x = left + 80
    new_chat_y = top + 55
    pyautogui.click(new_chat_x, new_chat_y)
    log(f"🆕 Clicked New Chat at ({new_chat_x}, {new_chat_y})")
    time.sleep(2)
    return True


def upload_file_to_claude(win, file_path: str) -> bool:
    """
    Open the file picker via the + button and upload file_path.
    Adjust pixel offsets if your Claude Desktop layout is different.
    """
    left, top, width, height = win.left, win.top, win.width, win.height
    full_path = os.path.abspath(file_path)

    if not os.path.exists(full_path):
        log(f"❌ File not found for upload: {full_path}")
        return False

    # Click the + (paperclip / add files) button
    plus_x = left + 315
    plus_y = top + height - 75
    pyautogui.click(plus_x, plus_y)
    log(f"📎 Clicked + at ({plus_x}, {plus_y})")
    time.sleep(PLUS_MENU_WAIT)

    # Click "Add files or photos" in the popup menu
    menu_x = plus_x + 60
    menu_y = plus_y - 340
    pyautogui.click(menu_x, menu_y)
    log(f"📁 Clicked 'Add files' at ({menu_x}, {menu_y})")
    time.sleep(2)

    # Type the path into the Windows file dialog and press Enter
    pyautogui.write(full_path, interval=0.02)
    pyautogui.press("enter")
    log(f"⬆️  Uploading {full_path}...")
    time.sleep(UPLOAD_WAIT)
    return True


def send_prompt_to_claude(win, prompt: str):
    """Type a prompt into the Claude chat box and press Enter."""
    left, top, width, height = win.left, win.top, win.width, win.height

    # Click chat input area (bottom-center)
    pyautogui.click(left + width // 2, top + height - 50)
    time.sleep(0.5)

    # Use clipboard paste to handle special characters safely
    pyperclip.copy(prompt)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.press("enter")
    log("📨 Prompt sent. Waiting for Claude...")


def extract_claude_response(win) -> str:
    """
    Wait for Claude to finish, then Ctrl+A / Ctrl+C the full chat text.
    Returns whatever is on the clipboard.
    """
    time.sleep(CLAUDE_RESPONSE_WAIT)

    left, top, width, height = win.left, win.top, win.width, win.height
    pyautogui.click(left + width // 2, top + height // 2)
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.8)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.8)

    text = pyperclip.paste()
    log(f"📋 Captured {len(text)} chars from Claude.")
    return text


def query_claude(prompt: str, bundle_path: str = BUNDLE_OUTPUT) -> str | None:
    """
    Full flow: open new chat → upload bundle → send prompt → extract response.
    Returns the raw response text, or None on failure.
    """
    win = get_claude_window()
    if not win:
        return None

    if not open_new_chat(win):
        return None

    if not upload_file_to_claude(win, bundle_path):
        return None

    send_prompt_to_claude(win, prompt)
    response = extract_claude_response(win)
    return response if response else None


# ─────────────── ANTIGRAVITY HANDOFF ─────────────────────────────────────────

def has_code_changes(claude_response: str) -> bool:
    """Return True if Claude provided code blocks (i.e. there are changes to apply)."""
    if not claude_response:
        return False
    lower = claude_response.lower()
    # Claude signals no changes with this exact phrase
    if "no_changes_needed" in lower:
        return False
    # At least one fenced code block
    return "```" in claude_response


def hand_off_to_antigravity(claude_response: str):
    """
    Write Claude's response to the shared handoff file.
    The Antigravity agents (or apply_claude_suggestions.py) watch this file.
    """
    os.makedirs(os.path.dirname(ANTIGRAVITY_CHAT_FILE), exist_ok=True)

    # Clear the apply-done signal before handing off
    if os.path.exists(APPLY_SIGNAL_FILE):
        os.remove(APPLY_SIGNAL_FILE)

    with open(ANTIGRAVITY_CHAT_FILE, "w", encoding="utf-8") as f:
        f.write(claude_response)

    log(f"📝 Suggestions written to {ANTIGRAVITY_CHAT_FILE}")
    log("⏳ Waiting for Antigravity agents to apply changes and push to GitHub...")


def wait_for_antigravity_to_finish() -> bool:
    """
    Poll until Antigravity writes APPLY_SIGNAL_FILE, or we time out.
    Returns True on success, False on timeout.
    """
    deadline = time.time() + APPLY_WAIT_TIMEOUT
    while time.time() < deadline:
        if os.path.exists(APPLY_SIGNAL_FILE):
            with open(APPLY_SIGNAL_FILE, "r") as f:
                signal = f.read().strip()
            if signal in ("DONE", "APPLIED"):
                log("✅ Antigravity agents finished applying changes.")
                return True
        time.sleep(5)
    log(f"⏰ Timed out waiting for Antigravity ({APPLY_WAIT_TIMEOUT}s).")
    return False


# ─────────────── BUG / CRASH HANDLER ─────────────────────────────────────────

def get_latest_error() -> str | None:
    """
    Read the last line(s) of the error log that appeared since the previous check.
    Returns the error string or None if log is empty / unchanged.
    """
    if not os.path.exists(ERROR_LOG_FILE):
        return None
    try:
        with open(ERROR_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        return lines[-1] if lines else None
    except Exception:
        return None


def clear_error_log():
    if os.path.exists(ERROR_LOG_FILE):
        with open(ERROR_LOG_FILE, "w") as f:
            f.write("")


def ask_claude_to_fix_bug(error: str) -> str | None:
    """Send the crash error to a fresh Claude chat and get a fix."""
    log(f"🐛 Crash detected: {error[:120]}...")
    prompt = ERROR_PROMPT_TEMPLATE.format(error=error)
    return query_claude(prompt)


# ─────────────── MAIN LOOP ────────────────────────────────────────────────────

def self_improving_loop():
    log("🚀 Antigravity Self-Improving Loop started.")
    log(f"   Max iterations : {MAX_ITERATIONS}")
    log(f"   Bundle file    : {BUNDLE_OUTPUT}")
    log(f"   Handoff file   : {ANTIGRAVITY_CHAT_FILE}")
    log(f"   Apply signal   : {APPLY_SIGNAL_FILE}")
    print()

    iteration = 0

    # ── Pre-flight: make sure Claude Desktop is running ──────────────────────
    if not get_claude_window():
        log("❌ Please open Claude Desktop before running this script.")
        sys.exit(1)

    # ── Clear old error log so stale errors don't trigger a false alarm ──────
    clear_error_log()

    while iteration < MAX_ITERATIONS:
        iteration += 1
        log(f"━━━━━━━━━━━━━━━  ITERATION {iteration} / {MAX_ITERATIONS}  ━━━━━━━━━━━━━━━")

        # ── 1. Bundle the project ────────────────────────────────────────────
        if not bundle_project():
            log("⚠️  Bundling failed — skipping this iteration.")
            time.sleep(10)
            continue

        bundle_hash_before = file_hash(BUNDLE_OUTPUT)

        # ── 2. Ask Claude for improvements ───────────────────────────────────
        log("🤖 Querying Claude Desktop for code improvements...")
        response = query_claude(REVIEW_PROMPT)

        if not response:
            log("❌ No response from Claude. Retrying next iteration.")
            time.sleep(15)
            continue

        # ── 3. Check if Claude has suggestions ───────────────────────────────
        if not has_code_changes(response):
            log("🎉 Claude says NO_CHANGES_NEEDED. Loop complete!")
            break

        log(f"💡 Claude provided suggestions ({len(response)} chars). Handing off...")

        # ── 4. Hand off to Antigravity ────────────────────────────────────────
        hand_off_to_antigravity(response)

        # ── 5. Wait for agents to apply changes & push ───────────────────────
        applied = wait_for_antigravity_to_finish()
        if not applied:
            log("⚠️  Antigravity did not confirm. Continuing anyway...")

        # ── 6. Check for runtime errors ──────────────────────────────────────
        time.sleep(5)  # Give the app a moment to potentially crash
        error = get_latest_error()
        if error:
            log(f"🐛 Runtime error detected after applying changes!")
            fix_response = ask_claude_to_fix_bug(error)
            if fix_response and has_code_changes(fix_response):
                log("🔧 Claude provided a bug fix. Handing off...")
                hand_off_to_antigravity(fix_response)
                wait_for_antigravity_to_finish()
                clear_error_log()
            else:
                log("⚠️  Claude couldn't auto-fix the bug. Continuing loop...")

        # ── 7. Re-bundle and compare ──────────────────────────────────────────
        bundle_project()
        bundle_hash_after = file_hash(BUNDLE_OUTPUT)

        if bundle_hash_before == bundle_hash_after:
            log("⚠️  Bundle hash unchanged — changes may not have been written. Looping anyway.")
        else:
            log("✅ Bundle updated. Starting next review iteration...")

        time.sleep(3)

    else:
        log(f"⛔ Reached max iterations ({MAX_ITERATIONS}). Stopping.")

    log("🏁 Self-Improving Loop finished.")


# ─────────────── ENTRY POINT ─────────────────────────────────────────────────

if __name__ == "__main__":
    self_improving_loop()
