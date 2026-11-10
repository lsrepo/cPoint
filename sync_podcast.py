#!/usr/bin/env python3
"""Publish Cantonese read-aloud episodes for articles on/after
PODCAST_START_DATE that aren't already in podcast_episodes.

Intentionally forward-only: historical columns already in articles.db
are never synthesized or uploaded. New rows from sync_articles.py
(date >= start) become one RSS episode each.

Audio files go to R2; episode metadata is stored in articles.db so the
daily sync-articles workflow can commit it the same way it commits new
articles. The live /podcast.xml route reads those rows — it never talks
to R2, so a Dokploy rebuild doesn't need object-storage credentials just
to serve the feed.
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

import db

LANG = "yue"
DEFAULT_START_DATE = "2026-11-09"
REQUIRED_ENV = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "PODCAST_MEDIA_BASE_URL",
)


def credentials_ready():
    return all(os.environ.get(name) for name in REQUIRED_ENV)


def guid_for(nid):
    return f"cpoint-yue-{nid}"


def enclosure_key(nid):
    return f"yue/{nid}.m4a"


def synthesize_episode(nid, lang, text, dest_path):
    import asyncio
    import tts
    return asyncio.run(tts.synthesize_audio_m4a(text, lang, dest_path))


def upload_episode(local_path, key, content_type):
    import r2
    r2.upload_file(
        local_path,
        key,
        content_type,
        account_id=os.environ["R2_ACCOUNT_ID"],
        access_key=os.environ["R2_ACCESS_KEY_ID"],
        secret_key=os.environ["R2_SECRET_ACCESS_KEY"],
        bucket=os.environ["R2_BUCKET"],
    )


def sync(db_path, since_date, media_base_url, synthesize, upload):
    conn = db.connect(db_path)
    published = 0
    tmpdir = tempfile.mkdtemp(prefix="cpoint-podcast-")
    try:
        for article in db.unpublished_articles_since(conn, since_date):
            if not (article["body"] or "").strip():
                continue
            nid = article["nid"]
            dest = os.path.join(tmpdir, f"{nid}.m4a")
            duration_seconds = synthesize(nid, LANG, article["body"], dest)
            key = enclosure_key(nid)
            upload(dest, key, "audio/mp4")
            db.save_podcast_episode(
                conn, nid,
                guid=guid_for(nid),
                media_url=f"{media_base_url.rstrip('/')}/{key}",
                byte_length=os.path.getsize(dest),
                duration_seconds=duration_seconds,
                published_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            published += 1
            print(f"  + podcast yue nid={nid} bytes={os.path.getsize(dest)} duration={duration_seconds}s")
        return published
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        conn.close()


def main():
    if not credentials_ready():
        print("Skipping podcast sync: R2 credentials not set")
        return
    since_date = os.environ.get("PODCAST_START_DATE", DEFAULT_START_DATE)
    media_base_url = os.environ["PODCAST_MEDIA_BASE_URL"]
    n = sync(
        db.DB_PATH,
        since_date=since_date,
        media_base_url=media_base_url,
        synthesize=synthesize_episode,
        upload=upload_episode,
    )
    print(f"Podcast sync complete: {n} new episode(s).")


if __name__ == "__main__":
    main()
    sys.exit(0)
