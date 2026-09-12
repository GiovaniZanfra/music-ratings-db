import re

from config import MUSIC_HEADERS, SHEET_MUSIC
from lastfm import fetch_album_tracks, fetch_recent_tracks, get_track_details
from sheets import open_spreadsheet, setup_worksheet

# Authenticate, open spreadsheet and set up the main music sheet
ss = open_spreadsheet()
ws_music = setup_worksheet(ss, SHEET_MUSIC, MUSIC_HEADERS)

def get_existing_data():
    """Fetch existing data to prevent duplicates"""
    existing = {
        'tracks': set()  # (ArtistID, AlbumID, TrackName) as key
    }

    # Get existing tracks
    for row in ws_music.get_all_records():
        key = (row['ArtistID'], row['AlbumID'], row['TrackName'])
        existing['tracks'].add(key)

    return existing

def clean_name(name):
    """Clean names for consistent comparison"""
    return re.sub(r'[^\w\s]', '', name).strip().lower() if name else ""

def get_artist_info(artist_name):
    """Get artist ID and name"""
    clean_artist = clean_name(artist_name)

    # Generate consistent artist ID
    return {
        'id': f"artist_{clean_artist[:30]}",
        'name': artist_name
    }

def get_album_info(artist_id, album_name):
    """Get album ID and name"""
    clean_album = clean_name(album_name)

    # Generate consistent album ID
    return {
        'id': f"{artist_id[:10]}_{clean_album[:20]}",
        'name': album_name
    }

def upload_data():
    """Main function to process and upload data"""
    data = fetch_recent_tracks(limit=100)
    existing = get_existing_data()
    new_tracks = []

    for track in data.get('recenttracks', {}).get('track', []):
        try:
            track_name = track.get('name', '').strip()
            artist_name = track.get('artist', {}).get('#text', '').strip()
            album_name = track.get('album', {}).get('#text', '').strip()
            timestamp = track.get('date', {}).get('uts', '')

            if not artist_name or not track_name or not album_name:
                continue

            # Get artist info
            artist_info = get_artist_info(artist_name)

            # Get album info
            album_info = get_album_info(artist_info['id'], album_name)

            # Create unique track key
            track_key = (artist_info['id'], album_info['id'], track_name)

            # Skip existing tracks
            if track_key in existing['tracks']:
                continue

            # Get track duration + play count (username-scoped, same call)
            duration, playcount = get_track_details(artist_name, track_name)

            # Get the rest of the album's tracklist (genre/release year are
            # album-level and live on the Albums tab, not here -- see
            # enrich_albums.py)
            album_tracks, _genre, _release_year = fetch_album_tracks(artist_name, album_name)

            # Add to new tracks
            new_tracks.append([
                artist_info['id'],
                artist_info['name'],
                album_info['id'],
                album_info['name'],
                track_name,
                duration,
                '',  # Empty rating
                timestamp,
                '',  # Notes
                playcount
            ])

            # Add to existing set
            existing['tracks'].add(track_key)

            # Add all album tracks (playcount left blank: not scrobbled here,
            # not worth an extra API call per filler track in the ongoing
            # pipeline — the backfill script covers these separately)
            for album_track in album_tracks:
                album_track_key = (artist_info['id'], album_info['id'], album_track['name'])

                if album_track_key not in existing['tracks']:
                    new_tracks.append([
                        artist_info['id'],
                        artist_info['name'],
                        album_info['id'],
                        album_info['name'],
                        album_track['name'],
                        album_track['duration'],
                        '',  # Empty rating
                        '',  # No play timestamp
                        '',  # Notes
                        ''  # PlayCount unknown for filler tracks
                    ])
                    existing['tracks'].add(album_track_key)

        except Exception as e:
            print(f"Error processing track: {e}")
            continue

    # Batch add new tracks
    if new_tracks:
        # Sort by timestamp to keep recent plays first
        new_tracks.sort(key=lambda x: x[7] or "0", reverse=True)
        ws_music.append_rows(new_tracks)

    print(f"Added {len(new_tracks)} new tracks")

if __name__ == "__main__":
    upload_data()
