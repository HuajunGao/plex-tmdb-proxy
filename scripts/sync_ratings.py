#!/usr/bin/env python3
"""
Sync audienceRating from taggings table to metadata_items via Plex API,
and set audienceRatingImage in extra_data so Plex clients display the badge.

Plex's custom HTTP metadata provider writes Rating[] into the taggings table
(tag_type=316) but does NOT populate metadata_items.audience_rating, and does
NOT write at:audienceRatingImage to extra_data (which controls the rating image
shown in the Plex UI).  Both are required for the audience rating badge to
appear in Plex clients.

This script:
  1. Calls PUT /library/metadata/{id}  → writes audience_rating
  2. Updates extra_data directly via Plex SQLite → writes at:audienceRatingImage

Usage:
    python3 scripts/sync_ratings.py
    python3 scripts/sync_ratings.py --dry-run
    python3 scripts/sync_ratings.py --plex-host 192.168.31.41 --plex-port 32400
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from urllib.parse import quote

DB_PATH = (
    "/var/lib/plexmediaserver/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
)
PLEX_SQLITE = "/usr/lib/plexmediaserver/Plex SQLite"
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
    Return list of (id, title, guid, rating_value, current_audience_rating, extra_data)
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
            mi.audience_rating,
            mi.extra_data
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


def needs_extra_data_update(extra_data_json):
    """Return True if at:audienceRatingImage is not yet set in extra_data."""
    if not extra_data_json:
        return True
    try:
        data = json.loads(extra_data_json)
        return "at:audienceRatingImage" not in data
    except (json.JSONDecodeError, TypeError):
        return True


def build_updated_extra_data(extra_data_json):
    """Add at:audienceRatingImage to the extra_data JSON blob."""
    try:
        data = json.loads(extra_data_json) if extra_data_json else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    data["at:audienceRatingImage"] = RATING_IMAGE

    # Rebuild the url field (URL-encoded query string representation)
    url_parts = []
    for k, v in data.items():
        if k == "url":
            continue
        url_parts.append(quote(k, safe="") + "=" + quote(str(v), safe="~"))
    data["url"] = "&".join(url_parts)

    return json.dumps(data, separators=(",", ":"))


def sync_extra_data_batch(db_path, updates, dry_run=False):
    """
    Write at:audienceRatingImage into extra_data for a batch of items.
    Uses Plex's bundled SQLite binary because the DB has custom FTS triggers
    that the system sqlite3 cannot handle.

    updates: list of (item_id, new_extra_data_json)
    Returns (success_count, fail_count)
    """
    if dry_run or not updates:
        return len(updates), 0

    # Build SQL statements; escape single-quotes by doubling them
    sql_lines = []
    for item_id, new_extra in updates:
        escaped = new_extra.replace("'", "''")
        sql_lines.append(f"UPDATE metadata_items SET extra_data='{escaped}' WHERE id={item_id};")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
        f.write("\n".join(sql_lines) + "\n")
        tmpfile = f.name

    try:
        result = subprocess.run(
            [PLEX_SQLITE, db_path],
            stdin=open(tmpfile),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  Plex SQLite error: {result.stderr}", file=sys.stderr)
            return 0, len(updates)
        return len(updates), 0
    except FileNotFoundError:
        print(f"  ERROR: Plex SQLite not found at {PLEX_SQLITE}", file=sys.stderr)
        return 0, len(updates)
    finally:
        os.unlink(tmpfile)


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
                        help="Only update items where audience_rating is NULL or audienceRatingImage unset (default: True)")
    parser.add_argument("--all", dest="only_missing", action="store_false",
                        help="Update ALL items even if already set")
    args = parser.parse_args()

    if not args.token:
        print("ERROR: No Plex token found. Set PLEX_TOKEN env var or --token.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("[DRY RUN] No changes will be made")

    rows = fetch_ratings(DB_PATH)
    print(f"Found {len(rows)} items with Rating tags from custom agent")

    updated_rating = 0
    updated_image = 0
    skipped = 0
    failed = 0

    extra_data_updates = []

    for item_id, title, guid, rating_value, current_rating, extra_data in rows:
        label = title or guid or str(item_id)
        needs_rating = current_rating is None
        needs_image = needs_extra_data_update(extra_data)

        if args.only_missing and not needs_rating and not needs_image:
            skipped += 1
            continue

        action = "DRY-RUN" if args.dry_run else "PUT"
        parts = []
        if needs_rating or not args.only_missing:
            parts.append(f"audienceRating={round(rating_value, 1)}")
        if needs_image or not args.only_missing:
            parts.append(f"audienceRatingImage={RATING_IMAGE}")
        print(f"  [{action}] id={item_id} '{label}' → {', '.join(parts)}")

        if needs_rating or not args.only_missing:
            ok = put_rating(args.plex_host, args.plex_port, args.token, item_id, rating_value, args.dry_run)
            if ok:
                updated_rating += 1
            else:
                failed += 1
                print(f"  FAILED PUT for id={item_id}")

        if needs_image or not args.only_missing:
            new_extra = build_updated_extra_data(extra_data)
            extra_data_updates.append((item_id, new_extra))

    # Batch-update extra_data via Plex SQLite
    if extra_data_updates:
        action = "DRY-RUN" if args.dry_run else "DB"
        print(f"\n[{action}] Writing audienceRatingImage to extra_data for {len(extra_data_updates)} items...")
        ok_count, fail_count = sync_extra_data_batch(DB_PATH, extra_data_updates, args.dry_run)
        updated_image = ok_count
        failed += fail_count
        if not args.dry_run and ok_count:
            print(f"  Updated extra_data for {ok_count} items")

    print(f"\nDone: rating_updated={updated_rating}, image_updated={updated_image}, skipped={skipped} (already set), failed={failed}")


if __name__ == "__main__":
    main()
