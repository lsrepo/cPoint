#!/usr/bin/env python3
"""Warm the last 5 days' Cantonese/Mandarin read-aloud audio on the live
production site, so a 7:30am HKT visitor never hits tts.py's cold-generation
latency (a minute or more per article, see server.py's /audio endpoint).
Hits production's own /api/article/{nid}/audio/{lang} endpoint -- the same
one real visitors hit -- purely to trigger generation + caching in that
container's writable layer. This never touches articles.db directly, so
unlike sync_vocab.py there is nothing to commit back: the cache lives only
in the running container and is re-warmed by this script every morning
regardless of whether a redeploy wiped it since yesterday."""
import datetime
import json
import sys
import urllib.request

DEFAULT_BASE_URL = "https://cpoint.paklau.com"
LANGS = ("cmn", "yue")
DAYS = 5

# See sync_vocab.py: Cloudflare's Bot Fight Mode blocklists urllib's
# default "Python-urllib/x.y" User-Agent specifically.
USER_AGENT = "cPoint-tts-pregenerate/1.0 (+https://github.com/lsrepo/cPoint)"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def warm(base_url, nid, lang):
    url = f"{base_url}/api/article/{nid}/audio/{lang}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # Cold generation of a full article can take over a minute (tts.py
    # synthesizes the whole body in one call) -- give it plenty of room.
    with urllib.request.urlopen(req, timeout=240) as res:
        return res.status, len(res.read())


def recent_articles(base_url, days):
    articles = fetch_json(f"{base_url}/api/articles")
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return [a for a in articles if a["date"] >= cutoff]


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    articles = recent_articles(base_url, DAYS)

    warmed = 0
    for article in articles:
        for lang in LANGS:
            try:
                status, size = warm(base_url, article["nid"], lang)
                print(f"nid={article['nid']} lang={lang} status={status} bytes={size}")
                warmed += 1
            except Exception as e:
                print(f"nid={article['nid']} lang={lang} FAILED: {e}")
    print(f"Warmed {warmed}/{len(articles) * len(LANGS)} article/lang pair(s).")


if __name__ == "__main__":
    main()
