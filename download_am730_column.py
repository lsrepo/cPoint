#!/usr/bin/env python3
"""
Download all am730 columnist articles published in a given year.

Default target: 施永青's "C觀點" column
(https://www.am730.com.hk/columnist/28169/C觀點:%20施永青)

Uses only the Python standard library (no requests/bs4 needed).
"""
import argparse
import html
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SITE = "https://www.am730.com.hk"
DEFAULT_COLUMNIST_URL = SITE + "/columnist/28169/C%E8%A7%80%E9%BB%9E:%20%E6%96%BD%E6%B0%B8%E9%9D%92"

HKT = timezone(timedelta(hours=8))


def to_hkt_date(publish_date):
    """Convert an API publishDate (UTC ISO string) to a YYYY-MM-DD date in HKT."""
    dt = datetime.strptime(publish_date[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(HKT).strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}

MAX_RETRIES = 4
BACKOFF_BASE = 1.5
MAX_BACKOFF = 20.0


def _retry_after_seconds(http_error):
    val = http_error.headers.get("Retry-After") if http_error.headers else None
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def request_with_retry(req, max_retries=MAX_RETRIES):
    """Fetch `req`, retrying transient failures with exponential backoff.
    Honors a Retry-After header on 429/503 when the server sends one.
    Non-retryable HTTP errors (4xx other than 429) raise immediately.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            last_exc = e
            wait = _retry_after_seconds(e) or min(BACKOFF_BASE ** attempt, MAX_BACKOFF)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
            last_exc = e
            wait = min(BACKOFF_BASE ** attempt, MAX_BACKOFF)

        if attempt < max_retries:
            print(f"    retry {attempt + 1}/{max_retries} after {wait:.1f}s ({last_exc})", file=sys.stderr)
            time.sleep(wait)
    raise last_exc


def post_page(columnist_url, page, next_key, next_date):
    payload = urllib.parse.urlencode({
        "page": page,
        "nextPageKey": next_key,
        "nextPageDate": next_date,
    }).encode()
    req = urllib.request.Request(columnist_url, data=payload, headers=HEADERS, method="POST")
    body = request_with_retry(req)
    return json.loads(body)


def fetch_articles_for_year(columnist_url, year, delay):
    """Walk the columnist's cursor-paginated article feed (newest first)
    and collect every article whose publishDate falls in `year`. Stops
    as soon as an older year is seen, since results are date-descending.
    """
    articles = []
    page = 1
    next_key, next_date = "", ""
    while True:
        result = post_page(columnist_url, page, next_key, next_date)
        data = result.get("data", {})
        items = data.get("data", [])
        if not items:
            break

        stop = False
        for item in items:
            pub_date = item.get("publishDate", "")
            if not pub_date:
                continue
            year_str = to_hkt_date(pub_date)[:4]
            item_year = int(year_str)
            if item_year == year:
                articles.append(item)
            elif item_year < year:
                stop = True

        pagination = data.get("pagination") or {}
        if stop or not pagination.get("hasNextPage"):
            break

        cursor = pagination.get("nextPageCursor") or {}
        next_key = cursor.get("nextPageKey", "")
        next_date = cursor.get("nextPageDate", "")
        page += 1
        time.sleep(delay)

    return articles


def find_balanced_div(text, start):
    """`start` is the index right after an opening <div ...> tag's '>'.
    Returns (inner_html, index_right_after_the_matching_closing_tag).
    """
    depth = 1
    pos = start
    tag_re = re.compile(r"<div\b[^>]*>|</div>")
    while True:
        m = tag_re.search(text, pos)
        if not m:
            return text[start:], len(text)
        if m.group().startswith("<div"):
            depth += 1
        else:
            depth -= 1
        if depth == 0:
            return text[start:m.start()], m.end()
        pos = m.end()


def strip_div_class_blocks(text, class_name):
    """Remove every <div class="{class_name}...">...</div> block (e.g. ads)."""
    out = []
    pos = 0
    pattern = re.compile(r'<div class="' + re.escape(class_name) + r'(?:\s[^"]*)?"[^>]*>')
    while True:
        m = pattern.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        _, end = find_balanced_div(text, m.end())
        pos = end
    return "".join(out)


def strip_tag_blocks(text, tag):
    """Remove every <tag>...</tag> block (non-nesting tags like <figure>)."""
    out = []
    pos = 0
    open_re = re.compile(r"<" + tag + r"\b[^>]*>")
    close_re = re.compile(r"</" + tag + r">")
    while True:
        m = open_re.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        cm = close_re.search(text, m.end())
        pos = cm.end() if cm else m.end()
    return "".join(out)


def html_to_text(body_html):
    text = re.sub(r"(?i)<br\s*/?>", "\n", body_html)
    text = re.sub(r"(?i)</(p|div)>", "\n", text)
    text = re.sub(r"(?i)<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n\n".join(lines)


def extract_body_text(page):
    """Pull the article__body div out of a full page's HTML and turn it
    into plain text, stripping known ad-widget blocks first: `adbox`
    (banner ads) and `custom_content` (a native-ad widget whose visible
    "ADVERTISEMENT" label otherwise leaks into the extracted text)."""
    m = re.search(r'<div class="article__body"[^>]*>', page)
    if not m:
        return ""
    body_html, _ = find_balanced_div(page, m.end())
    body_html = strip_div_class_blocks(body_html, "adbox")
    body_html = strip_div_class_blocks(body_html, "custom_content")
    body_html = strip_tag_blocks(body_html, "figure")
    return html_to_text(body_html)


def fetch_article_text(relative_url):
    full_url = SITE + urllib.parse.quote(relative_url, safe="/:")
    req = urllib.request.Request(full_url, headers=HEADERS)
    page = request_with_retry(req).decode("utf-8", errors="replace")
    return extract_body_text(page)


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()[:100]


def find_empty_articles(out_dir):
    """Scan previously-saved .txt files for ones whose body came out empty
    (the fetch failed or the extraction found nothing) and return enough
    info from each file's header to re-fetch it."""
    targets = []
    if not os.path.isdir(out_dir):
        return targets
    for fname in sorted(os.listdir(out_dir)):
        if not fname.endswith(".txt"):
            continue
        path = os.path.join(out_dir, fname)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        if len(lines) < 4:
            continue
        title, pub_date, url = lines[0], lines[1], lines[2]
        body = "\n".join(lines[4:]).strip()
        if not body:
            targets.append((path, title, pub_date, url))
    return targets


def repair(out_dir, delay):
    targets = find_empty_articles(out_dir)
    print(f"Found {len(targets)} article(s) with empty bodies in {out_dir}/.", file=sys.stderr)
    fixed = 0
    for i, (path, title, pub_date, url) in enumerate(targets, 1):
        rel_url = url[len(SITE):] if url.startswith(SITE) else url
        print(f"[{i}/{len(targets)}] retrying {pub_date}  {title}", file=sys.stderr)
        try:
            body = fetch_article_text(rel_url)
        except Exception as e:
            print(f"    still failing: {e}", file=sys.stderr)
            continue
        if not body:
            print("    still empty after re-fetch", file=sys.stderr)
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{title}\n{pub_date}\n{url}\n\n")
            f.write(body)
        fixed += 1
        time.sleep(delay)
    print(f"Repaired {fixed}/{len(targets)} article(s).", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026, help="Year to download (default: 2026)")
    parser.add_argument("--columnist-url", default=DEFAULT_COLUMNIST_URL,
                         help="Columnist page URL (default: 施永青 C觀點)")
    parser.add_argument("--out", default=None, help="Output directory (default: articles_<year>)")
    parser.add_argument("--delay", type=float, default=0.4,
                         help="Delay in seconds between requests (default: 0.4)")
    parser.add_argument("--repair", action="store_true",
                         help="Re-fetch only articles already in --out that saved with an empty "
                              "body (failed last time), instead of re-downloading everything")
    args = parser.parse_args()

    out_dir = args.out or f"articles_{args.year}"
    os.makedirs(out_dir, exist_ok=True)

    if args.repair:
        repair(out_dir, args.delay)
        return

    print(f"Fetching article list for {args.year}...", file=sys.stderr)
    articles = fetch_articles_for_year(args.columnist_url, args.year, args.delay)
    articles.sort(key=lambda a: a.get("publishDate", ""))
    print(f"Found {len(articles)} articles in {args.year}.", file=sys.stderr)

    for i, item in enumerate(articles, 1):
        nid = item.get("nid")
        title = item.get("title", "")
        pub_date = to_hkt_date(item.get("publishDate", ""))
        rel_url = item.get("url", "")
        print(f"[{i}/{len(articles)}] {pub_date}  {title}", file=sys.stderr)

        try:
            body = fetch_article_text(rel_url)
        except Exception as e:
            print(f"    FAILED: {e}", file=sys.stderr)
            body = ""

        fname = f"{pub_date}_{nid}_{safe_filename(title)}.txt"
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{title}\n{pub_date}\n{SITE}{rel_url}\n\n")
            f.write(body)

        time.sleep(args.delay)

    print(f"Done. Saved {len(articles)} articles to {out_dir}/", file=sys.stderr)
    empty = find_empty_articles(out_dir)
    if empty:
        print(f"{len(empty)} article(s) saved with an empty body. Re-run with --repair to retry them.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
