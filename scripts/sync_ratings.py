#!/usr/bin/env python3
"""
Sync audienceRating from taggings table to metadata_items via Plex API.

Plex's custom HTTP metadata provider writes Rating[] into the taggings table
(tag_type=316) but does NOT populate metadata_items.audience_rating.
This script reads the stored rating values from taggings and pushes them to
Plex via PUT /library/metadata/{id}, which writes audience_rating correctly.

Usage:
    python3 scripts/sync_ratings.py
    python3 scripts/sync_ratings.py --dry-run
    python3 scripts/sync_ratings.py --plex-host 192.168.31.41 --plex-port 32400
"""

import argparse
import sqlite3
import urllib.request
import urllib.parse
import os
import sys

DB_PATH = (
    "/var/lib/plexmediaserver/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
)
PLEX_HOST = os.environ.get("PLEX_HOST", "192.168.31.41")
PLEX_PORT = os.environ.get("PLEX_PORT", "32400")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "")
AGENT_PREFIX = "tv.plex.agents.custom.tmdb.zh"
RATING_IMAGE = "imdb://image.rating"


def get_token():
    prefs = (
        "/var/lib/plexmediaserver/Library/Application Support/"
        "Plex Media Server/Preferences.xml"
    )
    try:
        with open(prefs) as f:
            content = f.read()
        import re
        m = re.search(r'PlexOnlineToken="([^"]+)"', content)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def fetch_ratings(db_path):
    """
    Return list of (metadata_item_id, rating_value, current_audience_rating)
    for all items from our custom agent that have a Rating in taggings.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            mi.id,
            mi.title,
            mi.guid,
            CAST(tg.text AS FLOAT) AS rating_value,
            mi.audience_rating
        FROM metadata_items mi
        JOIN taggings tg ON tg.metadata_item_id = mi.id
        JOIN tags t ON t.id = tg.tag_id
        WHERE mi.guid LIKE ?
          AND t.tag_type = 316
          AND t.tag LIKE '%://image.rating'
          AND tg.text IS NOT NULL
          AND tg.text != ''
        ORDER BY mi.id
    """, (f"{AGENT_PREFIX}%",))
    rows = cur.fetchall()
    conn.close()
    return rows


def put_rating(plex_host, plex_port, token, item_id, rating_value, dry_run=False):
    params = urllib.parse.urlencode({
        "audienceRating.value": str(round(rating_value, 1)),
        "audienceRating.locked": "0",
        "audienceRatingImage.value": RATING_IMAGE,
        "audienceRatingImage.locked": "0",
        "X-Plex-Token": token,
    })
    url = f"http://{plex_host}:{plex_port}/library/metadata/{item_id}?{params}"
    if dry_run:
        return True
    req = urllib.request.Request(url, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Sync ratings to Plex for custom agent items")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without making changes")
    parser.add_argument("--plex-host", default=PLEX_HOST)
    parser.add_argument("--plex-port", default=PLEX_PORT)
    parser.add_argument("--token", default=PLEX_TOKEN or get_token())
    parser.add_argument("--only-missing", action="store_true", default=True,
                        help="Only update items where audience_rating is NULL (default: True)")
    parser.add_argument("--all", dest="only_missing", action="store_false",
                        help="Update ALL items even if audience_rating already set")
    args = parser.parse_args()

    if not args.token:
        print("ERROR: No Plex token found. Set PLEX_TOKEN env var or --token.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("[DRY RUN] No changes will be made")

    rows = fetch_ratings(DB_PATH)
    print(f"Found {len(rows)} items with Rating tags from custom agent")

    updated = 0
    skipped = 0
    failed = 0

    for item_id, title, guid, rating_value, current_rating in rows:
        if args.only_missing and current_rating is not None:
            skipped += 1
            continue

        label = title or guid or str(item_id)
        action = "DRY-RUN" if args.dry_run else "PUT"
        print(f"  [{action}] id={item_id} '{label}' → audienceRating={round(rating_value, 1)}")

        ok = put_rating(args.plex_host, args.plex_port, args.token, item_id, rating_value, args.dry_run)
        if ok:
            updated += 1
        else:
            failed += 1
            print(f"  FAILED for id={item_id}")

    print(f"\nDone: updated={updated}, skipped={skipped} (already set), failed={failed}")


if __name__ == "__main__":
    main()
