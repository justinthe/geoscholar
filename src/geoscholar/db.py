"""SQLite store for paper metadata and pipeline status.

Each paper moves through: fetched -> downloaded -> indexed.
If a step fails, status becomes 'failed' and the error is saved, so a re-run
can skip finished papers and you can inspect what broke.
"""
import json
import sqlite3

from geoscholar.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id          TEXT PRIMARY KEY,   -- arXiv ID without version, e.g. 2410.01234
    version     TEXT,               -- e.g. v2
    title       TEXT NOT NULL,
    abstract    TEXT,
    authors     TEXT,               -- JSON list
    published   TEXT,               -- YYYY-MM-DD
    year        INTEGER,
    categories  TEXT,               -- JSON list
    pdf_url     TEXT,
    topic       TEXT,               -- which search topic found it first
    status      TEXT NOT NULL DEFAULT 'fetched',
    parser      TEXT,               -- 'grobid' or 'pymupdf'
    n_chunks    INTEGER,
    error       TEXT,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path=DB_PATH):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row      # rows behave like dicts: row["title"]
    conn.execute(SCHEMA)
    return conn


def insert_paper(conn, p):
    """Insert a paper if new. Returns True if it was inserted."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO papers
           (id, version, title, abstract, authors, published, year, categories, pdf_url, topic)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (p["id"], p["version"], p["title"], p["abstract"], json.dumps(p["authors"]),
         p["published"], p["year"], json.dumps(p["categories"]), p["pdf_url"], p["topic"]),
    )
    conn.commit()
    return cur.rowcount == 1


def set_status(conn, paper_id, status, error=None, **fields):
    cols = ["status = ?", "error = ?", "updated_at = CURRENT_TIMESTAMP"]
    vals = [status, error]
    for k, v in fields.items():          # e.g. parser="grobid", n_chunks=12
        cols.append(f"{k} = ?")
        vals.append(v)
    vals.append(paper_id)
    conn.execute(f"UPDATE papers SET {', '.join(cols)} WHERE id = ?", vals)
    conn.commit()


def papers_with_status(conn, status):
    return conn.execute("SELECT * FROM papers WHERE status = ? ORDER BY id", (status,)).fetchall()


def status_counts(conn):
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM papers GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}