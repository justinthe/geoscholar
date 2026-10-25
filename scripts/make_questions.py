"""Draft evaluation questions with the local LLM: one question per sampled paper.

Each draft keeps the chunk it was written from, so you can check it in review.
Resumable: papers already in the draft file are skipped.

    python scripts/make_questions.py --n 120
"""
import argparse
import json
import random
import re

from geoscholar import config
from geoscholar.index import Index
from geoscholar.llm import chat

SKIP_SECTIONS = re.compile(r"abstract|acknowledg|reference|appendix|funding|conflict|author", re.I)

SYSTEM = """You write evaluation questions for a search engine over remote sensing research papers.
Rules:
- Write ONE specific question that this passage answers.
- The question must make sense on its own, as if asked by a researcher who has not seen the passage.
- Never say "this paper", "the authors", "the passage", "the proposed method" or "the study".
- Mention the concrete topic (e.g. the sensor, task, dataset or technique) so the question is searchable.
- Use your own words; do not copy long phrases from the passage.
- If the passage has no specific, answerable fact (e.g. it is only background), set "usable" to false.
Reply as JSON: {"question": "...", "usable": true}"""


def pick_chunks(index, n, seed):
    by_paper = {}
    for p in index.all_payloads():
        if p.get("n_tokens", 0) < 120 or SKIP_SECTIONS.search(p.get("section", "")):
            continue
        by_paper.setdefault(p["paper_id"], []).append(p)
    rng = random.Random(seed)
    papers = sorted(by_paper)
    rng.shuffle(papers)
    return [rng.choice(by_paper[pid]) for pid in papers[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120, help="number of papers to sample")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--collection", default=config.COLLECTION)
    ap.add_argument("--out", default=str(config.EVAL_DIR / "questions_draft.jsonl"))
    args = ap.parse_args()

    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    try:
        with open(args.out, encoding="utf-8") as f:
            done = {json.loads(line)["paper_ids"][0] for line in f if line.strip()}
    except FileNotFoundError:
        pass

    index = Index(embedder=None, collection=args.collection)   # only reading payloads
    chunks = [c for c in pick_chunks(index, args.n, args.seed) if c["paper_id"] not in done]
    print(f"{len(chunks)} chunks to turn into questions ({len(done)} already drafted)")

    with open(args.out, "a", encoding="utf-8") as out:
        for i, c in enumerate(chunks, 1):
            prompt = f"Paper title: {c['title']}\nSection: {c['section']}\n\nPassage:\n{c['text']}"
            try:
                reply = json.loads(chat(prompt, system=SYSTEM, temperature=0.3, json_mode=True))
            except Exception as exc:
                print(f"  skip {c['paper_id']}: {exc}")
                continue
            question = str(reply.get("question", "")).strip()
            if not reply.get("usable", True) or len(question) < 15:
                print(f"  skip {c['paper_id']}: not usable")
                continue
            out.write(json.dumps({
                "id": f"g-{c['paper_id']}",          # one question per paper, so this is unique
                "question": question,
                "paper_ids": [c["paper_id"]],
                "type": "generated",
                "source_chunk_id": c["chunk_id"],
                "source_section": c["section"],
                "source_text": c["text"],
            }, ensure_ascii=False) + "\n")
            out.flush()
            print(f"[{i}/{len(chunks)}] {question}")


if __name__ == "__main__":
    main()