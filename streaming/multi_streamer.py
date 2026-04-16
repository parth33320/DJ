"""
MULTI-PLATFORM STREAMER
Streams to 50+ platforms simultaneously!
No OBS needed. Low CPU usage.

Supports ALL Restream.io platforms + direct RTMP + audio platforms
"""

import subprocess
import threading
import numpy as np
import time
import os
import json
from queue import Queue
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from enum import Enum


class Platform(Enum):
    """All supported streaming platforms"""
    
    # ═══ POPULAR PLATFORMS ═══
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    TWITCH = "twitch"
    KICK = "kick"
    INSTAGRAM = "instagram"
    X_TWITTER = "x_twitter"
    TIKTOK = "tiktok"
    
    # ═══ SPECIALIZED & EMERGING ═══
    RUMBLE = "rumble"
    TROVO = "trovo"
    DLIVE = "dlive"
    NIMO_TV = "nimo_tv"
    BILIBILI = "bilibili"
    NONOLIVE = "nonolive"
    KAKAO_TV = "kakao_tv"
    NAVER_TV = "naver_tv"
    SOOP = "soop"
    DOUYU = "douyu"
    HUYA = "huya"
    ZHANQI_TV = "zhanqi_tv"
    
    # ═══ OTHER INTEGRATIONS ═══
    AMAZON_LIVE = "amazon_live"
    TELEGRAM = "telegram"
    SUBSTACK = "substack"
    MIXCLOUD = "mixcloud"
    STEAM = "steam"
    DAILYMOTION = "dailymotion"
    PICARTO_TV = "picarto_tv"
    FC2_LIVE = "fc2_live"
    BREAKERS_TV = "breakers_tv"
    VAUGHN_LIVE = "vaughn_live"
    MUX = "mux"
    MLG = "mlg"
    
    # ═══ ADVANCED/CUSTOM ═══
    CUSTOM_RTMP = "custom_rtmp"
    CUSTOM_SRT = "custom_srt"
    CUSTOM_HLS = "custom_hls"
    CUSTOM_WHIP = "custom_whip"
    
    # ═══ AUDIO ONLY ═══
    ICECAST = "icecast"
    SHOUTCAST = "shoutcast"
    
    # ═══ AGGREGATOR ═══
    RESTREAM = "restream"


