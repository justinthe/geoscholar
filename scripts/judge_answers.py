"""Judge the answers of one run with the LLM judge, then print and save summary metrics.

    python scripts/judge_answers.py --tag baseline

Reads  eval/results/answers_<tag>.jsonl
Writes eval/results/judged_<tag>.jsonl (resumable) and appends to eval/results/answer_summary.csv
"""
import argparse
import csv
import json
from datetime import datetime

from geoscholar import config
from geoscholar.answer_eval import aggregate, judge_record


def read_jsonl(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--judge", default=config.JUDGE_MODEL, help="Ollama model used as judge")
    args = ap.parse_args()

    res = config.EVAL_DIR / "results"
    answers = read_jsonl(res / f"answers_{args.tag}.jsonl")
    judged_path = res / f"judged_{args.tag}.jsonl"
    done = {r["id"] for r in read_jsonl(judged_path)}
    todo = [r for r in answers if r["id"] not in done]
    print(f"Judging {len(todo)} answers with '{args.judge}' ({len(done)} already judged)")

    with open(judged_path, "a", encoding="utf-8") as out:
        for i, rec in enumerate(todo, 1):
            judged = judge_record(rec, model=args.judge)
            out.write(json.dumps(judged, ensure_ascii=False) + "\n")
            out.flush()
            verdicts = [c["verdict"][0].upper() for c in judged["claims"]]   # S / P / U / E
            print(f"[{i}/{len(todo)}] {'refused' if rec['refused'] else ' '.join(verdicts) or '-':20s} "
                  f"rel={judged['relevance']}  {rec['question'][:60]}")

    metrics = aggregate(read_jsonl(judged_path))
    print()
    for k, v in metrics.items():
        print(f"  {k:28s} {v:.3f}" if isinstance(v, float) else f"  {k:28s} {v}")

    meta_path = res / f"answers_{args.tag}.meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    row = {"run_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "tag": args.tag, "judge": args.judge,
           **{k: meta.get(k) for k in ("mode", "rerank", "k", "order", "llm")},
           "gpu_mb_models_loaded": (meta.get("gpu_mb_models_loaded") or [None])[0],
           **{k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()}}
    summary = res / "answer_summary.csv"
    new = not summary.exists()
    with open(summary, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)
    print(f"\nAppended to {summary}")


if __name__ == "__main__":
    main()