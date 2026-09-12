import argparse

import gspread

from config import MUSIC_HEADERS, SHEET_MUSIC
from lastfm import get_track_details
from sheets import chunked, open_spreadsheet, setup_worksheet, write_batch

CHUNK_SIZE = 200


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill PlayCount for existing rows in the Music sheet."
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


def main():
    args = parse_args()

    ss = open_spreadsheet()
    ws = setup_worksheet(ss, SHEET_MUSIC, MUSIC_HEADERS)

    records = ws.get_all_records()
    playcount_col = MUSIC_HEADERS.index('PlayCount') + 1  # 1-based

    pending_rows = []  # list of (row_number, record)
    for i, record in enumerate(records):
        if record.get('PlayCount', '') not in ('', None):
            continue
        if not record.get('ArtistName') or not record.get('TrackName'):
            continue  # blank/malformed row, nothing to look up
        row_number = i + 2  # +1 for header row, +1 for 1-based indexing
        pending_rows.append((row_number, record))

    total_pending = len(pending_rows)
    if args.limit is not None:
        pending_rows = pending_rows[:args.limit]

    print(f"{total_pending} row(s) pending PlayCount; processing {len(pending_rows)} now "
          f"in chunks of {CHUNK_SIZE}.")

    track_calls = 0
    written = 0

    for chunk in chunked(pending_rows, CHUNK_SIZE):
        chunk_updates = []  # list of (row_number, playcount)

        for row_number, record in chunk:
            artist_name = record.get('ArtistName', '')
            track_name = record.get('TrackName', '')

            _, playcount = get_track_details(artist_name, track_name)
            track_calls += 1

            chunk_updates.append((row_number, playcount))
            print(f"  row {row_number}: {artist_name} - {track_name} -> playcount={playcount!r}")

        if args.dry_run:
            continue

        batch_data = [
            {
                'range': gspread.utils.rowcol_to_a1(row_number, playcount_col),
                'values': [[playcount]],
            }
            for row_number, playcount in chunk_updates
        ]
        write_batch(ws, batch_data)
        written += len(chunk_updates)
        print(f"  -> wrote {written}/{len(pending_rows)} row(s) so far.")

    print(f"\n{len(pending_rows)} row(s) processed ({track_calls} track.getInfo call(s)).")

    if args.dry_run:
        print("Dry run: nothing written to the sheet.")
    else:
        print(f"Wrote {written} row(s) to the sheet.")


if __name__ == "__main__":
    main()
