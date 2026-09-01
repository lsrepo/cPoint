#!/usr/bin/env python3
"""Verify the /api/article/{nid}/vocab route: cache-miss calls the LLM
exactly once, cache-hit skips it, LLM failure surfaces as a 502, and the
X-Vocab-Generated-In timing header is set only on a fresh generation, not
on a cache hit. vocab.generate_vocab is monkeypatched so this never hits
the network."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import db
import server
import vocab


def main():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)

    conn = db.connect(path)
    db.upsert_article(conn, "1", "Title A", "2025-01-02", "http://x/1", "Body A", [])
    db.upsert_article(conn, "2", "Title B", "2025-01-01", "http://x/2", "Body B", [])
    conn.commit()
    conn.close()

    server.DB_PATH = path
    client = TestClient(server.app)

    calls = []
    fake_terms = [{"term": "cabinet", "pos": "noun", "ipa": "/kab/", "zh": "內閣", "example": "x"}]
    real_generate_vocab = vocab.generate_vocab

    def fake_generate_vocab(title, body):
        calls.append((title, body))
        return fake_terms

    def failing_generate_vocab(title, body):
        raise vocab.VocabError("boom")

    try:
        vocab.generate_vocab = fake_generate_vocab

        res = client.get("/api/article/1/vocab")
        assert res.status_code == 200
        assert res.json() == fake_terms, res.json()
        assert len(calls) == 1, calls
        assert "X-Vocab-Generated-In" in res.headers, "fresh generation should report timing"

        res = client.get("/api/article/1/vocab")
        assert res.status_code == 200
        assert res.json() == fake_terms
        assert len(calls) == 1, "second request should hit the cache, not the LLM"
        assert "X-Vocab-Generated-In" not in res.headers, "cache hit should not report timing"

        res = client.get("/api/article/999/vocab")
        assert res.status_code == 404

        vocab.generate_vocab = failing_generate_vocab
        res = client.get("/api/article/2/vocab")
        assert res.status_code == 502, res.json()

        print("OK: /api/article/{nid}/vocab caches LLM output and surfaces failures as 502")
    finally:
        vocab.generate_vocab = real_generate_vocab
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
