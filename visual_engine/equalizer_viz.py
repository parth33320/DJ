import numpy as np
from PIL import Image, ImageDraw
import librosa
import math

class EqualizerViz:
    """
    Real-time frequency equalizer visualizer
    Analyzes actual audio being played
    """
    def __init__(self, config):
        self.config = config
        self.width = config['visual']['width']
        self.height = config['visual']['height']
        self.sr = config['audio']['sample_rate']
        self.bar_count = 128
        self.smoothed_bars = np.zeros(self.bar_count)
        self.decay = 0.85

    def generate_frame(self, audio_chunk, genre_hint='Pop/Other'):
        """
        Generate equalizer frame from audio chunk
        Returns PIL Image
        """
        img = Image.new('RGB', (self.width, self.height), (5, 5, 15))
        draw = ImageDraw.Draw(img)

        # Get frequency data from audio chunk
        if audio_chunk is not None and len(audio_chunk) > 0:
            bars = self._compute_fft_bars(audio_chunk)
        else:
            bars = np.zeros(self.bar_count)

        # Smooth bars with decay
        self.smoothed_bars = (
            np.maximum(bars, self.smoothed_bars * self.decay)
        )

        # Get color scheme from genre
        color_scheme = self._genre_colors(genre_hint)

        self._draw_bars(draw, self.smoothed_bars, color_scheme)
        self._draw_peak_dots(draw, bars, self.smoothed_bars)
        self._draw_reflection(draw, self.smoothed_bars, color_scheme)

        return img

    def _compute_fft_bars(self, audio_chunk):
        """Compute FFT and map to bar heights"""
        # FFT
        fft = np.abs(np.fft.rfft(audio_chunk, n=2048))
        fft = fft[:len(fft)//2]

        # Map FFT bins to bar_count bars (logarithmic)
        bars = np.zeros(self.bar_count)
        fft_len = len(fft)

        for i in range(self.bar_count):
            # Log scale: more bars for low frequencies
            start = int((i / self.bar_count) ** 2 * fft_len)
            end = int(((i + 1) / self.bar_count) ** 2 * fft_len)
            end = max(end, start + 1)
            end = min(end, fft_len)

            if start < fft_len:
                bars[i] = np.mean(fft[start:end])

        # Normalize
        max_val = np.max(bars)
        if max_val > 0:
            bars = bars / max_val

        return bars

    def _genre_colors(self, genre_hint):
        """Get color gradient based on genre"""
        schemes = {
            'EDM/Techno':   [(0, 200, 255), (150, 0, 255)],
            'House/Dance':  [(255, 100, 0), (255, 0, 150)],
            'Hip-Hop/Rap':  [(255, 200, 0), (255, 80, 0)],
            'R&B/Soul':     [(200, 0, 100), (100, 0, 200)],
            'Rock/Metal':   [(255, 50, 0), (200, 0, 0)],
            'Ambient/Chill':[(0, 150, 200), (0, 50, 150)],
            'Pop/Other':    [(100, 0, 255), (255, 0, 150)],
        }
        return schemes.get(genre_hint, schemes['Pop/Other'])

    def _draw_bars(self, draw, bars, colors):
        """Draw main equalizer bars"""
        bar_width = self.width // self.bar_count
        max_height = int(self.height * 0.7)
        base_y = int(self.height * 0.85)

        for i, bar_val in enumerate(bars):
            bar_height = int(bar_val * max_height)
            if bar_height < 2:
                bar_height = 2

            x = i * bar_width

            # Interpolate color based on position
            progress = i / self.bar_count
            r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * progress)
            g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * progress)
            b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * progress)

            # Brighter at top
            brightness = 0.5 + (bar_val * 0.5)
            color = (
                min(255, int(r * brightness)),
                min(255, int(g * brightness)),
                min(255, int(b * brightness))
            )

            draw.rectangle(
                [x + 1, base_y - bar_height,
                 x + bar_width - 1, base_y],
                fill=color
            )

    def _draw_peak_dots(self, draw, current_bars, smoothed_bars):
        """Draw peak indicator dots above bars"""
        bar_width = self.width // self.bar_count
        max_height = int(self.height * 0.7)
        base_y = int(self.height * 0.85)

        for i, bar_val in enumerate(smoothed_bars):
            peak_y = base_y - int(bar_val * max_height) - 5
            x = i * bar_width + bar_width // 2
            draw.ellipse(
                [x - 2, peak_y - 2, x + 2, peak_y + 2],
                fill=(255, 255, 255)
            )

    def _draw_reflection(self, draw, bars, colors):
        """Draw mirrored reflection below bars"""
        bar_width = self.width // self.bar_count
        max_height = int(self.height * 0.15)
        base_y = int(self.height * 0.85)

        for i, bar_val in enumerate(bars):
            bar_height = int(bar_val * max_height)

            x = i * bar_width
            progress = i / self.bar_count
            r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * progress)
            g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * progress)
            b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * progress)

            # Dimmer reflection
            color = (r // 4, g // 4, b // 4)

            draw.rectangle(
                [x + 1, base_y,
                 x + bar_width - 1, base_y + bar_height],
                fill=color
            )
