"""
Smart Prefetcher - Download and analyze next songs in advance
Fixes: Blocking downloads, no lookahead, cold starts
"""

import threading
import queue
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PrefetchJob:
    song_id: str
    priority: int
    requested_at: float
    status: str = 'pending'  # pending, downloading, analyzing, ready, failed
    filepath: Optional[str] = None
    analysis: Optional[dict] = None
    error: Optional[str] = None


class Prefetcher:
    """
    Smart prefetcher that:
    - Downloads next N songs in advance
    - Pre-analyzes if not in cache
    - Prioritizes based on play probability
    - Cleans up after playback
    """
    
    def __init__(self, config, downloader, analyzer, cache_manager):
        self.config = config
        self.downloader = downloader
        self.analyzer = analyzer
        self.cache = cache_manager
        
        # How many songs to prefetch
        self.lookahead = config.get('prefetch', {}).get('lookahead', 3)
        
        # Jobs
        self.jobs: Dict[str, PrefetchJob] = {}
        self.job_queue = queue.PriorityQueue()
        
        # Workers
        self.is_running = False
        self.download_thread = None
        self.analyze_thread = None
        
        # Currently playing
        self.current_song_id = None
        
    def start(self):
        """Start prefetcher"""
        if self.is_running:
            return
        
        self.is_running = True
        
        self.download_thread = threading.Thread(
            target=self._download_loop,
            daemon=True
        )
        self.download_thread.start()
        
        self.analyze_thread = threading.Thread(
            target=self._analyze_loop,
            daemon=True
        )
        self.analyze_thread.start()
        
        print("🚀 Prefetcher started")
    
    def stop(self):
        """Stop prefetcher"""
        self.is_running = False
        print("⏹️ Prefetcher stopped")
    
    def prefetch(self, song_ids: List[str], song_metadata: Dict[str, dict]):
        """
        Request prefetch for list of song IDs
        Called when selector picks next songs
        """
        for priority, song_id in enumerate(song_ids[:self.lookahead]):
            if song_id in self.jobs:
                continue
            
            job = PrefetchJob(
                song_id=song_id,
                priority=priority,
                requested_at=time.time(),
            )
            
            self.jobs[song_id] = job
            
            # Check if already cached
            if self.cache.exists('audio', song_id):
                job.filepath = self.cache.get('audio', song_id)
                job.status = 'analyzing'
            else:
                self.job_queue.put((priority, song_id, 'download'))
    
    def get_ready_song(self, song_id: str) -> Optional[dict]:
        """
        Get prefetched song if ready
        Returns {'filepath': ..., 'analysis': ...} or None
        """
        if song_id not in self.jobs:
            return None
        
        job = self.jobs[song_id]
        
        if job.status == 'ready':
            return {
                'filepath': job.filepath,
                'analysis': job.analysis,
            }
        
        return None
    
    def wait_for_song(self, song_id: str, timeout: float = 30) -> Optional[dict]:
        """
        Wait for song to be ready
        Returns result or None if timeout
        """
        start = time.time()
        
        while time.time() - start < timeout:
            result = self.get_ready_song(song_id)
            if result:
                return result
            
            # Check if failed
            if song_id in self.jobs and self.jobs[song_id].status == 'failed':
                return None
            
            time.sleep(0.5)
        
        return None
    
    def set_current_song(self, song_id: str):
        """
        Mark song as currently playing
        Cleans up older prefetched songs
        """
        self.current_song_id = song_id
        
        # Remove from jobs (no longer needed in prefetch)
        if song_id in self.jobs:
            del self.jobs[song_id]
        
        # Cleanup old jobs
        self._cleanup_old_jobs()
    
    def _download_loop(self):
        """Download worker loop"""
        while self.is_running:
            try:
                priority, song_id, action = self.job_queue.get(timeout=1)
                
                if action != 'download':
                    continue
                
                if song_id not in self.jobs:
                    continue
                
                job = self.jobs[song_id]
                
                if job.status != 'pending':
                    continue
                
                job.status = 'downloading'
                
                try:
                    # Get song URL from metadata
                    # This assumes we have access to playlist info
                    url = f"https://youtube.com/watch?v={song_id}"
                    
                    filepath = self.downloader.download_song(url, song_id)
                    job.filepath = filepath
                    job.status = 'analyzing'
                    
                    # Queue for analysis
                    self.job_queue.put((priority, song_id, 'analyze'))
                    
                except Exception as e:
                    job.status = 'failed'
                    job.error = str(e)
                    print(f"❌ Prefetch download failed for {song_id}: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Prefetch download error: {e}")
    
    def _analyze_loop(self):
        """Analysis worker loop"""
        while self.is_running:
            try:
                # Find jobs needing analysis
                for song_id, job in list(self.jobs.items()):
                    if job.status != 'analyzing':
                        continue
                    
                    if not job.filepath:
                        continue
                    
                    try:
                        # Check cache first
                        cached = self.cache.get('metadata', song_id)
                        if cached:
                            import json
                            with open(cached, 'r') as f:
                                job.analysis = json.load(f)
                            job.status = 'ready'
                            continue
                        
                        # Run analysis
                        analysis = self.analyzer.analyze_track(
                            job.filepath, song_id
                        )
                        job.analysis = analysis
                        job.status = 'ready'
                        
                        print(f"✅ Prefetched: {song_id}")
                        
                    except Exception as e:
                        job.status = 'failed'
                        job.error = str(e)
                        print(f"❌ Prefetch analysis failed for {song_id}: {e}")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Prefetch analyze error: {e}")
                time.sleep(1)
    
    def _cleanup_old_jobs(self):
        """Remove old completed/failed jobs"""
        current_time = time.time()
        max_age = 600  # 10 minutes
        
        to_remove = []
        
        for song_id, job in self.jobs.items():
            if song_id == self.current_song_id:
                continue
            
            age = current_time - job.requested_at
            
            if age > max_age and job.status in ['ready', 'failed']:
                to_remove.append(song_id)
                
                # Delete audio file to save space
                if job.filepath and job.status == 'ready':
                    try:
                        self.cache.delete('audio', song_id)
                    except:
                        pass
        
        for song_id in to_remove:
            del self.jobs[song_id]
    
    def get_stats(self) -> dict:
        """Get prefetcher statistics"""
        status_counts = {}
        for job in self.jobs.values():
            status_counts[job.status] = status_counts.get(job.status, 0) + 1
        
        return {
            'total_jobs': len(self.jobs),
            'queue_size': self.job_queue.qsize(),
            'status_counts': status_counts,
            'lookahead': self.lookahead,
        }
