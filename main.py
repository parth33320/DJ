
"""
PRO AI DJ APP - Main Entry Point
FIXED VERSION - All imports and loops complete
"""

import os
import sys
import yaml
import time
import threading
import signal
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
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def print_banner():
    print(f"""
{Fore.CYAN}
╔═══════════════════════════════════════════════════════════╗
║              PRO AI DJ APP v2.1 - FIXED                   ║
║   Automated DJ • 24/7 • All Genres • Multi-Platform       ║
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
        self.entry_finder = EntryPointFinder(self.config)
        self.compatibility_scorer = CompatibilityScorer(self.config)
        
        self.update_status("idle")

    def update_status(self, status):
        """Update agent status for mobile workbench and send ntfy if critical"""
        try:
            p = os.path.join(self.config['paths']['logs'], 'agent_status.txt')
            with open(p, 'w') as f:
                f.write(status)
            
            # If me waiting for approval, tell the phone!
            if status == "WAITING_FOR_APPROVAL":
                from utils.notifier import send_notification
                send_notification("🚨 ACTION REQUIRED: Please click ACCEPT ALL on your desktop!", topic='dj-agent-parth')
        except:
            pass

    def start_djing(self):
        """Main DJ loop"""
        self.is_playing = True
        
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
            self.obs_bridge = OBSBridge(self.config)
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
        
        # ═══════════════════════════════════════════════════════
        # SIGNAL HANDLERS
        # ═══════════════════════════════════════════════════════
        
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            pass  # Not in main thread
        
        print(f"{Fore.GREEN}✅ All components initialized{Style.RESET_ALL}")
    
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
                import json
                with open(meta_path, 'r') as f:
                    self.metadata_cache[song_id] = json.load(f)
                print(f"   ✅ Cached: {song['title'][:40]}")
                return
            
            # Download
            filepath = self.downloader.download_song(song['url'], song_id)
            
            # Analyze
            analysis = self.analyzer.analyze_track(filepath, song_id)
            analysis['title'] = song['title']
            
            # Phrases
            try:
                phrases = self.phrase_detector.detect_phrases(filepath, song_id)
                analysis['phrases'] = phrases
            except:
                pass
            
            # Entry points
            try:
                entry_points = self.entry_finder.find_entry_points(filepath, analysis, song_id)
                analysis['entry_points'] = entry_points
            except:
                pass
            
            self.metadata_cache[song_id] = analysis
            
            # Delete audio to save space
            self.downloader.delete_audio(song_id)
            
            print(f"   ✅ Processed: {song['title'][:40]}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error processing {song.get('title', 'unknown')}: {e}{Style.RESET_ALL}")
    
    def start_djing(self):
        """Main DJ loop"""
        self.is_playing = True
        
        # Start services
        if self.audio_engine:
            self.audio_engine.start()
        
        if self.streaming_enabled and self.streamer:
            self.streamer.start()
        
        if self.obs_bridge:
            self.obs_bridge.connect()
        
        # Background threads
        threading.Thread(target=self._playlist_watch_loop, daemon=True).start()
        
        print(f"\n{Fore.GREEN}🎧 DJ APP LIVE!{Style.RESET_ALL}")
        
        # Pick first song
        if self.metadata_cache:
            self.current_song = self.selector.pick_first_song(self.metadata_cache)
        
        # Main loop
        while self.is_playing:
            try:
                if not self.current_song:
                    time.sleep(1)
                    continue
                
                self._play_current_song()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
                time.sleep(2)
    
    def _play_current_song(self):
        """Play current song with transition to next"""
        if not self.current_song or self.current_song not in self.metadata_cache:
            return
        
        current = self.metadata_cache[self.current_song]
        print(f"\n{Fore.CYAN}▶️  NOW: {current.get('title', 'Unknown')}{Style.RESET_ALL}")
        
        # Pick next song
        next_song_id, compatibility = self.selector.pick_next_song(
            current, self.metadata_cache
        )
        
        if not next_song_id:
            time.sleep(5)
            return
        
        next_analysis = self.metadata_cache.get(next_song_id, {})
        
        # Decide transition
        technique = self.transition_decider.decide(
            current, next_analysis, compatibility
        )
        params = self.transition_decider.get_params(current, next_analysis, technique)
        
        print(f"   Next: {next_analysis.get('title', 'Unknown')}")
        print(f"   Technique: {technique}")
        
        # Update streaming overlay
        if self.streaming_enabled and self.streamer:
            self.streamer.update_song(
                title=current.get('title', ''),
                bpm=current.get('bpm', 0),
                key=current.get('camelot', ''),
                genre=current.get('genre_hint', ''),
                next_title=next_analysis.get('title', '')
            )
        
        # Execute transition
        self.transition_engine.execute(
            self.current_song,
            next_song_id,
            technique,
            params,
            current,
            next_analysis
        )
        
        # Move to next song
        self.current_song = next_song_id
    
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


def main():
    print_banner()
    
    try:
        app = DJApp()
        
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
