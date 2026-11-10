#!/usr/bin/env python3
"""Verify sync_podcast.sync() publishes only articles on/after the start
date that aren't already episodes, uploads yue/{nid}.m4a, and records the
row — using fake synthesize/upload so this needs no network, R2, or TTS."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import sync_podcast


def main():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    try:
        conn = db.connect(path)
        db.upsert_article(conn, "10", "Old column", "2026-11-08", "http://x/10", "old body", [])
        db.upsert_article(conn, "20", "Today column", "2026-11-09", "http://x/20", "today body", [])
        db.upsert_article(conn, "30", "Empty body", "2026-11-09", "http://x/30", "   ", [])
        db.upsert_article(conn, "40", "Already published", "2026-11-09", "http://x/40", "already body", [])
        db.save_podcast_episode(
            conn, "40",
            guid="cpoint-yue-40",
            media_url="https://audio.example/yue/40.m4a",
            byte_length=9,
            duration_seconds=1,
            published_at="2026-11-09T00:00:00Z",
        )
        conn.commit()
        conn.close()

        synthesized = []
        uploaded = []

        def fake_synthesize(nid, lang, text, dest_path):
            synthesized.append((nid, lang, text, dest_path))
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(b"M4A" + nid.encode() + b"xxxx")
            return 12

        def fake_upload(local_path, key, content_type):
            with open(local_path, "rb") as f:
                payload = f.read()
            uploaded.append((key, content_type, payload))

        published = sync_podcast.sync(
            path,
            since_date="2026-11-09",
            media_base_url="https://audio.example",
            synthesize=fake_synthesize,
            upload=fake_upload,
        )

        assert published == 1, f"expected only nid 20, got {published}"
        assert synthesized == [("20", "yue", "today body", synthesized[0][3])], synthesized
        assert uploaded == [("yue/20.m4a", "audio/mp4", b"M4A20xxxx")], uploaded

        conn = db.connect(path)
        assert db.get_podcast_episode(conn, "10") is None, "must not backfill pre-start-date articles"
        assert db.get_podcast_episode(conn, "30") is None, "must skip empty-body articles"
        assert db.get_podcast_episode(conn, "40")["byte_length"] == 9, "must not re-publish"
        ep = db.get_podcast_episode(conn, "20")
        assert ep is not None
        assert ep["guid"] == "cpoint-yue-20"
        assert ep["media_url"] == "https://audio.example/yue/20.m4a"
        assert ep["byte_length"] == 9
        assert ep["duration_seconds"] == 12
        conn.close()

        # A second run is a no-op — no more synthesize/upload.
        published_again = sync_podcast.sync(
            path,
            since_date="2026-11-09",
            media_base_url="https://audio.example",
            synthesize=fake_synthesize,
            upload=fake_upload,
        )
        assert published_again == 0
        assert len(synthesized) == 1
        assert len(uploaded) == 1

        print("OK: sync_podcast publishes only new post-cutoff Cantonese episodes")
    finally:
        if os.path.exists(path):
            os.remove(path)

    _check_upload_failure_does_not_record()
    _check_credentials_ready()


def _check_upload_failure_does_not_record():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    try:
        conn = db.connect(path)
        db.upsert_article(conn, "50", "Will fail", "2026-11-09", "http://x/50", "fail body", [])
        conn.commit()
        conn.close()

        def fake_synthesize(nid, lang, text, dest_path):
            with open(dest_path, "wb") as f:
                f.write(b"xx")
            return 1

        def boom(local_path, key, content_type):
            raise RuntimeError("r2 down")

        try:
            sync_podcast.sync(
                path,
                since_date="2026-11-09",
                media_base_url="https://audio.example",
                synthesize=fake_synthesize,
                upload=boom,
            )
            raise AssertionError("expected upload failure to propagate")
        except RuntimeError as e:
            assert "r2 down" in str(e)

        conn = db.connect(path)
        assert db.get_podcast_episode(conn, "50") is None
        conn.close()
        print("OK: sync_podcast does not record an episode if R2 upload fails")
    finally:
        if os.path.exists(path):
            os.remove(path)


def _check_credentials_ready():
    orig = dict(os.environ)
    for key in (
        "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET", "PODCAST_MEDIA_BASE_URL",
    ):
        os.environ.pop(key, None)
    try:
        assert sync_podcast.credentials_ready() is False
        os.environ["R2_ACCOUNT_ID"] = "acct"
        os.environ["R2_ACCESS_KEY_ID"] = "id"
        os.environ["R2_SECRET_ACCESS_KEY"] = "secret"
        os.environ["R2_BUCKET"] = "cpoint-podcast"
        os.environ["PODCAST_MEDIA_BASE_URL"] = "https://audio.example"
        assert sync_podcast.credentials_ready() is True
        print("OK: sync_podcast.credentials_ready requires the R2 env vars")
    finally:
        os.environ.clear()
        os.environ.update(orig)


if __name__ == "__main__":
    main()
