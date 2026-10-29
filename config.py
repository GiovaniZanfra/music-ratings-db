import os

# Load KEY=VALUE pairs from a local, gitignored .env (real env vars win).
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

USER = "gigs12345678"
API_KEY = os.environ["LASTFM_API_KEY"]
URL = "http://ws.audioscrobbler.com/2.0/"

SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
CREDS_FILE = 'lastfm-to-sheets-ed442fe7881c.json'
SPREADSHEET_NAME = 'music_db_ratings'
SHEET_MUSIC = 'Music'  # One row per track (denormalized)
SHEET_ALBUMS = 'Albums'  # Pre-existing tab: AlbumName/ArtistName are live
                          # spilled formulas reading from Music; RawScore/
                          # FinalScore are the user's own manual album scores.

MUSIC_HEADERS = [
    'ArtistID',
    'ArtistName',
    'AlbumID',
    'AlbumName',
    'TrackName',
    'Duration',
    'Rating',
    'LastPlayed',
    'Notes',
    'PlayCount',  # per-track, from track.getInfo(username=...)
]

# Appended to whatever header row the Albums tab already has (AlbumName,
# ArtistName, RawScore, FinalScore, Notes, ...) -- never replaces it.
ALBUM_EXTRA_COLUMNS = ['Genre', 'ReleaseYear', 'Decade']
