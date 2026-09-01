import os
import re
import time

import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials

# Constants
USER = "gigs12345678"
API_KEY = os.environ["LASTFM_API_KEY"]
URL = "http://ws.audioscrobbler.com/2.0/"

# Google Sheets setup
SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
CREDS_FILE = 'lastfm-to-sheets-ed442fe7881c.json'
SPREADSHEET_NAME = 'music_db_ratings'
SHEET_MUSIC = 'Music'  # Single denormalized sheet

# Authenticate and open spreadsheet
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
gc = gspread.authorize(creds)
ss = gc.open(SPREADSHEET_NAME)

# Get or create main worksheet
def setup_worksheet(name, headers, rows=10000, cols=10):
    try:
        ws = ss.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=name, rows=rows, cols=len(headers))
    
    current_headers = ws.row_values(1) if ws.get_all_values() else []
    if current_headers != headers:
        ws.clear()
        ws.append_row(headers)
    return ws

# Setup main music sheet with denormalized structure
ws_music = setup_worksheet(SHEET_MUSIC, [
    'ArtistID', 
    'ArtistName', 
    'AlbumID', 
    'AlbumName', 
    'TrackName', 
    'Duration', 
    'Rating',
    'LastPlayed',
    'Notes'
])

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

def fetch_entity_info(method, **params):
    """Generic function to fetch entity info from Last.fm"""
    params.update({
        "method": method,
        "api_key": API_KEY,
        "format": "json"
    })
    try:
        response = requests.get(URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None

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

def get_track_duration(artist_name, track_name):
    """Fetch track duration"""
    track_data = fetch_entity_info("track.getInfo", artist=artist_name, track=track_name)
    time.sleep(0.2)  # Rate limiting
    
    duration = 0
    if track_data and 'track' in track_data:
        # Get duration (convert to seconds)
        duration_str = track_data['track'].get('duration')
        if duration_str:
            try:
                duration = int(duration_str) // 1000  # Convert ms to seconds
            except (ValueError, TypeError):
                duration = 0
    
    return duration

def fetch_album_tracks(artist_name, album_name):
    """Fetch all tracks from an album"""
    album_data = fetch_entity_info("album.getInfo", artist=artist_name, album=album_name)
    time.sleep(0.2)
    
    tracks = []
    if album_data and 'album' in album_data and 'tracks' in album_data['album']:
        tracks_data = album_data['album']['tracks'].get('track', [])
        
        # Handle single track case
        if isinstance(tracks_data, dict):
            tracks_data = [tracks_data]
        
        for track in tracks_data:
            track_name = track.get('name', '').strip()
            if not track_name:
                continue
            
            # Handle duration safely
            duration = 0
            duration_val = track.get('duration')
            if duration_val is not None:
                try:
                    duration = int(duration_val)  # Already in seconds
                except (ValueError, TypeError):
                    duration = 0
                
            tracks.append({
                'name': track_name,
                'duration': duration
            })
    
    return tracks

def fetch_recent_tracks(limit=100):
    """Fetch recent tracks from Last.fm"""
    params = {
        "method": "user.getrecenttracks",
        "user": USER,
        "api_key": API_KEY,
        "format": "json",
        "limit": limit
    }
    response = requests.get(URL, params=params)
    response.raise_for_status()
    return response.json()

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
            
            # Get track duration
            duration = get_track_duration(artist_name, track_name)
            
            # Add to new tracks
            new_tracks.append([
                artist_info['id'],
                artist_info['name'],
                album_info['id'],
                album_info['name'],
                track_name,
                duration,
                '',  # Empty rating
                timestamp
            ])
            
            # Add to existing set
            existing['tracks'].add(track_key)
            
            # Add all album tracks
            album_tracks = fetch_album_tracks(artist_name, album_name)
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
                        ''   # No play timestamp
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