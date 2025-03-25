import requests
from psycopg2 import sql
from config.constants import URL, USER, API_KEY, DB_CONFIG
from utils import get_db_connection
import argparse

class APIRequestor:
    def __init__(self, user, api_key, url, limit=100):
        self.user = user
        self.api_key = api_key
        self.url = url
        self.limit = limit

    def fetch_recent_tracks(self):
        params = {
            "method": "user.getrecenttracks",
            "user": self.user,
            "api_key": self.api_key,
            "format": "json",
            "limit": self.limit
        }
        response = requests.get(self.url, params=params)
        response.raise_for_status()
        return response.json().get("recenttracks", {}).get("track", [])

    def fetch_album_tracks(self, artist_name, album_name):
        params = {
            "method": "album.getinfo",
            "artist": artist_name,
            "album": album_name,
            "api_key": self.api_key,
            "format": "json"
        }
        response = requests.get(self.url, params=params)
        response.raise_for_status()
        return response.json()

class AlbumParser:
    def parse_album_info(self, album_info):
        album = album_info.get("album", {})
        # Extract tracks (handle dict or list)
        tracks = album.get("tracks", {}).get("track", [])
        if isinstance(tracks, dict):
            tracks = [tracks]
        tracklist = [
                {
                    "name": t.get("name", "Unknown"),
                    "duration": int(t.get("duration", 0)) if t.get("duration") else 0,
                    "tags": t.get("tags", {}).get("tag", []) if isinstance(t.get("tags"), dict) else []
                }
                for t in tracks
                    ]

        # Extract tags, handling dict, string, or empty string
        tags_data = album.get("tags", {})
        tags = []
        if isinstance(tags_data, dict):
            tag_list = tags_data.get("tag", [])
            if isinstance(tag_list, dict):
                tag_list = [tag_list]
            tags = [t.get("name", "Unknown") for t in tag_list if isinstance(t, dict)]
        elif isinstance(tags_data, str) and tags_data.strip():
            # Non-empty string; treat it as a single tag
            tags = [tags_data.strip()]
        # Else, if tags_data is an empty string or other type, leave tags as empty list
        return tracklist, tags

class ConsoleFormatter:
    # ANSI escape codes for styling
    BOLD = "\033[1m"
    RESET = "\033[0m"
    ARTIST_COLOR = "\033[1;34m"  # Blue
    ALBUM_COLOR = "\033[1;33m"   # Yellow
    TRACK_COLOR = "\033[1;32m"   # Green

    def format_artist(self, artist_name):
        return f"{self.ARTIST_COLOR}{self.BOLD}{artist_name}{self.RESET}"

    def format_album(self, album_name, artist_name):
        return f"{self.ALBUM_COLOR}{self.BOLD}{album_name}{self.RESET} for artist: {self.ARTIST_COLOR}{self.BOLD}{artist_name}{self.RESET}"

    def format_track(self, track_name, album_name, artist_name):
        return f"{self.TRACK_COLOR}{self.BOLD}{track_name}{self.RESET} for album: {self.ALBUM_COLOR}{self.BOLD}{album_name}{self.RESET} by artist: {self.ARTIST_COLOR}{self.BOLD}{artist_name}{self.RESET}"

    def print_artist(self, artist_name):
        print(f"Loading artist: {self.format_artist(artist_name)}")

    def print_album(self, artist_name, album_name):
        print(f"Loading album: {self.format_album(album_name, artist_name)}")

    def print_track(self, artist_name, album_name, track_name):
        print(f"Loading track: {self.format_track(track_name, album_name, artist_name)}")

    def print_log(self, message):
        # You can add styling or timestamping here if needed
        print(f"[LOG]: {message}")

