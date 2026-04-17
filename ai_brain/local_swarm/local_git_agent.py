import os
import time
import subprocess
import requests
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# =================================================================
# 🦖 LOCAL GIT AGENT
# =================================================================
# Automatically pushes code changes to GitHub to save Gemini credits.
# =================================================================

UPDATE_INTERVAL = 60 # 1 minute
NTFY_TOPIC = "antigravity_dj_updates"

def send_update(msg):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg)
    except:
        pass

def run_git_loop():
    print("🐙 [LOCAL GIT AGENT] Started. Monitoring for code changes...")
    
    while True:
        try:
            # Check for changes
            status = subprocess.check_output(["git", "status", "--porcelain"])
            
            if status:
                print("📝 Changes detected! Pushing to GitHub...")
                subprocess.run(["git", "add", "."], check=True)
                subprocess.run(["git", "commit", "-m", "🦖 Auto-sync: Innovative logic update from Antigravity"], check=True)
                subprocess.run(["git", "push", "origin", "master"], check=True)
                
                send_update("📦 Code successfully pushed to GitHub! 🦖")
                print("✅ Push complete.")
            else:
                print("😴 No code changes. Sleeping.")
                
        except Exception as e:
            print(f"❌ Git Agent Error: {e}")
            
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    run_git_loop()
