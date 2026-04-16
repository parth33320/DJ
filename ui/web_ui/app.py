from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dj_app_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global reference to DJ app
dj_app_ref = None

def start_web_ui(dj_app_instance, port=5000):
    """Start Flask web UI in background thread"""
    global dj_app_ref
    dj_app_ref = dj_app_instance
    socketio.run(app, host='0.0.0.0', port=port, debug=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get current DJ status"""
    if not dj_app_ref:
        return jsonify({'error': 'App not initialized'})

    current = None
    if dj_app_ref.current_song:
        current = dj_app_ref.metadata_cache.get(
            dj_app_ref.current_song, {}
        )

    return jsonify({
        'is_playing': dj_app_ref.is_playing,
        'mode': dj_app_ref.mode,
        'current_song': {
            'title': current.get('title', 'Unknown') if current else None,
            'bpm': current.get('bpm', 0) if current else 0,
            'key': current.get('camelot', 'N/A') if current else 'N/A',
            'genre': current.get('genre_hint', '') if current else '',
        },
        'total_songs': len(dj_app_ref.metadata_cache),
        'playlist_count': len(dj_app_ref.playlist)
    })

@app.route('/api/playlist')
def get_playlist():
    """Get full playlist with analysis data"""
    if not dj_app_ref:
        return jsonify([])

    songs = []
    for song in dj_app_ref.playlist:
        meta = dj_app_ref.metadata_cache.get(song['id'], {})
        songs.append({
            'id': song['id'],
            'title': song['title'],
            'bpm': meta.get('bpm', 0),
            'key': meta.get('camelot', 'N/A'),
            'genre': meta.get('genre_hint', 'Unknown'),
            'duration': meta.get('duration', 0),
            'is_current': song['id'] == dj_app_ref.current_song
        })
    return jsonify(songs)

@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Switch between auto and semi-auto mode"""
    if not dj_app_ref:
        return jsonify({'error': 'App not initialized'})

    data = request.json
    mode = data.get('mode', 'auto')
    if mode in ['auto', 'semi']:
        dj_app_ref.mode = mode
        return jsonify({'success': True, 'mode': mode})
    return jsonify({'error': 'Invalid mode'})

@app.route('/api/skip', methods=['POST'])
def skip_song():
    """Skip current song"""
    if not dj_app_ref:
        return jsonify({'error': 'App not initialized'})
    # Signal skip
    dj_app_ref.skip_requested = True
    return jsonify({'success': True})

@app.route('/api/wordplay_index')
def get_wordplay_index():
    """Get word connections found across songs"""
    if not dj_app_ref:
        return jsonify({})

    index = dj_app_ref.wordplay_agent.word_index
    # Return only words that appear in 2+ songs
    multi_song_words = {
        word: entries for word, entries in index.items()
        if len(set(e['song_id'] for e in entries)) >= 2
    }
    return jsonify({
        'total_words': len(index),
        'cross_song_words': len(multi_song_words),
        'top_connections': list(multi_song_words.keys())[:50]
    })

@socketio.on('connect')
def handle_connect():
    emit('connected', {'data': 'Connected to DJ App'})

@socketio.on('request_update')
def handle_update_request():
    """Send current state to connected client"""
    if dj_app_ref and dj_app_ref.current_song:
        current = dj_app_ref.metadata_cache.get(
            dj_app_ref.current_song, {}
        )
        emit('state_update', {
            'title': current.get('title', 'Unknown'),
            'bpm': current.get('bpm', 0),
            'key': current.get('camelot', 'N/A'),
            'genre': current.get('genre_hint', ''),
            'mode': dj_app_ref.mode
        })

def broadcast_now_playing(title, bpm, key, genre, technique):
    """Broadcast to all connected web clients"""
    socketio.emit('now_playing', {
        'title': title,
        'bpm': bpm,
        'key': key,
        'genre': genre,
        'technique': technique
    })
