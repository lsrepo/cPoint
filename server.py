#!/usr/bin/env python3
"""FastAPI backend: JSON API backed by articles.db, plus a static mount
for the built React frontend (frontend/dist, once it exists)."""
import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import vocab

load_dotenv()

logger = logging.getLogger("uvicorn.error")

DB_PATH = db.DB_PATH
FRONTEND_DIST = os.path.join("frontend", "dist")
ENGLISH_CORNER_ENABLED = os.environ.get("ENGLISH_CORNER_ENABLED", "true").lower() not in ("false", "0", "")

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


class AdjacentArticle(BaseModel):
    nid: str
    title: str
    date: str


class ArticleDetail(ArticleSummary):
    url: str
    body: str
    prev: AdjacentArticle | None = None
    next: AdjacentArticle | None = None


class TagCount(BaseModel):
    tag: str
    count: int


class VocabTerm(BaseModel):
    term: str
    pos: str
    ipa: str
    zh: str
    example: str


@app.get("/api/articles", response_model=list[ArticleSummary])
def get_articles(tag: str | None = None, year: str | None = None):
    conn = db.connect(DB_PATH)
    try:
        return db.list_articles(conn, tag=tag, year=year)
    finally:
        conn.close()


@app.get("/api/tags", response_model=list[TagCount])
def get_tags(year: str | None = None):
    conn = db.connect(DB_PATH)
    try:
        return db.list_tags(conn, year=year)
    finally:
        conn.close()


@app.get("/api/years", response_model=list[str])
def get_years():
    conn = db.connect(DB_PATH)
    try:
        return db.list_years(conn)
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


@app.get("/api/article/{nid}/vocab", response_model=list[VocabTerm])
def get_article_vocab(nid: str):
    if not ENGLISH_CORNER_ENABLED:
        raise HTTPException(status_code=404, detail="English Corner disabled")

    start = time.monotonic()
    conn = db.connect(DB_PATH)
    try:
        article = db.get_article(conn, nid)
        if article is None:
            raise HTTPException(status_code=404, detail="not found")

        cached = db.get_vocab_cache(conn, nid)
        if cached is not None:
            logger.info("vocab nid=%s cache_hit latency=%.3fs", nid, time.monotonic() - start)
            return cached

        try:
            terms = vocab.generate_vocab(article["title"], article["body"])
        except vocab.VocabError as e:
            logger.warning(
                "vocab nid=%s generation_failed latency=%.3fs error=%s",
                nid, time.monotonic() - start, e,
            )
            raise HTTPException(status_code=502, detail=str(e)) from e

        logger.info(
            "vocab nid=%s generated latency=%.3fs terms=%d",
            nid, time.monotonic() - start, len(terms),
        )
        db.save_vocab_cache(conn, nid, terms)
        return terms
    finally:
        conn.close()


# Mounted last so it never shadows the /api/* routes above; only present
# once `npm run build` (Task 9) has produced frontend/dist.
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=8420)
