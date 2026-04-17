"""
PRO AI DJ APP - Main Entry Point
FIXED VERSION - All imports, Tree of Thoughts, and Headless Fixes integrated
"""

import os
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import yaml
import time
import threading
import signal
import json
from colorama import init, Fore, Style
init()

# ═══════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════

from ingestion.downloader import PlaylistDownloader
from ingestion.stem_separator import StemSeparator
from ingestion.lyrics_fetcher import LyricsFetcher
from ingestion.playlist_watcher import PlaylistWatcher
from analysis.audio_analyzer import AudioAnalyzer
from analysis.phrase_detector import PhraseDetector
from analysis.vocal_analyzer import VocalAnalyzer
from analysis.entry_point_finder import EntryPointFinder
from analysis.compatibility_scorer import CompatibilityScorer
from ai_brain.agents.selector_agent import SelectorAgent
from ai_brain.agents.transition_agent import TransitionAgent
from ai_brain.agents.quality_agent import QualityAgent
from ai_brain.agents.wordplay_agent import WordplayAgent
from ai_brain.agents.self_improve_agent import SelfImproveAgent
from transition_engine.master_transition import MasterTransitionEngine

# Optional imports with fallbacks
try:
    from visual_engine.obs_bridge import OBSBridge
except ImportError:
    OBSBridge = None

try:
    from utils.drive_manager import DriveManager
except ImportError:
    DriveManager = None

try:
    from core.audio_engine import AudioEngine
    from core.task_queue import TaskQueue, TaskPriority
    from core.cache_manager import CacheManager
    from core.health_monitor import HealthMonitor
    from core.prefetcher import Prefetcher
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    AudioEngine = None
    TaskQueue = None
    CacheManager = None
    HealthMonitor = None
    Prefetcher = None

try:
    from streaming.multi_streamer import MultiPlatformStreamer
    STREAMING_AVAILABLE = True
except ImportError:
    STREAMING_AVAILABLE = False
    MultiPlatformStreamer = None


