# Ingest run results

Date: 2026-10-25

Raw output of `.venv/bin/python scripts/ingest.py --status`:

```
Status: {'failed': 1, 'indexed': 399}
```

| Metric | Value |
|---|---|
| Papers fetched | 400. This is the row count of the `papers` table (all statuses), since every fetched paper gets a row. All 400 came from topic `combined`. |
| Papers indexed | 399 (`status='indexed'`) |
| Failed (and main reasons) | 1 (`status='failed'`). Only reason: download 404 Not Found for 2608.03539 (`https://arxiv.org/pdf/2608.03539v2`), 1 of 1. |
| Parsed by GROBID / PyMuPDF | GROBID 399 / PyMuPDF 0 (grouped by `parser` among indexed) |
| Total chunks in Qdrant | 19,650 in collection `papers_c300` (exact count). Matches `sum(n_chunks)` in the DB (19,650). No mismatch. |
| Average chunks per paper | 49.25 (19,650 / 399). Min 6, max 191. |
| Time for the index stage | About 14 min (derived from logs, see notes). Log timestamps: 10:35:22 start ("399 papers to parse and index") to 10:49:23 (last "indexed 390/399" line) = 14 min 1 s. The DB's last `updated_at` for an indexed paper is 03:49:44 UTC (= 10:49:44 local), giving about 14 min 22 s. |

Notes:

- Index time is derived, not measured. The log has no "indexing finished" line and no "indexed 399/399" line, because progress is only logged every 10 papers. The last logged line is 390/399, so the log-only figure undercounts by roughly 20 s. The DB timestamp gives the better end point. This assumes log times are local (UTC+7) and `updated_at` is UTC, which is consistent with the first paper's DB timestamp (03:35:24 UTC) landing 2 s after the log start line. Model loading happens before the start line, so it is not included.
- The one failure is a download failure, not an index failure. 395 PDFs were queued for download, 1 gave a 404, and 399 papers reached the index stage. 400 - 1 = 399, so all downloaded papers were indexed with zero index failures.
- The log shows 395 PDFs queued, not 399. Likely 4 PDFs were already on disk from an earlier run (not confirmed). The log file (67 lines) also starts at the fetch stage and only shows "380 new papers" at its last fetch line, while the DB has 400, so earlier fetch activity is not fully in the log.
- GROBID handled every paper with no fallback to PyMuPDF. Chunk counts range widely (6 to 191), so a few very short or very long papers are worth spot-checking.
