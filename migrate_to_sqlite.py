#!/usr/bin/env python3
"""One-time migration: import the already-downloaded articles_<year>/*.txt
bodies into articles.db, joined by nid against a fresh walk of the listing
API for hashtags/title/date/url. Safe to re-run (upsert is idempotent)."""
import os
import re
import sys
import time

import db
import download_am730_column as dl

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d+)_.*\.txt$")
BOILERPLATE_TAGS = {"C觀點", "施永青"}


def load_local_bodies(root_dir):
    """nid -> (title, date, url, body), read from the downloaded .txt files."""
    bodies = {}
    for entry in sorted(os.listdir(root_dir)):
        year_dir = os.path.join(root_dir, entry)
        if not (entry.startswith("articles_") and os.path.isdir(year_dir)):
            continue
        for fname in sorted(os.listdir(year_dir)):
            m = FILENAME_RE.match(fname)
            if not m:
                continue
            nid = m.group(2)
            with open(os.path.join(year_dir, fname), encoding="utf-8") as f:
                lines = f.read().split("\n")
            title, date, url = lines[0], lines[1], lines[2]
            body = "\n".join(lines[4:]).strip()
            bodies[nid] = (title, date, url, body)
    return bodies


def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.4

    bodies = load_local_bodies(root_dir)
    print(f"Found {len(bodies)} locally downloaded article bodies.")

    if len(bodies) == 0:
        print(
            "No local articles_<year>/*.txt files were found under "
            f"{root_dir!r}.\n"
            "This script expects the original downloader's output "
            "directories (articles_<year>/) to already exist on disk — it "
            "does not download article bodies itself, only hashtag "
            "metadata from the listing API.\n"
            "If you're starting from a fresh clone with no prior scrape, "
            "run `python3 sync_articles.py` instead: it will walk the "
            "full archive from empty (slower, since it fetches every "
            "article body over the network) but is self-contained and "
            "doesn't require the local text files."
        )
        sys.exit(1)

    conn = db.connect(os.path.join(root_dir, db.DB_PATH))
    page, next_key, next_date = 1, "", ""
    imported, skipped = 0, 0
    while True:
        result = dl.post_page(dl.DEFAULT_COLUMNIST_URL, page, next_key, next_date)
        data = result.get("data", {})
        items = data.get("data", [])
        if not items:
            break
        for item in items:
            nid = str(item.get("nid"))
            if nid not in bodies:
                skipped += 1
                continue
            title, date, url, body = bodies[nid]
            tags = [t for t in item.get("hashtags", []) if t not in BOILERPLATE_TAGS]
            db.upsert_article(conn, nid, title, date, url, body, tags)
            imported += 1
        conn.commit()

        pagination = data.get("pagination") or {}
        if not pagination.get("hasNextPage"):
            break
        cursor = pagination.get("nextPageCursor") or {}
        next_key = cursor.get("nextPageKey", "")
        next_date = cursor.get("nextPageDate", "")
        page += 1
        time.sleep(delay)

    conn.close()
    print(f"Migrated {imported} articles into {db.DB_PATH} "
          f"({skipped} listing entries had no local body on disk)")


if __name__ == "__main__":
    main()
