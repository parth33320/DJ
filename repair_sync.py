import os
import re

def repair_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Generic pattern to catch sync_github damage
    # try:\n    try:\n    import/from ...\nexcept ...:\n    ...\nexcept ...:\n    ...
    # Note: Using non-greedy and dotall to handle variations
    
    # regex to find the double-try mess
    # We want to catch the specific pattern of try: try: indented_import except: fallback except: fallback
    pattern = re.compile(r'try:\s+try:\s+(import|from)\s+([^\n]+)\s+except\s*([^:]*):\s+([^\n]+)\s+except\s*([^:]*):\s+[^\n]+', re.MULTILINE)
    
    def replacer(match):
        keyword = match.group(1)
        module = match.group(2)
        ex_type = match.group(3) or "Exception"
        fallback = match.group(4)
        return f'try:\n    {keyword} {module}\nexcept {ex_type}:\n    {fallback}'

    new_content = pattern.sub(replacer, content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

def walk_and_repair(root_dir):
    repaired = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                if repair_file(path):
                    repaired.append(path)
    return repaired

if __name__ == "__main__":
    repaired_files = walk_and_repair('.')
    print(f"Repaired {len(repaired_files)} files:")
    for f in repaired_files:
        print(f" - {f}")
