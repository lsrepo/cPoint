#!/usr/bin/env python3
"""Verify sync_articles.sync() inserts only genuinely new articles and
stops at the first already-known nid — using a fake in-memory listing API
so this test needs no network access."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import download_am730_column as dl
import sync_articles

FAKE_PAGES = [
    # page 1 (newest first)
    {"data": {"data": [
        {"nid": 103, "title": "New C", "publishDate": "2026-01-03T00:00:00Z", "url": "/c", "hashtags": ["x"]},
        {"nid": 102, "title": "New B", "publishDate": "2026-01-02T00:00:00Z", "url": "/b", "hashtags": ["x"]},
    ], "pagination": {"hasNextPage": True, "nextPageCursor": {"nextPageKey": "k1", "nextPageDate": "d1"}}}},
    # page 2: first item already known -> sync must stop here, never fetching page 3
    {"data": {"data": [
        {"nid": 101, "title": "Already known A", "publishDate": "2026-01-01T00:00:00Z", "url": "/a", "hashtags": ["x"]},
        {"nid": 100, "title": "Older, should never be fetched", "publishDate": "2025-12-31T00:00:00Z", "url": "/z", "hashtags": []},
    ], "pagination": {"hasNextPage": True, "nextPageCursor": {"nextPageKey": "k2", "nextPageDate": "d2"}}}},
]


def main():
    calls = {"post_page": 0, "fetch_article_text": []}

    def fake_post_page(columnist_url, page, next_key, next_date):
        calls["post_page"] += 1
        return FAKE_PAGES[page - 1]

    def fake_fetch_article_text(rel_url):
        calls["fetch_article_text"].append(rel_url)
        return f"body for {rel_url}"

    orig_post_page, orig_fetch = dl.post_page, dl.fetch_article_text
    dl.post_page, dl.fetch_article_text = fake_post_page, fake_fetch_article_text

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    try:
        conn = db.connect(path)
        db.upsert_article(conn, "101", "Already known A", "2026-01-01", "http://x/a", "old body", ["x"])
        conn.commit()
        conn.close()

        new_count = sync_articles.sync(dl.DEFAULT_COLUMNIST_URL, path, delay=0)

        assert new_count == 2, f"expected 2 new articles (103, 102), got {new_count}"
        assert calls["post_page"] == 2, f"expected exactly 2 pages fetched, got {calls['post_page']}"
        assert sorted(calls["fetch_article_text"]) == ["/b", "/c"], calls["fetch_article_text"]

        conn = db.connect(path)
        nids = {a["nid"] for a in db.list_articles(conn)}
        assert nids == {"101", "102", "103"}, nids
        assert "100" not in nids, "sync must not fetch articles older than the known cutoff"
        conn.close()

        print("OK: sync stops at the first already-known nid and inserts only genuinely new articles")
    finally:
        dl.post_page, dl.fetch_article_text = orig_post_page, orig_fetch
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
