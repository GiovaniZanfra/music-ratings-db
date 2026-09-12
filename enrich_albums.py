import argparse

import gspread

from config import ALBUM_EXTRA_COLUMNS, SHEET_ALBUMS, SHEET_MUSIC
from lastfm import compute_decade, fetch_album_tracks
from sheets import chunked, ensure_headers, open_spreadsheet, write_batch

CHUNK_SIZE = 200


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill Genre/ReleaseYear/Decade for the existing Albums tab "
                     "(columns appended after whatever is already there)."
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Print what would be written without touching the sheet."
    )
    parser.add_argument(
        '--limit', type=int, default=None,
        help="Only process this many pending (not-yet-enriched) rows."
    )
    return parser.parse_args()


def load_music_migration_cache(ss):
    """Reuse Genre/ReleaseYear/Decade already sitting in the Music sheet from
    an earlier (since-reverted) attempt at storing them per-track, so we
    don't re-hit the Last.fm API for albums we've already fetched.
    Returns {} if Music no longer has those columns (nothing to reuse).
    """
    ws_music = ss.worksheet(SHEET_MUSIC)
    values = ws_music.get_all_values()
    if not values:
        return {}

    header = values[0]
    needed = ['ArtistName', 'AlbumName', 'Genre', 'ReleaseYear', 'Decade']
    if not all(col in header for col in needed):
        return {}

    idx = {col: header.index(col) for col in needed}
    cache = {}
    for row in values[1:]:
        def cell(col):
            i = idx[col]
            return row[i] if i < len(row) else ''

        artist, album = cell('ArtistName'), cell('AlbumName')
        genre, year, decade = cell('Genre'), cell('ReleaseYear'), cell('Decade')
        if not artist or not album:
            continue
        key = (artist, album)
        if key not in cache and (genre or year or decade):
            cache[key] = (genre, year, decade)
    return cache


def main():
    args = parse_args()
    ss = open_spreadsheet()

    migration_cache = load_music_migration_cache(ss)
    print(f"Reusing {len(migration_cache)} album(s) already enriched previously (no API call needed).")

    ws_albums = ss.worksheet(SHEET_ALBUMS)
    current_headers = ws_albums.row_values(1)
    if all(col in current_headers for col in ALBUM_EXTRA_COLUMNS):
        headers = current_headers
    else:
        headers = current_headers + ALBUM_EXTRA_COLUMNS
    ensure_headers(ws_albums, headers)

    genre_col = headers.index('Genre') + 1  # 1-based
    year_col = headers.index('ReleaseYear') + 1
    decade_col = headers.index('Decade') + 1

    values = ws_albums.get_all_values()

    pending_rows = []  # list of (row_number, artist_name, album_name)
    for i, row in enumerate(values[1:], start=2):
        album_name = row[0] if len(row) > 0 else ''
        artist_name = row[1] if len(row) > 1 else ''
        if not album_name:
            continue

        def filled(col_1based):
            idx0 = col_1based - 1
            return idx0 < len(row) and row[idx0] not in ('', None)

        if filled(genre_col) and filled(year_col) and filled(decade_col):
            continue

        pending_rows.append((i, artist_name, album_name))

    total_pending = len(pending_rows)
    if args.limit is not None:
        pending_rows = pending_rows[:args.limit]

    print(f"{total_pending} album row(s) pending; processing {len(pending_rows)} now "
          f"in chunks of {CHUNK_SIZE}.")

    api_calls = 0
    reused = 0
    written = 0

    for chunk in chunked(pending_rows, CHUNK_SIZE):
        chunk_updates = []  # list of (row_number, [genre, year, decade])

        for row_number, artist_name, album_name in chunk:
            key = (artist_name, album_name)
            if key in migration_cache:
                genre, year, decade = migration_cache[key]
                reused += 1
            else:
                _, genre, year = fetch_album_tracks(artist_name, album_name)
                decade = compute_decade(year)
                api_calls += 1

            chunk_updates.append((row_number, [genre, year, decade]))
            print(f"  row {row_number}: {artist_name} - {album_name} "
                  f"-> genre={genre!r} year={year!r} decade={decade!r}")

        if args.dry_run:
            continue

        batch_data = []
        for row_number, values3 in chunk_updates:
            range_name = (
                gspread.utils.rowcol_to_a1(row_number, genre_col)
                + ":"
                + gspread.utils.rowcol_to_a1(row_number, decade_col)
            )
            batch_data.append({'range': range_name, 'values': [values3]})
        write_batch(ws_albums, batch_data)
        written += len(chunk_updates)
        print(f"  -> wrote {written}/{len(pending_rows)} row(s) so far.")

    print(f"\n{len(pending_rows)} row(s) processed "
          f"({api_calls} album.getInfo call(s), {reused} reused from Music).")

    if args.dry_run:
        print("Dry run: nothing written to the sheet.")
    else:
        print(f"Wrote {written} row(s) to the sheet.")


if __name__ == "__main__":
    main()
