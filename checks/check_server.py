#!/usr/bin/env python3
"""Verify server.py's FastAPI routes against a seeded temporary database,
using FastAPI's TestClient (in-process, no real socket or process needed)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import db
import server


def main():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)

    conn = db.connect(path)
    db.upsert_article(conn, "1", "Title A", "2025-01-02", "http://x/1", "Body A", ["樓市"])
    db.upsert_article(conn, "2", "Title B", "2025-01-01", "http://x/2", "Body B", ["樓市", "美國"])
    conn.commit()
    conn.close()

    server.DB_PATH = path
    client = TestClient(server.app)

    try:
        res = client.get("/api/articles")
        assert res.status_code == 200
        articles = res.json()
        assert [a["nid"] for a in articles] == ["1", "2"], articles

        res = client.get("/api/articles", params={"tag": "樓市"})
        assert res.status_code == 200
        assert [a["nid"] for a in res.json()] == ["1", "2"]

        res = client.get("/api/tags")
        assert res.status_code == 200
        tags = {t["tag"]: t["count"] for t in res.json()}
        assert tags == {"樓市": 2, "美國": 1}, tags

        res = client.get("/api/article/1")
        assert res.status_code == 200
        article = res.json()
        assert article["title"] == "Title A"
        assert article["body"] == "Body A"

        res = client.get("/api/article/999")
        assert res.status_code == 404

        print("OK: FastAPI routes serve the JSON API correctly")
    finally:
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
