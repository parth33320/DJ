import librosa
import numpy as np
import json
import os

class EntryPointFinder:
    """
    Finds best playback entry points and anchor hooks by combining:
    1. Viewer comment timestamps (highest recognition anchors)
    2. Structural self-similarity matrix repetition (chorus/verse)
    3. RMS energy peaks (drops/hooks)
    """
    def __init__(self, config):
        self.config = config
        self.metadata_dir = config.get('paths', {}).get('metadata', 'data/metadata')
        os.makedirs(self.metadata_dir, exist_ok=True)

    def find_entry_points(self, filepath, analysis, song_id):
        cache_path = os.path.join(self.metadata_dir, f"{song_id}_entries.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

        # Load audio if file exists
        if filepath and os.path.exists(filepath):
            try:
                y, sr = librosa.load(filepath, sr=22050, mono=True)
                duration = len(y) / sr
            except Exception as e:
                print(f"⚠️ Librosa load warning for {song_id}: {e}")
                y, sr = None, 22050
                duration = float(analysis.get('duration', 180.0))
        else:
            y, sr = None, 22050
            duration = float(analysis.get('duration', 180.0))

        # 1. Viewer comment anchor points
        comment_anchors = analysis.get('anchor_points', [])
        if not comment_anchors and 'comments' in analysis:
            # Parse if present
            from ingestion.playlist_watcher import PlaylistWatcher
            pw = PlaylistWatcher(self.config)
            comment_anchors = pw.parse_comment_timestamps(analysis.get('comments', []))

        # 2. Structural Repetition via Self-Similarity Matrix
        repetitive_sections = []
        if y is not None and len(y) > sr * 10:
            try:
                chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
                rec = librosa.segment.recurrence_matrix(chroma, mode='affinity')
                row_sums = np.sum(rec, axis=1)
                # Find top candidate frames
                top_frames = np.argsort(row_sums)[::-1][:5]
                times = librosa.frames_to_time(top_frames, sr=sr)
                repetitive_sections = [float(t) for t in times if t < duration - 10]
            except Exception as e:
                print(f"⚠️ Recurrence matrix calculation skipped: {e}")

        # 3. Bar times & candidates scoring
        bar_times = analysis.get('bar_times', [])
        if not bar_times:
            # Generate default bar grid every 2 seconds (~120 BPM)
            bar_times = [float(t) for t in range(0, int(duration), 2)]

        entry_candidates = []
        for bar_time in bar_times[::4]: # Check every 4 bars
            if bar_time > duration - 10:
                continue

            score = self._score_entry_point(
                y=y, sr=sr, time=bar_time, duration=duration,
                comment_anchors=comment_anchors,
                repetitive_sections=repetitive_sections
            )

            entry_candidates.append({
                'time': float(bar_time),
                'score': float(score),
                'is_comment_anchor': any(abs(bar_time - a['time']) < 5.0 for a in comment_anchors)
            })

        entry_candidates.sort(key=lambda x: x['score'], reverse=True)

        best_entry = entry_candidates[0] if entry_candidates else {'time': 0.0, 'score': 10.0}

        # Override best entry if high-confidence viewer anchor exists
        if comment_anchors:
            top_anchor = comment_anchors[0]
            if top_anchor['time'] < duration - 10:
                best_entry = {
                    'time': float(top_anchor['time']),
                    'score': float(best_entry['score'] + 50.0),
                    'is_comment_anchor': True,
                    'anchor_text': top_anchor.get('text', '')
                }

        result = {
            'standard_start': 0.0,
            'best_entry': best_entry,
            'comment_anchors': comment_anchors,
            'top_5_entries': entry_candidates[:5],
            'all_candidates': entry_candidates
        }

        try:
            with open(cache_path, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

        return result

    def _score_entry_point(self, y, sr, time, duration, comment_anchors, repetitive_sections):
        score = 10.0

        # Comment anchor weight (+40)
        for anchor in comment_anchors:
            if abs(time - anchor['time']) < 4.0:
                score += 40.0 * (anchor.get('likes', 1) / 5.0)

        # Repetition weight (+20)
        for rep_time in repetitive_sections:
            if abs(time - rep_time) < 4.0:
                score += 20.0

        # Audio RMS energy & spectral richness
        if y is not None:
            sample = int(time * sr)
            window = int(sr * 4)
            if sample + window <= len(y):
                segment = y[sample:sample + window]
                rms = float(np.sqrt(np.mean(segment ** 2)))
                score += rms * 25.0

        # Early track preference bonus
        if time < duration * 0.4:
            score *= 1.2

        return score
