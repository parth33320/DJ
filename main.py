"""
PRO AI DJ APP - Main Entry Point
With all performance and reliability improvements
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

# Original imports
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
from visual_engine.obs_bridge import OBSBridge
from ui.web_ui.app import start_web_ui

# 🆕 NEW: Core improvements
try:
    from core.audio_engine import AudioEngine
    from core.task_queue import TaskQueue, TaskPriority
    from core.cache_manager import CacheManager
    from core.health_monitor import HealthMonitor
    from core.prefetcher import Prefetcher
    CORE_AVAILABLE = True
except ImportError as e:
    print(f"{Fore.YELLOW}⚠️ Core modules not found: {e}{Style.RESET_ALL}")
    CORE_AVAILABLE = False

# 🆕 NEW: Streaming
try:
    from streaming.multi_streamer import MultiPlatformStreamer
    STREAMING_AVAILABLE = True
except ImportError:
    STREAMING_AVAILABLE = False


def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)


def create_directories(config):
    for key, path in config['paths'].items():
        os.makedirs(path, exist_ok=True)
    os.makedirs('data/recordings', exist_ok=True)
    os.makedirs('assets', exist_ok=True)
    os.makedirs('core', exist_ok=True)
    os.makedirs('streaming', exist_ok=True)
    print(f"{Fore.GREEN}✅ Directories created{Style.RESET_ALL}")


def print_banner():
    print(f"""
{Fore.CYAN}
╔═══════════════════════════════════════════════════════════╗
║              PRO AI DJ APP v2.0                           ║
║   Automated DJ • 24/7 • All Genres • 50+ Platforms        ║
║   🆕 Now with: Async I/O, Smart Caching, Auto-Recovery    ║
╚═══════════════════════════════════════════════════════════╝
{Style.RESET_ALL}""")


class DJApp:
    def __init__(self):
        self.config = load_config()
        create_directories(self.config)
        
        print(f"{Fore.YELLOW}🔧 Initializing components...{Style.RESET_ALL}")
        
        # ═══════════════════════════════════════════════════════
        # 🆕 CORE SYSTEMS (New)
        # ═══════════════════════════════════════════════════════
        
        if CORE_AVAILABLE:
            # Task queue for async operations
            self.task_queue = TaskQueue(num_workers=4)
            self.task_queue.start()
            
            # Cache manager
            self.cache = CacheManager(self.config)
            
            # Health monitor
            self.health_monitor = HealthMonitor(self.config)
            
            # Audio engine (non-blocking)
            self.audio_engine = AudioEngine(
                self.config,
                on_chunk_callback=self._on_audio_chunk
            )
        else:
            self.task_queue = None
            self.cache = None
            self.health_monitor = None
            self.audio_engine = None
        
        # ═══════════════════════════════════════════════════════
        # ORIGINAL COMPONENTS
        # ═══════════════════════════════════════════════════════
        
        # Ingestion
        self.downloader = PlaylistDownloader(self.config)
        self.stem_separator = StemSeparator(self.config)
        self.lyrics_fetcher = LyricsFetcher(self.config)
        self.playlist_watcher = PlaylistWatcher(self.config)
        
        # Analysis
        self.analyzer = AudioAnalyzer(self.config)
        self.phrase_detector = PhraseDetector(self.config)
        self.vocal_analyzer = VocalAnalyzer(self.config)
        self.entry_finder = EntryPointFinder(self.config)
        self.compatibility_scorer = CompatibilityScorer(self.config)
        
        # AI Agents
        self.selector = SelectorAgent(self.config)
        self.transition_decider = TransitionAgent(self.config)
        self.quality_checker = QualityAgent(self.config)
        self.wordplay_agent = WordplayAgent(self.config)
        self.self_improver = SelfImproveAgent(self.config)
        
        # Engines
        self.transition_engine = MasterTransitionEngine(self.config)
        self.obs_bridge = OBSBridge(self.config)
        
        # ═══════════════════════════════════════════════════════
        # 🆕 PREFETCHER (New)
        # ═══════════════════════════════════════════════════════
        
        if CORE_AVAILABLE:
            self.prefetcher = Prefetcher(
                self.config,
                self.downloader,
                self.analyzer,
                self.cache
            )
        else:
            self.prefetcher = None
        
        # ═══════════════════════════════════════════════════════
        # 🆕 STREAMING (New)
        # ═══════════════════════════════════════════════════════
        
        self.streamer = None
        self.streaming_enabled = False
        
        if STREAMING_AVAILABLE:
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
        
        # ═══════════════════════════════════════════════════════
        # 🆕 HEALTH CHECKS (New)
        # ═══════════════════════════════════════════════════════
        
        if self.health_monitor:
            self._setup_health_checks()
        
        # ═══════════════════════════════════════════════════════
        # 🆕 GRACEFUL SHUTDOWN (New)
        # ═══════════════════════════════════════════════════════
        
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            pass
        
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
    
    def _setup_health_checks(self):
        """Setup health monitoring"""
        # Audio engine health
        self.health_monitor.add_check(
            'audio_engine',
            lambda: self.audio_engine and self.audio_engine.is_playing,
            recovery_func=lambda: self.audio_engine.start()
        )
        
        # Streaming health
        if self.streaming_enabled:
            self.health_monitor.add_check(
                'streaming',
                lambda: self.streamer and self.streamer.is_streaming,
                recovery_func=lambda: self.streamer.start()
            )
        
        # Task queue health
        if self.task_queue:
            self.health_monitor.add_check(
                'task_queue',
                lambda: self.task_queue.is_healthy(),
            )
        
        self.health_monitor.start()
    
    def _on_audio_chunk(self, chunk):
        """Callback for each audio chunk (for streaming)"""
        if self.streaming_enabled and self.streamer:
            self.streamer.send_audio(chunk)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n{Fore.YELLOW}⏹️ Shutdown signal received...{Style.RESET_ALL}")
        self.shutdown()
        sys.exit(0)
    
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
        
        total = len(self.playlist)
        for i, song in enumerate(self.playlist):
            print(f"\n[{i+1}/{total}] Processing: {song['title'][:50]}")
            
            # 🆕 Use task queue for parallel processing
            if self.task_queue:
                self.task_queue.add(
                    self._process_song,
                    args=(song,),
                    priority=TaskPriority.NORMAL,
                    name=f"process_{song['id']}"
                )
            else:
                self._process_song(song)
        
        # Wait for all tasks
        if self.task_queue:
            while self.task_queue.tasks_pending > 0:
                time.sleep(1)
                print(f"   Pending: {self.task_queue.tasks_pending}")
        
        # Build word index
        print(f"\n{Fore.YELLOW}🗂️ Building word index...{Style.RESET_ALL}")
        self.wordplay_agent.build_word_index(self.metadata_cache)
        
        print(f"\n{Fore.GREEN}✅ Setup complete! {len(self.metadata_cache)} songs ready{Style.RESET_ALL}")
    
    def _process_song(self, song):
        """Process a single song (can run in parallel)"""
        try:
            # Check cache first
            if self.cache and self.cache.exists('metadata', song['id']):
                cached_path = self.cache.get('metadata', song['id'])
                import json
                with open(cached_path, 'r') as f:
                    analysis = json.load(f)
                self.metadata_cache[song['id']] = analysis
                print(f"   ✅ Cached: {song['title'][:40]}")
                return
            
            # Download
            filepath = self.downloader.download_song(song['url'], song['id'])
            
            # Analyze
            analysis = self.analyzer.analyze_track(filepath, song['id'])
            analysis['title'] = song['title']
            
            # Detect phrases
            phrases = self.phrase_detector.detect_phrases(filepath, song['id'])
            analysis['phrases'] = phrases
            
            # Entry points
            entry_points = self.entry_finder.find_entry_points(
                filepath, analysis, song['id']
            )
            analysis['entry_points'] = entry_points
            
            # Stems
            stems = self.stem_separator.separate(filepath, song['id'])
            analysis['stems'] = stems
            
            # Lyrics
            lyrics = self.lyrics_fetcher.fetch(
                song['title'], song['id'],
                stems.get('vocals')
            )
            analysis['lyrics'] = lyrics
            
            # Vocals
            if lyrics:
                phonemes = self.vocal_analyzer.analyze(
                    stems.get('vocals'), lyrics, song['id']
                )
                analysis['phonemes'] = phonemes
            
            self.metadata_cache[song['id']] = analysis
            
            # Cache the analysis
            if self.cache:
                import json
                cache_path = f"data/metadata/{song['id']}.json"
                with open(cache_path, 'w') as f:
                    json.dump(analysis, f)
                self.cache.put('metadata', song['id'], cache_path)
            
            # Delete audio
            self.downloader.delete_audio(song['id'])
            
            print(f"   ✅ Processed: {song['title'][:40]}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error processing {song['title']}: {e}{Style.RESET_ALL}")
    
    def start_djing(self):
        """Main DJ loop"""
        self.is_playing = True
        
        # Start services
        if self.audio_engine:
            self.audio_engine.start()
        
        if self.prefetcher:
            self.prefetcher.start()
        
        if self.streaming_enabled and self.streamer:
            self.streamer.start()
        
        # Background threads
        threading.Thread(target=self._playlist_watch_loop, daemon=True).start()
        threading.Thread(target=self._self_improve_loop, daemon=True).start()
        
        # Web UI
        threading.Thread(target=start_web_ui, args=(self,), daemon=True).start()
        
        # OBS (backward compatibility)
        self.obs_bridge.connect()
        
        print(f"\n{Fore.GREEN}🎧 DJ APP LIVE!{Style.RESET_ALL}")
        
        # Pick first song
        self.current_song = self.selector.pick_first_song(self.metadata_cache)
        
        while self.is_playing:
            try:
                self._play_current_song()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
                time.sleep(2)
    
    def _play_current_song(self):
        """Play current song with all improvements"""
        current = self.metadata_cache[self.current_song]
        
        print(f"\n{Fore.CYAN}▶️  NOW: {current['title']}{Style.RESET_ALL}")
        
        # Update streaming overlay
        if self.streaming_enabled and self.streamer:
            self.streamer.update_song(
                title=current.get('title', ''),
                bpm=current.get('bpm', 0),
                key=current.get('camelot', ''),
                genre=current.get('genre_hint', ''),
            )
        
        # Pick next songs and prefetch
        next_song_id, compatibility = self.selector.pick_next_song(
            current, self.metadata_cache
        )
        
        # 🆕 Prefetch
