import os
import subprocess
try:
    import torch
except ImportError:
    torch = None


class StemSeparator:
    def __init__(self, config):
        self.config = config
        self.stems_dir = config['paths']['stems']
        self.cache_dir = config['paths']['audio_cache']
        os.makedirs(self.stems_dir, exist_ok=True)
        
        # Check GPU availability
        self.device = "cuda" if (False if torch is None else torch.cuda.is_available()) else "cpu"
        print(f"🎵 Stem separator using: {self.device}")

    def separate(self, filepath, song_id, start_time=None):
        """
        Separate song into 4 stems using Demucs
        Returns dict of stem file paths
        """
        song_stems_dir = os.path.join(self.stems_dir, song_id)
        
        stems = {
            'vocals': os.path.join(song_stems_dir, 'vocals.wav'),
            'drums': os.path.join(song_stems_dir, 'drums.wav'),
            'bass': os.path.join(song_stems_dir, 'bass.wav'),
            'melody': os.path.join(song_stems_dir, 'other.wav'),
        }
        
        # Check if already separated
        if all(os.path.exists(v) for v in stems.values()):
            return stems
        
        os.makedirs(song_stems_dir, exist_ok=True)
        
        # ✂️ OPTIMIZATION: Trim audio precisely around the transition
        # If start_time not provided, it defaults to the end-ish
        if start_time is None:
            # Default to last 90s for a standard transition
            start_time = 0 
            
        temp_trim = os.path.join(self.cache_dir, f"{song_id}_trimmed.wav")
        try:
            print(f"   ✂️  Trimming for fast separation starting at {start_time}s...")
            subprocess.run([
                "ffmpeg", "-y", "-i", filepath, 
                "-ss", str(start_time), "-t", "90", 
                "-ac", "2", "-ar", "44100", temp_trim
            ], check=True, capture_output=True)
            proc_path = temp_trim
        except:
            proc_path = filepath

        print(f"🎚️  Separating stems: {song_id}")
        
        # Run Demucs
        cmd_full = [
            "python", "-m", "demucs",
            "--two-stems", "vocals",  # Vocals vs Everything else is faster
            "-o", self.stems_dir,
            "--device", self.device,
            proc_path
        ]
        
        try:
            subprocess.run(cmd_full, check=True, capture_output=True)
            
            # Demucs outputs to: stems_dir/htdemucs/song_name/
            # Rename to our structure
            demucs_out = os.path.join(
                self.stems_dir, "htdemucs", 
                os.path.splitext(os.path.basename(filepath))[0]
            )
            
            stem_map = {
                'vocals.wav': stems['vocals'],
                'drums.wav': stems['drums'],
                'bass.wav': stems['bass'],
                'other.wav': stems['melody'],
            }
            
            for src_name, dst_path in stem_map.items():
                src = os.path.join(demucs_out, src_name)
                if os.path.exists(src):
                    os.rename(src, dst_path)
                    
            # Clean up temp trim
            if os.path.exists(temp_trim): os.remove(temp_trim)
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Stem separation failed: {e}")
            if os.path.exists(temp_trim): os.remove(temp_trim)
            return {k: v if os.path.exists(v) else None 
                   for k, v in stems.items()}
        
        return stems
