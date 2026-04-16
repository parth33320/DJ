import os
import json
import threading
from analysis.audio_analyzer import AudioAnalyzer
from analysis.phrase_detector import PhraseDetector
from analysis.melody_detector import MelodyDetector
from analysis.entry_point_finder import EntryPointFinder
from analysis.vocal_analyzer import VocalAnalyzer
from ingestion.stem_separator import StemSeparator
from ingestion.lyrics_fetcher import LyricsFetcher

class AnalyzerAgent:
    """
    Agent 1: Master analysis coordinator
    Runs all analysis pipelines on a song
    Orchestrates: audio analysis, phrase detection,
    melody detection, stem separation, lyrics, vocals
    """
    def __init__(self, config):
        self.config = config
        self.metadata_dir = config['paths']['metadata']

        # Sub-analyzers
        self.audio_analyzer = AudioAnalyzer(config)
        self.phrase_detector = PhraseDetector(config)
        self.melody_detector = MelodyDetector(config)
        self.entry_finder = EntryPointFinder(config)
        self.vocal_analyzer = VocalAnalyzer(config)
        self.stem_separator = StemSeparator(config)
        self.lyrics_fetcher = LyricsFetcher(config)

        self.analysis_queue = []
        self.is_processing = False

    def analyze_song_full(self, filepath, song_id, title=''):
        """
        Run complete analysis pipeline on one song
        Returns complete analysis dict
        """
        print(f"\n   🔬 Full analysis: {title or song_id}")

        result = {}

        # Step 1: Core audio analysis
        try:
            audio_analysis = self.audio_analyzer.analyze_track(
                filepath, song_id
            )
            audio_analysis['title'] = title
            result.update(audio_analysis)
            print(f"      ✅ Audio: BPM={audio_analysis.get('bpm', 0):.1f} "
                  f"Key={audio_analysis.get('camelot', 'N/A')}")
        except Exception as e:
            print(f"      ❌ Audio analysis failed: {e}")
            result['song_id'] = song_id
            result['title'] = title

        # Step 2: Phrase detection
        try:
            phrases = self.phrase_detector.detect_phrases(
                filepath, song_id
            )
            result['phrases'] = phrases
            total_bars = phrases.get('total_bars', 0)
            print(f"      ✅ Phrases: {total_bars} bars detected")
        except Exception as e:
            print(f"      ❌ Phrase detection failed: {e}")
            result['phrases'] = {}

        # Step 3: Melody detection
        try:
            melody = self.melody_detector.detect(filepath, song_id)
            result['melody'] = melody
            note_count = len(melody.get('raw_notes', []))
            print(f"      ✅ Melody: {note_count} notes detected")
        except Exception as e:
            print(f"      ❌ Melody detection failed: {e}")
            result['melody'] = {}

        # Step 4: Entry point analysis
        try:
            entries = self.entry_finder.find_entry_points(
                filepath, result, song_id
            )
            result['entry_points'] = entries
            best = entries.get('best_entry', {})
            print(f"      ✅ Entry: best at "
                  f"{best.get('time', 0):.1f}s "
                  f"(score={best.get('score', 0):.2f})")
        except Exception as e:
            print(f"      ❌ Entry point failed: {e}")
            result['entry_points'] = {}

        # Step 5: Stem separation
        try:
            stems = self.stem_separator.separate(filepath, song_id)
            result['stems'] = stems
            available = [k for k, v in stems.items() if v]
            print(f"      ✅ Stems: {available}")
        except Exception as e:
            print(f"      ❌ Stem separation failed: {e}")
            result['stems'] = {}

        # Step 6: Lyrics fetching
        try:
            vocals_path = result.get('stems', {}).get('vocals')
            lyrics = self.lyrics_fetcher.fetch(
                title, song_id, vocals_path
            )
            result['lyrics'] = lyrics
            if lyrics:
                lang = lyrics.get('language', 'unknown')
                word_count = len(lyrics.get('timed_words', []))
                print(f"      ✅ Lyrics: {lang}, {word_count} words")
            else:
                print(f"      ⚠️  No lyrics found")
        except Exception as e:
            print(f"      ❌ Lyrics fetch failed: {e}")
            result['lyrics'] = None

        # Step 7: Vocal/phoneme analysis
        try:
            if result.get('lyrics') and result.get('stems', {}).get('vocals'):
                phonemes = self.vocal_analyzer.analyze(
                    result['stems']['vocals'],
                    result['lyrics'],
                    song_id
                )
                result['phonemes'] = phonemes
                if phonemes:
                    print(f"      ✅ Phonemes: "
                          f"{phonemes.get('word_count', 0)} words indexed")
            else:
                result['phonemes'] = None
        except Exception as e:
            print(f"      ❌ Vocal analysis failed: {e}")
            result['phonemes'] = None

        # Save complete analysis
        self._save_complete_analysis(song_id, result)

        print(f"      ✅ Complete analysis saved: {song_id}")
        return result

    def analyze_batch(self, songs, downloader, callback=None):
        """
        Analyze a batch of songs
        songs: list of {'id', 'title', 'url'} dicts
        callback: called after each song with (song_id, analysis)
        """
        total = len(songs)
        results = {}

        for i, song in enumerate(songs):
            print(f"\n[{i+1}/{total}] {song['title'][:50]}")

            try:
                filepath = downloader.download_song(
                    song['url'], song['id']
                )
                analysis = self.analyze_song_full(
                    filepath, song['id'], song['title']
                )
                results[song['id']] = analysis

                if callback:
                    callback(song['id'], analysis)

                # Delete main audio after analysis
                downloader.delete_audio(song['id'])

            except Exception as e:
                print(f"   ❌ Failed: {e}")
                continue

        return results

    def analyze_async(self, filepath, song_id, title,
                      on_complete=None):
        """
        Analyze a song in background thread
        Used for pre-analyzing next song while current plays
        """
        def _run():
            analysis = self.analyze_song_full(filepath, song_id, title)
            if on_complete:
                on_complete(song_id, analysis)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread

    def is_analyzed(self, song_id):
        """Check if a song has been fully analyzed"""
        meta_path = os.path.join(
            self.metadata_dir, f"{song_id}.json"
        )
        return os.path.exists(meta_path)

    def load_analysis(self, song_id):
        """Load existing analysis from cache"""
        meta_path = os.path.join(
            self.metadata_dir, f"{song_id}.json"
        )
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_complete_analysis(self, song_id, analysis):
        """Save complete analysis to disk"""
        from utils.json_utils import make_serializable
        meta_path = os.path.join(
            self.metadata_dir, f"{song_id}.json"
        )
        # Convert any non-serializable types
        clean = make_serializable(analysis)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)
