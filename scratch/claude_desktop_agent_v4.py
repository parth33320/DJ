import pyautogui
import pygetwindow as gw
import time
import os
import pyperclip

pyautogui.FAILSAFE = False

def run_claude_query(bundle_path, prompt):
    # 1. Bring Claude to front
    claude_wins = gw.getWindowsWithTitle("Claude")
    if not claude_wins:
        print("[ERROR] Claude window not found.")
        return None
    
    win = claude_wins[0]
    try:
        win.activate()
        win.restore()
    except:
        pass
    time.sleep(2)
    
    left, top, width, height = win.left, win.top, win.width, win.height
    print(f"[INFO] Claude Active at: {left}, {top}")

    # 2. Start New Chat
    pyautogui.click(left + 80, top + 90)
    time.sleep(2)
    print("[INFO] Started New Chat")

    # 3. Click Plus (Add files)
    pyautogui.click(left + 315, top + height - 75)
    time.sleep(1)
    print("[INFO] Clicking Plus button...")

    # 4. Click 'Add files or photos' in the popup
    # It appears roughly 280-300px above the plus button
    pyautogui.click(left + 380, top + height - 370)
    time.sleep(2)
    print("[INFO] Clicking 'Add files or photos'...")

    # 5. Type path in Windows Dialog
    full_path = os.path.abspath(bundle_path)
    if not os.path.exists(full_path):
        print(f"[ERROR] File not found: {full_path}")
        return None
        
    pyautogui.write(full_path, interval=0.01)
    pyautogui.press('enter')
    time.sleep(8) # Wait for upload
    print(f"[INFO] Uploaded {bundle_path}")

    # 6. Type Prompt and Send
    pyautogui.write(prompt, interval=0.01)
    pyautogui.press('enter')
    print("[INFO] Prompt Sent")

    # 7. Wait for response
    print("[INFO] Waiting 70 seconds for Claude's analysis...")
    time.sleep(70)

    # 8. Extract response
    print("[INFO] Extracting response...")
    pyautogui.click(left + width // 2, top + height // 2)
    time.sleep(1)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(1)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(1)
    
    suggestions = pyperclip.paste()
    return suggestions

if __name__ == "__main__":
    prompt = (
        "Analyze this project and suggest technical improvements. "
        "Return the response as a series of code blocks for specific files. "
        "Include the full file path and the code block. "
        "I will apply them automatically, so be precise."
    )
    res = run_claude_query("project_bundle.txt", prompt)
    if res:
        with open('scratch/claude_suggestions.txt', 'w', encoding='utf-8') as f:
            f.write(res)
        print("[SUCCESS] Suggestions saved to scratch/claude_suggestions.txt")
    else:
        print("[ERROR] Failed to get suggestions.")
