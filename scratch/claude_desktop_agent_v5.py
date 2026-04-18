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
    win.activate()
    win.restore()
    time.sleep(2)
    
    left, top, width, height = win.left, win.top, win.width, win.height
    print(f"[INFO] Window: {left}, {top}, {width}, {height}")

    # 2. Click sidebar to ensure focus
    pyautogui.click(left + 100, top + 100)
    time.sleep(1)

    # 3. Click Plus button (bottom left)
    plus_x = left + 315
    plus_y = top + height - 75
    pyautogui.click(plus_x, plus_y)
    print(f"[INFO] Clicked Plus at {plus_x}, {plus_y}")
    time.sleep(2)

    # 4. Click 'Add files or photos' (Top of the menu)
    # The menu is ~350px tall. We click near its top.
    menu_item_x = plus_x + 60
    menu_item_y = plus_y - 340
    pyautogui.click(menu_item_x, menu_item_y)
    print(f"[INFO] Clicked 'Add files' at {menu_item_x}, {menu_item_y}")
    time.sleep(2)

    # 5. Type path in Windows Dialog
    full_path = os.path.abspath(bundle_path)
    pyautogui.write(full_path, interval=0.01)
    pyautogui.press('enter')
    time.sleep(10) # Heavy wait for upload
    print(f"[INFO] Uploaded {bundle_path}")

    # 6. Type Prompt and Send
    pyautogui.write(prompt, interval=0.01)
    pyautogui.press('enter')
    print("[INFO] Prompt Sent")

    # 7. Wait for response
    print("[INFO] Waiting 75 seconds for Claude...")
    time.sleep(75)

    # 8. Extract response
    pyautogui.click(left + width // 2, top + height // 2)
    time.sleep(1)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(1)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(1)
    
    return pyperclip.paste()

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
