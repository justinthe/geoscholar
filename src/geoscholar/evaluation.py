"""Retrieval evaluation: load labelled questions, compute recall@k and MRR, with confidence intervals.

Relevance is judged at the PAPER level: a retrieved chunk counts as relevant if it comes
from one of the question's relevant papers. This keeps labels valid across chunk sizes
(chunk IDs change when you re-chunk; paper IDs don't).
"""
import json
import time

import numpy as np

KS = (1, 3, 5, 10)
DEPTH = max(KS)                       # how many chunks we retrieve per question


def load_questions(path):
    """Read a JSONL file: one {"id", "question", "paper_ids", "type", ...} object per line."""
    questions = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            q = json.loads(line)
            if "question" not in q or "paper_ids" not in q:
                raise ValueError(f"{path}:{line_no} needs 'question' and 'paper_ids'")
            q.setdefault("id", f"q{line_no}")
            q.setdefault("type", "unknown")
            questions.append(q)
    return questions


def first_relevant_rank(ranked_paper_ids, relevant):
    """1-based rank of the first chunk from a relevant paper, or None if absent."""
    for rank, pid in enumerate(ranked_paper_ids, start=1):
        if pid in relevant:
            return rank
    return None


def recall_at_k(ranked_paper_ids, relevant, k):
    """Fraction of the relevant papers that appear somewhere in the top-k chunks."""
    found = set(ranked_paper_ids[:k]) & set(relevant)
    return len(found) / len(relevant)


def reciprocal_rank(ranked_paper_ids, relevant, cutoff=DEPTH):
    rank = first_relevant_rank(ranked_paper_ids[:cutoff], relevant)
    return 1.0 / rank if rank else 0.0


def bootstrap_ci(values, n_boot=2000, alpha=0.05, seed=0):
    """95% confidence interval of the mean, by resampling questions with replacement."""
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    return (float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def evaluate(search_fn, questions, name):
    """Run search_fn(question_text) -> [(score, payload), ...] on every answerable question.

    Returns (per_question_rows, summary_dict).
    """
    rows = []
    for q in questions:
        relevant = set(q["paper_ids"])
        if not relevant:                     # unanswerable questions are for week 4
            continue
        t0 = time.perf_counter()
        hits = search_fn(q["question"])
        ms = (time.perf_counter() - t0) * 1000
        ranked = [p["paper_id"] for _, p in hits[:DEPTH]]
        row = {
            "config": name,
            "qid": q["id"],
            "type": q["type"],
            "question": q["question"],
            "relevant": ";".join(sorted(relevant)),
            "first_rank": first_relevant_rank(ranked, relevant),
            "rr": reciprocal_rank(ranked, relevant),
            "latency_ms": round(ms, 1),
            "top1_paper": ranked[0] if ranked else "",
            "top1_section": hits[0][1].get("section", "") if hits else "",
        }
        for k in KS:
            row[f"recall@{k}"] = recall_at_k(ranked, relevant, k)
        rows.append(row)
    return rows, summarize(rows, name)


def summarize(rows, name):
    summary = {"config": name, "n": len(rows)}
    for k in KS:
        vals = [r[f"recall@{k}"] for r in rows]
        summary[f"recall@{k}"] = float(np.mean(vals)) if vals else float("nan")
    summary["mrr"] = float(np.mean([r["rr"] for r in rows])) if rows else float("nan")
    lo, hi = bootstrap_ci([r["recall@5"] for r in rows])
    summary["recall@5_ci_low"], summary["recall@5_ci_high"] = lo, hi
    summary["p50_ms"] = float(np.median([r["latency_ms"] for r in rows])) if rows else float("nan")
    return summary