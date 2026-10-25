"""Generate an answer for every eval question (answerable and unanswerable) and save it.

    python scripts/run_answers.py --tag baseline
    python scripts/run_answers.py --tag sandwich --order sandwich
    python scripts/run_answers.py --tag k3 --k 3

Writes eval/results/answers_<tag>.jsonl (resumable) and answers_<tag>.meta.json (settings, GPU memory).
"""
import argparse
import json
import logging

from geoscholar import config
from geoscholar.evaluation import load_questions
from geoscholar.index import Embedder, Index
from geoscholar.rag import RAGPipeline, gpu_memory_mb
from geoscholar.retrieval import Reranker, Retriever


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="name for this run, e.g. baseline")
    ap.add_argument("--collection", default=config.COLLECTION)
    ap.add_argument("--mode", default=config.RETRIEVAL_MODE, choices=["dense", "bm25", "hybrid"])
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--k", type=int, default=config.TOP_K)
    ap.add_argument("--order", default=config.CONTEXT_ORDER, choices=["relevance", "sandwich"])
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions (for testing)")
    ap.add_argument("--questions", nargs="+", default=[
        str(config.EVAL_DIR / "questions.jsonl"),
        str(config.EVAL_DIR / "questions_manual.jsonl"),
    ])
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    questions = []
    for path in args.questions:
        questions += load_questions(path)
    questions = questions[: args.limit]

    out_dir = config.EVAL_DIR / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"answers_{args.tag}.jsonl"
    done = set()
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            done = {json.loads(line)["id"] for line in f if line.strip()}

    rerank = not args.no_rerank
    embedder = Embedder()
    retriever = Retriever(Index(embedder, collection=args.collection),
                          reranker=Reranker() if rerank else None)
    pipeline = RAGPipeline(retriever, mode=args.mode, rerank=rerank, k=args.k, order=args.order)

    gpu_before = gpu_memory_mb()
    pipeline.answer("What is synthetic aperture radar?")          # warm-up: loads all models
    gpu_loaded = gpu_memory_mb()

    meta = {"tag": args.tag, "collection": args.collection, "mode": args.mode, "rerank": rerank,
            "k": args.k, "order": args.order, "llm": config.LLM_MODEL, "num_ctx": config.LLM_NUM_CTX,
            "gpu_mb_before_warmup": gpu_before, "gpu_mb_models_loaded": gpu_loaded}
    (out_dir / f"answers_{args.tag}.meta.json").write_text(json.dumps(meta, indent=2))

    todo = [q for q in questions if q["id"] not in done]
    print(f"{len(todo)} questions to answer ({len(done)} done). GPU memory (used, total) MiB: {gpu_loaded}")
    with open(out_path, "a", encoding="utf-8") as out:
        for i, q in enumerate(todo, 1):
            rec = pipeline.answer(q["question"])
            rec.update({"id": q["id"], "type": q["type"], "paper_ids": q["paper_ids"],
                        "tags": q.get("tags", [])})
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            flag = "REFUSED" if rec["refused"] else f"cites {rec['cited']}"
            print(f"[{i}/{len(todo)}] {rec['timings_ms']['total'] / 1000:5.1f}s  {flag:14s} {q['question'][:70]}")


if __name__ == "__main__":
    main()