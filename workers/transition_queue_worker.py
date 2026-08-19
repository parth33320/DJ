import os
import sys
import time
import shutil
import logging
import threading
import asyncio
from typing import Dict, Optional, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from transition_engine.master_transition import MasterTransitionEngine
from analysis.compatibility_scorer import CompatibilityScorer
from ai_brain.agents.selector_agent import SelectorAgent

logging.basicConfig(level=logging.INFO, format='[QueueWorker] %(asctime)s - %(message)s')

class TransitionQueueWorker:
    """
    Asynchronous semi-live background queue worker.
    Pre-renders the next transition pair into output/next_pair.mp3 while current_pair plays live.
    Supports seamless hot-swapping zero-dead-air promotion and request injection.
    """
    def __init__(self, config: Dict, app_context=None):
        self.config = config
        self.app = app_context
        self.output_dir = os.path.abspath("output")
        os.makedirs(self.output_dir, exist_ok=True)

        self.current_pair_file = os.path.join(self.output_dir, "current_pair.mp3")
        self.next_pair_file = os.path.join(self.output_dir, "next_pair.mp3")

        self.engine = MasterTransitionEngine(config)
        self.selector = SelectorAgent(config)
        self.scorer = CompatibilityScorer(config)

        self.pending_requests: List[Dict] = []
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        self.current_pair_info: Optional[Dict] = None
        self.next_pair_info: Optional[Dict] = None

    def inject_request(self, song_metadata: Dict):
        """Injects a user-requested song into the queue for the next transition."""
        with self.lock:
            self.pending_requests.append(song_metadata)
            logging.info(f"📥 Song request injected: {song_metadata.get('title', 'Unknown')}")

    def pre_render_pair(self, song_a_id: str, song_b_id: str, metadata_cache: Dict, target_filepath: str) -> Optional[str]:
        """
        Pre-renders a transition mix pair into target_filepath.
        Returns the output path if successful.
        """
        if song_a_id not in metadata_cache or song_b_id not in metadata_cache:
            logging.error(f"❌ Missing metadata for {song_a_id} or {song_b_id}")
            return None

        ana_a = metadata_cache[song_a_id]
        ana_b = metadata_cache[song_b_id]

        compat = self.scorer.score(ana_a, ana_b)
        technique = compat.get('recommended_transition', 'beatmatch_crossfade')
        params = {'crossfade_bars': 8, 'duration': 16}

        logging.info(f"⚡ Pre-rendering pair: {ana_a.get('title', song_a_id[:8])} -> {ana_b.get('title', song_b_id[:8])} ({technique})")

        out_path = self.engine.generate_transition_mix(
            cur_id=song_a_id,
            nxt_id=song_b_id,
            technique=technique,
            params=params,
            cur_ana=ana_a,
            nxt_ana=ana_b
        )

        if out_path and os.path.exists(out_path):
            # Target extension
            if target_filepath.endswith('.mp3') and out_path.endswith('.wav'):
                target_filepath = target_filepath.replace('.mp3', '.wav')
            shutil.copy(out_path, target_filepath)
            logging.info(f"✅ Pre-rendered pair ready at {target_filepath}")
            return target_filepath
        else:
            logging.error("❌ Pre-rendering failed")
            return None

    def promote_next_to_current(self) -> bool:
        """
        Promotes next_pair file/info to current_pair, enabling seamless hot-swap.
        """
        with self.lock:
            next_wav = self.next_pair_file.replace('.mp3', '.wav')
            curr_wav = self.current_pair_file.replace('.mp3', '.wav')

            source = next_wav if os.path.exists(next_wav) else self.next_pair_file
            target = curr_wav if source.endswith('.wav') else self.current_pair_file

            if os.path.exists(source):
                shutil.move(source, target)
                self.current_pair_info = self.next_pair_info
                self.next_pair_info = None
                logging.info(f"🔄 Promoted {source} to {target}")
                return True
            else:
                logging.warning(f"⚠️ No next_pair file found at {source} to promote")
                return False

    def start_worker(self, metadata_cache: Dict):
        """Starts background worker thread."""
        self.is_running = True
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(metadata_cache,),
            daemon=True
        )
        self.worker_thread.start()
        logging.info("🚀 Background transition queue worker started")

    def stop_worker(self):
        """Stops background worker thread."""
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3)
        logging.info("🛑 Background transition queue worker stopped")

    def _worker_loop(self, metadata_cache: Dict):
        """Continuous background loop for pre-rendering next pair."""
        while self.is_running:
            try:
                # Check if next_pair is missing or needs staging
                next_wav = self.next_pair_file.replace('.mp3', '.wav')
                if not os.path.exists(self.next_pair_file) and not os.path.exists(next_wav):
                    if not metadata_cache:
                        time.sleep(2)
                        continue

                    # Determine track A and track B
                    with self.lock:
                        if self.pending_requests:
                            req = self.pending_requests.pop(0)
                            song_b_id = req.get('id')
                            metadata_cache[song_b_id] = req
                        else:
                            song_b_id = None

                    available_keys = list(metadata_cache.keys())
                    if len(available_keys) < 2:
                        time.sleep(2)
                        continue

                    import random
                    song_a_id = random.choice(available_keys)
                    if not song_b_id:
                        remaining = [k for k in available_keys if k != song_a_id]
                        song_b_id = random.choice(remaining) if remaining else song_a_id

                    rendered = self.pre_render_pair(
                        song_a_id, song_b_id, metadata_cache, self.next_pair_file
                    )

                    if rendered:
                        self.next_pair_info = {
                            'song_a': song_a_id,
                            'song_b': song_b_id,
                            'rendered_at': time.time(),
                            'filepath': rendered
                        }

                time.sleep(1)
            except Exception as e:
                logging.error(f"Error in queue worker loop: {e}")
                time.sleep(2)
