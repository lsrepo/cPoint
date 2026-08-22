#!/usr/bin/env python3
"""Verify articles.db after migrate_to_sqlite.py has been run for real
against the local archive and the live listing API."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def main():
    conn = db.connect(db.DB_PATH)
    articles = db.list_articles(conn)
    assert len(articles) > 3800, f"expected >3800 migrated articles, got {len(articles)}"

    dates = [a["date"] for a in articles]
    assert dates == sorted(dates, reverse=True), "list_articles must return date-descending order"

    tagged = [a for a in articles if a["hashtags"]]
    assert len(tagged) > 2000, f"expected >2000 tagged articles, got {len(tagged)}"

    pre_2017 = [a for a in articles if a["date"] < "2016-11-01"]
    assert pre_2017, "expected pre-2017 articles to exist"
    assert all(not a["hashtags"] for a in pre_2017), \
        "articles from before tagging began should have empty hashtags"

    sample = db.get_article(conn, articles[0]["nid"])
    assert sample is not None
    assert sample["body"].strip(), "sample article body must not be empty"
    conn.close()

    print(f"OK: {len(articles)} articles migrated, {len(tagged)} tagged, "
          f"sample article {articles[0]['nid']} OK")


if __name__ == "__main__":
    main()
