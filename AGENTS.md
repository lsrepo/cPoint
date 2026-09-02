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

- Run all: `python3 checks/check_db.py checks/check_migrate.py
  checks/check_sync.py checks/check_sync_vocab.py` and (venv active)
  `checks/check_server.py checks/check_vocab.py
  checks/check_vocab_request.py checks/check_server_vocab.py`.
- `cd frontend && npm run lint` — expect exactly 7 warnings, all
  reviewed and accepted, not bugs to fix: 5 `react(set-state-in-effect)`
  in components that reset state at the top of a data-loading
  `useEffect` (`TagFilteredView.jsx`, `ArticleView.jsx`,
  `TagListView.jsx`, `CantoneseAudioPlayer.jsx`, `EnglishCorner.jsx`),
  plus `react(only-export-components)` in `RandomView.jsx` (shares a
  constant alongside the component) and `react(refs)` in
  `ArticleView.jsx` (`paragraphRefs.current = []` reset during render,
  so each paragraph can push itself in via its own ref callback — needed
  for the arrow-key paragraph-navigation feature). If the count or set
  of files changes, that's a real signal worth checking, not just
  updating this number.
- If verifying a change through the Docker image, **open a genuinely new
  browser tab**, not a reload of one that was already pointed at
  `localhost:8420`. A rebuilt image serving on the same URL does not
  reliably bust an already-open tab's cached JS bundle — even a forced
  reload can silently keep executing the old bundle. This cost a full
  debugging detour once already.

## English Corner (vocab generation)

`vocab.py` calls an OpenRouter model to extract vocab for
`/api/article/{nid}/vocab`, gated by `ENGLISH_CORNER_ENABLED` (env var,
default enabled) and stored per-article in the `db.vocab` table so each
article only ever triggers one LLM call. (Named `vocab`, not
`vocab_cache` — from the DB's own perspective it's just permanent rows
keyed by `article_nid`, no TTL or eviction; "cache" described the access
pattern, not what the table actually is.)

- **`OPENROUTER_MODEL` differs between local and production on purpose.**
  Local `.env` (gitignored) sets it to a free model
  (`nvidia/nemotron-3.5-lightning:free` as of this writing) so local dev
  doesn't spend the production API key's budget; Dokploy's production env
  has no `OPENROUTER_MODEL` set, so it falls back to `DEFAULT_MODEL`
  (`deepseek/deepseek-v4-flash-0731`). Don't be alarmed if local latency
  looks very different from production — it's a different model, not a
  regression. Production env vars live in Dokploy itself (dashboard, or
  its REST-ish API at `/api/<router>.<procedure>` with an `x-api-key`
  header) — not tracked in this repo.
- **Reasoning models can silently eat most of the latency budget.**
  `deepseek-v4-flash-0731` defaults to emitting a hidden "reasoning"
  scratchpad before its actual answer — one real trace measured 1882 of
  2348 completion tokens as pure reasoning, turning a ~2s task into 71s.
  `reasoning: {"enabled": false}` in the request payload fixes this for
  models that support disabling it. Some free-tier models (e.g.
  `minimax/minimax-m2.7:free`) reject that toggle outright with a 400
  "reasoning is mandatory" error, and can't have reasoning capped via
  `reasoning.max_tokens` either — they'll burn the entire `max_tokens`
  budget on reasoning and return empty content. `generate_vocab` handles
  this with a one-time retry (drop the toggle, raise the budget) on that
  specific 400.
- **OpenRouter load-balances one model across third-party providers with
  very different speeds** — one real trace saw 91 tok/s (Reka) vs 18 tok/s
  (Ambient) for the same model and similar output length. `provider:
  {"sort": "throughput"}` mitigates this but doesn't guarantee bounded
  latency (occasional outliers still land past 10s); the route's 10s
  timeout + existing "hide the section on any non-2xx" frontend behavior
  is the actual backstop, not a hard latency guarantee.
- **Testing vocab generation against the real local `articles.db` writes
  real rows into `db.vocab`** — and that file is checked into git, not
  gitignored (see Architecture above). Running `generate_vocab`/hitting
  `/vocab` locally during manual testing will leave a `git diff` on
  `articles.db`; run `git checkout -- articles.db` before committing if
  you don't want dev-model-generated rows in the repo's source-of-truth
  DB. (`db.connect()` also self-migrates the table on every call — even
  read-only testing that never generates anything can still touch the
  file if it's connecting to a pre-rename DB with the old `vocab_cache`
  name.)
- **On-demand generation, but durably persisted**: production's
  `articles.db` is baked into the Docker image (see Deployment below),
  so a `vocab` row generated for a real visitor only lives in that
  running container's writable layer and is wiped on the next redeploy.
  `sync_vocab.py` + `.github/workflows/sync-vocab-cache.yml` closes that
  gap — daily, it pulls everything currently cached from the live
  `/api/admin/vocab` export endpoint and merges it into the checked-in
  `articles.db`, same commit-and-push-if-changed pattern as
  `sync_articles.py`. This is still zero precomputation: nothing is ever
  generated except in direct response to an actual visitor hitting
  `/vocab`; the sync only persists what already happened. Scheduled 1h
  before the article sync (21:00 UTC vs 22:00 UTC) so the two workflows'
  commit-and-push steps never race each other on `articles.db`.
- **`cpoint.paklau.com` is Cloudflare-proxied**, and Cloudflare's Bot
  Fight Mode blocklists `urllib`'s default `Python-urllib/x.y`
  User-Agent with a bare 403 — this killed `sync-vocab-cache`'s first
  scheduled run in production. Confirmed narrow: it's that one exact
  signature, not a broad non-browser or GitHub-Actions-IP/ASN block —
  `curl`'s default UA and even `python-requests/...` both pass fine.
  `sync_vocab.py`'s `fetch_export` sets an explicit `User-Agent` for this
  reason; if a future script also calls `cpoint.paklau.com` from
  `urllib.request` directly (rather than through `download_am730_column.py`,
  which already sets a browser UA for the unrelated reason of not getting
  blocked by the *source* am730 site), it needs the same treatment.

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

**Daily sync → redeploy loop.** `.github/workflows/sync-articles.yml` runs
`sync_articles.py` on a schedule (06:00 HKT / 22:00 UTC cron, plus
`workflow_dispatch` for manual runs) and, only if `articles.db` actually
changed, commits and pushes it to `main` as `github-actions[bot]`. The
live deployment is on Dokploy with GitOps watching `main`, so that push is
what triggers the rebuild + redeploy — there's no separate deploy step or
webhook configured in this repo, Dokploy does it on its own by watching
the branch. This means `articles.db` in the deployed container is only as
fresh as the last successful push from this workflow, not continuously
live; the container itself does not re-sync while running (see
`docker-entrypoint.sh` above — sync only happens at container start).
`.github/workflows/sync-vocab-cache.yml` runs the same loop 1h earlier
(05:00 HKT / 21:00 UTC) for `sync_vocab.py`, so real-visitor-generated
`vocab` rows also persist across redeploys instead of being wiped every
time — see "English Corner (vocab generation)" above.
