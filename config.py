import os

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
