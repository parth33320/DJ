import json
import os

class PlaylistWatcher:
    def __init__(self, config):
        self.config = config

    def check_for_changes(self, playlist_url, current_playlist,
                          metadata_cache, app):
        """
        Check YouTube playlist for added/removed songs
        """
        print("\n🔄 Checking playlist for changes...")

        # Get current playlist from YouTube
        from ingestion.downloader import PlaylistDownloader
        downloader = PlaylistDownloader(self.config)
        fresh_playlist = downloader.get_playlist_metadata(playlist_url)

        current_ids = {s['id'] for s in current_playlist}
        fresh_ids = {s['id'] for s in fresh_playlist}

        # Find new songs
        new_ids = fresh_ids - current_ids
        # Find removed songs (keep files per config)
        removed_ids = current_ids - fresh_ids

        if new_ids:
            print(f"✨ {len(new_ids)} new songs found!")
            new_songs = [s for s in fresh_playlist if s['id'] in new_ids]
            self._process_new_songs(new_songs, metadata_cache, app)

        if removed_ids:
            print(f"🗑️  {len(removed_ids)} songs removed from playlist")
            print("   (Files kept in cache per config)")

        if not new_ids and not removed_ids:
            print("✅ No changes detected")

    def _process_new_songs(self, new_songs, metadata_cache, app):
        """Process and analyze new songs"""
        for song in new_songs:
            print(f"   Processing new song: {song['title'][:40]}")
            try:
                filepath = app.downloader.download_song(
                    song['url'], song['id']
                )
                analysis = app.analyzer.analyze_track(filepath, song['id'])
                analysis['title'] = song['title']

                phrases = app.phrase_detector.detect_phrases(
                    filepath, song['id']
                )
                analysis['phrases'] = phrases

                stems = app.stem_separator.separate(filepath, song['id'])
                analysis['stems'] = stems

                lyrics = app.lyrics_fetcher.fetch(
                    song['title'], song['id'],
                    stems.get('vocals')
                )
                analysis['lyrics'] = lyrics

                if lyrics:
                    phonemes = app.vocal_analyzer.analyze(
                        stems.get('vocals'), lyrics, song['id']
                    )
                    analysis['phonemes'] = phonemes

                metadata_cache[song['id']] = analysis
                app.playlist.append(song)

                # Update word index with new song
                app.wordplay_agent.build_word_index(metadata_cache)

                app.downloader.delete_audio(song['id'])
                print(f"   ✅ New song ready: {song['title'][:40]}")

            except Exception as e:
                print(f"   ❌ Failed to process {song['title']}: {e}")
