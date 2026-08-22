# 施永青「C觀點」文章庫

A local website for browsing the am730 column archive: FastAPI + SQLite
backend, React frontend.

## Run with Docker

The simplest way to run it — no local Python/Node setup needed:

```bash
docker build -t cpoint .
docker run -p 8420:8420 cpoint
```

Open <http://localhost:8420/>. `articles.db` is checked into the repo and
baked into the image, so it works immediately; on startup the container
also runs `sync_articles.py` in the background to pull in anything
published since the image was built (see "Keeping it up to date" below —
same script, same stop-at-known-article behavior).

## First-time setup (without Docker)

From the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..
```

`articles.db` is checked into the repo, so no migration step is needed —
a fresh clone already has the full archive. `migrate_to_sqlite.py` only
matters if you're re-bootstrapping from a raw local scrape
(`articles_<year>/*.txt`) instead of using the checked-in database; if you
ever need to start from a completely empty database instead, run
`python3 sync_articles.py` — it walks the entire listing API from empty
and populates `articles.db` directly (slower, since it fetches every
article body over the network, but self-contained).

## Run it

```bash
source venv/bin/activate   # if not already active
python3 server.py
```

Open <http://localhost:8420/>.

## Keeping it up to date

New articles are published roughly daily. Run this any time to pull in
whatever's new — it stops as soon as it reaches an article already stored,
so it never re-walks the full archive:

```bash
python3 sync_articles.py
```

`server.py` reads `articles.db` live, so a sync takes effect immediately —
no restart needed.

## Development mode

For frontend changes with hot-reload, run two processes instead of the
built version above:

```bash
# terminal 1
source venv/bin/activate
uvicorn server:app --reload --port 8420

# terminal 2
cd frontend
npm run dev
```

Open <http://localhost:5173/> — Vite proxies `/api/*` requests to the
backend on port 8420. Re-run `npm run build` (Step 2 above) when you're
done, so `python3 server.py` alone serves the latest frontend again.