class DatabaseLoader:
    def __init__(self, db_config, formatter=None):
        self.db_config = db_config
        self.formatter = formatter if formatter is not None else ConsoleFormatter()

    def load_artist(self, artist_name):
        conn = get_db_connection(**self.db_config)
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO artists (artist_name)
                    VALUES (%s)
                    ON CONFLICT (artist_name) DO NOTHING;
                """
                cursor.execute(query, (artist_name,))
            conn.commit()
            self.formatter.print_artist(artist_name)
        except Exception as e:
            print(f"Error inserting artist: {e}")
        finally:
            conn.close()

    def load_album(self, artist_name, album_name):
        conn = get_db_connection(**self.db_config)
        try:
            with conn.cursor() as cursor:
                query_artist = "SELECT artist_id FROM artists WHERE artist_name = %s;"
                cursor.execute(query_artist, (artist_name,))
                artist_id = cursor.fetchone()
                if artist_id:
                    artist_id = artist_id[0]
                    query_album = """
                        INSERT INTO albums (artist_id, album_name)
                        VALUES (%s, %s)
                        ON CONFLICT (artist_id, album_name) DO NOTHING;
                    """
                    cursor.execute(query_album, (artist_id, album_name))
                    conn.commit()
                    self.formatter.print_album(artist_name, album_name)
                else:
                    print(f"Artist '{artist_name}' not found in the database.")
        except Exception as e:
            print(f"Error inserting album: {e}")
        finally:
            conn.close()

    def load_track(self, artist_name, album_name, track_name, track_duration):
        conn = get_db_connection(**self.db_config)
        try:
            with conn.cursor() as cursor:
                query_artist = "SELECT artist_id FROM artists WHERE artist_name = %s;"
                cursor.execute(query_artist, (artist_name,))
                artist_id = cursor.fetchone()
                if artist_id:
                    artist_id = artist_id[0]
                    query_album = "SELECT album_id FROM albums WHERE artist_id = %s AND album_name = %s;"
                    cursor.execute(query_album, (artist_id, album_name))
                    album_id = cursor.fetchone()
                    if album_id:
                        album_id = album_id[0]
                        query_track = """
                            INSERT INTO tracks (artist_id, album_id, track_name, track_duration)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (artist_id, album_id, track_name) DO NOTHING;
                        """
                        cursor.execute(query_track, (artist_id, album_id, track_name, track_duration))
                        conn.commit()
                        self.formatter.print_track(artist_name, album_name, track_name)
                    else:
                        print(f"Album '{album_name}' not found for artist '{artist_name}'.")
                else:
                    print(f"Artist '{artist_name}' not found in the database.")
        except Exception as e:
            print(f"Error inserting track: {e}")
        finally:
            conn.close()

class TrackService:
    def __init__(self, api_requestor, album_parser, data_loader):
        self.api_requestor = api_requestor
        self.album_parser = album_parser
        self.data_loader = data_loader

    def process_tracks(self):
        recent_tracks = self.api_requestor.fetch_recent_tracks()
        print(len(recent_tracks))
        for track in recent_tracks:
            artist_name = track.get("artist", {}).get("#text", "Unknown")
            album_name = track.get("album", {}).get("#text", "Unknown")
            album_info = self.api_requestor.fetch_album_tracks(artist_name, album_name)
            tracklist, tags = self.album_parser.parse_album_info(album_info)
            self.data_loader.load_artist(artist_name)
            self.data_loader.load_album(artist_name, album_name)
            for track in tracklist:
                track_name = track["name"]
                track_duration = track["duration"]
                self.data_loader.load_track(artist_name, album_name, track_name, track_duration)

class NullFormatter:
    def print_artist(self, artist_name): pass
    def print_album(self, artist_name, album_name): pass
    def print_track(self, artist_name, album_name, track_name): pass
    def print_log(self, message): pass

parser = argparse.ArgumentParser(description='PyTorch Classification')
parser.add_argument('--verbose', '-v', action='store_true', help='If ingestion should be logged on console')
parser.add_argument('--num-tracks', default=100, type=int, help='Number of tracks that is going to be requested to LastFM API')
args = parser.parse_args()

def main():
    api_requestor = APIRequestor(USER, API_KEY, URL, args.num_tracks)
    formatter = ConsoleFormatter() if args.verbose else NullFormatter()
    service = TrackService(api_requestor, AlbumParser(), DatabaseLoader(DB_CONFIG, formatter=formatter))
    service.process_tracks()

if __name__ == "__main__":
    main()
