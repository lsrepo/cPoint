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


# Mounted last so it never shadows the /api/* routes above; only present
# once `npm run build` (Task 9) has produced frontend/dist.
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=8420)
