#!/usr/bin/env python3
"""Regression test for the ADVERTISEMENT-suffix bug: am730 embeds a
native-ad widget (`<div class="custom_content">`) at the end of every
article body, containing a visible "ADVERTISEMENT" label. The existing
ad-stripping only removed `adbox` blocks, so the label text leaked into
every scraped article. This verifies both ad-block classes are stripped
before html_to_text runs."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import download_am730_column as dl

# Trimmed down from a real am730 article page, keeping the structure
# fetch_article_text actually parses: a full page with an
# <div class="article__body"> containing both known ad-widget shapes.
SAMPLE_PAGE_HTML = """
<html><body>
<div class="article__body" itemprop="articleBody">
<p>正文第一段。</p>
<div class="adbox foo"><p>banner ad text</p></div>
<p>正文第二段。</p>
<div class="custom_content"><div id='ABB-20260107M'><p style='color: #8a9299;'>ADVERTISEMENT</p><h3 style='text-align: center;'></h3><p style='text-align:center'><a href='https://www.google.com/preferences/source' target='_blank'><img alt='ad' src='https://cdn3.am730.com.hk/media/ad.jpg' /></a></p></div></div>
</div><!--/.article__body-->
</body></html>
"""


def main():
    text = dl.extract_body_text(SAMPLE_PAGE_HTML)
    assert "ADVERTISEMENT" not in text, f"ADVERTISEMENT leaked into text: {text!r}"
    assert "banner ad text" not in text, f"adbox content leaked into text: {text!r}"
    assert "正文第一段" in text and "正文第二段" in text, f"real content missing: {text!r}"
    print("OK: adbox and custom_content ad blocks are stripped from article body")


if __name__ == "__main__":
    main()
