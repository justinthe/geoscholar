"""Evaluate retrieval configurations on the labelled questions.

    python scripts/run_eval.py                         # all 5 configs on the default collection
    python scripts/run_eval.py --configs dense hybrid  # just these
    python scripts/run_eval.py --collection papers_c500

Writes:
    eval/results/per_question_<collection>.csv   one row per question per config (overwritten)
    eval/results/summary.csv                     one row per run (appended)
"""
import argparse
import csv
import logging
from datetime import datetime

from geoscholar import config
from geoscholar.evaluation import evaluate, load_questions, summarize
from geoscholar.index import Embedder, Index
from geoscholar.retrieval import Reranker, Retriever

CONFIGS = {                     # name: (mode, rerank)
    "dense":         ("dense", False),
    "bm25":          ("bm25", False),
    "hybrid":        ("hybrid", False),
    "dense+rerank":  ("dense", True),
    "hybrid+rerank": ("hybrid", True),
}


def write_csv(path, rows, append=False):
    new_file = not path.exists() or not append
    with open(path, "a" if append else "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new_file:
            w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", default=config.COLLECTION)
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=list(CONFIGS))
    ap.add_argument("--questions", nargs="+", default=[
        str(config.EVAL_DIR / "questions.jsonl"),
        str(config.EVAL_DIR / "questions_manual.jsonl"),
    ])
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    questions = []
    for path in args.questions:
        try:
            questions += load_questions(path)
        except FileNotFoundError:
            print(f"(skipping missing file {path})")
    answerable = [q for q in questions if q["paper_ids"]]
    print(f"{len(answerable)} answerable questions, collection '{args.collection}'\n")

    embedder = Embedder()
    index = Index(embedder, collection=args.collection)
    need_rerank = any(CONFIGS[c][1] for c in args.configs)
    retriever = Retriever(index, reranker=Reranker() if need_rerank else None)
    retriever.search("warm-up query", mode="hybrid", rerank=need_rerank)   # load models before timing

    results_dir = config.EVAL_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_rows, summaries = [], []
    for name in args.configs:
        mode, rerank = CONFIGS[name]
        rows, summary = evaluate(
            lambda text: retriever.search(text, k=10, mode=mode, rerank=rerank),
            questions, name)
        all_rows += rows
        summaries.append({"run_at": stamp, "collection": args.collection, **summary})

        print(f"{name:14s} R@1 {summary['recall@1']:.3f}  R@5 {summary['recall@5']:.3f} "
              f"[{summary['recall@5_ci_low']:.2f}-{summary['recall@5_ci_high']:.2f}]  "
              f"R@10 {summary['recall@10']:.3f}  MRR {summary['mrr']:.3f}  "
              f"p50 {summary['p50_ms']:.0f} ms")
        for qtype in sorted({r["type"] for r in rows}):
            sub = summarize([r for r in rows if r["type"] == qtype], name)
            print(f"{'':14s}   {qtype:18s} n={sub['n']:3d}  R@5 {sub['recall@5']:.3f}")

    write_csv(results_dir / f"per_question_{args.collection}.csv", all_rows)
    write_csv(results_dir / "summary.csv", summaries, append=True)
    print(f"\nSaved to {results_dir}")


if __name__ == "__main__":
    main()