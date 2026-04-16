from PIL import Image, ImageDraw, ImageFont
import os
import math

class LyricDisplay:
    """
    Karaoke-style lyric display
    Highlights current word as it's sung
    """
    def __init__(self, config):
        self.config = config
        self.width = config['visual']['width']
        self.height = config['visual']['height']
        self.current_line = ""
        self.next_line = ""
        self.current_word_idx = 0

        # Try to load a font
        self.font_large = self._load_font(52)
        self.font_small = self._load_font(36)

    def _load_font(self, size):
        """Load font with fallback"""
        font_paths = [
            "C:/Windows/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def update(self, timed_words, current_time):
        """
        Update display state based on current playback time
        Returns (current_word, line_of_words)
        """
        if not timed_words:
            return None, []

        current_word = None
        visible_words = []

        for i, word_entry in enumerate(timed_words):
            start = word_entry.get('start', 0)
            end = word_entry.get('end', start + 0.3)

            # Show words in a 5 second window
            if current_time - 2 <= start <= current_time + 3:
                visible_words.append({
                    'word': word_entry['word'],
                    'start': start,
                    'end': end,
                    'active': start <= current_time <= end
                })

            if start <= current_time <= end:
                current_word = word_entry['word']

        return current_word, visible_words

    def draw_lyrics(self, draw, timed_words, current_time):
        """
        Draw karaoke-style lyrics on frame
        Active word is highlighted/larger
        """
        if not timed_words:
            return

        current_word, visible_words = self.update(timed_words, current_time)

        if not visible_words:
            return

        # Build display line
        lyric_y = int(self.height * 0.82)
        total_width = 0
        word_positions = []

        # Measure total width
        for entry in visible_words:
            font = self.font_large if entry['active'] else self.font_small
            try:
                bbox = draw.textbbox((0, 0), entry['word'] + " ", font=font)
                w = bbox[2] - bbox[0]
            except Exception:
                w = len(entry['word']) * 20

            word_positions.append((entry, w))
            total_width += w

        # Center the line
        start_x = (self.width - total_width) // 2
        current_x = start_x

        for entry, w in word_positions:
            word = entry['word']
            is_active = entry['active']

            if is_active:
                color = (255, 255, 100)  # Yellow highlight
                font = self.font_large
                # Draw glow effect
                for offset in [(1,0),(-1,0),(0,1),(0,-1)]:
                    draw.text(
                        (current_x + offset[0], lyric_y + offset[1]),
                        word + " ",
                        font=font,
                        fill=(200, 150, 0)
                    )
            else:
                color = (200, 200, 200)  # White
                font = self.font_small

            draw.text(
                (current_x, lyric_y),
                word + " ",
                font=font,
                fill=color
            )
            current_x += w
