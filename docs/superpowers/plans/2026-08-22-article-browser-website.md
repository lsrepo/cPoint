# Article Browser Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local website, backed by SQLite and served by FastAPI, to browse the growing archive of am730 column articles by date and by hashtag, with a React frontend and cheap incremental updates as new articles are published daily.

**Architecture:** A SQLite database (`articles.db`) stores every article (`nid`, title, date, url, body) plus a `tags`/`article_tags` join table. A one-time migration script (`migrate_to_sqlite.py`) imports the already-downloaded `articles_<year>/*.txt` bodies, joined by `nid` against a fresh walk of the listing API for hashtags. An incremental sync script (`sync_articles.py`) walks the same listing API newest-first and stops as soon as it reaches an `nid` already in the database. A FastAPI backend (`server.py`) exposes `/api/tags`, `/api/articles`, `/api/articles?tag=`, `/api/article/{nid}`, and serves the built React frontend as static files. The React app (`frontend/`, built with Vite, routed with `react-router-dom`'s `HashRouter`) renders the same four views as before — by-date, tag list, tag-filtered, article detail — each fetching from the API on demand.

**Tech Stack:** Backend: Python 3, FastAPI, Uvicorn, installed into a project-local virtual environment. Data layer (`db.py`, `migrate_to_sqlite.py`, `sync_articles.py`) stays standard-library-only (`sqlite3`, `urllib`) — the framework switch applies to the HTTP/UI layers only. Frontend: React 19 + Vite, `react-router-dom` for routing, plain CSS (no component library).

**Spec:** [docs/superpowers/specs/2026-08-22-article-browser-website.md](../specs/2026-08-22-article-browser-website.md)

## Global Constraints

- Data layer (`db.py`, `migrate_to_sqlite.py`, `sync_articles.py`) uses only the Python standard library — no FastAPI/React dependency belongs there (spec NFR2).
- Backend dependencies (`fastapi`, `uvicorn`, `httpx` for testing) are installed into a project-local virtual environment via `requirements.txt`, never system-wide (spec NFR2; this machine's Python is externally managed and refuses global `pip install`).
- Migration and sync both join on `nid`, never on publish date (spec "Unique Identifier").
- Migration must be idempotent; sync must stop at the first already-known `nid` and never re-walk the full archive (spec NFR3/NFR4).
- Articles with no hashtags (2011–2016) must remain browsable by date but must never appear in a tag-filtered result, and must render without error (spec FR6).
- The deliverable is one command, `python3 server.py`, after the frontend has been built once with `npm run build`; a separate two-process dev mode (Vite + Uvicorn) is expected during development, not a spec violation (spec FR8/NFR5).

---

## File Structure

- **Create:** `db.py` — SQLite schema and query/write helpers. Shared by every backend script.
- **Create:** `migrate_to_sqlite.py` — one-time bootstrap from local `.txt` bodies + a fresh listing-API walk for hashtags.
- **Create:** `sync_articles.py` — incremental daily sync, stops at the first known `nid`.
- **Create:** `requirements.txt` — `fastapi`, `uvicorn[standard]`, `httpx` (the last only for the FastAPI `TestClient` used in tests).
- **Create:** `server.py` — FastAPI app: Pydantic response models, `/api/*` routes backed by `db.py`, static mount of `frontend/dist` for the built frontend.
- **Create:** `frontend/` — Vite + React app: `src/App.jsx` (HashRouter + routes), `src/api.js` (fetch helpers), `src/index.css`, `src/components/{DateView,TagListView,TagFilteredView,ArticleView}.jsx`.
- **Create:** `checks/check_db.py`, `checks/check_migrate.py`, `checks/check_sync.py` — data-layer tests (stdlib only, no FastAPI dependency, run with the system Python).
- **Create:** `checks/check_server.py` — FastAPI route tests using `TestClient` (needs the virtual environment active).
- **Create:** `README.md` — setup, run, and dev-mode instructions (folded into Task 9).
- **Create:** `.gitignore` — excludes `articles.db`, `venv/`, `__pycache__/`, `frontend/node_modules/`, `frontend/dist/`.

---

### Task 1: SQLite schema and query helpers

**Files:**
- Create: `db.py`
- Test: `checks/check_db.py`

**Interfaces:**
- Consumes: nothing (foundation for every other task).
- Produces: `DB_PATH = "articles.db"`; `connect(db_path=DB_PATH) -> sqlite3.Connection`; `upsert_article(conn, nid: str, title: str, date: str, url: str, body: str, hashtags: list[str])`; `article_exists(conn, nid: str) -> bool`; `list_articles(conn, tag: str | None = None) -> list[dict]` (`{nid, title, date, hashtags}`, date-descending); `list_tags(conn) -> list[dict]` (`{tag, count}`, count-descending); `get_article(conn, nid: str) -> dict | None` (`{nid, title, date, url, hashtags, body}`). Every later task imports these with exactly these signatures.

- [ ] **Step 1: Write the failing check**

Create `checks/check_db.py`:

```python
#!/usr/bin/env python3
"""Verify db.py's schema and query helpers, using an isolated temporary
database. No network access, fully deterministic."""
import os
import tempfile

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

        tags = db.list_tags(conn)
        tags_by_name = {t["tag"]: t["count"] for t in tags}
        assert tags_by_name == {"tag1": 1, "tag2": 2}, tags_by_name

        article = db.get_article(conn, "1")
        assert article["title"] == "Title A"
        assert article["body"] == "Body A"
        assert set(article["hashtags"]) == {"tag1", "tag2"}
        assert db.get_article(conn, "999") is None

        # re-upserting an existing nid replaces its tag set rather than accumulating it
        db.upsert_article(conn, "1", "Title A (edited)", "2025-01-01", "http://x/1", "Body A edited", ["tag3"])
        conn.commit()
        article = db.get_article(conn, "1")
        assert article["title"] == "Title A (edited)"
        assert article["hashtags"] == ["tag3"], article["hashtags"]

        conn.close()
        print("OK: db.py schema and query helpers behave correctly")
    finally:
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 checks/check_db.py`
Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Write `db.py`**

```python
#!/usr/bin/env python3
"""SQLite schema and query helpers for the article database. Shared by
migrate_to_sqlite.py, sync_articles.py, and server.py."""
import sqlite3

DB_PATH = "articles.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    nid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    url TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS article_tags (
    article_nid TEXT NOT NULL REFERENCES articles(nid),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (article_nid, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);
"""

TAGS_SUBQUERY = """
    (SELECT GROUP_CONCAT(t2.name, ';') FROM article_tags at2
     JOIN tags t2 ON t2.id = at2.tag_id WHERE at2.article_nid = a.nid)
"""


def connect(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_article(conn, nid, title, date, url, body, hashtags):
    conn.execute(
        "INSERT INTO articles (nid, title, date, url, body) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(nid) DO UPDATE SET title=excluded.title, date=excluded.date, "
        "url=excluded.url, body=excluded.body",
        (nid, title, date, url, body),
    )
    conn.execute("DELETE FROM article_tags WHERE article_nid = ?", (nid,))
    for tag in hashtags:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
        conn.execute(
            "INSERT OR IGNORE INTO article_tags (article_nid, tag_id) VALUES (?, ?)",
            (nid, row[0]),
        )


def article_exists(conn, nid):
    return conn.execute("SELECT 1 FROM articles WHERE nid = ?", (nid,)).fetchone() is not None


def _row_to_summary(row):
    nid, title, date, tags = row
    return {"nid": nid, "title": title, "date": date, "hashtags": tags.split(";") if tags else []}


def list_articles(conn, tag=None):
    if tag:
        query = f"""
            SELECT a.nid, a.title, a.date, {TAGS_SUBQUERY} AS tags
            FROM articles a
            JOIN article_tags at ON at.article_nid = a.nid
            JOIN tags t ON t.id = at.tag_id
            WHERE t.name = ?
            ORDER BY a.date DESC
        """
        rows = conn.execute(query, (tag,)).fetchall()
    else:
        query = f"""
            SELECT a.nid, a.title, a.date, {TAGS_SUBQUERY} AS tags
            FROM articles a
            ORDER BY a.date DESC
        """
        rows = conn.execute(query).fetchall()
    return [_row_to_summary(row) for row in rows]


def list_tags(conn):
    rows = conn.execute(
        "SELECT t.name, COUNT(*) AS n FROM tags t "
        "JOIN article_tags at ON at.tag_id = t.id "
        "GROUP BY t.name ORDER BY n DESC"
    ).fetchall()
    return [{"tag": name, "count": n} for name, n in rows]


def get_article(conn, nid):
    row = conn.execute(
        "SELECT nid, title, date, url, body FROM articles WHERE nid = ?", (nid,)
    ).fetchone()
    if row is None:
        return None
    nid, title, date, url, body = row
    tags = [r[0] for r in conn.execute(
        "SELECT t.name FROM tags t JOIN article_tags at ON at.tag_id = t.id "
        "WHERE at.article_nid = ?", (nid,)
    ).fetchall()]
    return {"nid": nid, "title": title, "date": date, "url": url, "hashtags": tags, "body": body}
```

- [ ] **Step 4: Run the check to confirm it passes**

Run: `python3 checks/check_db.py`
Expected: `OK: db.py schema and query helpers behave correctly`

- [ ] **Step 5: Commit**

```bash
git add db.py checks/check_db.py
git commit -m "feat: add SQLite schema and query helpers for the article database"
```

---

### Task 2: One-time migration into SQLite

**Files:**
- Create: `migrate_to_sqlite.py`
- Test: `checks/check_migrate.py`

**Interfaces:**
- Consumes: `db.connect`, `db.upsert_article` (Task 1). Consumes `dl.post_page(columnist_url, page, next_key, next_date)` and `dl.DEFAULT_COLUMNIST_URL` from `download_am730_column.py` (already has retry/backoff built in). Consumes `articles_<year>/*.txt` files named `<date>_<nid>_<title>.txt`, first 3 lines `title`/`date`/`url`, blank line, then body.
- Produces: a populated `articles.db`. `sync_articles.py` (Task 3) does not depend on this script — only on `db.py` and `download_am730_column.py`.

- [ ] **Step 1: Write the failing check**

Create `checks/check_migrate.py`:

```python
#!/usr/bin/env python3
"""Verify articles.db after migrate_to_sqlite.py has been run for real
against the local archive and the live listing API."""
import db


def main():
    conn = db.connect(db.DB_PATH)
    articles = db.list_articles(conn)
    assert len(articles) > 3800, f"expected >3800 migrated articles, got {len(articles)}"

    dates = [a["date"] for a in articles]
    assert dates == sorted(dates, reverse=True), "list_articles must return date-descending order"

    tagged = [a for a in articles if a["hashtags"]]
    assert len(tagged) > 2000, f"expected >2000 tagged articles, got {len(tagged)}"

    pre_2017 = [a for a in articles if a["date"] < "2016-11-01"]
    assert pre_2017, "expected pre-2017 articles to exist"
    assert all(not a["hashtags"] for a in pre_2017), \
        "articles from before tagging began should have empty hashtags"

    sample = db.get_article(conn, articles[0]["nid"])
    assert sample is not None
    assert sample["body"].strip(), "sample article body must not be empty"
    conn.close()

    print(f"OK: {len(articles)} articles migrated, {len(tagged)} tagged, "
          f"sample article {articles[0]['nid']} OK")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 checks/check_migrate.py`
Expected: `sqlite3.OperationalError: no such table: articles` (or a FileNotFoundError — `articles.db` doesn't exist yet).

- [ ] **Step 3: Write `migrate_to_sqlite.py`**

```python
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
```

- [ ] **Step 4: Run the migration**

Run: `python3 migrate_to_sqlite.py`
This walks the ~962-page listing (roughly 6–8 minutes) and writes `articles.db`.
Expected: `Migrated 3848 articles into articles.db (0 listing entries had no local body on disk)`.

- [ ] **Step 5: Run the check to confirm it passes**

Run: `python3 checks/check_migrate.py`
Expected: `OK: 3848 articles migrated, 2401 tagged, sample article <nid> OK`

- [ ] **Step 6: Commit**

```bash
git add migrate_to_sqlite.py checks/check_migrate.py
git commit -m "feat: add one-time SQLite migration from the downloaded archive"
```

(Do not commit `articles.db` — see Task 9's `.gitignore` step.)

---

### Task 3: Incremental daily sync

**Files:**
- Create: `sync_articles.py`
- Test: `checks/check_sync.py`

**Interfaces:**
- Consumes: `db.connect`, `db.article_exists`, `db.upsert_article` (Task 1). Consumes `dl.post_page`, `dl.fetch_article_text`, `dl.SITE`, `dl.DEFAULT_COLUMNIST_URL` from `download_am730_column.py`.
- Produces: `sync(columnist_url: str, db_path: str, delay: float) -> int` (count of newly inserted articles) — called by `python3 sync_articles.py` and exercised in Task 9's final verification.

- [ ] **Step 1: Write the failing check**

Create `checks/check_sync.py`:

```python
#!/usr/bin/env python3
"""Verify sync_articles.sync() inserts only genuinely new articles and
stops at the first already-known nid — using a fake in-memory listing API
so this test needs no network access."""
import os
import tempfile

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
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 checks/check_sync.py`
Expected: `ModuleNotFoundError: No module named 'sync_articles'`

- [ ] **Step 3: Write `sync_articles.py`**

```python
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
```

- [ ] **Step 4: Run the check to confirm it passes**

Run: `python3 checks/check_sync.py`
Expected: `OK: sync stops at the first already-known nid and inserts only genuinely new articles`

- [ ] **Step 5: Run it for real**

Run: `python3 sync_articles.py`
Expected: `Sync complete: 0 new article(s) added.` (or a small positive number if new articles were published since Task 2's migration) — either way, well under a minute.

- [ ] **Step 6: Commit**

```bash
git add sync_articles.py checks/check_sync.py
git commit -m "feat: add incremental daily sync that stops at the first known article"
```

---

### Task 4: FastAPI backend

**Files:**
- Create: `requirements.txt`
- Create: `server.py`
- Test: `checks/check_server.py`

**Interfaces:**
- Consumes: `db.connect`, `db.list_articles`, `db.list_tags`, `db.get_article` (Task 1).
- Produces: `app` (the FastAPI instance) and `DB_PATH` (module global, overridable by tests before making requests), both consumed directly by `checks/check_server.py`. Produces the HTTP contract every view in Tasks 6–8 relies on: `GET /api/articles` → `[{nid, title, date, hashtags}, ...]`; `GET /api/articles?tag=<name>` → same shape, filtered; `GET /api/tags` → `[{tag, count}, ...]`; `GET /api/article/{nid}` → `{nid, title, date, url, hashtags, body}` or 404.

- [ ] **Step 1: Write `requirements.txt`**

```
fastapi>=0.115
uvicorn[standard]>=0.34
httpx>=0.27
```

(`httpx` is only needed for `fastapi.testclient.TestClient` in `checks/check_server.py` — FastAPI's test client is built on it.)

- [ ] **Step 2: Create the virtual environment and install**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Every command from this task onward that touches `server.py` (or anything importing `fastapi`) must run with `venv` activated. Tasks 1–3 do not need it — `db.py`, `migrate_to_sqlite.py`, and `sync_articles.py` stay on the system Python.

- [ ] **Step 3: Write the failing check**

Create `checks/check_server.py`:

```python
#!/usr/bin/env python3
"""Verify server.py's FastAPI routes against a seeded temporary database,
using FastAPI's TestClient (in-process, no real socket or process needed)."""
import os
import tempfile

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
```

- [ ] **Step 4: Run it to confirm it fails**

Run: `python3 checks/check_server.py` (with `venv` active)
Expected: `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 5: Write `server.py`**

```python
#!/usr/bin/env python3
"""FastAPI backend: JSON API backed by articles.db, plus a static mount
for the built React frontend (frontend/dist, once it exists)."""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db

DB_PATH = db.DB_PATH
FRONTEND_DIST = os.path.join("frontend", "dist")

app = FastAPI(title="施永青「C觀點」文章庫 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["GET"],
    allow_headers=["*"],
)


class ArticleSummary(BaseModel):
    nid: str
    title: str
    date: str
    hashtags: list[str]


class ArticleDetail(ArticleSummary):
    url: str
    body: str


class TagCount(BaseModel):
    tag: str
    count: int


@app.get("/api/articles", response_model=list[ArticleSummary])
def get_articles(tag: str | None = None):
    conn = db.connect(DB_PATH)
    try:
        return db.list_articles(conn, tag=tag)
    finally:
        conn.close()


@app.get("/api/tags", response_model=list[TagCount])
def get_tags():
    conn = db.connect(DB_PATH)
    try:
        return db.list_tags(conn)
    finally:
        conn.close()


@app.get("/api/article/{nid}", response_model=ArticleDetail)
def get_article(nid: str):
    conn = db.connect(DB_PATH)
    try:
        article = db.get_article(conn, nid)
    finally:
        conn.close()
    if article is None:
        raise HTTPException(status_code=404, detail="not found")
    return article


# Mounted last so it never shadows the /api/* routes above; only present
# once `npm run build` (Task 9) has produced frontend/dist.
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 6: Run the check to confirm it passes**

Run: `python3 checks/check_server.py` (with `venv` active)
Expected: `OK: FastAPI routes serve the JSON API correctly`

- [ ] **Step 7: Commit**

```bash
git add requirements.txt server.py checks/check_server.py
git commit -m "feat: add FastAPI backend with JSON API"
```

(Do not commit `venv/` — see Task 9's `.gitignore` step.)

---

### Task 5: Scaffold the React frontend and routing shell

**Files:**
- Create: `frontend/` (via `npm create vite@latest frontend -- --template react`)
- Create/Modify: `frontend/src/App.jsx`, `frontend/src/main.jsx`, `frontend/src/index.css`, `frontend/vite.config.js`
- Create: `frontend/src/api.js`

**Interfaces:**
- Consumes: nothing yet (routes render placeholders; Tasks 6–8 fill them in). The Vite dev proxy consumes `server.py` (Task 4) running on port 8000.
- Produces: `getArticles(tag?)`, `getTags()`, `getArticle(nid)` in `frontend/src/api.js` — the only functions Tasks 6–8's components import for data fetching. Produces the `<Routes>` skeleton in `App.jsx` with paths `/date`, `/tags`, `/tag/:tag`, `/article/:nid` that Tasks 6–8 swap from `<Placeholder />` to real components.

- [ ] **Step 1: Scaffold the project**

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install react-router-dom
```

- [ ] **Step 2: Configure the dev proxy**

Replace `frontend/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 3: Write `frontend/src/api.js`**

```javascript
export async function getArticles(tag) {
  const url = tag ? `/api/articles?tag=${encodeURIComponent(tag)}` : "/api/articles";
  const res = await fetch(url);
  return res.json();
}

export async function getTags() {
  const res = await fetch("/api/tags");
  return res.json();
}

export async function getArticle(nid) {
  const res = await fetch(`/api/article/${nid}`);
  if (!res.ok) return null;
  return res.json();
}
```

- [ ] **Step 4: Replace `frontend/src/index.css`**

(Delete the Vite template's `frontend/src/App.css` — it isn't imported anymore.)

```css
:root {
  --bg: #fafafa;
  --fg: #222;
  --accent: #2350a9;
  --muted: #666;
  --border: #ddd;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Microsoft JhengHei", sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.6;
}
header {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: #fff;
}
.site-title { margin: 0 0 .5rem; font-size: 1.2rem; }
nav a {
  margin-right: 1rem;
  color: var(--accent);
  text-decoration: none;
  font-weight: 600;
}
nav a:hover { text-decoration: underline; }
main { max-width: 720px; margin: 0 auto; padding: 1.5rem; }
details { margin-bottom: .5rem; border: 1px solid var(--border); border-radius: 6px; background: #fff; }
summary { padding: .6rem 1rem; cursor: pointer; font-weight: 600; }
details ul { margin: 0; padding: .5rem 1rem 1rem 2rem; }
ul { padding-left: 1.5rem; }
li { margin-bottom: .3rem; }
a { color: var(--accent); }
.tag-filter { width: 100%; padding: .5rem; margin-bottom: 1rem; border: 1px solid var(--border); border-radius: 4px; font-size: 1rem; }
.meta { color: var(--muted); font-size: .9rem; }
.tags { margin: .5rem 0 1.5rem; }
.tag {
  display: inline-block;
  background: #eef2fb;
  color: var(--accent);
  border-radius: 12px;
  padding: .15rem .6rem;
  margin: 0 .3rem .3rem 0;
  font-size: .85rem;
  text-decoration: none;
}
.tag:hover { background: #dde6f8; }
```

- [ ] **Step 5: Write `frontend/src/App.jsx`**

```jsx
import { HashRouter, Routes, Route, Navigate, Link } from "react-router-dom";
import "./index.css";

function Placeholder() {
  return <p>此檢視尚未實作。</p>;
}

export default function App() {
  return (
    <HashRouter>
      <header>
        <h1 className="site-title">施永青「C觀點」文章庫</h1>
        <nav>
          <Link to="/date">依日期</Link>
          <Link to="/tags">依標籤</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/date" replace />} />
          <Route path="/date" element={<Placeholder />} />
          <Route path="/tags" element={<Placeholder />} />
          <Route path="/tag/:tag" element={<Placeholder />} />
          <Route path="/article/:nid" element={<Placeholder />} />
        </Routes>
      </main>
    </HashRouter>
  );
}
```

- [ ] **Step 6: Confirm `frontend/src/main.jsx` renders `App`**

The default Vite React template already does this — open `frontend/src/main.jsx` and confirm it matches:

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

If it still imports `./App.css` or renders the Vite/React logo counter template, replace it with the version above.

- [ ] **Step 7: Verify in a browser**

Start both processes (two terminals):
```bash
# terminal 1, repo root, venv active
python3 server.py
```
```bash
# terminal 2
cd frontend
npm run dev
```
Open `http://localhost:5173/`. Expected: the header "施永青「C觀點」文章庫" and nav links render; clicking "依日期" or "依標籤" changes the URL to `#/date` / `#/tags` and shows "此檢視尚未實作。" (since the real views don't exist until Tasks 6–8). Stop both processes after checking.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/index.html frontend/src
git commit -m "feat: scaffold React frontend with routing shell"
```

---

### Task 6: By-date view

**Files:**
- Create: `frontend/src/components/DateView.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `getArticles()` (Task 5's `api.js`), `GET /api/articles` (Task 4).
- Produces: `DateView` component, wired into `App.jsx`'s `/date` route. No new shared state — Tasks 7–8 each fetch independently.

- [ ] **Step 1: Write `frontend/src/components/DateView.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getArticles } from "../api";

function groupByYear(articles) {
  const groups = new Map();
  for (const a of articles) {
    const year = a.date.slice(0, 4);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(a);
  }
  return Array.from(groups.entries()).sort((a, b) => b[0].localeCompare(a[0]));
}

export default function DateView() {
  const [articles, setArticles] = useState(null);

  useEffect(() => {
    getArticles().then(setArticles);
  }, []);

  if (articles === null) return <p>載入中...</p>;

  const groups = groupByYear(articles);
  const currentYear = groups.length ? groups[0][0] : "";

  return (
    <>
      <h1>依日期瀏覽</h1>
      {groups.map(([year, arts]) => (
        <details key={year} open={year === currentYear}>
          <summary>{year}（{arts.length}）</summary>
          <ul>
            {arts.map((a) => (
              <li key={a.nid}>
                <Link to={`/article/${a.nid}`}>{a.date} — {a.title}</Link>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </>
  );
}
```

- [ ] **Step 2: Wire it into `App.jsx`**

Add the import and swap the route:

```jsx
import DateView from "./components/DateView";
```

```jsx
<Route path="/date" element={<DateView />} />
```

- [ ] **Step 3: Verify in a browser**

With both `python3 server.py` and `npm run dev` running, open `http://localhost:5173/#/date`.
Expected: a `<details>` block per year (most recent expanded, showing its count), each row a clickable date + title link. Confirm 2011 is present (collapsed). Stop both processes after checking.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/DateView.jsx
git commit -m "feat: add by-date view"
```

---

### Task 7: Tag list and tag-filtered views

**Files:**
- Create: `frontend/src/components/TagListView.jsx`
- Create: `frontend/src/components/TagFilteredView.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `getTags()`, `getArticles(tag)` (Task 5's `api.js`); `GET /api/tags`, `GET /api/articles?tag=` (Task 4); `useParams()` from `react-router-dom` for the `:tag` route param.
- Produces: `TagListView` and `TagFilteredView`, wired into `App.jsx`'s `/tags` and `/tag/:tag` routes.

- [ ] **Step 1: Write `frontend/src/components/TagListView.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTags } from "../api";

export default function TagListView() {
  const [tags, setTags] = useState(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getTags().then(setTags);
  }, []);

  if (tags === null) return <p>載入中...</p>;

  const filtered = tags.filter((t) => t.tag.includes(query));

  return (
    <>
      <h1>依標籤瀏覽</h1>
      <input
        className="tag-filter"
        type="text"
        placeholder="搜尋標籤..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <p>共 {tags.length} 個標籤</p>
      <ul>
        {filtered.map(({ tag, count }) => (
          <li key={tag}>
            <Link to={`/tag/${encodeURIComponent(tag)}`}>{tag}</Link>（{count}）
          </li>
        ))}
      </ul>
    </>
  );
}
```

- [ ] **Step 2: Write `frontend/src/components/TagFilteredView.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getArticles } from "../api";

export default function TagFilteredView() {
  const { tag } = useParams();
  const [articles, setArticles] = useState(null);

  useEffect(() => {
    setArticles(null);
    getArticles(tag).then(setArticles);
  }, [tag]);

  if (articles === null) return <p>載入中...</p>;

  return (
    <>
      <h1>標籤：{tag}（{articles.length} 篇）</h1>
      <p><Link to="/tags">&laquo; 返回標籤列表</Link></p>
      <ul>
        {articles.map((a) => (
          <li key={a.nid}>
            <Link to={`/article/${a.nid}`}>{a.date} — {a.title}</Link>
          </li>
        ))}
      </ul>
    </>
  );
}
```

(`tag` from `useParams()` is already URL-decoded by react-router, and `getArticles` re-encodes it via `encodeURIComponent` when building the fetch URL — no double-encoding.)

- [ ] **Step 3: Wire both into `App.jsx`**

```jsx
import TagListView from "./components/TagListView";
import TagFilteredView from "./components/TagFilteredView";
```

```jsx
<Route path="/tags" element={<TagListView />} />
<Route path="/tag/:tag" element={<TagFilteredView />} />
```

- [ ] **Step 4: Verify in a browser**

With both processes running, open `http://localhost:5173/#/tags`.
Expected: a search box, a tag count, tags sorted by frequency descending (特朗普 near the top). Type into the search box, confirm live filtering. Click a tag, confirm the URL becomes `#/tag/<name>` and the list shows only matching articles, most recent first, with a "« 返回標籤列表" link back. Stop both processes after checking.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/TagListView.jsx frontend/src/components/TagFilteredView.jsx
git commit -m "feat: add tag list and tag-filtered views"
```

---

### Task 8: Article detail view

**Files:**
- Create: `frontend/src/components/ArticleView.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `getArticle(nid)` (Task 5's `api.js`); `GET /api/article/{nid}` (Task 4); `useParams()` for the `:nid` route param.
- Produces: `ArticleView`, wired into `App.jsx`'s `/article/:nid` route. Nothing later depends on this task.

- [ ] **Step 1: Write `frontend/src/components/ArticleView.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getArticle } from "../api";

export default function ArticleView() {
  const { nid } = useParams();
  const [article, setArticle] = useState(undefined);

  useEffect(() => {
    setArticle(undefined);
    getArticle(nid).then(setArticle);
  }, [nid]);

  if (article === undefined) return <p>載入中...</p>;
  if (article === null) return <p>找不到文章。</p>;

  return (
    <>
      <p><Link to="/date">&laquo; 返回文章列表</Link></p>
      <h1>{article.title}</h1>
      <p className="meta">
        {article.date} ·{" "}
        <a href={article.url} target="_blank" rel="noopener noreferrer">原文連結</a>
      </p>
      <p className="tags">
        {article.hashtags.map((t) => (
          <Link key={t} className="tag" to={`/tag/${encodeURIComponent(t)}`}>{t}</Link>
        ))}
      </p>
      {article.body.split("\n\n").map((para, i) => (
        <p key={i}>{para}</p>
      ))}
    </>
  );
}
```

(No manual HTML-escaping utility is needed here, unlike the earlier vanilla-JS design — JSX escapes all interpolated text content by default.)

- [ ] **Step 2: Wire it into `App.jsx`**

```jsx
import ArticleView from "./components/ArticleView";
```

```jsx
<Route path="/article/:nid" element={<ArticleView />} />
```

- [ ] **Step 3: Verify in a browser**

With both processes running, open `#/date`, click any article link.
Expected: title, date, a working "原文連結" link opening the original am730 article in a new tab, clickable tag pills (post-2017 article) or an empty tags row with no error (pre-2017 article), body rendered as separate paragraphs. Click a tag pill, confirm it navigates to that tag's filtered view. Click "« 返回文章列表", confirm it returns to the date view. Stop both processes after checking.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/ArticleView.jsx
git commit -m "feat: add article detail view"
```

---

### Task 9: Production build, full verification, run instructions, and .gitignore

**Files:**
- Create: `README.md`
- Create: `.gitignore`

**Interfaces:**
- Consumes: everything from Tasks 1–8, exercised together as a single deployable unit for the first time (`python3 server.py` alone, no separate Vite dev server).
- Produces: nothing consumed by other tasks — final verification gate and documentation.

- [ ] **Step 1: Write `.gitignore`**

```
articles.db
venv/
__pycache__/
*.pyc
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 2: Build the frontend**

```bash
cd frontend
npm run build
cd ..
```

This produces `frontend/dist/`, which `server.py`'s `StaticFiles` mount (Task 4) picks up automatically on next start.

- [ ] **Step 3: Write `README.md`**

```markdown
# 施永青「C觀點」文章庫

A local website for browsing the am730 column archive: FastAPI + SQLite
backend, React frontend.

## First-time setup

From the repository root:

\`\`\`bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 migrate_to_sqlite.py   # one-time: import articles_<year>/*.txt into articles.db

cd frontend
npm install
npm run build
cd ..
\`\`\`

## Run it

\`\`\`bash
source venv/bin/activate   # if not already active
python3 server.py
\`\`\`

Open <http://localhost:8000/>.

## Keeping it up to date

New articles are published roughly daily. Run this any time to pull in
whatever's new — it stops as soon as it reaches an article already stored,
so it never re-walks the full archive:

\`\`\`bash
python3 sync_articles.py
\`\`\`

`server.py` reads `articles.db` live, so a sync takes effect immediately —
no restart needed.

## Development mode

For frontend changes with hot-reload, run two processes instead of the
built version above:

\`\`\`bash
# terminal 1
source venv/bin/activate
uvicorn server:app --reload --port 8000

# terminal 2
cd frontend
npm run dev
\`\`\`

Open <http://localhost:5173/> — Vite proxies `/api/*` requests to the
backend on port 8000. Re-run `npm run build` (Step 2 above) when you're
done, so `python3 server.py` alone serves the latest frontend again.
```

- [ ] **Step 4: Run every backend check in order**

Run, in order (with `venv` active for the last one):
1. `python3 checks/check_db.py` → expect `OK: ...`
2. `python3 checks/check_migrate.py` → expect `OK: ...` (re-verifies the `articles.db` from Task 2)
3. `python3 checks/check_sync.py` → expect `OK: ...`
4. `python3 checks/check_server.py` → expect `OK: ...`

All four must pass with no assertion errors.

- [ ] **Step 5: Manual final walkthrough of the built, single-command deliverable**

```bash
source venv/bin/activate
python3 server.py
```

Open `http://localhost:8000/` (no separate Vite process this time — confirming the `StaticFiles` mount serves the build from Step 2). Walk through: `#/date` → expand a past year → open an article → click one of its tags → confirm the filtered list is correct → open another article from there → "« 返回文章列表". Stop the server after checking.

- [ ] **Step 6: Commit**

```bash
git add .gitignore README.md
git commit -m "docs: add run instructions and ignore generated/build artifacts"
```

---

## Self-Review Notes

- **Spec coverage:** FR1/FR2 → Task 6 + Task 8. FR3/FR4 → Task 7. FR5 → Task 8's tag pills linking into Task 7's tag view. FR6 → `checks/check_db.py` and `checks/check_migrate.py` assert pre-2017 articles have empty `hashtags`; `list_articles(conn, tag=...)`'s inner join structurally cannot match a tagless article. FR7/FR8 → `server.py`'s `StaticFiles` mount (Task 4) plus Task 9's build step and `README.md`. FR9/NFR4 → `sync_articles.py`'s stop-at-known-`nid` logic (Task 3), verified without touching the network in `checks/check_sync.py`. NFR1 → migration reads local `.txt` bodies rather than re-downloading (Task 2). NFR2 → data layer stays stdlib-only (Global Constraint); FastAPI/Uvicorn/httpx confined to `requirements.txt` and a project-local `venv/`; React/Vite/react-router-dom confined to `frontend/`. NFR3 → `db.upsert_article`'s `ON CONFLICT DO UPDATE` (Task 1), used unchanged by both migration and sync. NFR5 → Task 5–8's verification steps explicitly run the two-process dev setup; Task 9 explicitly re-verifies the single-command built version separately.
- **Placeholder scan:** every step has literal, runnable code and exact commands; no "TBD"/"similar to Task N" placeholders remain.
- **Type/name consistency:** `nid` is a string end-to-end — `str(item.get("nid"))` at both ingestion points (Tasks 2, 3), `TEXT PRIMARY KEY` in the schema (Task 1), `nid: str` in FastAPI's `ArticleSummary`/`get_article(nid: str)` (Task 4), and the route param `nid` passed straight through by `useParams()` in React (Task 8) without ever being parsed as a number. `db.py`'s five functions are defined once (Task 1) and only ever called, never redefined, by Tasks 2–4. `frontend/src/api.js`'s three functions (`getArticles`, `getTags`, `getArticle`) are defined once (Task 5) and imported, never redefined, by Tasks 6–8.
