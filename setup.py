"""
One-click setup script
Run this ONCE before starting the app:
    python setup.py
"""
import os
import sys
import subprocess
import yaml

def check_python():
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")

def check_ffmpeg():
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True, check=True
        )
        print("✅ FFmpeg found")
    except Exception:
        print("❌ FFmpeg not found!")
        print("   Download from: https://www.gyan.dev/ffmpeg/builds/")
        print("   Add to PATH then re-run setup.py")
        sys.exit(1)

def install_requirements():
    print("\n📦 Installing Python packages...")
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
        check=True
    )
    print("✅ Packages installed")

def create_directories():
    dirs = [
        'data/audio_cache',
        'data/stems',
        'data/metadata',
        'data/lyrics',
        'data/phonemes',
        'data/word_index',
        'data/training_data',
        'data/models',
        'data/logs',
        'data/sandbox',
        'transition_engine',
        'ai_brain/agents',
        'ai_brain/training',
        'ai_brain/models',
        'ingestion',
        'analysis',
        'visual_engine',
        'ui/web_ui/templates',
        'ui/web_ui/static',
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    # Create __init__.py files
    packages = [
        'ingestion', 'analysis', 'ai_brain',
        'ai_brain/agents', 'ai_brain/training',
        'transition_engine', 'visual_engine',
        'ui', 'ui/web_ui'
    ]
    for pkg in packages:
        init_file = os.path.join(pkg, '__init__.py')
        if not os.path.exists(init_file):
            open(init_file, 'w').close()

    print("✅ Directory structure created")

def check_config():
    if not os.path.exists('config.yaml'):
        print("❌ config.yaml not found!")
        print("   Make sure config.yaml is in the project root")
        sys.exit(1)

    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    playlist_url = config.get('youtube', {}).get('playlist_url', '')
    if not playlist_url:
        print("\n⚠️  No playlist URL in config.yaml")
        url = input("Enter your YouTube playlist URL now: ").strip()
        config['youtube']['playlist_url'] = url
        with open('config.yaml', 'w') as f:
            yaml.dump(config, f)
        print("✅ Playlist URL saved")
    else:
        print(f"✅ Playlist URL found")

def check_obs():
    print("\n📺 OBS Setup")
    print("   Make sure OBS is running with WebSocket enabled:")
    print("   OBS → Tools → WebSocket Server Settings")
    print("   Enable WebSocket server, port 4455")
    print("   Add password to config.yaml if set")

def print_next_steps():
    print("""
╔══════════════════════════════════════════╗
║           SETUP COMPLETE! 🎧             ║
╠══════════════════════════════════════════╣
║                                          ║
║  Next steps:                             ║
║                                          ║
║  1. Start OBS Studio                     ║
║  2. Enable OBS WebSocket (port 4455)     ║
║  3. Run the app:                         ║
║     python main.py                       ║
║                                          ║
║  Web UI available at:                    ║
║     http://localhost:5000                ║
║                                          ║
║  First run will analyze all 600 songs    ║
║  This takes several hours - let it run   ║
║  overnight or on Google Colab            ║
║                                          ║
╚══════════════════════════════════════════╝
""")

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════╗
║       PRO AI DJ APP - SETUP              ║
╚══════════════════════════════════════════╝
""")
    check_python()
    check_ffmpeg()
    check_config()
    create_directories()
    install_requirements()
    check_obs()
    print_next_steps()
