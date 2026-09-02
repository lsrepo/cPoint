#!/usr/bin/env python3
"""Verify sync_vocab.sync() merges every exported row for an article that
exists locally, and skips rows for articles that don't (yet) — using a
fake in-memory export so this test needs no network access."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import sync_vocab

FAKE_EXPORT = [
    {
        "nid": "1",
        "terms": [{"term": "cabinet", "pos": "noun", "ipa": "/kab/", "zh": "內閣", "example": "x"}],
        "generated_in_seconds": 3.5,
    },
    {
        "nid": "2",
        "terms": [{"term": "veto", "pos": "noun", "ipa": "/v/", "zh": "否決", "example": "y"}],
        "generated_in_seconds": None,
    },
    {
        # Not in the local DB — production ahead of this repo's sync.
        # Merging this would violate the FK on vocab.article_nid.
        "nid": "999",
        "terms": [{"term": "ghost", "pos": "noun", "ipa": "/g/", "zh": "x", "example": "z"}],
        "generated_in_seconds": 1.0,
    },
]


def main():
    calls = []

    def fake_fetch_export(export_url):
        calls.append(export_url)
        return FAKE_EXPORT

    real_fetch_export = sync_vocab.fetch_export
    sync_vocab.fetch_export = fake_fetch_export

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    try:
        conn = db.connect(path)
        db.upsert_article(conn, "1", "Title A", "2025-01-01", "http://x/1", "Body A", [])
        db.upsert_article(conn, "2", "Title B", "2025-01-02", "http://x/2", "Body B", [])
        conn.commit()
        conn.close()

        synced = sync_vocab.sync("http://fake-export-url", path)

        assert calls == ["http://fake-export-url"], calls
        assert synced == 2, f"expected 2 rows merged (nid 999 skipped), got {synced}"

        conn = db.connect(path)
        assert db.get_vocab(conn, "1") == (FAKE_EXPORT[0]["terms"], 3.5)
        assert db.get_vocab(conn, "2") == (FAKE_EXPORT[1]["terms"], None)
        assert db.get_vocab(conn, "999") is None, "must not insert vocab for an article missing locally"
        conn.close()

        print("OK: sync_vocab.sync() merges rows for known articles and skips unknown ones")
    finally:
        sync_vocab.fetch_export = real_fetch_export
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
