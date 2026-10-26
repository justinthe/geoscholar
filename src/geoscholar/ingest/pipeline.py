"""The ingestion stages as plain functions, shared by scripts/ingest.py and the API."""
import logging

from geoscholar import config, db
from geoscholar.ingest.chunk import chunk_paper
from geoscholar.ingest.download import download_pdfs, pdf_path
from geoscholar.ingest.fetch import fetch_metadata
from geoscholar.ingest.parse import parse_pdf

log = logging.getLogger("ingest")


def index_papers(conn, embedder=None, limit=None, use_grobid=True, collection=config.COLLECTION,
                 progress=None):
    """Parse, chunk, embed and index every 'downloaded' paper. Returns the number indexed.

    embedder: reuse an already-loaded Embedder (the API passes its own); None loads one.
    progress: optional callback(done, total) for reporting.
    """
    from geoscholar.index import Embedder, Index      # imported here: loads torch, slow

    embedder = embedder or Embedder()
    index = Index(embedder, collection=collection)
    index.ensure_collection()
    todo = db.papers_with_status(conn, "downloaded")[:limit]
    log.info("%d papers to parse and index into '%s'", len(todo), collection)
    indexed = 0
    for i, p in enumerate(todo, 1):
        try:
            sections, parser = parse_pdf(pdf_path(p["id"]), p["id"], use_grobid=use_grobid)
            chunks = chunk_paper(p, sections, count=embedder.count_tokens)
            n = index.replace_paper(p["id"], chunks)
            db.set_status(conn, p["id"], "indexed", parser=parser, n_chunks=n)
            indexed += 1
        except Exception as exc:
            log.warning("index failed for %s: %s", p["id"], exc)
            db.set_status(conn, p["id"], "failed", error=f"index: {exc}")
        if progress:
            progress(i, len(todo))
        if i % 10 == 0:
            log.info("indexed %d/%d (collection now has %d chunks)", i, len(todo), index.count())
    return indexed


def run(conn, stages=("fetch", "download", "index"), limit=None, use_grobid=True,
        embedder=None, progress=None):
    """Run the given stages in order. progress(stage, done, total) is optional."""
    report = lambda stage: (lambda d, t: progress(stage, d, t)) if progress else None
    if "fetch" in stages:
        if progress:
            progress("fetch", 0, None)
        fetch_metadata(conn, target=limit or config.TARGET_PAPERS)
    if "download" in stages:
        if progress:
            progress("download", 0, None)
        download_pdfs(conn, limit=limit)
    if "index" in stages:
        index_papers(conn, embedder=embedder, limit=limit, use_grobid=use_grobid,
                     progress=report("index"))
    return db.status_counts(conn)