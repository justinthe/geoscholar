"""Run the ingestion pipeline.

Examples:
    python scripts/ingest.py --stage fetch
    python scripts/ingest.py --stage download --limit 20
    python scripts/ingest.py --stage index
    python scripts/ingest.py --stage all
    python scripts/ingest.py --status
"""
import argparse
import logging
import sys

from geoscholar import config, db
from geoscholar.ingest.chunk import chunk_paper
from geoscholar.ingest.download import download_pdfs, pdf_path
from geoscholar.ingest.fetch import fetch_metadata
from geoscholar.ingest.parse import parse_pdf


def setup_logging():
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(config.LOG_DIR / "ingest.log", encoding="utf-8")],
    )
    for noisy in ("httpx", "urllib3", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def run_index(conn, limit=None, use_grobid=True):
    from geoscholar.index import Embedder, Index     # imported here: loads torch, slow

    log = logging.getLogger("index")
    embedder = Embedder()
    index = Index(embedder)
    index.ensure_collection()
    todo = db.papers_with_status(conn, "downloaded")[:limit]
    log.info("%d papers to parse and index into '%s'", len(todo), index.collection)
    for i, p in enumerate(todo, 1):
        try:
            sections, parser = parse_pdf(pdf_path(p["id"]), p["id"], use_grobid=use_grobid)
            chunks = chunk_paper(p, sections, count=embedder.count_tokens)
            n = index.replace_paper(p["id"], chunks)
            db.set_status(conn, p["id"], "indexed", parser=parser, n_chunks=n)
        except Exception as exc:
            log.warning("index failed for %s: %s", p["id"], exc)
            db.set_status(conn, p["id"], "failed", error=f"index: {exc}")
        if i % 10 == 0:
            log.info("indexed %d/%d (collection now has %d chunks)", i, len(todo), index.count())


def main():
    ap = argparse.ArgumentParser(description="GeoScholar ingestion pipeline")
    ap.add_argument("--stage", choices=["fetch", "download", "index", "all"])
    ap.add_argument("--limit", type=int, default=None, help="process at most N papers")
    ap.add_argument("--no-grobid", action="store_true", help="use PyMuPDF only")
    ap.add_argument("--retry-failed", action="store_true", help="reset failed papers first")
    ap.add_argument("--reindex", action="store_true",
                    help="re-parse and re-index papers already indexed (e.g. new chunk size)")
    ap.add_argument("--status", action="store_true", help="print status counts and exit")
    args = ap.parse_args()

    setup_logging()
    conn = db.connect()

    if args.retry_failed:
        conn.execute("UPDATE papers SET status = 'fetched', error = NULL WHERE status = 'failed'")
        conn.commit()
    if args.reindex:
        conn.execute("UPDATE papers SET status = 'downloaded' WHERE status = 'indexed'")
        conn.commit()

    if args.stage in ("fetch", "all"):
        fetch_metadata(conn, target=args.limit or config.TARGET_PAPERS)
    if args.stage in ("download", "all"):
        download_pdfs(conn, limit=args.limit)
    if args.stage in ("index", "all"):
        run_index(conn, limit=args.limit, use_grobid=not args.no_grobid)

    print("Status:", db.status_counts(conn))


if __name__ == "__main__":
    main()