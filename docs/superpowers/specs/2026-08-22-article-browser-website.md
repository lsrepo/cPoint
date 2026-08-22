# Article Browser Website — Requirements

## Background

`download_am730_column.py` has downloaded all 3,848 articles (2011–2026) from
施永青's "C觀點" am730 column into `articles_<year>/*.txt` (one file per
article: title, date, source URL, then body text). Hashtags are only
populated by the site from late 2016 onward — 2011–2016 articles (~1,447 of
them) have no hashtags at all.

The user wants a simple local website to browse this archive two ways. Since
new articles are published roughly daily, the storage layer needs to support
cheap incremental updates rather than a full rebuild every time — so this
revision moves from a static-JSON design to a SQLite database queried live
by a small local Python backend.

## Functional Requirements

- **FR1 — Browse by date.** List all articles sorted by publish date (most
  recent first), grouped by year so the list is navigable rather than one
  flat 3,848-row list.
- **FR2 — Read an article.** Selecting an article from any list view opens
  its full content: title, date, link to the original am730 URL, and body
  text.
- **FR3 — Browse tags.** List all distinct hashtags that appear on at least
  one article, each showing how many articles carry it.
- **FR4 — Filter by tag.** Selecting a tag shows only the articles carrying
  that tag, sorted by date (most recent first).
- **FR5 — Navigate from a filtered view.** From the tag-filtered list, the
  user can open any article the same way as from the date view (FR2).
- **FR6 — Untagged articles stay visible but unfilterable.** The ~1,447
  articles from 2011–2016 with no hashtags must still appear in the by-date
  view. They must never appear in a tag-filtered result (since they carry no
  tags) and must not break tag-list rendering (empty tag arrays, not nulls).
- **FR7 — Local backend, SQLite-backed.** A local Python backend (FastAPI)
  serves a JSON API backed by a SQLite database (`articles.db`), and serves
  the built frontend. No third-party hosting, no external services —
  everything runs on localhost.
- **FR8 — Runnable with one command, after a one-time build.** Once the
  frontend has been built (`npm run build`), the user starts the whole site
  with one command (`python3 server.py`) and opens the given localhost URL.
  Rebuilding the frontend is only needed again if its source changes.
- **FR9 — Incremental daily growth.** New articles are published roughly
  daily. Adding them must not require re-downloading or reprocessing
  articles already stored — only genuinely new articles are fetched.

## Non-Functional Requirements

- **NFR1 — Reuse existing data.** The one-time migration into SQLite reuses
  the already-downloaded `articles_<year>/*.txt` bodies. Do not re-download
  bodies that are already on disk.
- **NFR2 — Minimal, deliberate dependencies.** Backend: Python + FastAPI +
  Uvicorn, installed into a project-local virtual environment (`requirements.txt`).
  Frontend: React, built with Vite, routed with `react-router-dom`. Data
  layer (`db.py`, `migrate_to_sqlite.py`, `sync_articles.py`) stays on the
  Python standard library only — the framework switch applies to the HTTP
  and UI layers, not the ingestion/storage layer, which has no reason to
  change.
- **NFR3 — Idempotent migration.** The one-time migration script is safe to
  re-run (e.g. `INSERT ... ON CONFLICT DO UPDATE`) without creating
  duplicates or erroring on rows that already exist.
- **NFR4 — Incremental sync.** The ongoing sync process walks the listing
  API newest-first and stops as soon as it reaches an article `nid` already
  present in the database — it never re-fetches or re-walks the full
  archive to pick up new articles.
- **NFR5 — Dev/prod split is expected.** During development the frontend
  (`npm run dev`, Vite on port 5173) and backend (`uvicorn server:app
  --reload`, port 8000) run as two processes, with Vite proxying `/api/*`
  to the backend. This is normal for a React+FastAPI stack and is not a
  violation of FR8, which describes the built/deliverable state.

## Unique Identifier

Every article has a stable, reliable id: the site's own `nid` (e.g. the
`2009330` in `2026-08-20_2009330_...txt`), present both in the already
-downloaded filenames and in the live listing API's JSON (`item["nid"]`).
Migration and sync both join on `nid` — not on publish date — since two
articles landing on the same date (however rare for this column) would
silently collide under a date-based join. `articles_metadata.csv` (built
earlier for hashtag frequency analysis) is not part of this pipeline; the
listing API is queried directly for hashtags during both migration and sync.

## Out of Scope

- Full-text search across article bodies.
- Multi-select tag filtering (AND/OR across tags) — one tag at a time only.
- Authentication, comments, or any write operations.
- Automatic scheduling of `sync_articles.py` (e.g. cron) — it's run
  manually or wired up externally; this plan only builds the script itself.
- Deployment/hosting beyond localhost.
- Styling beyond basic readability (no responsive/mobile design pass).
