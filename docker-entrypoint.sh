#!/bin/sh
set -e

# Fetch anything published since the image was built. Runs in the
# background so it never delays the server becoming reachable; it stops
# as soon as it reaches an article already in articles.db, so this is
# fast even when there's little or nothing new.
python3 sync_articles.py &

exec python3 server.py
