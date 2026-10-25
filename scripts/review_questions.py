"""Review drafted questions one by one in the terminal: keep, edit or drop.

Kept questions go to eval/questions.jsonl, dropped IDs to eval/rejected.txt.
Resumable: anything already decided is skipped. Type q to stop at any time.

    python scripts/review_questions.py
"""
import json
import textwrap

from geoscholar import config

DRAFT = config.EVAL_DIR / "questions_draft.jsonl"
KEPT = config.EVAL_DIR / "questions.jsonl"
REJECTED = config.EVAL_DIR / "rejected.txt"


def read_ids(path, jsonl=True):
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        if jsonl:
            return {json.loads(line)["id"] for line in f if line.strip()}
        return {line.strip() for line in f if line.strip()}


def main():
    decided = read_ids(KEPT) | read_ids(REJECTED, jsonl=False)
    with open(DRAFT, encoding="utf-8") as f:
        drafts = [json.loads(line) for line in f if line.strip()]
    todo = [d for d in drafts if d["id"] not in decided]
    print(f"{len(todo)} to review ({len(decided)} already done)\n")

    for n, d in enumerate(todo, 1):
        print("=" * 100)
        print(f"[{n}/{len(todo)}] {d['id']}   paper {d['paper_ids'][0]}   section: {d['source_section']}")
        print(textwrap.fill(d["source_text"][:1200], 100))
        print(f"\nQUESTION: {d['question']}\n")
        while True:
            choice = input("[k]eep  [e]dit  [d]rop  [q]uit > ").strip().lower()
            if choice in ("k", "e", "d", "q"):
                break
        if choice == "q":
            break
        if choice == "d":
            with open(REJECTED, "a", encoding="utf-8") as f:
                f.write(d["id"] + "\n")
            continue
        if choice == "e":
            new = input("New question: ").strip()
            if new:
                d["question"] = new
                d["type"] = "generated-edited"
        kept = {k: d[k] for k in ("id", "question", "paper_ids", "type", "source_chunk_id")}
        with open(KEPT, "a", encoding="utf-8") as f:
            f.write(json.dumps(kept, ensure_ascii=False) + "\n")

    print(f"\nKept so far: {len(read_ids(KEPT))}")


if __name__ == "__main__":
    main()