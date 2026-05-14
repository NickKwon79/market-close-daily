"""Aggregate market news headlines from public RSS feeds."""
from __future__ import annotations

import hashlib
import logging
from typing import List

import feedparser

log = logging.getLogger(__name__)

RSS_FEEDS = [
    ("Reuters Markets",     "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best"),
    ("CNBC Markets",        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"),
    ("Yahoo Finance",       "https://finance.yahoo.com/news/rssindex"),
    ("MarketWatch Top",     "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Investing.com News",  "https://www.investing.com/rss/news.rss"),
    ("Bloomberg Markets",   "https://feeds.bloomberg.com/markets/news.rss"),
    ("FT Markets",          "https://www.ft.com/markets?format=rss"),
    ("Korea Herald Biz",    "https://biz.heraldcorp.com/common_prog/rssdisp.php?ct=011000000000.xml"),
]

MAX_PER_FEED = 6
MAX_TOTAL = 30


def _hash_title(title: str) -> str:
    return hashlib.md5(title.strip().lower().encode("utf-8")).hexdigest()


def fetch_all() -> List[dict]:
    seen = set()
    items: List[dict] = []
    for source, url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(url)
            entries = parsed.entries[:MAX_PER_FEED]
        except Exception as e:
            log.warning("news:%s failed: %s", source, e)
            continue
        for entry in entries:
            title = (getattr(entry, "title", "") or "").strip()
            link = getattr(entry, "link", "") or ""
            if not title or not link:
                continue
            h = _hash_title(title)
            if h in seen:
                continue
            seen.add(h)
            items.append({
                "source": source,
                "title": title[:240],
                "url": link,
                "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            })
            if len(items) >= MAX_TOTAL:
                log.info("news: %d headlines collected (capped)", len(items))
                return items
    log.info("news: %d headlines collected", len(items))
    return items
