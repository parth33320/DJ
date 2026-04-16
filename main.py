import os
import sys
import yaml
import time
import threading
import schedule
from colorama import init, Fore, Style
init()

# ═══════════════════════════════════════════════════════════════
# ORIGINAL IMPORTS (ALL PRESERVED - NO CHANGES)
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
from visual_engine.obs_bridge import OBSBridge
from ui.web_ui.app import start_web_ui
from utils.drive_manager import DriveManager

# ═══════════════════════════════════════════════════════════════
# 🆕 NEW IMPORT - Multi-Platform Streaming (Optional)
# ═══════════════════════════════════════════════════════════════

try:
    from streaming.multi_streamer import MultiPlatformStreamer
    STREAMING_AVAILABLE = True
except ImportError:
    STREAMING_AVAILABLE = False
    print(f"{Fore.YELLOW}⚠️ Streaming module not found - streaming disabled{Style.RESET_ALL}")
    print(f"   Create streaming/multi_streamer.py to enable")


# ═══════════════════════════════════════════════════════════════
# ORIGINAL FUNCTIONS (ALL PRESERVED - NO CHANGES)
# ═══════════════════════════════════════════════════════════════

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_directories(config):
    for key, path in config['paths'].items():
        os.makedirs(path, exist_ok=True)
    # 🆕 Also create streaming directories
    os.makedirs('data/recordings', exist_ok=True)
    os.makedirs('assets', exist_ok=True)
    os.makedirs('streaming', exist_ok=True)
    print(f"{Fore.GREEN}✅ Directories created{Style.RESET_ALL}")


def print_banner():
    print(f"""
{Fore.CYAN}
╔═══════════════════════════════════════════╗
║          PRO AI DJ APP v1.0               ║
║   Automated DJ • 24/7 • All Genres        ║
║   🆕 Now with 50+ Platform Streaming!     ║
╚═══════════════════════════════════════════╝
{Style.RESET_ALL}""")


# ═══════════════════════════════════════════════════════════════
# DJ APP CLASS (ORIGINAL + NEW STREAMING FEATURES)
# ═══════════════════════════════════════════════════════════════

