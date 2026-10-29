import re
import time

import requests

from config import API_KEY, URL, USER


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


def extract_release_year(wiki_summary):
    """Best-effort year extraction from the album wiki summary text.

    Last.fm's album.getInfo has no structured release-date field; the year
    (when present) shows up in prose like "... released in 1997.".
    """
    if not wiki_summary:
        return ""
    # Allow a day/month between "released" and the year ("released July 30, 1969").
    match = re.search(r"released?\b.{0,40}?\b((?:19|20)\d{2})\b", wiki_summary, re.IGNORECASE)
    return match.group(1) if match else ""


def compute_decade(year):
    """Turn a 4-digit year string into a decade label, e.g. '1997' -> '1990s'."""
    if not year:
        return ""
    try:
        return f"{(int(year) // 10) * 10}s"
    except ValueError:
        return ""


def get_track_details(artist_name, track_name):
    """Fetch track duration and the user's play count for that track"""
    track_data = fetch_entity_info(
        "track.getInfo", artist=artist_name, track=track_name, username=USER
    )
    time.sleep(0.2)  # Rate limiting

    duration = 0
    playcount = ""
    if track_data and 'track' in track_data:
        # Get duration (convert to seconds)
        duration_str = track_data['track'].get('duration')
        if duration_str:
            try:
                duration = int(duration_str) // 1000  # Convert ms to seconds
            except (ValueError, TypeError):
                duration = 0

        playcount = track_data['track'].get('userplaycount', "")

    return duration, playcount


def fetch_album_tracks(artist_name, album_name):
    """Fetch all tracks from an album, plus album-level genre/release year"""
    album_data = fetch_entity_info("album.getInfo", artist=artist_name, album=album_name)
    time.sleep(0.2)

    tracks = []
    genre = ""
    release_year = ""

    if album_data and 'album' in album_data:
        album = album_data['album']

        tags_data = album.get('tags', {})
        if isinstance(tags_data, dict):
            tag_list = tags_data.get('tag', [])
            if isinstance(tag_list, dict):
                tag_list = [tag_list]
            genre = ", ".join(t.get('name', '') for t in tag_list if isinstance(t, dict))

        wiki = album.get('wiki', {})
        if isinstance(wiki, dict):
            release_year = extract_release_year(wiki.get('summary', ''))

        if 'tracks' in album:
            tracks_data = album['tracks'].get('track', [])

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

    return tracks, genre, release_year


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