def load_config():
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_directories(config):
    dirs = [
        config['paths']['audio_cache'],
        config['paths']['stems'],
        config['paths']['metadata'],
        config['paths']['lyrics'],
        config['paths']['phonemes'],
        config['paths']['word_index'],
        config['paths']['training_data'],
        config['paths']['models'],
        config['paths']['logs'],
        'data/sandbox',
        'data/library',
        'data/recordings',
        'data/transitions',  # Added for transition output
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def print_banner():
    print(f"""
{Fore.CYAN}
╔═══════════════════════════════════════════════════════════╗
║            PRO AI DJ APP v2.3 - TOT EDITION               ║
║    Automated DJ • 24/7 • All Genres • Multi-Platform      ║
╚═══════════════════════════════════════════════════════════╝
{Style.RESET_ALL}""")


class DJApp:
    def __init__(self):
        self.config = load_config()
        create_directories(self.config)
        
        print(f"{Fore.YELLOW}🔧 Initializing components...{Style.RESET_ALL}")
        
        # ═══════════════════════════════════════════════════════
        # CORE SYSTEMS
        # ═══════════════════════════════════════════════════════
        
        self.task_queue = None
        self.cache = None
        self.health_monitor = None
        self.audio_engine = None
        self.prefetcher = None
        
        if CORE_AVAILABLE:
            try:
                self.task_queue = TaskQueue(num_workers=4)
                self.task_queue.start()
                self.cache = CacheManager(self.config)
                self.health_monitor = HealthMonitor(self.config)
                self.audio_engine = AudioEngine(self.config, on_chunk_callback=self._on_audio_chunk)
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ Core modules partial init: {e}{Style.RESET_ALL}")
        
        # ═══════════════════════════════════════════════════════
        # INGESTION
        # ═══════════════════════════════════════════════════════
        
        self.downloader = PlaylistDownloader(self.config)
        self.stem_separator = StemSeparator(self.config)
        self.lyrics_fetcher = LyricsFetcher(self.config)
        self.playlist_watcher = PlaylistWatcher(self.config)
        
        # ═══════════════════════════════════════════════════════
        # ANALYSIS
        # ═══════════════════════════════════════════════════════
        
        self.analyzer = AudioAnalyzer(self.config)
        self.phrase_detector = PhraseDetector(self.config)  
        self.vocal_analyzer = VocalAnalyzer(self.config)  
        self.entry_finder = EntryPointFinder(self.config)
        self.compatibility_scorer = CompatibilityScorer(self.config)
        
        # ═══════════════════════════════════════════════════════
        # AI AGENTS
        # ═══════════════════════════════════════════════════════
        self.selector = SelectorAgent(self.config)
        self.transition_decider = TransitionAgent(self.config)
        self.quality_checker = QualityAgent(self.config)
        self.wordplay_agent = WordplayAgent(self.config)
        self.self_improver = SelfImproveAgent(self.config)
        
        # ═══════════════════════════════════════════════════════
        # ENGINES
        # ═══════════════════════════════════════════════════════
        self.transition_engine = MasterTransitionEngine(self.config)
        
        if OBSBridge:
            try:
                self.obs_bridge = OBSBridge(self.config)
            except:
                self.obs_bridge = None
        else:
            self.obs_bridge = None
        
        # ═══════════════════════════════════════════════════════
        # DRIVE MANAGER
        # ═══════════════════════════════════════════════════════
        if DriveManager:
            try:
                self.drive_manager = DriveManager(self.config)
            except Exception:
                self.drive_manager = None
        else:
            self.drive_manager = None
        
        # ═══════════════════════════════════════════════════════
        # STREAMING
        # ═══════════════════════════════════════════════════════
        self.streamer = None
        self.streaming_enabled = False
        
        if STREAMING_AVAILABLE and MultiPlatformStreamer:
            streaming_cfg = self.config.get('streaming', {})
            if streaming_cfg.get('enabled', False):
                self._init_streaming()
        
        # ═══════════════════════════════════════════════════════
        # STATE
        # ═══════════════════════════════════════════════════════
        self.playlist = []
        self.metadata_cache = {}
        self.is_playing = False
        self.current_song = None
        self.next_song = None
        self.mode = "auto"
        self.skip_requested = False
        self.transition_history = []
        
        # Load existing metadata cache
        self._load_metadata_cache()
        
        self.update_status("idle")
        print(f"{Fore.GREEN}✅ All components initialized{Style.RESET_ALL}")

    def _load_metadata_cache(self):
        """Load all existing metadata from disk"""
        meta_dir = self.config['paths']['metadata']
        if os.path.exists(meta_dir):
            for filename in os.listdir(meta_dir):
                if filename.endswith('.json'):
                    try:
                        filepath = os.path.join(meta_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            song_id = filename.replace('.json', '')
                            self.metadata_cache[song_id] = data
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠️ Failed to load {filename}: {e}{Style.RESET_ALL}")
        
        if self.metadata_cache:
            print(f"{Fore.GREEN}📂 Loaded {len(self.metadata_cache)} songs from cache{Style.RESET_ALL}")

    def update_status(self, status):
        """Update agent status for mobile workbench and send ntfy if critical"""
        try:
            p = os.path.join(self.config['paths']['logs'], 'agent_status.txt')
            with open(p, 'w') as f:
                f.write(status)
            
            # If waiting for approval, notify phone
            if status == "WAITING_FOR_APPROVAL":
                try:
                    from utils.notifier import send_notification
                    send_notification("🚨 ACTION REQUIRED: Please click ACCEPT ALL on your desktop!", topic='dj-agent-parth')
                except:
                    pass
        except:
            pass

    def _init_streaming(self):
        """Initialize streaming"""
        try:
            self.streamer = MultiPlatformStreamer(self.config)
            self.streamer.load_from_config()
            
            total = len(self.streamer.video_endpoints) + len(self.streamer.audio_endpoints)
            if total > 0:
                self.streaming_enabled = True
                print(f"{Fore.GREEN}✅ Streaming: {total} platforms{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}❌ Streaming init failed: {e}{Style.RESET_ALL}")
    
    def _on_audio_chunk(self, chunk):
        """Callback for audio chunks (streaming)"""
        if self.streaming_enabled and self.streamer:
            try:
                self.streamer.send_audio(chunk)
            except:
                pass
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n{Fore.YELLOW}⏹️ Shutdown signal received...{Style.RESET_ALL}")
        self.shutdown()
        sys.exit(0)
    
    def shutdown(self):
        """Clean shutdown"""
        self.is_playing = False
        
        if self.audio_engine:
            try:
                self.audio_engine.stop()
            except:
                pass
        
        if self.streaming_enabled and self.streamer:
            try:
                self.streamer.stop()
            except:
                pass
        
        if self.task_queue:
            try:
                self.task_queue.stop()
            except:
                pass
        
        if self.health_monitor:
            try:
                self.health_monitor.stop()
            except:
                pass
        
        print(f"{Fore.GREEN}✅ Shutdown complete{Style.RESET_ALL}")
    
    def initial_setup(self):
        """First time setup - analyze all songs"""
        print(f"\n{Fore.CYAN}📋 INITIAL SETUP{Style.RESET_ALL}")
        print("=" * 50)
        
        playlist_url = self.config['youtube']['playlist_url']
        if not playlist_url:
            playlist_url = input("Enter your YouTube playlist URL: ").strip()
            self.config['youtube']['playlist_url'] = playlist_url
            with open('config.yaml', 'w') as f:
                yaml.dump(self.config, f)
        
        print(f"\n{Fore.YELLOW}📥 Fetching playlist...{Style.RESET_ALL}")
        self.playlist = self.downloader.get_playlist_metadata(playlist_url)
        
        print(f"Found {len(self.playlist)} songs")
        
        # Process each song
        total = len(self.playlist)
        for i, song in enumerate(self.playlist):
            print(f"\n[{i+1}/{total}] Processing: {song['title'][:50]}")
            self._process_song(song)
        
        # Build word index
        print(f"\n{Fore.YELLOW}🗂️ Building word index...{Style.RESET_ALL}")
        self.wordplay_agent.build_word_index(self.metadata_cache)
        
        print(f"\n{Fore.GREEN}✅ Setup complete! {len(self.metadata_cache)} songs ready{Style.RESET_ALL}")
    
    def _process_song(self, song):
        """Process a single song"""
        try:
            song_id = song['id']
            
            # Check cache first
            meta_path = os.path.join(self.config['paths']['metadata'], f"{song_id}.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    self.metadata_cache[song_id] = json.load(f)
                print(f"   ✅ Cached: {song['title'][:40]}")
                return
            
            # Download
            filepath = self.downloader.download_song(song['url'], song_id)
            if not filepath or not os.path.exists(filepath):
                print(f"   ❌ Download failed: {song['title'][:40]}")
                return
            
            # Analyze
            analysis = self.analyzer.analyze_track(filepath, song_id)
            analysis['title'] = song['title']
            analysis['url'] = song.get('url', '')
            analysis['id'] = song_id
            
            # Phrases
            try:
                phrases = self.phrase_detector.detect_phrases(filepath, song_id)
                analysis['phrases'] = phrases
            except Exception as e:
                print(f"   ⚠️ Phrase detection failed: {e}")
                analysis['phrases'] = []
            
            # Entry points
            try:
                entry_points = self.entry_finder.find_entry_points(filepath, analysis, song_id)
                analysis['entry_points'] = entry_points
            except Exception as e:
                print(f"   ⚠️ Entry point detection failed: {e}")
                analysis['entry_points'] = []
            
            # Save metadata
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2)
            
            self.metadata_cache[song_id] = analysis
            
            print(f"   ✅ Processed: {song['title'][:40]}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error processing {song.get('title', 'unknown')}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
    
    def start_djing(self):
        """Main DJ loop - FIXED"""
        self.is_playing = True
        
        # Signal handlers
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            pass  # Not in main thread
        
        # Start services
        if self.audio_engine:
            self.audio_engine.start()
        
        if self.streaming_enabled and self.streamer:
            self.streamer.start()
        
        if self.obs_bridge:
            try:
                self.obs_bridge.connect()
            except:
                pass
        
        # Background threads
        threading.Thread(target=self._playlist_watch_loop, daemon=True).start()
        
        print(f"\n{Fore.GREEN}🎧 DJ APP LIVE!{Style.RESET_ALL}")
        
        # Pick first song
        if self.metadata_cache:
            self.current_song = self.selector.pick_first_song(self.metadata_cache)
            if self.current_song:
                title = self.metadata_cache[self.current_song].get('title', 'Unknown')
                print(f"{Fore.CYAN}🎵 Starting with: {title}{Style.RESET_ALL}")
        
        # Main loop
        while self.is_playing:
            try:
                if not self.current_song:
                    print(f"{Fore.YELLOW}⚠️ No current song, waiting...{Style.RESET_ALL}")
                    time.sleep(1)
                    continue
                
                self._play_current_song()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"{Fore.RED}❌ Error in main loop: {e}{Style.RESET_ALL}")
                import traceback
                traceback.print_exc()
                time.sleep(2)
    
    def _play_current_song(self):
        """Play current song with transition to next"""
        if not self.current_song or self.current_song not in self.metadata_cache:
            self.current_song = self.selector.pick_first_song(self.metadata_cache)
            return
        
        current = self.metadata_cache[self.current_song]
        print(f"\n{Fore.CYAN}▶️  NOW: {current.get('title', 'Unknown')}{Style.RESET_ALL}")
        
        self.update_status(f"playing:{current.get('title', 'Unknown')}")
        
        # Pick next song
        next_song_id, compatibility = self.selector.pick_next_song(
            current, self.metadata_cache
        )
        
        if not next_song_id:
            print(f"{Fore.YELLOW}⚠️ No next song found, picking random...{Style.RESET_ALL}")
            import random
            available = [k for k in self.metadata_cache.keys() if k != self.current_song]
            if available:
                next_song_id = random.choice(available)
                compatibility = {'score': 0.5, 'reason': 'random selection'}
            else:
                time.sleep(5)
                return
        
        next_analysis = self.metadata_cache.get(next_song_id, {})
        
        # ────────────────────────────────────────────────────────
        # 🤖 DECIDE TRANSITION (Tree of Thoughts Integration)
        # ────────────────────────────────────────────────────────
        decide_result = self.transition_decider.decide_transition(
            current.get('title', 'Unknown'), 
            next_analysis.get('title', 'Unknown'), 
            current, 
            next_analysis
        )
        
        if isinstance(decide_result, tuple):
            technique, params = decide_result
        else:
            technique = decide_result
            params = {"duration": 16}
        
        print(f"   {Fore.MAGENTA}⏭️  Next: {next_analysis.get('title', 'Unknown')}{Style.RESET_ALL}")
        print(f"   {Fore.YELLOW}🔀 Technique: {technique}{Style.RESET_ALL}")
        print(f"   {Fore.BLUE}📊 Compatibility: {compatibility.get('score', 0):.2f}{Style.RESET_ALL}")
        
        # Update streaming overlay
        if self.streaming_enabled and self.streamer:
            try:
                self.streamer.update_song(
                    title=current.get('title', ''),
                    bpm=current.get('bpm', 0),
                    key=current.get('camelot', ''),
                    genre=current.get('genre_hint', ''),
                    next_title=next_analysis.get('title', '')
                )
            except:
                pass
        
        # ────────────────────────────────────────────────────────
        # 🎧 EXECUTE TRANSITION (Headless File Generation Fix)
        # ────────────────────────────────────────────────────────
        self.update_status(f"transitioning:{current.get('title', '')} -> {next_analysis.get('title', '')}")
        
        output_path = self.transition_engine.generate_transition_mix(
            cur_id=self.current_song,
            nxt_id=next_song_id,
            technique=technique,
            params=params,
            cur_ana=current,
            nxt_ana=next_analysis
        )
        
        if output_path and os.path.exists(output_path):
            print(f"   {Fore.GREEN}✅ Transition generated: {output_path}{Style.RESET_ALL}")
            
            # Upload to Drive for mobile testing
            if self.drive_manager:
                try:
                    drive_link = self.drive_manager.upload_transition(output_path)
                    if drive_link:
                        print(f"   {Fore.CYAN}📱 Mobile link: {drive_link}{Style.RESET_ALL}")
                        self._save_transition_link(output_path, drive_link, current, next_analysis, technique)
                except Exception as e:
                    print(f"   {Fore.YELLOW}⚠️ Drive upload failed: {e}{Style.RESET_ALL}")
            
            # Record for quality feedback
            self.transition_history.append({
                'from': self.current_song,
                'to': next_song_id,
                'technique': technique,
                'output': output_path,
                'timestamp': time.time()
            })
        else:
            print(f"   {Fore.RED}❌ Transition generation failed{Style.RESET_ALL}")
        
        # Move to next song
        self.current_song = next_song_id
        
        # Small delay before next transition
        time.sleep(2)
    
    def _save_transition_link(self, output_path, drive_link, current, next_analysis, technique):
        """Save transition link for mobile testing"""
        try:
            links_file = os.path.join(self.config['paths']['logs'], 'transition_links.json')
            
            links = []
            if os.path.exists(links_file):
                with open(links_file, 'r') as f:
                    links = json.load(f)
            
            links.append({
                'from_title': current.get('title', ''),
                'to_title': next_analysis.get('title', ''),
                'technique': technique,
                'drive_link': drive_link,
                'local_path': output_path,
                'timestamp': time.time(),
                'tested': False,
                'rating': None
            })
            
            # Keep last 50 transitions
            links = links[-50:]
            
            with open(links_file, 'w') as f:
                json.dump(links, f, indent=2)
                
        except Exception as e:
            print(f"   ⚠️ Failed to save transition link: {e}")
    
    def _playlist_watch_loop(self):
        """Background loop to watch for playlist changes"""
        check_interval = self.config['youtube'].get('check_interval_hours', 6) * 3600
        
        while self.is_playing:
            time.sleep(check_interval)
            try:
                playlist_url = self.config['youtube']['playlist_url']
                if playlist_url:
                    self.playlist_watcher.check_for_changes(
                        playlist_url,
                        self.playlist,
                        self.metadata_cache,
                        self
                    )
            except Exception as e:
                print(f"Playlist watch error: {e}")
    
    def test_single_transition(self, song1_id=None, song2_id=None):
        """Test a single transition between two songs"""
        import random
        
        if not self.metadata_cache:
            print(f"{Fore.RED}❌ No songs in cache. Run initial_setup first.{Style.RESET_ALL}")
            return None
        
        # Pick random songs if not specified
        available = list(self.metadata_cache.keys())
        if not song1_id:
            song1_id = random.choice(available)
        if not song2_id:
            remaining = [s for s in available if s != song1_id]
            song2_id = random.choice(remaining) if remaining else song1_id
        
        current = self.metadata_cache.get(song1_id, {})
        next_analysis = self.metadata_cache.get(song2_id, {})
        
        print(f"\n{Fore.CYAN}🧪 TESTING TRANSITION{Style.RESET_ALL}")
        print(f"   From: {current.get('title', 'Unknown')}")
        print(f"   To: {next_analysis.get('title', 'Unknown')}")
        
        # Get compatibility
        compatibility = self.compatibility_scorer.score(current, next_analysis)
        
        # ────────────────────────────────────────────────────────
        # 🤖 DECIDE TRANSITION (Tree of Thoughts Integration)
        # ────────────────────────────────────────────────────────
        decide_result = self.transition_decider.decide_transition(
            current.get('title', 'Unknown'),
            next_analysis.get('title', 'Unknown'),
            current,
            next_analysis
        )
        
        if isinstance(decide_result, tuple):
            technique, params = decide_result
        else:
            technique = decide_result
            params = {"duration": 16}
        
        print(f"   Technique: {technique}")
        print(f"   Compatibility: {compatibility.get('score', 0):.2f}")
        
        # ────────────────────────────────────────────────────────
        # 🎧 EXECUTE TRANSITION (Headless File Generation Fix)
        # ────────────────────────────────────────────────────────
        output_path = self.transition_engine.generate_transition_mix(
            cur_id=song1_id,
            nxt_id=song2_id,
            technique=technique,
            params=params,
            cur_ana=current,
            nxt_ana=next_analysis
        )
        
        if output_path and os.path.exists(output_path):
            print(f"{Fore.GREEN}✅ Transition saved: {output_path}{Style.RESET_ALL}")
            return output_path
        else:
            print(f"{Fore.RED}❌ Transition failed{Style.RESET_ALL}")
            return None


def main():
    print_banner()
    
    try:
        app = DJApp()
        
        # Check command line args
        if len(sys.argv) > 1:
            if sys.argv[1] == 'setup':
                app.initial_setup()
                return
            elif sys.argv[1] == 'test':
                # Test single transition
                result = app.test_single_transition()
                if result:
                    print(f"\n{Fore.GREEN}Test complete! File: {result}{Style.RESET_ALL}")
                return
            elif sys.argv[1] == 'test-loop':
                # Test multiple transitions
                count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
                for i in range(count):
                    print(f"\n{'='*50}")
                    print(f"Test {i+1}/{count}")
                    app.test_single_transition()
                return
        
        # Check if we have songs
        if not app.metadata_cache:
            print(f"\n{Fore.YELLOW}📋 No songs in cache. Running initial setup...{Style.RESET_ALL}")
            app.initial_setup()
        
        app.start_djing()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 Goodbye!{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}❌ Fatal error: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
