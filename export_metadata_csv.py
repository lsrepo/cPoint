#!/usr/bin/env python3
"""
Export publishDate, title, and hashtags for every article on the columnist
page into a single CSV. Metadata-only (no article bodies fetched), so this
is a single continuous walk through the paginated listing API.
"""
import argparse
import csv
import sys
import time

import download_am730_column as dl


def fetch_all_articles(columnist_url, delay):
    articles = []
    page = 1
    next_key, next_date = "", ""
    while True:
        result = dl.post_page(columnist_url, page, next_key, next_date)
        data = result.get("data", {})
        items = data.get("data", [])
        if not items:
            break
        articles.extend(items)

        pagination = data.get("pagination") or {}
        total_pages = pagination.get("totalPages")
        if page == 1 or page % 50 == 0:
            print(f"  page {page}/{total_pages}  ({len(articles)} articles so far)", file=sys.stderr)

        if not pagination.get("hasNextPage"):
            break
        cursor = pagination.get("nextPageCursor") or {}
        next_key = cursor.get("nextPageKey", "")
        next_date = cursor.get("nextPageDate", "")
        page += 1
        time.sleep(delay)
    return articles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--columnist-url", default=dl.DEFAULT_COLUMNIST_URL,
                         help="Columnist page URL (default: 施永青 C觀點)")
    parser.add_argument("--out", default="articles_metadata.csv", help="Output CSV path")
    parser.add_argument("--delay", type=float, default=0.4,
                         help="Delay in seconds between requests (default: 0.4)")
    args = parser.parse_args()

    print("Fetching full article list...", file=sys.stderr)
    articles = fetch_all_articles(args.columnist_url, args.delay)
    articles.sort(key=lambda a: a.get("publishDate", ""))
    print(f"Fetched {len(articles)} articles total.", file=sys.stderr)

    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["publishDate", "title", "hashtags"])
        writer.writeheader()
        for item in articles:
            writer.writerow({
                "publishDate": item.get("publishDate", ""),
                "title": item.get("title", ""),
                "hashtags": ";".join(item.get("hashtags", [])),
            })

    print(f"Wrote {len(articles)} rows to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
