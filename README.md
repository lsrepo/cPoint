# 施永青「C觀點」文章庫

A local website for browsing the am730 column archive: FastAPI + SQLite
backend, React frontend.

## First-time setup

From the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 migrate_to_sqlite.py   # one-time: import articles_<year>/*.txt into articles.db

cd frontend
npm install
npm run build
cd ..
```

`migrate_to_sqlite.py` is a one-time historical bootstrap: it requires the
original downloader's output directories (`articles_<year>/*.txt`) to
already exist locally, and only fetches hashtag metadata over the network
— it does not download article bodies itself. If those directories don't
exist (e.g. a fresh clone with no prior scrape), skip it and run
`python3 sync_articles.py` instead — it walks the entire listing API from
an empty database and populates `articles.db` directly. That's slower
(it fetches every article body over the network) but self-contained.

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
