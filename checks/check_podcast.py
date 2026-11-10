#!/usr/bin/env python3
"""Verify podcast.rss_xml() emits an Apple-Podcasts-importable RSS 2.0
feed from episode rows. No network, no R2, no TTS."""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import podcast

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"

EPISODES = [
    {
        "nid": "200",
        "title": "Newer column",
        "date": "2026-11-10",
        "body": "Body of the newer column.",
        "url": "https://www.am730.com.hk/200",
        "guid": "cpoint-yue-200",
        "media_url": "https://audio.example/yue/200.m4a",
        "byte_length": 2222,
        "duration_seconds": 90,
        "published_at": "2026-11-10T22:00:00Z",
    },
    {
        "nid": "100",
        "title": "Older column",
        "date": "2026-11-09",
        "body": "Body of the older column.",
        "url": "https://www.am730.com.hk/100",
        "guid": "cpoint-yue-100",
        "media_url": "https://audio.example/yue/100.m4a",
        "byte_length": 1111,
        "duration_seconds": 45,
        "published_at": "2026-11-09T22:00:00Z",
    },
]


def main():
    xml = podcast.rss_xml(
        EPISODES,
        site_url="https://cpoint.paklau.com",
        feed_url="https://cpoint.paklau.com/podcast.xml",
        cover_url="https://cpoint.paklau.com/podcast-cover.jpg",
        owner_email="pak@example.com",
    )
    assert xml.startswith("<?xml version="), xml[:80]
    root = ET.fromstring(xml)
    assert root.tag == "rss"
    assert root.attrib.get("version") == "2.0"

    channel = root.find("channel")
    assert channel is not None
    assert channel.findtext("title")
    assert channel.findtext("description")
    assert channel.findtext("language") == "zh-hk"
    assert channel.findtext("link") == "https://cpoint.paklau.com/"

    atom_self = channel.find(f"{{{ATOM}}}link")
    assert atom_self is not None
    assert atom_self.attrib["href"] == "https://cpoint.paklau.com/podcast.xml"
    assert atom_self.attrib["rel"] == "self"

    image = channel.find(f"{{{ITUNES}}}image")
    assert image is not None
    assert image.attrib["href"] == "https://cpoint.paklau.com/podcast-cover.jpg"

    assert channel.findtext(f"{{{ITUNES}}}explicit") == "false"
    category = channel.find(f"{{{ITUNES}}}category")
    assert category is not None and category.attrib.get("text")
    owner = channel.find(f"{{{ITUNES}}}owner")
    assert owner is not None
    assert owner.findtext(f"{{{ITUNES}}}email") == "pak@example.com"

    items = channel.findall("item")
    assert [i.findtext("title") for i in items] == ["Newer column", "Older column"]

    first = items[0]
    enclosure = first.find("enclosure")
    assert enclosure is not None
    assert enclosure.attrib["url"] == "https://audio.example/yue/200.m4a"
    assert enclosure.attrib["length"] == "2222"
    assert enclosure.attrib["type"] == "audio/mp4"
    guid = first.find("guid")
    assert guid is not None
    assert guid.text == "cpoint-yue-200"
    assert guid.attrib.get("isPermaLink") == "false"
    assert first.findtext(f"{{{ITUNES}}}duration") == "90"
    pub = first.findtext("pubDate")
    assert pub and "10 Nov 2026" in pub and "+0800" in pub, pub
    assert first.findtext("link") == "https://cpoint.paklau.com/#/article/200"

    empty = podcast.rss_xml(
        [],
        site_url="https://cpoint.paklau.com",
        feed_url="https://cpoint.paklau.com/podcast.xml",
        cover_url="https://cpoint.paklau.com/podcast-cover.jpg",
        owner_email="pak@example.com",
    )
    empty_items = ET.fromstring(empty).find("channel").findall("item")
    assert empty_items == []

    print("OK: podcast.rss_xml emits an Apple-importable RSS 2.0 feed")


if __name__ == "__main__":
    main()
