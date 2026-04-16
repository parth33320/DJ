"""
Streaming module - Multi-platform streaming without OBS

Supports 50+ platforms via Restream.io or direct RTMP connections:

POPULAR PLATFORMS:
- YouTube, Facebook, LinkedIn, Twitch, Kick
- Instagram, X/Twitter, TikTok

SPECIALIZED & EMERGING:
- Rumble, Trovo, DLive, Nimo TV, Bilibili
- Nonolive, KakaoTV, Naver TV, SOOP
- Douyu, Huya, Zhanqi.tv

OTHER INTEGRATIONS:
- Amazon Live, Telegram, Substack, Mixcloud
- Steam, Dailymotion, Picarto.TV, FC2 Live
- Breakers.TV, Vaughn Live, Mux, MLG

AUDIO-ONLY (Internet Radio):
- Icecast, SHOUTcast

CUSTOM:
- Custom RTMP, SRT, HLS, WHIP endpoints

Usage:
    from streaming.multi_streamer import MultiPlatformStreamer
    
    streamer = MultiPlatformStreamer(config)
    streamer.load_from_config()  # Load from config.yaml
    # OR add manually:
    streamer.add_restream('your-stream-key')
    streamer.add_youtube('your-stream-key')
    
    streamer.start()
    
    # During playback:
    streamer.update_song(title='Song Name', bpm=120, key='8A')
    streamer.send_audio(audio_chunk)
    
    # When done:
    streamer.stop()
"""

from .multi_streamer import MultiPlatformStreamer, Platform

__all__ = ['MultiPlatformStreamer', 'Platform']