class DJApp:
    def __init__(self):
        self.config = load_config()
        create_directories(self.config)
        
        print(f"{Fore.YELLOW}🔧 Initializing components...{Style.RESET_ALL}")
        
        # ═══════════════════════════════════════════════════════
        # ORIGINAL COMPONENTS (ALL PRESERVED - NO CHANGES)
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
        self.obs_bridge = OBSBridge(self.config)  # Keep for backward compatibility
        
        # Storage
        self.drive_manager = DriveManager(self.config)
        
        # ═══════════════════════════════════════════════════════
        # 🆕 NEW: Multi-Platform Streamer (replaces OBS need)
        # ═══════════════════════════════════════════════════════
        
        self.streamer = None
        self.streaming_enabled = False
        
        if STREAMING_AVAILABLE:
            streaming_cfg = self.config.get('streaming', {})
            if streaming_cfg.get('enabled', False):
                self._init_streaming()
        
        # ═══════════════════════════════════════════════════════
        # ORIGINAL STATE VARIABLES (ALL PRESERVED - NO CHANGES)
        # ═══════════════════════════════════════════════════════
        
        self.playlist = []
        self.metadata_cache = {}
        self.is_playing = False
        self.current_song = None
        self.next_song = None
        self.mode = "auto"  # auto or semi
        
        print(f"{Fore.GREEN}✅ All components initialized{Style.RESET_ALL}")
    
    # ═══════════════════════════════════════════════════════════
    # 🆕 NEW METHOD: Initialize Streaming
    # ═══════════════════════════════════════════════════════════
    
    def _init_streaming(self):
        """Initialize multi-platform streaming"""
        try:
            print(f"{Fore.YELLOW}📺 Initializing streaming...{Style.RESET_ALL}")
            
            self.streamer = MultiPlatformStreamer(self.config)
            self.streamer.load_from_config()
            
            # Check if any platforms configured
            total = len(self.streamer.video_endpoints) + len(self.streamer.audio_endpoints)
            
            if total > 0:
                self.streaming_enabled = True
                print(f"{Fore.GREEN}✅ Streaming ready: {total} platform(s){Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}⚠️ No streaming platforms configured{Style.RESET_ALL}")
                print(f"   Add stream keys in config.yaml to enable")
                
        except Exception as e:
            print(f"{Fore.RED}❌ Streaming init failed: {e}{Style.RESET_ALL}")
            self.streaming_enabled = False
    
    # ═══════════════════════════════════════════════════════════
    # ORIGINAL METHOD: initial_setup (ALL PRESERVED - NO CHANGES)
    # ═══════════════════════════════════════════════════════════
    
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
        
        # Get playlist
        print(f"\n{Fore.YELLOW}📥 Fetching playlist...{Style.RESET_ALL}")
        self.playlist = self.downloader.get_playlist_metadata(playlist_url)
        
        # Process each song
        total = len(self.playlist)
        for i, song in enumerate(self.playlist):
            print(f"\n[{i+1}/{total}] Processing: {song['title'][:50]}")
            
            try:
                # Download
                filepath = self.downloader.download_song(song['url'], song['id'])
                
                # Analyze
                analysis = self.analyzer.analyze_track(filepath, song['id'])
                analysis['title'] = song['title']
                
                # Detect phrases
                phrases = self.phrase_detector.detect_phrases(filepath, song['id'])
                analysis['phrases'] = phrases
                
                # Find best entry points
                entry_points = self.entry_finder.find_entry_points(
                    filepath, analysis, song['id']
                )
                analysis['entry_points'] = entry_points
                
                # Separate stems
                stems = self.stem_separator.separate(filepath, song['id'])
                analysis['stems'] = stems
                
                # Get lyrics
                lyrics = self.lyrics_fetcher.fetch(
                    song['title'], song['id'], 
                    stems.get('vocals')
                )
                analysis['lyrics'] = lyrics
                
                # Analyze vocals/words
                if lyrics:
                    phonemes = self.vocal_analyzer.analyze(
                        stems.get('vocals'), lyrics, song['id']
                    )
                    analysis['phonemes'] = phonemes
                
                self.metadata_cache[song['id']] = analysis
                
                # Delete main audio (keep stems)
                self.downloader.delete_audio(song['id'])
                
            except Exception as e:
                print(f"{Fore.RED}❌ Error processing {song['title']}: {e}{Style.RESET_ALL}")
                continue
        
        # Build word index
        print(f"\n{Fore.YELLOW}🗂️ Building word index...{Style.RESET_ALL}")
        self.wordplay_agent.build_word_index(self.metadata_cache)
        
        print(f"\n{Fore.GREEN}✅ Setup complete! {len(self.metadata_cache)} songs ready{Style.RESET_ALL}")
    
    # ═══════════════════════════════════════════════════════════
    # ORIGINAL METHOD: start_djing (ENHANCED with streaming)
    # ═══════════════════════════════════════════════════════════
    
    def start_djing(self):
        """Main DJ loop"""
        self.is_playing = True
        
        # ═══ ORIGINAL: Start background services ═══
        threading.Thread(target=self._playlist_watch_loop, daemon=True).start()
        threading.Thread(target=self._self_improve_loop, daemon=True).start()
        
        # ═══ ORIGINAL: Start web UI ═══
        threading.Thread(
            target=start_web_ui, 
            args=(self,), 
            daemon=True
        ).start()
        
        # ═══ ORIGINAL: Connect to OBS (kept for backward compatibility) ═══
        self.obs_bridge.connect()
        
        # ═══ 🆕 NEW: Start multi-platform streaming ═══
        if self.streaming_enabled and self.streamer:
            print(f"\n{Fore.CYAN}📺 Starting multi-platform stream...{Style.RESET_ALL}")
            self.streamer.start()
        
        print(f"\n{Fore.GREEN}🎧 DJ APP LIVE! Starting mix...{Style.RESET_ALL}")
        
        # Pick first song
        self.current_song = self.selector.pick_first_song(self.metadata_cache)
        
        while self.is_playing:
            try:
                self._play_current_song()
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}⏹️ Stopping DJ App...{Style.RESET_ALL}")
                self._shutdown()
                break
            except Exception as e:
                print(f"{Fore.RED}❌ Playback error: {e}{Style.RESET_ALL}")
                time.sleep(2)
    
    # ═══════════════════════════════════════════════════════════
    # ORIGINAL METHOD: _play_current_song (ENHANCED with streaming)
    # ═══════════════════════════════════════════════════════════
    
    def _play_current_song(self):
        """Play current song and prepare transition to next"""
        current = self.metadata_cache[self.current_song]
        
        print(f"\n{Fore.CYAN}▶️  NOW PLAYING: {current['title']}{Style.RESET_ALL}")
        print(f"   BPM: {current['bpm']:.1f} | "
              f"Key: {current['camelot']} | "
              f"Genre: {current['genre_hint']}")
        
        # ═══ 🆕 NEW: Update stream overlay ═══
        if self.streaming_enabled and self.streamer:
            self.streamer.update_song(
                title=current.get('title', 'Unknown'),
                bpm=current.get('bpm', 0),
                key=current.get('camelot', ''),
                genre=current.get('genre_hint', ''),
            )
        
        # ═══ ORIGINAL: Find best next song ═══
        next_song_id, compatibility = self.selector.pick_next_song(
            current, self.metadata_cache
        )
        next_song = self.metadata_cache[next_song_id]
        
        # ═══ ORIGINAL: Decide transition technique ═══
        technique = self.transition_decider.decide(
            current, next_song, compatibility
        )
        
        # ═══ ORIGINAL: Check for wordplay opportunity ═══
        wordplay = self.wordplay_agent.find_connection(
            current, next_song
        )
        if wordplay and wordplay['score'] > 0.75:
            technique = 'wordplay'
            technique_params = wordplay
        else:
            technique_params = self.transition_decider.get_params(
                current, next_song, technique
            )
        
        # ═══ ORIGINAL: Quality check ═══
        quality_score = self.quality_checker.check(
            current, next_song, technique, technique_params
        )
        
        if quality_score < self.config['transitions']['quality_threshold']:
            print(f"{Fore.YELLOW}⚠️ Quality check failed, trying alternative...{Style.RESET_ALL}")
            technique = self.transition_decider.get_fallback(current, next_song)
            technique_params = self.transition_decider.get_params(
                current, next_song, technique
            )
        
        print(f"   Next: {next_song['title'][:40]}")
        print(f"   Technique: {technique} | Quality: {quality_score:.2f}")
        
        # ═══ 🆕 NEW: Update stream with next song info ═══
        if self.streaming_enabled and self.streamer:
            self.streamer.update_song(
                title=current.get('title', 'Unknown'),
                bpm=current.get('bpm', 0),
                key=current.get('camelot', ''),
                genre=current.get('genre_hint', ''),
                next_title=next_song.get('title', '')[:40],
            )
        
        # ═══ ORIGINAL: Semi-auto mode approval ═══
        if self.mode == "semi":
            approval = input(f"\nApprove? (y/n/skip): ").strip().lower()
            if approval == 'n':
                next_song_id, compatibility = self.selector.pick_next_song(
                    current, self.metadata_cache, exclude=[next_song_id]
                )
                next_song = self.metadata_cache[next_song_id]
        
        # ═══ ORIGINAL: Download next song audio if needed ═══
        next_song_info = next(s for s in self.playlist if s['id'] == next_song_id)
        next_filepath = self.downloader.download_song(
            next_song_info['url'], next_song_id
        )
        
        # ═══ ORIGINAL: Update OBS visuals (kept for compatibility) ═══
        self.obs_bridge.update_display(current, next_song, technique)
        
        # ═══ ORIGINAL: Execute transition ═══
        self.transition_engine.execute(
            current_id=self.current_song,
            next_id=next_song_id,
            technique=technique,
            params=technique_params,
            current_analysis=current,
            next_analysis=next_song
        )
        
        # ═══ ORIGINAL: Move to next song ═══
        self.current_song = next_song_id
        
        # ═══ ORIGINAL: Cleanup ═══
        self.downloader.delete_audio(self.current_song)
    
    # ═══════════════════════════════════════════════════════════
    # ORIGINAL METHOD: _playlist_watch_loop (NO CHANGES)
    # ═══════════════════════════════════════════════════════════
    
    def _playlist_watch_loop(self):
        """Check for new/deleted songs periodically"""
        while self.is_playing:
            time.sleep(
                self.config['youtube']['check_interval_hours'] * 3600
            )
            self.playlist_watcher.check_for_changes(
                self.config['youtube']['playlist_url'],
                self.playlist,
                self.metadata_cache,
                self
            )
    
    # ═══════════════════════════════════════════════════════════
    # ORIGINAL METHOD: _self_improve_loop (NO CHANGES)
    # ═══════════════════════════════════════════════════════════
    
    def _self_improve_loop(self):
        """Periodic self-improvement"""
        schedule.every(
            self.config['ai']['self_improve_interval_days']
        ).days.do(self.self_improver.run_improvement_cycle)
        
        while self.is_playing:
            schedule.run_pending()
            time.sleep(3600)
    
    # ═══════════════════════════════════════════════════════════
    # 🆕 NEW METHOD: Graceful shutdown
    # ═══════════════════════════════════════════════════════════
    
    def _shutdown(self):
        """Graceful shutdown - stop all services"""
        self.is_playing = False
        
        # Stop streaming
        if self.streaming_enabled and self.streamer:
            print(f"{Fore.YELLOW}📺 Stopping stream...{Style.RESET_ALL}")
            self.streamer.stop()
        
        print(f"{Fore.GREEN}✅ DJ App stopped{Style.RESET_ALL}")
    
    # ═══════════════════════════════════════════════════════════
    # 🆕 NEW METHOD: Get streaming status (for web UI)
    # ═══════════════════════════════════════════════════════════
    
    def get_streaming_status(self):
        """Get current streaming status"""
        if not self.streaming_enabled or not self.streamer:
            return {'enabled': False}
        
        return self.streamer.get_status()


# ═══════════════════════════════════════════════════════════════
# ORIGINAL MAIN FUNCTION (ALL PRESERVED - NO CHANGES)
# ═══════════════════════════════════════════════════════════════

def main():
    print_banner()
    app = DJApp()
    
    # Check if already set up
    metadata_exists = os.path.exists('data/metadata') and \
                      len(os.listdir('data/metadata')) > 0
    
    if not metadata_exists:
        app.initial_setup()
    else:
        print(f"{Fore.GREEN}✅ Found existing analysis data{Style.RESET_ALL}")
        app.metadata_cache = app.analyzer.load_all_metadata()
        app.playlist = app.downloader.load_cached_playlist()
    
    app.start_djing()


if __name__ == "__main__":
    main()
