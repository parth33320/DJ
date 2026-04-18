import os

def bundle_project(root_dir, output_file):
    # Files to include
    extensions = ('.py', '.yaml', '.md', '.html', '.css', '.json', '.js')
    
    # Dirs to skip
    exclude_dirs = {'.git', '__pycache__', 'node_modules', 'venv', 'env', 'data', 'scratch', 'logs', '.gemini'}
    # Files to skip
    exclude_files = {output_file, 'project_snapshot.txt', 'project_bundle.txt', 'bundler.py', 'claude_desktop_agent.py', 'find_claude_win.py', 'capture_claude.py'}

    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write("PRO AI DJ PROJECT SOURCE CODE DUMP\n")
        outfile.write("==================================\n\n")
        
        for root, dirs, files in os.walk(root_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file.endswith(extensions) and file not in exclude_files:
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, root_dir)
                    
                    outfile.write(f"\n{'='*80}\n")
                    outfile.write(f"FILE: {rel_path}\n")
                    outfile.write(f"{'='*80}\n")
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as infile:
                            lines = infile.readlines()
                            for i, line in enumerate(lines, 1):
                                outfile.write(f"{i:4}: {line}")
                    except Exception as e:
                        outfile.write(f"ERROR READING FILE: {e}\n")
                    
                    outfile.write("\n\n")

if __name__ == "__main__":
    bundle_project('.', 'project_bundle.txt')
    print("Project bundled successfully into project_bundle.txt")
