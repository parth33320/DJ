import subprocess
import os
import re
import sys

# Set encoding for output to avoid UnicodeEncodeError on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def strip_emojis(text):
    # Remove things like "📄 " or other emojis at the start of paths
    # The emoji "📄" is often at the start
    text = text.replace('📄 ', '').replace('📄', '')
    return text.strip()

def apply_fixes(content, filename):
    if filename.endswith('.py'):
        # Apply the try-except fixes I did earlier to avoid ImportError crashes
        content = content.replace('import torch', 'try:\n    import torch\nexcept ImportError:\n    torch = None\n')
        content = content.replace('torch.cuda.is_available()', '(False if torch is None else torch.cuda.is_available())')
        content = content.replace('import whisper', 'try:\n    import whisper\nexcept ImportError:\n    whisper = None\n')
        content = content.replace('import pronouncing', 'try:\n    import pronouncing\nexcept:\n    pronouncing = None')
        content = content.replace('from phonemizer import phonemize', 'try:\n    from phonemizer import phonemize\nexcept:\n    phonemize = None')
        content = content.replace('import obsws_python as obs', 'try:\n    import obsws_python as obs\nexcept:\n    obs = None')
        
    return content

def sync():
    # Tell git not to quote paths with special characters
    subprocess.run(['git', 'config', 'core.quotepath', 'false'], check=True)

    print("Fetching file list from origin/main...")
    result = subprocess.run(['git', 'ls-tree', '-r', 'origin/main'], capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print("Error fetching file list")
        return

    lines = result.stdout.strip().split('\n')
    for line in lines:
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        
        raw_path = parts[1].strip('"') # Git might still surround it with quotes
        clean_path = strip_emojis(raw_path)
        
        # Skip files with names like "Open Command Prompt..." on Windows
        if "Open Command Prompt" in clean_path or "Install " in clean_path or clean_path.startswith("python install"):
            print(f"Skipping potentially problematic file: {clean_path}")
            continue

        print(f"Syncing {clean_path}...")
        
        # Get content
        # Use subprocess with shell=True for complex paths or just pass it directly
        # raw_path might contain spaces or special chars
        content_result = subprocess.run(['git', 'show', f'origin/main:{raw_path}'], capture_output=True, encoding='utf-8', errors='ignore')
        if content_result.returncode != 0:
            # Try once more with double quotes around path just in case
            content_result = subprocess.run(['git', 'show', f'origin/main:"{raw_path}"'], capture_output=True, encoding='utf-8', errors='ignore')
            if content_result.returncode != 0:
                print(f"Failed to get content for {raw_path}")
                continue
            
        content = content_result.stdout
        
        # Apply fixes
        content = apply_fixes(content, clean_path)
        
        # For config.yaml, we want to keep the playlist URL
        if clean_path == 'config.yaml' and os.path.exists(clean_path):
            with open(clean_path, 'r', encoding='utf-8') as f:
                old_conf = f.read()
            if 'youtube:' in content and 'playlist_url:' in old_conf:
                m = re.search(r'playlist_url:\s*"([^"]+)"', old_conf)
                if m:
                    current_url = m.group(1)
                    content = re.sub(r'playlist_url:\s*"[^"]*"', f'playlist_url: "{current_url}"', content)

        # Create directories
        target_dir = os.path.dirname(os.path.abspath(clean_path))
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        
        with open(clean_path, 'w', encoding='utf-8') as f:
            f.write(content)

    print("\nSync complete!")
    print("Applied local dependency fixes (try/except) to prevent crashes.")

if __name__ == "__main__":
    sync()