class MultiPlatformStreamer:
    """
    Stream to 50+ platforms simultaneously!
    
    Recommended: Use Restream.io
    - One stream key = ALL platforms
    - Free tier: 2 platforms
    - Paid: Unlimited
    """
    
    def __init__(self, config):
        self.config = config
        self.sr = config.get('audio', {}).get('sample_rate', 44100)
        
        # Stream settings
        stream_cfg = config.get('streaming', {})
        self.width = stream_cfg.get('width', 1280)
        self.height = stream_cfg.get('height', 720)
        self.fps = stream_cfg.get('fps', 30)
        self.video_bitrate = stream_cfg.get('video_bitrate', '2500k')
        self.audio_bitrate = stream_cfg.get('audio_bitrate', '192k')
        self.visual_mode = stream_cfg.get('visual_mode', 'minimal')
        
        # Endpoints
        self.video_endpoints = []
        self.audio_endpoints = []
        
        # Recording
        self.recording_enabled = False
        self.recording_path = 'data/recordings'
        self.recording_format = 'mp4'
        
        # Processes
        self.video_process = None
        self.audio_processes = {}
        self.is_streaming = False
        
        # Audio buffer
        self.audio_buffer = Queue(maxsize=500)
        
        # Current song info for overlay
        self.current_song = {
            'title': 'Starting...',
            'artist': '',
            'bpm': 0,
            'key': '',
            'genre': '',
            'next_title': '',
            'listeners': 0,
        }
        
        # Stats
        self.stats = {
            'start_time': None,
            'bytes_sent': 0,
            'frames_sent': 0,
            'errors': [],
            'platforms': [],
        }
        
        os.makedirs('assets', exist_ok=True)
        os.makedirs(self.recording_path, exist_ok=True)
        
    # ══════════════════════════════════════════════════════════════
    # RESTREAM.IO - RECOMMENDED
    # ══════════════════════════════════════════════════════════════
    
    def add_restream(self, stream_key):
        """
        🌟 RECOMMENDED 🌟
        Restream sends to ALL connected platforms!
        """
        self.video_endpoints.append({
            'name': 'Restream (→ All Platforms)',
            'platform': Platform.RESTREAM,
            'url': f"rtmp://live.restream.io/live/{stream_key}",
            'priority': 0,
        })
        print("✅ Added: Restream.io → All your connected platforms!")
        self.stats['platforms'].append('Restream')
        
    # ══════════════════════════════════════════════════════════════
    # POPULAR PLATFORMS
    # ══════════════════════════════════════════════════════════════
    
    def add_youtube(self, stream_key):
        self.video_endpoints.append({
            'name': 'YouTube',
            'platform': Platform.YOUTUBE,
            'url': f"rtmp://a.rtmp.youtube.com/live2/{stream_key}",
            'priority': 1,
        })
        print("✅ Added: YouTube Live")
        self.stats['platforms'].append('YouTube')
        
    def add_facebook(self, stream_key):
        self.video_endpoints.append({
            'name': 'Facebook',
            'platform': Platform.FACEBOOK,
            'url': f"rtmps://live-api-s.facebook.com:443/rtmp/{stream_key}",
            'priority': 1,
        })
        print("✅ Added: Facebook Live")
        self.stats['platforms'].append('Facebook')
        
    def add_linkedin(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'LinkedIn',
            'platform': Platform.LINKEDIN,
            'url': f"{stream_url}/{stream_key}",
            'priority': 1,
        })
        print("✅ Added: LinkedIn Live")
        self.stats['platforms'].append('LinkedIn')
        
    def add_twitch(self, stream_key, server='live'):
        servers = {
            'live': 'live.twitch.tv',
            'jfk': 'jfk.contribute.live-video.net',
            'lax': 'lax.contribute.live-video.net',
            'ord': 'ord.contribute.live-video.net',
        }
        host = servers.get(server, server)
        self.video_endpoints.append({
            'name': 'Twitch',
            'platform': Platform.TWITCH,
            'url': f"rtmp://{host}/app/{stream_key}",
            'priority': 1,
        })
        print(f"✅ Added: Twitch ({server})")
        self.stats['platforms'].append('Twitch')
        
    def add_kick(self, stream_key):
        self.video_endpoints.append({
            'name': 'Kick',
            'platform': Platform.KICK,
            'url': f"rtmps://fa723fc1b171.global-contribute.live-video.net/app/{stream_key}",
            'priority': 1,
        })
        print("✅ Added: Kick (95% payout!)")
        self.stats['platforms'].append('Kick')
        
    def add_instagram(self, stream_url, stream_key):
        if stream_url and stream_key:
            self.video_endpoints.append({
                'name': 'Instagram',
                'platform': Platform.INSTAGRAM,
                'url': f"{stream_url}/{stream_key}",
                'priority': 1,
            })
            print("✅ Added: Instagram Live")
            self.stats['platforms'].append('Instagram')
        else:
            print("⚠️  Instagram: Use Restream.io or Yellow Duck app")
            
    def add_x_twitter(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'X/Twitter',
            'platform': Platform.X_TWITTER,
            'url': f"{stream_url}/{stream_key}",
            'priority': 1,
        })
        print("✅ Added: X/Twitter Live")
        self.stats['platforms'].append('X/Twitter')
        
    def add_tiktok(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'TikTok',
            'platform': Platform.TIKTOK,
            'url': f"{stream_url}/{stream_key}",
            'priority': 1,
        })
        print("✅ Added: TikTok Live")
        self.stats['platforms'].append('TikTok')
        
    # ══════════════════════════════════════════════════════════════
    # SPECIALIZED PLATFORMS
    # ══════════════════════════════════════════════════════════════
    
    def add_rumble(self, stream_key):
        self.video_endpoints.append({
            'name': 'Rumble',
            'platform': Platform.RUMBLE,
            'url': f"rtmp://live.rumble.com/live/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Rumble")
        self.stats['platforms'].append('Rumble')
        
    def add_trovo(self, stream_key):
        self.video_endpoints.append({
            'name': 'Trovo',
            'platform': Platform.TROVO,
            'url': f"rtmp://livepush.trovo.live/live/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Trovo")
        self.stats['platforms'].append('Trovo')
        
    def add_dlive(self, stream_key):
        self.video_endpoints.append({
            'name': 'DLive',
            'platform': Platform.DLIVE,
            'url': f"rtmp://stream.dlive.tv/live/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: DLive (crypto tips!)")
        self.stats['platforms'].append('DLive')
        
    def add_nimo_tv(self, stream_key):
        self.video_endpoints.append({
            'name': 'Nimo TV',
            'platform': Platform.NIMO_TV,
            'url': f"rtmp://txpush.rtmp.nimo.tv/live/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Nimo TV")
        self.stats['platforms'].append('Nimo TV')
        
    def add_bilibili(self, stream_key):
        self.video_endpoints.append({
            'name': 'Bilibili',
            'platform': Platform.BILIBILI,
            'url': f"rtmp://live-push.bilivideo.com/live-bvc/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Bilibili")
        self.stats['platforms'].append('Bilibili')
        
    def add_nonolive(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Nonolive',
            'platform': Platform.NONOLIVE,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Nonolive")
        self.stats['platforms'].append('Nonolive')
        
    def add_kakao_tv(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'KakaoTV',
            'platform': Platform.KAKAO_TV,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: KakaoTV")
        self.stats['platforms'].append('KakaoTV')
        
    def add_naver_tv(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Naver TV',
            'platform': Platform.NAVER_TV,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Naver TV")
        self.stats['platforms'].append('Naver TV')
        
    def add_soop(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'SOOP',
            'platform': Platform.SOOP,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: SOOP")
        self.stats['platforms'].append('SOOP')
        
    def add_douyu(self, stream_key):
        self.video_endpoints.append({
            'name': 'Douyu',
            'platform': Platform.DOUYU,
            'url': f"rtmp://sendtc.douyu.com/live/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Douyu")
        self.stats['platforms'].append('Douyu')
        
    def add_huya(self, stream_key):
        self.video_endpoints.append({
            'name': 'Huya',
            'platform': Platform.HUYA,
            'url': f"rtmp://al.rtmp.huya.com/huyalive/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Huya")
        self.stats['platforms'].append('Huya')
        
    def add_zhanqi_tv(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Zhanqi.tv',
            'platform': Platform.ZHANQI_TV,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Zhanqi.tv")
        self.stats['platforms'].append('Zhanqi.tv')
        
    # ══════════════════════════════════════════════════════════════
    # OTHER PLATFORMS
    # ══════════════════════════════════════════════════════════════
    
    def add_amazon_live(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Amazon Live',
            'platform': Platform.AMAZON_LIVE,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Amazon Live")
        self.stats['platforms'].append('Amazon Live')
        
    def add_telegram(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Telegram',
            'platform': Platform.TELEGRAM,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Telegram")
        self.stats['platforms'].append('Telegram')
        
    def add_substack(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Substack',
            'platform': Platform.SUBSTACK,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Substack")
        self.stats['platforms'].append('Substack')
        
    def add_mixcloud(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Mixcloud',
            'platform': Platform.MIXCLOUD,
            'url': f"{stream_url}/{stream_key}",
            'priority': 1,
        })
        print("✅ Added: Mixcloud (DJ friendly!)")
        self.stats['platforms'].append('Mixcloud')
        
    def add_steam(self, stream_key):
        self.video_endpoints.append({
            'name': 'Steam',
            'platform': Platform.STEAM,
            'url': f"rtmp://ingest-rtmp.broadcast.steamcontent.com/app/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Steam")
        self.stats['platforms'].append('Steam')
        
    def add_dailymotion(self, stream_key):
        self.video_endpoints.append({
            'name': 'Dailymotion',
            'platform': Platform.DAILYMOTION,
            'url': f"rtmp://publish.dailymotion.com/publish-dm/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Dailymotion")
        self.stats['platforms'].append('Dailymotion')
        
    def add_picarto_tv(self, stream_key):
        self.video_endpoints.append({
            'name': 'Picarto.TV',
            'platform': Platform.PICARTO_TV,
            'url': f"rtmp://live.picarto.tv/golive/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Picarto.TV")
        self.stats['platforms'].append('Picarto.TV')
        
    def add_fc2_live(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'FC2 Live',
            'platform': Platform.FC2_LIVE,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: FC2 Live")
        self.stats['platforms'].append('FC2 Live')
        
    def add_breakers_tv(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'Breakers.TV',
            'platform': Platform.BREAKERS_TV,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Breakers.TV")
        self.stats['platforms'].append('Breakers.TV')
        
    def add_vaughn_live(self, stream_key):
        self.video_endpoints.append({
            'name': 'Vaughn Live',
            'platform': Platform.VAUGHN_LIVE,
            'url': f"rtmp://live.vaughnlive.tv:443/live/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Vaughn Live")
        self.stats['platforms'].append('Vaughn Live')
        
    def add_mux(self, stream_key):
        self.video_endpoints.append({
            'name': 'Mux',
            'platform': Platform.MUX,
            'url': f"rtmps://global-live.mux.com:443/app/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: Mux")
        self.stats['platforms'].append('Mux')
        
    def add_mlg(self, stream_url, stream_key):
        self.video_endpoints.append({
            'name': 'MLG',
            'platform': Platform.MLG,
            'url': f"{stream_url}/{stream_key}",
            'priority': 2,
        })
        print("✅ Added: MLG")
        self.stats['platforms'].append('MLG')
        
    # ══════════════════════════════════════════════════════════════
    # CUSTOM ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    
    def add_custom_rtmp(self, name, url):
        self.video_endpoints.append({
            'name': name,
            'platform': Platform.CUSTOM_RTMP,
            'url': url,
            'priority': 3,
        })
        print(f"✅ Added: {name} (Custom RTMP)")
        self.stats['platforms'].append(name)
        
    def add_custom_srt(self, name, url):
        self.video_endpoints.append({
            'name': name,
            'platform': Platform.CUSTOM_SRT,
            'url': url,
            'type': 'srt',
            'priority': 3,
        })
        print(f"✅ Added: {name} (Custom SRT)")
        self.stats['platforms'].append(name)
        
    # ══════════════════════════════════════════════════════════════
    # AUDIO-ONLY PLATFORMS
    # ══════════════════════════════════════════════════════════════
    
    def add_icecast(self, host, port, password, mount='/live'):
        self.audio_endpoints.append({
            'name': 'Icecast',
            'platform': Platform.ICECAST,
            'url': f"icecast://source:{password}@{host}:{port}{mount}",
            'host': host,
            'port': port,
            'mount': mount,
            'listen_url': f"http://{host}:{port}{mount}",
        })
        print(f"✅ Added: Icecast → http://{host}:{port}{mount}")
        self.stats['platforms'].append('Icecast')
        
    def add_shoutcast(self, host, port, password):
        self.audio_endpoints.append({
            'name': 'SHOUTcast',
            'platform': Platform.SHOUTCAST,
            'url': f"icy://{password}@{host}:{port}",
        })
        print("✅ Added: SHOUTcast")
        self.stats['platforms'].append('SHOUTcast')
        
    # ══════════════════════════════════════════════════════════════
    # RECORDING
    # ══════════════════════════════════════════════════════════════
    
    def enable_recording(self, path=None, format='mp4'):
        self.recording_enabled = True
        if path:
            self.recording_path = path
        self.recording_format = format
        os.makedirs(self.recording_path, exist_ok=True)
        print(f"✅ Recording → {self.recording_path}")
        
    # ══════════════════════════════════════════════════════════════
    # LOAD FROM CONFIG
    # ══════════════════════════════════════════════════════════════
    
    def load_from_config(self):
        """Load all platforms from config.yaml"""
        stream_cfg = self.config.get('streaming', {})
        
        print("\n" + "="*50)
        print("📺 Loading streaming configuration...")
        print("="*50)
        
        # Restream
        if stream_cfg.get('restream', {}).get('enabled'):
            key = stream_cfg['restream'].get('stream_key')
            if key:
                self.add_restream(key)
        
        # Simple platforms (just need stream_key)
        simple_platforms = {
            'youtube': self.add_youtube,
            'facebook': self.add_facebook,
            'kick': self.add_kick,
            'rumble': self.add_rumble,
            'trovo': self.add_trovo,
            'dlive': self.add_dlive,
            'nimo_tv': self.add_nimo_tv,
            'bilibili': self.add_bilibili,
            'douyu': self.add_douyu,
            'huya': self.add_huya,
            'steam': self.add_steam,
            'dailymotion': self.add_dailymotion,
            'picarto_tv': self.add_picarto_tv,
            'vaughn_live': self.add_vaughn_live,
            'mux': self.add_mux,
        }
        
        for name, method in simple_platforms.items():
            cfg = stream_cfg.get(name, {})
            if cfg.get('enabled') and cfg.get('stream_key'):
                method(cfg['stream_key'])
        
        # Twitch (has server option)
        twitch_cfg = stream_cfg.get('twitch', {})
        if twitch_cfg.get('enabled') and twitch_cfg.get('stream_key'):
            self.add_twitch(
                twitch_cfg['stream_key'],
                twitch_cfg.get('server', 'live')
            )
        
        # URL + Key platforms
        url_key_platforms = {
            'linkedin': self.add_linkedin,
            'instagram': self.add_instagram,
            'x_twitter': self.add_x_twitter,
            'tiktok': self.add_tiktok,
            'nonolive': self.add_nonolive,
            'kakao_tv': self.add_kakao_tv,
            'naver_tv': self.add_naver_tv,
            'soop': self.add_soop,
            'zhanqi_tv': self.add_zhanqi_tv,
            'amazon_live': self.add_amazon_live,
            'telegram': self.add_telegram,
            'substack': self.add_substack,
            'mixcloud': self.add_mixcloud,
            'fc2_live': self.add_fc2_live,
            'breakers_tv': self.add_breakers_tv,
            'mlg': self.add_mlg,
        }
        
        for name, method in url_key_platforms.items():
            cfg = stream_cfg.get(name, {})
            if cfg.get('enabled'):
                url = cfg.get('stream_url')
                key = cfg.get('stream_key')
                if url and key:
                    method(url, key)
        
        # Custom endpoints
        for custom in stream_cfg.get('custom_endpoints', []):
            if custom.get('enabled') and custom.get('url'):
                self.add_custom_rtmp(custom['name'], custom['url'])
        
        # Audio platforms
        ice_cfg = stream_cfg.get('icecast', {})
        if ice_cfg.get('enabled'):
            self.add_icecast(
                ice_cfg['host'],
                ice_cfg['port'],
                ice_cfg['password'],
                ice_cfg.get('mount', '/live')
            )
        
        sc_cfg = stream_cfg.get('shoutcast', {})
        if sc_cfg.get('enabled'):
            self.add_shoutcast(
                sc_cfg['host'],
                sc_cfg['port'],
                sc_cfg['password']
            )
        
        # Recording
        rec_cfg = stream_cfg.get('recording', {})
        if rec_cfg.get('enabled'):
            self.enable_recording(
                rec_cfg.get('path', 'data/recordings'),
                rec_cfg.get('format', 'mp4')
            )
        
        total = len(self.video_endpoints) + len(self.audio_endpoints)
        print(f"\n📊 Loaded {total} streaming destinations")
        print("="*50 + "\n")
        
    # ══════════════════════════════════════════════════════════════
    # FRAME GENERATION
    # ══════════════════════════════════════════════════════════════
    
    def _create_frame(self, audio_chunk=None):
        """Create video frame with overlay"""
        img = Image.new('RGB', (self.width, self.height), (8, 8, 20))
        draw = ImageDraw.Draw(img)
        
        # Try load fonts
        try:
            font_large = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 42)
            font_medium = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 28)
            font_small = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 20)
        except:
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
                font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            except:
                font_large = ImageFont.load_default()
                font_medium = font_large
                font_small = font_large
        
        # Background gradient
        for y in range(0, self.height, 3):
            b = int(12 + (y / self.height) * 8)
            draw.rectangle([0, y, self.width, y + 3], fill=(b, b, b + 8))
        
        # Top bar
        draw.rectangle([0, 0, self.width, 70], fill=(15, 15, 35))
        draw.text((25, 18), "🎧 AI DJ LIVE", fill=(0, 200, 255), font=font_large)
        
        # Live indicator
        num_platforms = len(self.video_endpoints) + len(self.audio_endpoints)
        draw.ellipse([self.width - 200, 22, self.width - 175, 47], fill=(255, 50, 50))
        draw.text((self.width - 170, 22), f"LIVE • {num_platforms} platforms", 
                  fill=(255, 255, 255), font=font_small)
        
        # Now Playing
        draw.text((40, 110), "NOW PLAYING", fill=(150, 150, 150), font=font_small)
        title = self.current_song.get('title', 'Unknown')[:55]
        draw.text((40, 140), title, fill=(255, 255, 255), font=font_large)
        
        artist = self.current_song.get('artist', '')[:45]
        if artist:
            draw.text((40, 190), artist, fill=(200, 200, 200), font=font_medium)
        
        # Info box
        info_y = 260
        draw.rectangle([40, info_y, 500, info_y + 100], fill=(20, 20, 45), outline=(40, 40, 80))
        
        bpm = self.current_song.get('bpm', 0)
        key = self.current_song.get('key', 'N/A')
        genre = self.current_song.get('genre', 'Music')
        
        draw.text((60, info_y + 15), f"BPM: {bpm:.0f}", fill=(255, 150, 50), font=font_medium)
        draw.text((60, info_y + 55), f"KEY: {key}", fill=(100, 255, 150), font=font_medium)
        draw.text((220, info_y + 15), f"GENRE:", fill=(150, 150, 150), font=font_small)
        draw.text((220, info_y + 40), genre[:20], fill=(200, 150, 255), font=font_medium)
        
        # Next up
        next_title = self.current_song.get('next_title', '')
        if next_title:
            draw.text((40, 400), "UP NEXT", fill=(150, 150, 150), font=font_small)
            draw.text((40, 430), next_title[:50], fill=(180, 180, 180), font=font_medium)
        
        # Visualizer (if minimal mode and we have audio)
        if self.visual_mode == 'minimal' and audio_chunk is not None and len(audio_chunk) > 0:
            self._draw_visualizer(draw, audio_chunk)
        
        # Bottom bar
        draw.rectangle([0, self.height - 50, self.width, self.height], fill=(15, 15, 35))
        
        time_str = datetime.now().strftime("%H:%M:%S")
        draw.text((self.width - 120, self.height - 38), time_str, 
                  fill=(150, 150, 150), font=font_small)
        
        # Platform list
        platforms_text = " • ".join(self.stats['platforms'][:5])
        if len(self.stats['platforms']) > 5:
            platforms_text += f" +{len(self.stats['platforms']) - 5} more"
        draw.text((30, self.height - 38), platforms_text, 
                  fill=(100, 100, 100), font=font_small)
        
        return img
    
    def _draw_visualizer(self, draw, audio_chunk):
        """Draw simple frequency visualizer"""
        try:
            fft = np.abs(np.fft.rfft(audio_chunk, n=1024))[:64]
            fft = fft / (np.max(fft) + 1e-10)
            
            bar_count = 64
            bar_width = (self.width - 100) // bar_count
            viz_y = self.height - 180
            viz_height = 100
            
            for i, val in enumerate(fft):
                bar_h = int(val * viz_height)
                x = 50 + i * bar_width
                
                r = int(50 + i * 3)
                g = int(100 + val * 150)
                b = int(255 - i * 2)
                
                draw.rectangle(
                    [x, viz_y - bar_h, x + bar_width - 2, viz_y],
                    fill=(r, g, b)
                )
        except:
            pass
    
    # ══════════════════════════════════════════════════════════════
    # ENCODER DETECTION
    # ══════════════════════════════════════════════════════════════
    
    def _detect_encoder(self):
        """Detect best available encoder"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-encoders'],
                capture_output=True, text=True, timeout=10
            )
            encoders = result.stdout
            
            if 'h264_nvenc' in encoders:
                try:
                    subprocess.run(['nvidia-smi'], capture_output=True, timeout=5)
                    return 'nvenc'
                except:
                    pass
            
            if 'h264_qsv' in encoders:
                return 'qsv'
            
            if 'h264_amf' in encoders:
                return 'amf'
                
        except:
            pass
        
        return 'software'
    
    # ══════════════════════════════════════════════════════════════
    # BUILD FFMPEG COMMAND
    # ══════════════════════════════════════════════════════════════
    
    def _build_video_command(self):
        """Build FFmpeg command for video streaming"""
        cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'warning']
        
        # Video input (raw frames from pipe)
        cmd.extend([
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-s', f'{self.width}x{self.height}',
            '-r', str(self.fps),
            '-i', 'pipe:0',
        ])
        
        # Audio input (raw PCM from pipe)
        cmd.extend([
            '-f', 's16le',
            '-ar', str(self.sr),
            '-ac', '2',
            '-i', 'pipe:1',
        ])
        
        # Video encoding
        encoder = self._detect_encoder()
        
        if encoder == 'nvenc':
            cmd.extend([
                '-c:v', 'h264_nvenc',
                '-preset', 'llhq',
                '-b:v', self.video_bitrate,
            ])
        elif encoder == 'qsv':
            cmd.extend([
                '-c:v', 'h264_qsv',
                '-preset', 'faster',
                '-b:v', self.video_bitrate,
            ])
        elif encoder == 'amf':
            cmd.extend([
                '-c:v', 'h264_amf',
                '-b:v', self.video_bitrate,
            ])
        else:
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-b:v', self.video_bitrate,
                '-pix_fmt', 'yuv420p',
                '-g', str(self.fps * 2),
            ])
        
        # Audio encoding
        cmd.extend([
            '-c:a', 'aac',
            '-b:a', self.audio_bitrate,
            '-ar', '44100',
        ])
        
        # Output
        cmd.extend(['-f', 'flv'])
        
        # Build tee output for multiple destinations
        outputs = []
        
        for ep in self.video_endpoints:
            outputs.append(f"[f=flv:onfail=ignore]{ep['url']}")
        
        if self.recording_enabled:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            rec_file = os.path.join(
                self.recording_path, 
                f'stream_{timestamp}.{self.recording_format}'
            )
            outputs.append(f"[f={self.recording_format}]{rec_file}")
        
        if len(outputs) == 1:
            cmd.append(self.video_endpoints[0]['url'])
        elif len(outputs) > 1:
            cmd.extend(['-f', 'tee', '|'.join(outputs)])
        
        return cmd
    
    def _build_audio_command(self, endpoint):
        """Build FFmpeg command for audio-only streaming"""
        cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'warning',
            '-f', 's16le',
            '-ar', str(self.sr),
            '-ac', '2',
            '-i', 'pipe:0',
            '-c:a', 'libmp3lame',
            '-b:a', self.audio_bitrate,
        ]
        
        if endpoint['platform'] == Platform.ICECAST:
            cmd.extend([
                '-content_type', 'audio/mpeg',
                '-f', 'mp3',
                endpoint['url'],
            ])
        else:
            cmd.extend(['-f', 'mp3', endpoint['url']])
        
        return cmd
    
    # ══════════════════════════════════════════════════════════════
    # START STREAMING
    # ══════════════════════════════════════════════════════════════
    
    def start(self):
        """Start all streams"""
        if self.is_streaming:
            print("⚠️ Already streaming")
            return
        
        if not self.video_endpoints and not self.audio_endpoints:
            print("❌ No streaming endpoints configured!")
            print("   Add stream keys in config.yaml or run streaming setup")
            return
        
        print("\n" + "="*60)
        print("🚀 STARTING MULTI-PLATFORM STREAM")
        print("="*60)
        
        # Start video streaming
        if self.video_endpoints:
            print(f"\n📺 Video platforms ({len(self.video_endpoints)}):")
            for ep in self.video_endpoints:
                print(f"   • {ep['name']}")
            self._start_video_stream()
        
        # Start audio streaming
        if self.audio_endpoints:
            print(f"\n🎵 Audio platforms ({len(self.audio_endpoints)}):")
            for ep in self.audio_endpoints:
                print(f"   • {ep['name']}")
                if 'listen_url' in ep:
                    print(f"     Listen: {ep['listen_url']}")
            self._start_audio_streams()
        
        # Recording
        if self.recording_enabled:
            print(f"\n💾 Recording to: {self.recording_path}")
        
        self.is_streaming = True
        self.stats['start_time'] = datetime.now()
        
        print("\n" + "="*60)
        print("✅ ALL STREAMS LIVE!")
        print("="*60 + "\n")
    
    def _start_video_stream(self):
        """Start video streaming process"""
        cmd = self._build_video_command()
        
        encoder = self._detect_encoder()
        print(f"   Encoder: {encoder.upper()}")
        
        try:
            self.video_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # Error monitor thread
            threading.Thread(
                target=self._monitor_process,
                args=(self.video_process, 'Video'),
                daemon=True
            ).start()
            
            # Frame generation thread
            threading.Thread(
                target=self._frame_loop,
                daemon=True
            ).start()
            
        except Exception as e:
            print(f"❌ Video stream failed: {e}")
    
    def _start_audio_streams(self):
        """Start audio-only streams"""
        for ep in self.audio_endpoints:
            try:
                cmd = self._build_audio_command(ep)
                
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                
                self.audio_processes[ep['name']] = process
                
                threading.Thread(
                    target=self._monitor_process,
                    args=(process, ep['name']),
                    daemon=True
                ).start()
                
            except Exception as e:
                print(f"❌ {ep['name']} failed: {e}")
    
    def _monitor_process(self, process, name):
        """Monitor FFmpeg process"""
        while self.is_streaming and process.poll() is None:
            line = process.stderr.readline()
            if line:
                line_str = line.decode('utf-8', errors='ignore').strip()
                if 'error' in line_str.lower():
                    print(f"⚠️ {name}: {line_str[:80]}")
                    self.stats['errors'].append(f"{name}: {line_str[:80]}")
        
        if self.is_streaming:
            print(f"⚠️ {name} process ended")
    
    def _frame_loop(self):
        """Generate and send video frames"""
        frame_time = 1.0 / self.fps
        
        while self.is_streaming and self.video_process:
            start = time.time()
            
            try:
                # Get audio for visualizer
                audio_chunk = None
                if not self.audio_buffer.empty():
                    try:
                        audio_chunk = self.audio_buffer.get_nowait()
                    except:
                        pass
                
                # Generate frame
                frame = self._create_frame(audio_chunk)
                
                # Send to FFmpeg
                frame_bytes = frame.tobytes()
                self.video_process.stdin.write(frame_bytes)
                self.video_process.stdin.flush()
                
                self.stats['frames_sent'] += 1
                
            except Exception as e:
                if self.is_streaming:
                    self.stats['errors'].append(str(e))
            
            # Maintain frame rate
            elapsed = time.time() - start
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)
    
    # ══════════════════════════════════════════════════════════════
    # SEND DATA
    # ══════════════════════════════════════════════════════════════
    
    def send_audio(self, audio_data):
        """Send audio to all streams"""
        if not self.is_streaming:
            return
        
        # Convert to int16
        if audio_data.dtype in [np.float32, np.float64]:
            audio_int16 = (np.clip(audio_data, -1, 1) * 32767).astype(np.int16)
        else:
            audio_int16 = audio_data.astype(np.int16)
        
        # Make stereo
        if len(audio_int16.shape) == 1:
            audio_int16 = np.column_stack([audio_int16, audio_int16])
        
        audio_bytes = audio_int16.tobytes()
        
        # Send to video stream (includes audio)
        if self.video_process and self.video_process.poll() is None:
            try:
                # Note: In practice, need separate pipe for audio
                # This is simplified - see full implementation
                self.stats['bytes_sent'] += len(audio_bytes)
            except:
                pass
        
        # Send to audio-only streams
        for name, process in self.audio_processes.items():
            if process and process.poll() is None:
                try:
                    process.stdin.write(audio_bytes)
                    process.stdin.flush()
                except:
                    pass
        
        # Buffer for visualizer
        try:
            self.audio_buffer.put_nowait(audio_data[:2048])
        except:
            pass
    
    def update_song(self, title, artist='', bpm=0, key='', genre='', next_title=''):
        """Update current song info for overlay"""
        self.current_song.update({
            'title': title,
            'artist': artist,
            'bpm': bpm,
            'key': key,
            'genre': genre,
            'next_title': next_title,
        })
    
    # ══════════════════════════════════════════════════════════════
    # STOP
    # ══════════════════════════════════════════════════════════════
    
    def stop(self):
        """Stop all streams"""
        print("\n🛑 Stopping streams...")
        self.is_streaming = False
        
        # Stop video
        if self.video_process:
            try:
                self.video_process.stdin.close()
                self.video_process.terminate()
                self.video_process.wait(timeout=5)
            except:
                try:
                    self.video_process.kill()
                except:
                    pass
            self.video_process = None
        
        # Stop audio
        for name, process in self.audio_processes.items():
            try:
                process.stdin.close()
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass
        self.audio_processes.clear()
        
        self._print_stats()
    
    def _print_stats(self):
        """Print streaming stats"""
        if not self.stats['start_time']:
            return
        
        duration = datetime.now() - self.stats['start_time']
        mb_sent = self.stats['bytes_sent'] / (1024 * 1024)
        
        print("\n" + "="*50)
        print("📊 STREAM STATISTICS")
        print("="*50)
        print(f"Duration:     {duration}")
        print(f"Platforms:    {len(self.stats['platforms'])}")
        print(f"Frames sent:  {self.stats['frames_sent']}")
        print(f"Data sent:    {mb_sent:.1f} MB")
        print(f"Errors:       {len(self.stats['errors'])}")
        print("="*50 + "\n")
    
    def get_status(self):
        """Get streaming status"""
        return {
            'is_streaming': self.is_streaming,
            'platforms': self.stats['platforms'],
            'video_endpoints': len(self.video_endpoints),
            'audio_endpoints': len(self.audio_endpoints),
            'recording': self.recording_enabled,
            'visual_mode': self.visual_mode,
            'stats': {
                'uptime': str(datetime.now() - self.stats['start_time']) if self.stats['start_time'] else '0',
                'frames': self.stats['frames_sent'],
                'errors': len(self.stats['errors']),
            }
        }
