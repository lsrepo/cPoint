#!/usr/bin/env python3
"""Verify the /api/article/{nid}/vocab route: cache-miss calls the LLM
exactly once, cache-hit skips it, LLM failure surfaces as a 502, and the
X-Vocab-Generated-In timing header is set on both a fresh generation and
a later cache hit (persisted alongside the cached terms, so real
visitors — who almost always hit a warm cache — still see how long the
original generation took). Also verifies /api/admin/vocab exports the
same cached rows, and does so even with ENGLISH_CORNER_ENABLED off (the
sync-vocab-cache pipeline should still be able to pull whatever's already
cached regardless of the feature flag). vocab.generate_vocab is
monkeypatched so this never hits the network."""
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
        first_timing = res.headers["X-Vocab-Generated-In"]

        res = client.get("/api/article/1/vocab")
        assert res.status_code == 200
        assert res.json() == fake_terms
        assert len(calls) == 1, "second request should hit the cache, not the LLM"
        assert res.headers.get("X-Vocab-Generated-In") == first_timing, (
            "cache hit should report the persisted original generation time"
        )

        res = client.get("/api/article/999/vocab")
        assert res.status_code == 404

        vocab.generate_vocab = failing_generate_vocab
        res = client.get("/api/article/2/vocab")
        assert res.status_code == 502, res.json()

        res = client.get("/api/admin/vocab")
        assert res.status_code == 200
        exported = res.json()
        assert len(exported) == 1, exported
        assert exported[0]["nid"] == "1" and exported[0]["terms"] == fake_terms, exported
        assert isinstance(exported[0]["generated_in_seconds"], float), exported
        assert round(exported[0]["generated_in_seconds"], 2) == float(first_timing), (
            exported[0]["generated_in_seconds"], first_timing,
        )

        real_enabled = server.ENGLISH_CORNER_ENABLED
        server.ENGLISH_CORNER_ENABLED = False
        try:
            assert client.get("/api/article/1/vocab").status_code == 404
            res = client.get("/api/admin/vocab")
            assert res.status_code == 200 and len(res.json()) == 1, (
                "export should stay available even with the feature flag off"
            )
        finally:
            server.ENGLISH_CORNER_ENABLED = real_enabled

        print(
            "OK: /api/article/{nid}/vocab caches LLM output and surfaces failures as 502; "
            "/api/admin/vocab exports cached rows regardless of the feature flag"
        )
    finally:
        vocab.generate_vocab = real_generate_vocab
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
