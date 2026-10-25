"""Check the LLM judge against your own judgement on a sample of claims.

Shows a claim and the evidence it was judged against, WITHOUT the judge's verdict,
asks you for yours, then reports agreement and Cohen's kappa.

    python scripts/spot_check.py --tag baseline --n 30

The sample is stratified: half from claims the judge called "supported", half from the rest,
so a judge that says "supported" to everything can't look good by luck. Resumable.
"""
import argparse
import json
import random
import textwrap

from geoscholar import config
from geoscholar.answer_eval import cohen_kappa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    res = config.EVAL_DIR / "results"
    with open(res / f"judged_{args.tag}.jsonl", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    items = []
    for r in records:
        by_n = {s["n"]: s["text"] for s in r["sources"]}
        for j, c in enumerate(r.get("claims", [])):
            if c["verdict"] == "error":
                continue
            valid = [n for n in c["cited"] if n in by_n]
            evidence = [by_n[n] for n in valid] if valid else list(by_n.values())
            items.append({"key": f"{r['id']}#{j}", "question": r["question"], "claim": c["plain"],
                          "evidence": evidence, "judge": c["verdict"] == "supported"})

    rng = random.Random(args.seed)
    yes = [x for x in items if x["judge"]]
    no = [x for x in items if not x["judge"]]
    rng.shuffle(yes)
    rng.shuffle(no)
    half = args.n // 2
    sample = no[:half] + yes[: args.n - min(half, len(no))]
    rng.shuffle(sample)

    out_path = res / f"spotcheck_{args.tag}.jsonl"
    labels = {}
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            labels = {d["key"]: d for d in map(json.loads, f)}

    todo = [x for x in sample if x["key"] not in labels]
    print(f"{len(todo)} claims to check ({len(labels)} done). Judge's verdict is hidden.\n")
    with open(out_path, "a", encoding="utf-8") as out:
        for i, x in enumerate(todo, 1):
            print("=" * 100)
            print(f"[{i}/{len(todo)}] Question: {x['question']}\n")
            for t in x["evidence"]:
                print(textwrap.fill(t[:1500], 100), "\n")
            print(f"CLAIM: {x['claim']}\n")
            ans = ""
            while ans not in ("y", "n", "s", "q"):
                ans = input("Fully supported by the evidence? [y]es [n]o [s]kip [q]uit > ").strip().lower()
            if ans == "q":
                break
            if ans == "s":
                continue
            d = {"key": x["key"], "human": ans == "y", "judge": x["judge"]}
            labels[x["key"]] = d
            out.write(json.dumps(d) + "\n")
            out.flush()

    # compare your labels with the CURRENT judged file, so labels can be reused after re-judging
    current = {x["key"]: x["judge"] for x in items}
    done = [d for d in labels.values() if d["key"] in current]
    if not done:
        return
    human = [d["human"] for d in done]
    judge = [current[d["key"]] for d in done]
    agree = sum(h == j for h, j in zip(human, judge)) / len(done)
    print(f"\nChecked {len(done)} claims")
    print(f"  agreement      {agree:.2f}")
    print(f"  Cohen's kappa  {cohen_kappa(human, judge):.2f}")
    print(f"  judge said supported, you said no : {sum(j and not h for h, j in zip(human, judge))}")
    print(f"  judge said not supported, you said yes: {sum(h and not j for h, j in zip(human, judge))}")


if __name__ == "__main__":
    main()