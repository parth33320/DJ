"""
EASY SETUP - Get streaming in 5 minutes
"""

import os
import yaml


def setup_streaming():
    """Interactive setup wizard"""
    
    print("""
╔══════════════════════════════════════════════════════════╗
║         🎧 DJ APP STREAMING SETUP WIZARD                 ║
╚══════════════════════════════════════════════════════════╝

This will configure streaming to multiple platforms.
You'll need stream keys from each platform.
    """)
    
    config = {
        'streaming': {
            'enabled': True,
            'visual_mode': 'minimal',
            'width': 1280,
            'height': 720,
            'fps': 30,
            'video_bitrate': '2500k',
            'audio_bitrate': '192k',
        }
    }
    
    # ═══ RESTREAM ═══
    print("\n" + "="*50)
    print("📺 RESTREAM.IO (Recommended - streams to 30+ platforms)")
    print("="*50)
    print("Get your key at: https://restream.io/settings/streaming-setup")
    
    use_restream = input("\nUse Restream? (y/n): ").strip().lower() == 'y'
    
    if use_restream:
        key = input("Restream key: ").strip()
        config['streaming']['restream'] = {
            'enabled': True,
            'stream_key': key,
        }
        print("✅ Restream configured!")
        print("   → Add YouTube, Twitch, Facebook, etc. in Restream dashboard")
    
    # ═══ DIRECT PLATFORMS ═══
    if not use_restream:
        print("\n" + "="*50)
        print("📺 DIRECT PLATFORM SETUP")
        print("="*50)
        
        # YouTube
        if input("\nAdd YouTube? (y/n): ").strip().lower() == 'y':
            key = input("YouTube stream key: ").strip()
            config['streaming']['youtube'] = {
                'enabled': True,
                'stream_key': key,
            }
            print("✅ YouTube configured!")
        
        # Twitch
        if input("\nAdd Twitch? (y/n): ").strip().lower() == 'y':
            key = input("Twitch stream key: ").strip()
            config['streaming']['twitch'] = {
                'enabled': True,
                'stream_key': key,
            }
            print("✅ Twitch configured!")
        
        # Facebook
        if input("\nAdd Facebook? (y/n): ").strip().lower() == 'y':
            key = input("Facebook stream key: ").strip()
            config['streaming']['facebook'] = {
                'enabled': True,
                'stream_key': key,
            }
            print("✅ Facebook configured!")
    
    # ═══ AUDIO PLATFORMS ═══
    print("\n" + "="*50)
    print("🎵 AUDIO-ONLY PLATFORMS (Internet Radio)")
    print("="*50)
    print("These let people listen on your website!")
    
    if input("\nSetup Icecast? (y/n): ").strip().lower() == 'y':
        print("""
To use Icecast, you need an Icecast server.
Options:
  1. Install locally: apt install icecast2
  2. Use a VPS (\$5/month): DigitalOcean, Vultr
  3. Use a service: listen2myradio.com, caster.fm
        """)
        
        host = input("Icecast host (e.g., localhost): ").strip() or 'localhost'
        port = input("Icecast port (e.g., 8000): ").strip() or '8000'
        password = input("Icecast source password: ").strip() or 'hackme'
        
        config['streaming']['icecast'] = {
            'enabled': True,
            'host': host,
            'port': int(port),
            'password': password,
            'mount': '/live',
        }
        print(f"✅ Icecast configured! Listeners: http://{host}:{port}/live")
    
    # ═══ RECORDING ═══
    print("\n" + "="*50)
    print("💾 RECORDING (Save VODs/Podcasts)")
    print("="*50)
    
    if input("\nEnable recording? (y/n): ").strip().lower() == 'y':
        config['streaming']['recording'] = {
            'enabled': True,
            'path': 'data/recordings',
        }
        print("✅ Recording enabled!")
    
    # ═══ SAVE ═══
    print("\n" + "="*50)
    print("💾 SAVING CONFIGURATION")
    print("="*50)
    
    # Load existing config
    existing = {}
    if os.path.exists('config.yaml'):
        with open('config.yaml', 'r') as f:
            existing = yaml.safe_load(f) or {}
    
    # Merge
    existing.update(config)
    
    with open('config.yaml', 'w') as f:
        yaml.dump(existing, f, default_flow_style=False)
    
    print("✅ Saved to config.yaml")
    
    print("""
╔══════════════════════════════════════════════════════════╗
║                    SETUP COMPLETE! 🎉                    ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Run your DJ app:                                        ║
║    python main.py                                        ║
║                                                          ║
║  Streaming will start automatically!                     ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    setup_streaming()
