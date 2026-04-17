import os
import subprocess
import shutil

class StemSeparator:
    def __init__(self, config):
        self.config = config
        self.stems_dir = config['paths']['stems']
        self.cache_dir = config['paths']['audio_cache']
        os.makedirs(self.stems_dir, exist_ok=True)

    def separate(self, filepath, song_id, start_time=0):
        """
        Ultra-optimized local separation.
        Instead of processing a 4-minute song (which takes 100% CPU for 5 mins),
        we trim the audio to just 90 seconds around the transition point.
        This takes only ~15 seconds on a standard laptop and needs NO cloud!
        """
        song_stems_dir = os.path.join(self.stems_dir, song_id)
        os.makedirs(song_stems_dir, exist_ok=True)

        stems = {
            'vocals': os.path.join(song_stems_dir, 'vocals.wav'),
            'melody': os.path.join(song_stems_dir, 'other.wav'),
            'drums': os.path.join(song_stems_dir, 'drums.wav'),
            'bass': os.path.join(song_stems_dir, 'bass.wav')
        }

        # If we already have the stems, skip instantly!
        if all(os.path.exists(v) for v in stems.values()):
            return stems

        print(f"✂️  Trimming and Separating Stems for {song_id} (Ultra-Fast Mode)...")

        # 1. Trim audio to 90 seconds (saves 90% of computer power!)
        temp_trim = os.path.join(self.cache_dir, f"{song_id}_trimmed.wav").replace("\\", "/")
        try:
            # Safely get a start time that won't go out of bounds
            safe_start = max(0, start_time - 10)
            subprocess.run([
                "ffmpeg", "-y", "-i", filepath.replace("\\", "/"), 
                "-ss", str(safe_start), "-t", "90", 
                "-ac", "2", "-ar", "44100", temp_trim
            ], check=True, capture_output=True)
        except Exception as e:
            print(f"⚠️ FFmpeg trim failed, using full file: {e}")
            temp_trim = filepath

        # 2. Run Local Demucs (Extremely fast on a 90s trim!)
        try:
            # This runs silently in the background
            subprocess.run([
                "demucs", "-n", "htdemucs",
                "--out", self.stems_dir,
                temp_trim
            ], check=True, capture_output=True)

            # Demucs outputs to: stems_dir/htdemucs/song_id_trimmed/...
            trim_basename = os.path.basename(temp_trim).replace(".wav", "")
            out_folder = os.path.join(self.stems_dir, "htdemucs", trim_basename)

            # Move stems to our expected dictionary paths
            if os.path.exists(out_folder):
                for stem_name in ['vocals', 'other', 'drums', 'bass']:
                    src = os.path.join(out_folder, f"{stem_name}.wav")
                    
                    if stem_name == 'other': dst = stems['melody']
                    else: dst = stems[stem_name]
                    
                    if os.path.exists(src):
                        shutil.copy(src, dst)

                # Clean up Demucs default output folder
                shutil.rmtree(os.path.join(self.stems_dir, "htdemucs"), ignore_errors=True)

            print(f"✅ Fast Stems generated locally for: {song_id}")

        except FileNotFoundError:
            print("❌ Demucs not installed! Fallback to original audio.")
            print("💡 FIX: Open terminal and type: pip install -U demucs")
            self._create_fake_stems(temp_trim, stems)
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Demucs processing failed: {e}")
            self._create_fake_stems(temp_trim, stems)

        # Cleanup the temporary 90s trim file
        if temp_trim != filepath and os.path.exists(temp_trim):
            try:
                os.remove(temp_trim)
            except Exception:
                pass

        return stems

    def _create_fake_stems(self, filepath, stems):
        """
        Ultimate safety net: If Demucs crashes or isn't installed, 
        copy the original audio as the stems so the DJ app NEVER crashes.
        """
        print("⚠️ Using original audio as fallback stems to prevent app crash!")
        for path in stems.values():
            if not os.path.exists(path):
                shutil.copy(filepath, path)
