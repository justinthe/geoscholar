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
from geoscholar.ingest import pipeline


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

    if args.stage:
        stages = ("fetch", "download", "index") if args.stage == "all" else (args.stage,)
        pipeline.run(conn, stages=stages, limit=args.limit, use_grobid=not args.no_grobid)

    print("Status:", db.status_counts(conn))


if __name__ == "__main__":
    main()