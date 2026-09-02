#!/usr/bin/env python3
"""Verify db.py's schema and query helpers, using an isolated temporary
database. No network access, fully deterministic."""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def main():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # db.connect() creates it fresh
    try:
        conn = db.connect(path)

        assert db.article_exists(conn, "1") is False

        db.upsert_article(conn, "1", "Title A", "2025-01-01", "http://x/1", "Body A", ["tag1", "tag2"])
        db.upsert_article(conn, "2", "Title B", "2025-02-01", "http://x/2", "Body B", ["tag2"])
        db.upsert_article(conn, "3", "Title C", "2024-01-01", "http://x/3", "Body C", [])
        conn.commit()

        assert db.article_exists(conn, "1") is True
        assert db.article_exists(conn, "999") is False

        all_articles = db.list_articles(conn)
        assert [a["nid"] for a in all_articles] == ["2", "1", "3"], \
            f"expected date-descending order, got {[a['nid'] for a in all_articles]}"
        assert set(all_articles[1]["hashtags"]) == {"tag1", "tag2"}, all_articles[1]
        assert all_articles[2]["hashtags"] == [], "untagged article must have an empty list, not null"

        tag2_articles = db.list_articles(conn, tag="tag2")
        assert [a["nid"] for a in tag2_articles] == ["2", "1"], tag2_articles

        year_2025_articles = db.list_articles(conn, year="2025")
        assert [a["nid"] for a in year_2025_articles] == ["2", "1"], year_2025_articles
        year_2024_articles = db.list_articles(conn, year="2024")
        assert [a["nid"] for a in year_2024_articles] == ["3"], year_2024_articles

        tag2_2025_articles = db.list_articles(conn, tag="tag2", year="2025")
        assert [a["nid"] for a in tag2_2025_articles] == ["2", "1"], tag2_2025_articles
        tag1_2025_articles = db.list_articles(conn, tag="tag1", year="2025")
        assert [a["nid"] for a in tag1_2025_articles] == ["1"], tag1_2025_articles
        tag1_2024_articles = db.list_articles(conn, tag="tag1", year="2024")
        assert tag1_2024_articles == [], \
            "tag+year combination must be an AND, not match an article satisfying only one"

        tags = db.list_tags(conn)
        tags_by_name = {t["tag"]: t["count"] for t in tags}
        assert tags_by_name == {"tag1": 1, "tag2": 2}, tags_by_name

        years = db.list_years(conn)
        assert years == ["2025", "2024"], years

        article = db.get_article(conn, "1")
        assert article["title"] == "Title A"
        assert article["body"] == "Body A"
        assert set(article["hashtags"]) == {"tag1", "tag2"}
        assert db.get_article(conn, "999") is None

        # prev/next are chronologically adjacent by (date, nid), not insertion order:
        # nid "1" is 2025-01-01, "2" is 2025-02-01, "3" is 2024-01-01
        article_1 = db.get_article(conn, "1")
        assert article_1["prev"] == {"nid": "3", "title": "Title C", "date": "2024-01-01"}, article_1["prev"]
        assert article_1["next"] == {"nid": "2", "title": "Title B", "date": "2025-02-01"}, article_1["next"]

        article_2 = db.get_article(conn, "2")  # most recent article has no next
        assert article_2["prev"]["nid"] == "1"
        assert article_2["next"] is None

        article_3 = db.get_article(conn, "3")  # oldest article has no prev
        assert article_3["prev"] is None
        assert article_3["next"]["nid"] == "1"

        # re-upserting an existing nid replaces its tag set rather than accumulating it
        db.upsert_article(conn, "1", "Title A (edited)", "2025-01-01", "http://x/1", "Body A edited", ["tag3"])
        conn.commit()
        article = db.get_article(conn, "1")
        assert article["title"] == "Title A (edited)"
        assert article["hashtags"] == ["tag3"], article["hashtags"]

        # get_vocab/save_vocab round trip
        assert db.get_vocab(conn, "1") is None
        terms = [{"term": "cabinet", "pos": "noun", "ipa": "/kab/", "zh": "內閣", "example": "x"}]
        db.save_vocab(conn, "1", terms, 3.5)
        assert db.get_vocab(conn, "1") == (terms, 3.5)
        # re-saving replaces rather than accumulating
        terms2 = [{"term": "veto", "pos": "noun", "ipa": "/v/", "zh": "否決", "example": "y"}]
        db.save_vocab(conn, "1", terms2, 1.2)
        assert db.get_vocab(conn, "1") == (terms2, 1.2)

        conn.close()
        print("OK: db.py schema and query helpers behave correctly")
    finally:
        if os.path.exists(path):
            os.remove(path)

    _check_vocab_cache_rename_migration()


def _check_vocab_cache_rename_migration():
    """db.connect() must transparently migrate a pre-rename DB (table still
    named vocab_cache, as this repo's articles.db and the deployed
    production DB were before the vocab_cache -> vocab rename) to the
    current schema, in both possible starting states: with and without
    the generated_in_seconds column (added in an earlier migration)."""
    for has_generated_in_seconds in (False, True):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(path)
        try:
            raw = sqlite3.connect(path)
            cols = "article_nid TEXT PRIMARY KEY, terms_json TEXT NOT NULL"
            if has_generated_in_seconds:
                cols += ", generated_in_seconds REAL"
            raw.execute(f"CREATE TABLE vocab_cache ({cols})")
            if has_generated_in_seconds:
                raw.execute(
                    "INSERT INTO vocab_cache VALUES (?, ?, ?)",
                    ("1", '[{"term": "cabinet"}]', 4.2),
                )
            else:
                raw.execute(
                    "INSERT INTO vocab_cache (article_nid, terms_json) VALUES (?, ?)",
                    ("1", '[{"term": "cabinet"}]'),
                )
            raw.commit()
            raw.close()

            conn = db.connect(path)
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert "vocab" in tables and "vocab_cache" not in tables, tables

            terms_json, generated_in_seconds = conn.execute(
                "SELECT terms_json, generated_in_seconds FROM vocab WHERE article_nid = '1'"
            ).fetchone()
            assert terms_json == '[{"term": "cabinet"}]', terms_json
            if has_generated_in_seconds:
                assert generated_in_seconds == 4.2, generated_in_seconds
            else:
                assert generated_in_seconds is None, generated_in_seconds

            conn.close()

            # connect() must also be idempotent — running the migration
            # again against an already-migrated DB shouldn't error.
            db.connect(path).close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    print("OK: db.connect() migrates a pre-rename vocab_cache table to vocab, with or without generated_in_seconds")


if __name__ == "__main__":
    main()
