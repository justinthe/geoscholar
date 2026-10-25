"""Fetch paper metadata from the arXiv API and store it in SQLite."""
import logging
import re
import time

import feedparser
import requests

from geoscholar import config, db

log = logging.getLogger(__name__)


def build_query(topics=config.ARXIV_TOPICS, categories=config.ARXIV_CATEGORIES):
    topic_part = " OR ".join(f'abs:"{t}"' for t in topics)
    cat_part = " OR ".join(f"cat:{c}" for c in categories)
    return f"({topic_part}) AND ({cat_part})"


def clean(text):
    return " ".join((text or "").split())


def parse_entry(e, topic="combined"):
    """Turn one feedparser entry into our paper dict."""
    raw_id = e.id.split("/abs/")[-1]                 # e.g. 2410.01234v2
    m = re.match(r"(.+?)(v\d+)?$", raw_id)
    paper_id, version = m.group(1), m.group(2) or "v1"
    pdf_url = next((l.href for l in e.get("links", []) if l.get("title") == "pdf"),
                   f"https://arxiv.org/pdf/{paper_id}{version}")
    published = e.get("published", "")[:10]
    return {
        "id": paper_id,
        "version": version,
        "title": clean(e.title),
        "abstract": clean(e.get("summary")),
        "authors": [a.name for a in e.get("authors", [])],
        "published": published,
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "categories": [t["term"] for t in e.get("tags", [])],
        "pdf_url": pdf_url,
        "topic": topic,
    }


def fetch_page(query, start, page_size=100):
    resp = requests.get(
        config.ARXIV_API,
        params={"search_query": query, "start": start, "max_results": page_size,
                "sortBy": "submittedDate", "sortOrder": "descending"},
        headers={"User-Agent": config.USER_AGENT},
        timeout=60,
    )
    resp.raise_for_status()
    return feedparser.parse(resp.text).entries


def fetch_metadata(conn, target=config.TARGET_PAPERS, page_size=100):
    """Page through arXiv results until `target` new papers are stored."""
    query = build_query()
    log.info("arXiv query: %s", query)
    added, start = 0, 0
    while added < target:
        entries = fetch_page(query, start, page_size)
        if not entries:
            log.info("No more results at start=%d", start)
            break
        for e in entries:
            if added >= target:
                break
            if db.insert_paper(conn, parse_entry(e)):
                added += 1
        log.info("start=%d: %d new papers so far", start, added)
        start += page_size
        time.sleep(config.ARXIV_DELAY_S)
    return added