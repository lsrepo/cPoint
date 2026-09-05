#!/usr/bin/env python3
"""One-time backfill: generate tags for articles that have none (mostly
2011-2016, where AM730's hashtag API evidently didn't cover that archived
content — see AGENTS.md). Not part of the regular sync pipeline; run
manually, review the git diff on articles.db, commit if it looks good.

Approach validated by experiment (100 already-tagged articles, real tags
hidden and compared against regeneration): show the LLM a candidate list
of existing tags (substring-matched, >=3 chars, in the article text) plus
the ~280 tags used >=10 times overall, and instruct it to prefer reusing
a candidate over inventing a new tag with similar meaning. This beat
free-generation-then-reconcile on precision/recall/F1 and, most
importantly, reuse rate (98.6% vs 71.1%) -- and beat showing the *entire*
tag vocabulary too (a shorter, pre-filtered candidate list outperforms
6826 mostly-irrelevant tags, both in quality and ~23x lower prompt cost).

Resumable: an article is skipped if it already has any tags, so a
partial run (rate limits, credits, Ctrl-C) can just be re-invoked.
"""
import argparse
import concurrent.futures
import json
import os
import sys
import time

import httpx
import opencc
from dotenv import load_dotenv

import db
import vocab

load_dotenv()

MODEL = os.environ.get("OPENROUTER_MODEL", vocab.DEFAULT_MODEL)
API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Prompt-only instructions to stay in Traditional Chinese aren't reliable —
# observed the model regenerate the exact same Simplified string (行政长官)
# even after adding an explicit "never Simplified" instruction. Converting
# every returned tag deterministically closes this regardless of model
# compliance. Must be s2hk (Hong Kong standard), not s2twp (Taiwan idiom) —
# s2twp also localizes vocabulary to Taiwan usage (互聯網 -> 網際網路,
# 大數據 -> 大資料), which would silently diverge from this publication's
# actual Hong Kong house style and from tags already in the vocabulary.
_S2T = opencc.OpenCC("s2hk")


def to_traditional(tag):
    return _S2T.convert(tag)

PROMPT = """You are tagging a Chinese-language (Traditional Chinese, Hong Kong) opinion column article with topic tags, in the same style as this publication's existing tagging system.

Article title: {title}

Article body:
{body}

Here is a list of tags that already exist in this publication's tag vocabulary and may be relevant to this article (some may not apply — use judgement):
{candidates}

Pick 5 to 10 tags for this article. Prefer reusing an existing tag from the list above whenever it genuinely fits, rather than inventing a new tag with a similar meaning. Only propose a new tag (not in the list) for a topic/entity the article covers that isn't already represented above.

Respond with ONLY a JSON object of this exact shape, no other text. Any new tag you propose must be written in Traditional Chinese (繁體中文), matching the article's own script — never Simplified Chinese:
{{"tags": ["tag1", "tag2", ...]}}
"""

TAG_SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
    "required": ["tags"],
    "additionalProperties": False,
}


class TagError(Exception):
    pass


def candidate_tags(title, body, all_tags, frequent_tags):
    text = title + body
    substring_hits = {t for t in all_tags if len(t) >= 3 and t in text}
    return sorted(substring_hits | frequent_tags)


def generate_tags(title, body, all_tags, frequent_tags):
    candidates = candidate_tags(title, body, all_tags, frequent_tags)
    prompt = PROMPT.format(title=title, body=body, candidates="、".join(candidates))
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 1200,
        "reasoning": {"enabled": False},
        "provider": {"sort": "throughput"},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "tags", "strict": True, "schema": TAG_SCHEMA},
        },
    }
    last_err = None
    for attempt in range(3):
        try:
            res = httpx.post(
                vocab.OPENROUTER_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                json=payload,
                timeout=30,
            )
            if res.status_code == 400 and "reasoning is mandatory" in res.text.lower():
                payload = dict(payload)
                del payload["reasoning"]
                payload["max_tokens"] = 4000
                res = httpx.post(
                    vocab.OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json=payload,
                    timeout=90,
                )
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            tags = [
                to_traditional(str(t).strip())
                for t in json.loads(content).get("tags", [])
                if str(t).strip()
            ]
            if tags:
                return tags, len(candidates)
            last_err = f"empty tags: {content!r}"
        except Exception as e:
            last_err = str(e)
        time.sleep(2 * (attempt + 1))
    raise TagError(last_err)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="process at most N articles")
    parser.add_argument("--nids", nargs="*", default=None, help="process only these specific nids")
    parser.add_argument("--nids-file", default=None, help="path to a file of whitespace-separated nids")
    parser.add_argument("--workers", type=int, default=3, help="concurrent LLM requests")
    args = parser.parse_args()
    if args.nids_file:
        with open(args.nids_file) as f:
            args.nids = f.read().split()

    if not API_KEY:
        sys.exit("OPENROUTER_API_KEY not configured")

    conn = db.connect(db.DB_PATH)
    all_tags = [r[0] for r in conn.execute("SELECT name FROM tags").fetchall()]
    frequent_tags = {r[0] for r in conn.execute(
        "SELECT t.name FROM tags t JOIN article_tags at ON at.tag_id=t.id "
        "GROUP BY t.id HAVING count(*) >= 10"
    ).fetchall()}
    print(f"model={MODEL}  total tags={len(all_tags)}  frequent(>=10)={len(frequent_tags)}")

    if args.nids:
        nids = args.nids
    else:
        rows = conn.execute(
            "SELECT nid FROM articles a "
            "WHERE NOT EXISTS (SELECT 1 FROM article_tags at WHERE at.article_nid = a.nid) "
            "ORDER BY date"
        ).fetchall()
        nids = [r[0] for r in rows]
        if args.limit:
            nids = nids[: args.limit]

    # Resumable: skip anything that already has tags (e.g. a prior partial
    # run, or an explicit --nids list that includes already-done articles).
    articles = []
    skipped = 0
    for nid in nids:
        row = conn.execute("SELECT title, body FROM articles WHERE nid=?", (nid,)).fetchone()
        if row is None:
            print(f"  WARNING: nid={nid} not found in articles table, skipping")
            continue
        has_tags = conn.execute("SELECT 1 FROM article_tags WHERE article_nid=?", (nid,)).fetchone()
        if has_tags:
            skipped += 1
            continue
        title, body = row
        articles.append((nid, title, body))
    print(f"processing {len(articles)} article(s) ({skipped} already tagged, skipped)")

    done = failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(generate_tags, title, body, all_tags, frequent_tags): (nid, title)
            for nid, title, body in articles
        }
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            nid, title = futures[fut]
            try:
                tags, n_candidates = fut.result()
            except TagError as e:
                print(f"  [{i}/{len(articles)}] FAILED nid={nid} {title!r}: {e}")
                failed += 1
                continue
            db.set_tags(conn, nid, tags)
            for t in tags:
                if t not in all_tags:
                    all_tags.append(t)
            print(f"  [{i}/{len(articles)}] nid={nid} {title!r} -> {tags} (from {n_candidates} candidates)")
            done += 1

    conn.close()
    print(f"\nDone: {done} tagged, {failed} failed, {skipped} already done.")


if __name__ == "__main__":
    main()
