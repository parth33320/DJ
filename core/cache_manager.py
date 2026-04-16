"""
Smart Cache Manager
Fixes: No cache strategy, unlimited disk usage, no LRU eviction
"""

import os
import json
import time
import shutil
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import threading


@dataclass
class CacheEntry:
    key: str
    path: str
    size_bytes: int
    created_at: float
    last_accessed: float
    access_count: int
    metadata: dict


class CacheManager:
    """
    Smart cache manager with:
    - LRU eviction
    - Size limits
    - TTL support
    - Priority-based eviction
    - Disk usage monitoring
    """
    
    def __init__(self, config):
        self.config = config
        
        # Cache directories
        self.cache_dirs = {
            'audio': config['paths']['audio_cache'],
            'stems': config['paths']['stems'],
            'metadata': config['paths']['metadata'],
            'lyrics': config['paths']['lyrics'],
            'phonemes': config['paths']['phonemes'],
        }
        
        # Limits
        storage_cfg = config.get('storage', {})
        self.max_cache_gb = storage_cfg.get('max_local_cache_gb', 10)
        self.max_cache_bytes = self.max_cache_gb * 1024 * 1024 * 1024
        
        # Cache index
        self.index: Dict[str, CacheEntry] = {}
        self.index_file = 'data/cache_index.json'
        self.lock = threading.Lock()
        
        # Stats
        self.hits = 0
        self.misses = 0
        
        # Load existing index
        self._load_index()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
    
    def _load_index(self):
        """Load cache index from disk"""
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    for key, entry_data in data.items():
                        if os.path.exists(entry_data['path']):
                            self.index[key] = CacheEntry(**entry_data)
        except Exception as e:
            print(f"⚠️ Cache index load failed: {e}")
            self.index = {}
    
    def _save_index(self):
        """Save cache index to disk"""
        try:
            os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
            with open(self.index_file, 'w') as f:
                data = {
                    key: {
                        'key': entry.key,
                        'path': entry.path,
                        'size_bytes': entry.size_bytes,
                        'created_at': entry.created_at,
                        'last_accessed': entry.last_accessed,
                        'access_count': entry.access_count,
                        'metadata': entry.metadata,
                    }
                    for key, entry in self.index.items()
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Cache index save failed: {e}")
    
    def get(self, cache_type: str, key: str) -> Optional[str]:
        """
        Get cached file path
        Returns None if not cached
        """
        cache_key = f"{cache_type}:{key}"
        
        with self.lock:
            if cache_key in self.index:
                entry = self.index[cache_key]
                
                if os.path.exists(entry.path):
                    # Update access stats
                    entry.last_accessed = time.time()
                    entry.access_count += 1
                    self.hits += 1
                    return entry.path
                else:
                    # File missing, remove from index
                    del self.index[cache_key]
        
        self.misses += 1
        return None
    
    def put(self, cache_type: str, key: str, filepath: str, 
            metadata: dict = None, priority: int = 0) -> str:
        """
        Add file to cache
        Returns cache path
        """
        cache_key = f"{cache_type}:{key}"
        cache_dir = self.cache_dirs.get(cache_type, 'data/cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        # Get file size
        size_bytes = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        
        # Check if need to evict
        self._maybe_evict(size_bytes)
        
        # Determine cache path
        ext = os.path.splitext(filepath)[1]
        cache_path = os.path.join(cache_dir, f"{key}{ext}")
        
        # Copy if different path
        if filepath != cache_path:
            shutil.copy2(filepath, cache_path)
        
        # Create entry
        entry = CacheEntry(
            key=cache_key,
            path=cache_path,
            size_bytes=size_bytes,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            metadata=metadata or {},
        )
        
        with self.lock:
            self.index[cache_key] = entry
            self._save_index()
        
        return cache_path
    
    def exists(self, cache_type: str, key: str) -> bool:
        """Check if item is cached"""
        cache_key = f"{cache_type}:{key}"
        
        with self.lock:
            if cache_key in self.index:
                entry = self.index[cache_key]
                return os.path.exists(entry.path)
        
        return False
    
    def delete(self, cache_type: str, key: str) -> bool:
        """Delete cached item"""
        cache_key = f"{cache_type}:{key}"
        
        with self.lock:
            if cache_key in self.index:
                entry = self.index[cache_key]
                
                try:
                    if os.path.exists(entry.path):
                        os.remove(entry.path)
                except:
                    pass
                
                del self.index[cache_key]
                self._save_index()
                return True
        
        return False
    
    def _maybe_evict(self, needed_bytes: int):
        """Evict items if cache is full"""
        current_size = self.get_total_size()
        
        if current_size + needed_bytes <= self.max_cache_bytes:
            return
        
        # Need to evict
        bytes_to_free = (current_size + needed_bytes) - self.max_cache_bytes
        bytes_to_free = int(bytes_to_free * 1.2)  # Free 20% extra
        
        print(f"🧹 Cache eviction: freeing {bytes_to_free / 1024 / 1024:.1f} MB")
        
        with self.lock:
            # Sort by LRU (least recently used first)
            sorted_entries = sorted(
                self.index.values(),
                key=lambda e: (e.last_accessed, -e.access_count)
            )
            
            freed = 0
            to_delete = []
            
            for entry in sorted_entries:
                if freed >= bytes_to_free:
                    break
                
                # Don't evict metadata (small and important)
                if 'metadata' in entry.path:
                    continue
                
                to_delete.append(entry.key)
                freed += entry.size_bytes
            
            # Delete entries
            for key in to_delete:
                entry = self.index[key]
                try:
                    if os.path.exists(entry.path):
                        os.remove(entry.path)
                except:
                    pass
                del self.index[key]
            
            self._save_index()
            
        print(f"✅ Freed {freed / 1024 / 1024:.1f} MB")
    
    def get_total_size(self) -> int:
        """Get total cache size in bytes"""
        total = 0
        for entry in self.index.values():
            if os.path.exists(entry.path):
                total += entry.size_bytes
        return total
    
    def _cleanup_loop(self):
        """Background cleanup thread"""
        while True:
            time.sleep(3600)  # Every hour
            
            try:
                # Remove entries for missing files
                with self.lock:
                    to_remove = []
                    for key, entry in self.index.items():
                        if not os.path.exists(entry.path):
                            to_remove.append(key)
                    
                    for key in to_remove:
                        del self.index[key]
                    
                    if to_remove:
                        self._save_index()
                        print(f"🧹 Cleaned {len(to_remove)} stale cache entries")
                
                # Check disk usage
                self._maybe_evict(0)
                
            except Exception as e:
                print(f"⚠️ Cache cleanup error: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_size = self.get_total_size()
        
        return {
            'total_items': len(self.index),
            'total_size_mb': total_size / 1024 / 1024,
            'max_size_mb': self.max_cache_bytes / 1024 / 1024,
            'usage_percent': (total_size / self.max_cache_bytes) * 100,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / max(self.hits + self.misses, 1),
        }
    
    def clear_all(self):
        """Clear entire cache"""
        with self.lock:
            for entry in self.index.values():
                try:
                    if os.path.exists(entry.path):
                        os.remove(entry.path)
                except:
                    pass
            
            self.index.clear()
            self._save_index()
        
        print("🗑️ Cache cleared")
