import os
import json
import numpy as np
from visual_engine.stick_figure_gen import StickFigureGen
from visual_engine.equalizer_viz import EqualizerViz
from visual_engine.lyric_display import LyricDisplay
from visual_engine.waveform_display import WaveformDisplay

class VisualAgent:
    """
    Agent 7: Visual Director
    Decides what to show on screen at any moment
    Coordinates stick figures, equalizer,
    waveforms, and lyric display
    Outputs frames to OBS bridge
    """
    def __init__(self, config):
        self.config = config
        self.width = config['visual']['width']
        self.height = config['visual']['height']
        self.fps = config['visual']['fps']

        # Visual engines
        self.stick_gen = StickFigureGen(config)
        self.eq_viz = EqualizerViz(config)
        self.lyric_display = LyricDisplay(config)
        self.waveform_display = WaveformDisplay(config)

        # State
        self.current_sentiment = 'neutral'
        self.current_genre = 'Pop/Other'
        self.has_lyrics = False
        self.transition_active = False
        self.transition_technique = ''

        # Sentiment keyword mappings
        self.sentiment_keywords = {
            'happy': [
                'happy', 'joy', 'smile', 'dance', 'party',
                'celebrate', 'fun', 'good', 'great', 'love',
                'beautiful', 'amazing', 'wonderful', 'khushi',
                'pyaar', 'rang', 'zindagi'
            ],
            'sad': [
                'sad', 'cry', 'tears', 'miss', 'lonely',
                'broken', 'pain', 'hurt', 'alone', 'sorry',
                'dard', 'dil', 'judaai', 'aansu'
            ],
            'angry': [
                'angry', 'fight', 'hate', 'war', 'kill',
                'mad', 'rage', 'fire', 'burn', 'destroy'
            ],
            'hype': [
                'hype', 'pump', 'go', 'run', 'fast',
                'power', 'energy', 'bounce', 'drop', 'bass',
                'money', 'rich', 'gang', 'lit', 'fire'
            ],
            'love': [
                'love', 'baby', 'heart', 'forever', 'together',
                'kiss', 'hold', 'feel', 'need', 'want',
                'ishq', 'mohabbat', 'dil', 'jaanu', 'saath'
            ]
        }

    def analyze_sentiment(self, lyrics_text):
        """
        Analyze lyrics sentiment
        Returns sentiment string
        """
        if not lyrics_text:
            return 'neutral'

        text_lower = lyrics_text.lower()
        scores = {sentiment: 0 for sentiment in self.sentiment_keywords}

        for sentiment, keywords in self.sentiment_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[sentiment] += 1

        # Return highest scoring sentiment
        max_sentiment = max(scores, key=scores.get)
        if scores[max_sentiment] == 0:
            return 'neutral'
        return max_sentiment

    def update_song(self, analysis):
        """
        Called when new song starts playing
        Updates visual state for new song
        """
        self.current_genre = analysis.get('genre_hint', 'Pop/Other')

        lyrics = analysis.get('lyrics')
        self.has_lyrics = (
            lyrics is not None and
            bool(lyrics.get('text', '').strip())
        )

        if self.has_lyrics:
            self.current_sentiment = self.analyze_sentiment(
                lyrics.get('text', '')
            )
        else:
            self.current_sentiment = 'neutral'

        print(f"   🎨 Visual: genre={self.current_genre} "
              f"sentiment={self.current_sentiment} "
              f"lyrics={self.has_lyrics}")

    def generate_frame(self, audio_chunk, current_time,
                       energy, beat_time, analysis):
        """
        Generate a complete video frame
        Composites all visual layers
        Returns PIL Image
        """
        from PIL import Image

        lyrics_data = analysis.get('lyrics')
        timed_words = lyrics_data.get('timed_words', []) if lyrics_data else []

        # Base layer: stick figures or equalizer
        if self.has_lyrics and self.current_sentiment != 'neutral':
            frame = self.stick_gen.generate_frame(
                lyrics_data,
                beat_time,
                energy,
                self.current_sentiment
            )
        else:
            frame = self.eq_viz.generate_frame(
                audio_chunk,
                self.current_genre
            )

        # Overlay lyrics
        if self.has_lyrics and timed_words:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(frame)
            self.lyric_display.draw_lyrics(
                draw, timed_words, current_time
            )

        # Overlay transition indicator
        if self.transition_active:
            frame = self._draw_transition_overlay(
                frame, self.transition_technique
            )

        return frame

    def _draw_transition_overlay(self, frame, technique):
        """Draw transition name overlay"""
        from PIL import ImageDraw
        draw = ImageDraw.Draw(frame)

        text = f"▶ {technique.replace('_', ' ').upper()}"

        # Draw with glow effect
        for offset in [(2, 2), (-2, -2), (2, -2), (-2, 2)]:
            draw.text(
                (self.width // 2 - 200 + offset[0],
                 30 + offset[1]),
                text,
                fill=(100, 80, 0)
            )

        draw.text(
            (self.width // 2 - 200, 30),
            text,
            fill=(255, 220, 50)
        )

        return frame

    def set_transition(self, technique, active=True):
        """Signal that a transition is happening"""
        self.transition_active = active
        self.transition_technique = technique

    def get_background_color(self):
        """Get current background color based on genre"""
        genre_colors = {
            'EDM/Techno':    (5, 0, 20),
            'House/Dance':   (20, 5, 0),
            'Hip-Hop/Rap':   (10, 8, 0),
            'R&B/Soul':      (15, 0, 10),
            'Rock/Metal':    (20, 0, 0),
            'Ambient/Chill': (0, 5, 20),
            'Pop/Other':     (5, 0, 15),
        }
        return genre_colors.get(self.current_genre, (10, 10, 20))
