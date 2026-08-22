# AGENTS.md

Notes for coding agents working in this repo. User-facing docs (features,
setup, running) live in [README.md](README.md) — this file is about
conventions and gotchas that aren't obvious from reading the code once.

## Architecture

SQLite (`articles.db`, checked into git — it's the single source of
truth, not gitignored) + FastAPI backend (`server.py`) + React frontend
(`frontend/`, Vite, `react-router-dom` `HashRouter`). `db.py` is the only
module that touches SQL; every other script/route goes through it.

Data pipeline: `migrate_to_sqlite.py` (one-time historical bootstrap,
rarely needed now that `articles.db` is checked in) and
`sync_articles.py` (incremental — stops at the first article `nid` it
already has) both reuse `download_am730_column.py`'s `post_page` /
`fetch_article_text` / retry logic rather than re-implementing HTTP
fetching.

## Conventions

- **Data layer stays stdlib-only.** `db.py`, `migrate_to_sqlite.py`,
  `sync_articles.py`, `download_am730_column.py` — no FastAPI/pydantic/etc
  imports there. The framework boundary is deliberate, not an oversight.
- **Frontend stays framework-minimal.** React + `react-router-dom` only —
  no state-management library, no UI kit, no CSS framework. Theming is
  plain CSS custom properties (`frontend/src/index.css`, `:root` /
  `:root[data-theme="dark"]`), not a CSS-in-JS solution.
- **`nid` is always a string**, end to end — schema (`TEXT PRIMARY KEY`),
  Pydantic models, route params, `useParams()`. Never coerce it to a
  number; two same-day articles could in principle collide if anything
  ever joined on date instead.
- **Every `checks/*.py` script needs this sys.path bootstrap** before its
  first repo-root import (`import db`, `import server`, etc.), so the
  literal `python3 checks/check_X.py` command works standalone:
  ```python
  import os, sys
  sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  ```
  Without it, Python only puts `checks/`'s own directory on `sys.path`,
  not the repo root — this bit every check script the first time it was
  written and cost a review round each time before the pattern was
  established.
- **No pytest.** Tests are plain scripts under `checks/` — `main()` with
  bare `assert`s, printing `OK: ...` on success, non-zero exit on
  failure. `check_db.py`/`check_migrate.py`/`check_sync.py` need only the
  system Python (stdlib); `check_server.py` needs the venv active
  (`source venv/bin/activate`) since it imports `server` → `fastapi`.

## Before claiming something works

- Run all four: `python3 checks/check_db.py checks/check_migrate.py
  checks/check_sync.py` and (venv active) `checks/check_server.py`.
- `cd frontend && npm run lint` — expect exactly the two
  `react(set-state-in-effect)` warnings in components that reset state at
  the top of a data-loading `useEffect` (`TagFilteredView.jsx`,
  `ArticleView.jsx`, and now `TagListView.jsx`); that pattern was
  reviewed and accepted, not a bug to fix.
- If verifying a change through the Docker image, **open a genuinely new
  browser tab**, not a reload of one that was already pointed at
  `localhost:8420`. A rebuilt image serving on the same URL does not
  reliably bust an already-open tab's cached JS bundle — even a forced
  reload can silently keep executing the old bundle. This cost a full
  debugging detour once already.

## Deployment

`Dockerfile` bakes `articles.db` into the image at build time (`COPY
articles.db .` — it must exist in the build context, which it does since
it's checked in). `docker-entrypoint.sh` backgrounds `sync_articles.py`
(catches up on anything published since the image was built) and `exec`s
`server.py` as the foreground process. `server.py`'s bind host reads a
`HOST` env var (default `127.0.0.1` for local/dev; the entrypoint sets
`HOST=0.0.0.0` since Docker's port mapping can't reach a loopback-only
bind). Port is 8420 everywhere in this project (not the more common 8000
— that port was already occupied by an unrelated process during
development; no need to reconcile if you see 8000 in a generic
FastAPI/Vite example elsewhere).
