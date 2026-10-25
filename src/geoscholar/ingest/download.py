"""Download PDFs for papers with status 'fetched'."""
import logging
import time

import requests

from geoscholar import config, db

log = logging.getLogger(__name__)


def pdf_path(paper_id):
    # Old-style IDs contain a slash (e.g. math/0601001), which is not valid in a filename
    return config.PDF_DIR / f"{paper_id.replace('/', '_')}.pdf"


def download_pdfs(conn, limit=None):
    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    todo = db.papers_with_status(conn, "fetched")[:limit]
    log.info("%d PDFs to download", len(todo))
    for i, p in enumerate(todo, 1):
        path = pdf_path(p["id"])
        if path.exists() and path.stat().st_size > 0:          # already on disk
            db.set_status(conn, p["id"], "downloaded")
            continue
        try:
            resp = requests.get(p["pdf_url"], headers={"User-Agent": config.USER_AGENT}, timeout=120)
            resp.raise_for_status()
            if not resp.content.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            tmp = path.with_suffix(".part")                     # write, then rename:
            tmp.write_bytes(resp.content)                       # a crash never leaves a
            tmp.rename(path)                                    # half-written .pdf behind
            db.set_status(conn, p["id"], "downloaded")
        except Exception as exc:
            log.warning("download failed for %s: %s", p["id"], exc)
            db.set_status(conn, p["id"], "failed", error=f"download: {exc}")
        if i % 25 == 0:
            log.info("downloaded %d/%d", i, len(todo))
        time.sleep(config.ARXIV_DELAY_S)