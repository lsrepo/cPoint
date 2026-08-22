#!/usr/bin/env python3
"""Incremental sync: fetch only articles newer than what's already in
articles.db, stopping as soon as an already-known nid is reached (the
listing API returns newest-first). Safe and cheap to run daily."""
import sys
import time

import db
import download_am730_column as dl

BOILERPLATE_TAGS = {"C觀點", "施永青"}


def sync(columnist_url, db_path, delay):
    conn = db.connect(db_path)
    page, next_key, next_date = 1, "", ""
    new_count = 0
    while True:
        result = dl.post_page(columnist_url, page, next_key, next_date)
        data = result.get("data", {})
        items = data.get("data", [])
        if not items:
            break

        stop = False
        for item in items:
            nid = str(item.get("nid"))
            if db.article_exists(conn, nid):
                stop = True
                break
            title = item.get("title", "")
            pub_date = item.get("publishDate", "")[:10]
            rel_url = item.get("url", "")
            tags = [t for t in item.get("hashtags", []) if t not in BOILERPLATE_TAGS]
            body = dl.fetch_article_text(rel_url)
            db.upsert_article(conn, nid, title, pub_date, dl.SITE + rel_url, body, tags)
            conn.commit()
            new_count += 1
            print(f"  + {pub_date} {title}")
            time.sleep(delay)

        if stop:
            break

        pagination = data.get("pagination") or {}
        if not pagination.get("hasNextPage"):
            break
        cursor = pagination.get("nextPageCursor") or {}
        next_key = cursor.get("nextPageKey", "")
        next_date = cursor.get("nextPageDate", "")
        page += 1
        time.sleep(delay)

    conn.close()
    return new_count


def main():
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 0.4
    new_count = sync(dl.DEFAULT_COLUMNIST_URL, db.DB_PATH, delay)
    print(f"Sync complete: {new_count} new article(s) added.")


if __name__ == "__main__":
    main()
