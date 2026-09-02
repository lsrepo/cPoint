#!/usr/bin/env python3
"""SQLite schema and query helpers for the article database. Shared by
migrate_to_sqlite.py, sync_articles.py, and server.py."""
import json
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
CREATE TABLE IF NOT EXISTS vocab (
    article_nid TEXT PRIMARY KEY REFERENCES articles(nid),
    terms_json TEXT NOT NULL,
    generated_in_seconds REAL
);
"""

TAGS_SUBQUERY = """
    (SELECT GROUP_CONCAT(t2.name, ';') FROM article_tags at2
     JOIN tags t2 ON t2.id = at2.tag_id WHERE at2.article_nid = a.nid)
"""


def connect(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate_vocab_cache_table_rename(conn)
    conn.executescript(SCHEMA)
    _migrate_vocab_generated_in_seconds(conn)
    return conn


def _migrate_vocab_cache_table_rename(conn):
    # Must run before executescript(SCHEMA) below: SCHEMA's CREATE TABLE IF
    # NOT EXISTS vocab would otherwise create a fresh empty `vocab` table
    # first, and ALTER TABLE ... RENAME TO then fails because the target
    # name is already taken. Existing DBs (this repo's checked-in
    # articles.db, and the deployed production DB) predate this rename —
    # it was originally named vocab_cache, which in hindsight described the
    # access pattern (avoid recomputing an LLM call) rather than what it
    # actually is from the DB's own perspective: just a table of rows, no
    # TTL or eviction, keyed by article_nid.
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "vocab_cache" in tables and "vocab" not in tables:
        conn.execute("ALTER TABLE vocab_cache RENAME TO vocab")
        conn.commit()


def _migrate_vocab_generated_in_seconds(conn):
    # SCHEMA's CREATE TABLE IF NOT EXISTS only applies to brand-new DBs;
    # some existing `vocab` tables (freshly renamed from vocab_cache above,
    # on a DB from before generated_in_seconds was added) predate this
    # column.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(vocab)")}
    if "generated_in_seconds" not in cols:
        conn.execute("ALTER TABLE vocab ADD COLUMN generated_in_seconds REAL")
        conn.commit()


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


def list_articles(conn, tag=None, year=None):
    joins = ""
    where = []
    params = []
    if tag:
        joins = "JOIN article_tags at ON at.article_nid = a.nid JOIN tags t ON t.id = at.tag_id"
        where.append("t.name = ?")
        params.append(tag)
    if year:
        where.append("substr(a.date, 1, 4) = ?")
        params.append(year)
    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    query = f"""
        SELECT a.nid, a.title, a.date, {TAGS_SUBQUERY} AS tags
        FROM articles a
        {joins}
        {where_clause}
        ORDER BY a.date DESC
    """
    rows = conn.execute(query, params).fetchall()
    return [_row_to_summary(row) for row in rows]


def list_tags(conn, year=None):
    if year:
        rows = conn.execute(
            "SELECT t.name, COUNT(*) AS n FROM tags t "
            "JOIN article_tags at ON at.tag_id = t.id "
            "JOIN articles a ON a.nid = at.article_nid "
            "WHERE substr(a.date, 1, 4) = ? "
            "GROUP BY t.name ORDER BY n DESC",
            (year,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.name, COUNT(*) AS n FROM tags t "
            "JOIN article_tags at ON at.tag_id = t.id "
            "GROUP BY t.name ORDER BY n DESC"
        ).fetchall()
    return [{"tag": name, "count": n} for name, n in rows]


def list_years(conn):
    rows = conn.execute(
        "SELECT DISTINCT substr(date, 1, 4) AS year FROM articles ORDER BY year DESC"
    ).fetchall()
    return [r[0] for r in rows]


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
    prev_row = conn.execute(
        "SELECT nid, title, date FROM articles WHERE (date, nid) < (?, ?) "
        "ORDER BY date DESC, nid DESC LIMIT 1",
        (date, nid),
    ).fetchone()
    next_row = conn.execute(
        "SELECT nid, title, date FROM articles WHERE (date, nid) > (?, ?) "
        "ORDER BY date ASC, nid ASC LIMIT 1",
        (date, nid),
    ).fetchone()
    prev = {"nid": prev_row[0], "title": prev_row[1], "date": prev_row[2]} if prev_row else None
    next_ = {"nid": next_row[0], "title": next_row[1], "date": next_row[2]} if next_row else None
    return {
        "nid": nid, "title": title, "date": date, "url": url,
        "hashtags": tags, "body": body, "prev": prev, "next": next_,
    }


def get_vocab(conn, nid):
    row = conn.execute(
        "SELECT terms_json, generated_in_seconds FROM vocab WHERE article_nid = ?", (nid,)
    ).fetchone()
    if row is None:
        return None
    terms_json, generated_in_seconds = row
    return json.loads(terms_json), generated_in_seconds


def save_vocab(conn, nid, terms, generated_in_seconds):
    conn.execute(
        "INSERT INTO vocab (article_nid, terms_json, generated_in_seconds) VALUES (?, ?, ?) "
        "ON CONFLICT(article_nid) DO UPDATE SET "
        "terms_json = excluded.terms_json, generated_in_seconds = excluded.generated_in_seconds",
        (nid, json.dumps(terms, ensure_ascii=False), generated_in_seconds),
    )
    conn.commit()
