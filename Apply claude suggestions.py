"""
apply_claude_suggestions.py — Antigravity Code-Apply Agent
===========================================================
Runs as a background agent (or one-shot) alongside the Antigravity swarm.

WHAT IT DOES:
  1. Watches ANTIGRAVITY_CHAT_FILE for a new Claude response
  2. Parses every fenced code block prefixed with  # FILE: <path>
  3. Writes those files to disk (creating directories as needed)
  4. Runs the Git agent logic to commit + push to GitHub
  5. Writes APPLY_SIGNAL_FILE = "DONE" so claude_desktop_agent_v6 can continue
  6. Resets and waits for the next iteration

DROP THIS FILE at the project root and add it to AntigravityMasterAgent.agents:
  "CLAUDE_APPLY": "apply_claude_suggestions.py"
"""

import os
import re
import sys
import time
import subprocess

# ──────────────── CONFIG ──────────────────────────────────────────────────────

ANTIGRAVITY_CHAT_FILE = "data/logs/claude_suggestions_pending.txt"
APPLY_SIGNAL_FILE     = "data/logs/apply_done.txt"
ERROR_LOG_FILE        = "data/logs/error_log.txt"
POLL_INTERVAL         = 5   # seconds between checks

# ──────────────── CONFIG UTF-8 FOR WINDOWS ────────────────────────────────────

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ──────────────── HELPERS ─────────────────────────────────────────────────────

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def parse_claude_suggestions(text: str) -> dict[str, str]:
    """
    Parse Claude's response into {relative_file_path: file_content}.

    Expected format (produced by the v6 review prompt):
        # FILE: path/to/file.py
        ```python
        <full file content>
        ```

    Works for any language fence (```python, ```javascript, plain ``` etc.)
    """
    result: dict[str, str] = {}

    # Match every block like:
    #   # FILE: some/path.py\n```...\n<content>\n```
    pattern = re.compile(
        r"#\s*FILE:\s*([^\n]+)\n```[^\n]*\n(.*?)```",
        re.DOTALL
    )

    for match in pattern.finditer(text):
        file_path = match.group(1).strip().replace("\\", "/")
        content   = match.group(2)  # keep trailing newline
        result[file_path] = content
        log(f"   📄 Parsed: {file_path} ({len(content)} chars)")

    return result


def apply_files(files: dict[str, str]) -> list[str]:
    """Write each file to disk. Returns list of successfully written paths."""
    written = []
    for rel_path, content in files.items():
        try:
            abs_path = os.path.abspath(rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            log(f"   ✅ Written: {rel_path}")
            written.append(rel_path)
        except Exception as e:
            log(f"   ❌ Failed to write {rel_path}: {e}")
            log_error(f"apply_claude_suggestions write error for {rel_path}: {e}")
    return written


def git_commit_and_push(changed_files: list[str]) -> bool:
    """Stage changed files, commit, and push to origin/master."""
    try:
        # Stage only the changed files (safer than `git add .`)
        for f in changed_files:
            subprocess.run(["git", "add", f], check=True)

        commit_msg = (
            f"🤖 Claude-suggested improvements — {len(changed_files)} file(s) updated\n\n"
            "Applied automatically by apply_claude_suggestions.py (Antigravity v6 loop)"
        )
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push", "origin", "master"], check=True)
        log("🐙 Pushed to GitHub.")
        return True
    except subprocess.CalledProcessError as e:
        log(f"❌ Git error: {e}")
        log_error(f"Git push failed: {e}")
        return False


def log_error(msg: str):
    """Append an error to the error log so the healing agent can see it."""
    os.makedirs(os.path.dirname(ERROR_LOG_FILE), exist_ok=True)
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} — {msg}\n")


def signal_done():
    """Write the apply-done signal so claude_desktop_agent_v6 can continue."""
    os.makedirs(os.path.dirname(APPLY_SIGNAL_FILE), exist_ok=True)
    with open(APPLY_SIGNAL_FILE, "w") as f:
        f.write("DONE")
    log(f"🏁 Wrote signal: {APPLY_SIGNAL_FILE}")


def clear_handoff():
    """Clear the handoff file after processing so we don't re-apply."""
    with open(ANTIGRAVITY_CHAT_FILE, "w") as f:
        f.write("")


# ──────────────── MAIN AGENT LOOP ─────────────────────────────────────────────

def run():
    log("🦖 [CLAUDE APPLY AGENT] Running. Watching for Claude suggestions...")
    log(f"   Handoff file : {ANTIGRAVITY_CHAT_FILE}")
    log(f"   Signal file  : {APPLY_SIGNAL_FILE}")
    os.makedirs("data/logs", exist_ok=True)

    while True:
        try:
            # ── Check if there is a pending Claude response ──────────────────
            if not os.path.exists(ANTIGRAVITY_CHAT_FILE):
                time.sleep(POLL_INTERVAL)
                continue

            with open(ANTIGRAVITY_CHAT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                time.sleep(POLL_INTERVAL)
                continue

            # ── We have content — process it ─────────────────────────────────
            log("💡 New Claude suggestions detected! Parsing...")

            # Quick sanity check: is this a "no changes" message?
            if "no_changes_needed" in content.lower():
                log("✅ Claude says no changes needed. Signalling done.")
                clear_handoff()
                signal_done()
                time.sleep(POLL_INTERVAL)
                continue

            files = parse_claude_suggestions(content)

            if not files:
                log("⚠️  No parseable code blocks found in Claude's response.")
                log("   (Claude may have responded with plain text only.)")
                # Still signal done so the loop isn't stuck
                clear_handoff()
                signal_done()
                time.sleep(POLL_INTERVAL)
                continue

            log(f"📝 Applying {len(files)} file(s)...")
            written = apply_files(files)

            if written:
                git_commit_and_push(written)
            else:
                log("⚠️  No files were written — nothing to commit.")

            # ── Clear handoff and signal v6 agent ────────────────────────────
            clear_handoff()
            signal_done()
            log("🔄 Ready for next iteration.\n")

        except Exception as e:
            log(f"❌ Agent error: {e}")
            log_error(f"apply_claude_suggestions agent error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
