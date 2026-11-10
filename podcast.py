#!/usr/bin/env python3
"""RSS 2.0 + iTunes podcast feed for the Cantonese column read-aloud.

The XML is generated from podcast_episodes rows (see db.py). Enclosure
bytes live on R2; this module never touches object storage."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.etree import ElementTree as ET

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
HKT = timezone(timedelta(hours=8))

CHANNEL_TITLE = "施永青「C觀點」"
CHANNEL_DESCRIPTION = (
    "施永青於 am730 專欄「C觀點」的粵語朗讀。每有新文章便新增一集，"
    "不回溯歷史文章。"
)
CHANNEL_AUTHOR = "施永青"
CHANNEL_CATEGORY = "News"
CHANNEL_LANGUAGE = "zh-hk"


def rfc2822(date_str):
    """Article dates are YYYY-MM-DD in HKT; emit morning-paper pubDate."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=6, minute=0, second=0, tzinfo=HKT,
    )
    return format_datetime(dt)


def rss_xml(episodes, *, site_url, feed_url, cover_url, owner_email):
    ET.register_namespace("itunes", ITUNES)
    ET.register_namespace("atom", ATOM)

    site = site_url.rstrip("/") + "/"
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = CHANNEL_TITLE
    ET.SubElement(channel, "link").text = site
    ET.SubElement(channel, "description").text = CHANNEL_DESCRIPTION
    ET.SubElement(channel, "language").text = CHANNEL_LANGUAGE
    ET.SubElement(channel, f"{{{ATOM}}}link", {
        "href": feed_url,
        "rel": "self",
        "type": "application/rss+xml",
    })
    ET.SubElement(channel, f"{{{ITUNES}}}author").text = CHANNEL_AUTHOR
    ET.SubElement(channel, f"{{{ITUNES}}}summary").text = CHANNEL_DESCRIPTION
    ET.SubElement(channel, f"{{{ITUNES}}}explicit").text = "false"
    ET.SubElement(channel, f"{{{ITUNES}}}image", {"href": cover_url})
    ET.SubElement(channel, f"{{{ITUNES}}}category", {"text": CHANNEL_CATEGORY})
    owner = ET.SubElement(channel, f"{{{ITUNES}}}owner")
    ET.SubElement(owner, f"{{{ITUNES}}}name").text = CHANNEL_AUTHOR
    ET.SubElement(owner, f"{{{ITUNES}}}email").text = owner_email
    ET.SubElement(channel, "image").append(
        _text_el("url", cover_url)
    )
    channel.find("image").append(_text_el("title", CHANNEL_TITLE))
    channel.find("image").append(_text_el("link", site))

    for ep in episodes:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = ep["title"]
        ET.SubElement(item, "description").text = ep["body"]
        ET.SubElement(item, "link").text = f"{site_url.rstrip('/')}/#/article/{ep['nid']}"
        ET.SubElement(item, "pubDate").text = rfc2822(ep["date"])
        guid = ET.SubElement(item, "guid", {"isPermaLink": "false"})
        guid.text = ep["guid"]
        ET.SubElement(item, "enclosure", {
            "url": ep["media_url"],
            "length": str(ep["byte_length"]),
            "type": "audio/mp4",
        })
        ET.SubElement(item, f"{{{ITUNES}}}duration").text = str(ep["duration_seconds"])
        ET.SubElement(item, f"{{{ITUNES}}}explicit").text = "false"
        ET.SubElement(item, f"{{{ITUNES}}}summary").text = ep["body"]
        ET.SubElement(item, f"{{{ITUNES}}}author").text = CHANNEL_AUTHOR

    ET.indent(rss, space="  ")
    body = ET.tostring(rss, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _text_el(tag, text):
    el = ET.Element(tag)
    el.text = text
    return el
