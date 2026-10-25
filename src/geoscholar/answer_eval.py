"""Answer evaluation: split answers into claims, judge them with an LLM, aggregate metrics.

Metrics (see the week 4 notes for definitions):
  refusal_rate_unanswerable   should be high
  false_refusal_rate          refused although the right paper WAS retrieved; should be low
  answered_without_evidence   answered although the right paper was NOT retrieved; risky
  faithfulness                share of claims supported by the passages they cite
  citation_coverage           share of claims that cite at least one source
  cites_relevant              answer cites the labelled paper (when it was retrieved)
  relevance_full              share of answers the judge rates as fully answering the question
"""
import json
import re

import numpy as np

from geoscholar import config
from geoscholar.llm import chat
from geoscholar.rag import BRACKET_RE, cited_numbers, is_refusal

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def split_claims(answer):
    """Split an answer into sentence-level claims, each with the source numbers it cites."""
    claims = []
    for line in answer.splitlines():
        line = BULLET.sub("", line).strip()
        if not line:
            continue
        for sent in SENTENCE_SPLIT.split(line):
            plain = re.sub(r"\s+([.,;:!?])", r"\1", BRACKET_RE.sub("", sent)).strip()
            if len(plain.split()) < 4 or is_refusal(plain):
                continue
            claims.append({"text": sent.strip(), "plain": plain, "cited": cited_numbers(sent)})
    return claims


CLAIM_JUDGE = """You check whether a claim is supported by evidence passages.
- "supported": everything in the claim is stated in, or directly follows from, the evidence.
- "partial": some of the claim is supported, but part is missing or goes beyond the evidence.
- "unsupported": the evidence does not support the claim, or contradicts it.
Judge only against the evidence, not your own knowledge.
Reply as JSON: {"verdict": "supported" | "partial" | "unsupported", "reason": "<one short sentence>"}"""

RELEVANCE_JUDGE = """You rate how well an answer addresses a question. Ignore whether it is factually correct.
3 = it directly and completely answers the question
2 = it partly answers the question, or answers a related but different question
1 = it does not answer the question
Reply as JSON: {"score": 1 | 2 | 3, "reason": "<one short sentence>"}"""


def _ask_json(prompt, system, model):
    try:
        return json.loads(chat(prompt, system=system, temperature=0.0, json_mode=True, model=model))
    except Exception as exc:
        return {"error": str(exc)}


def judge_claim(claim, evidence_texts, model=None):
    evidence = "\n\n".join(f"Evidence {i}:\n{t}" for i, t in enumerate(evidence_texts, 1))
    reply = _ask_json(f"{evidence}\n\nClaim: {claim}", CLAIM_JUDGE, model or config.JUDGE_MODEL)
    verdict = str(reply.get("verdict", "")).lower().strip()
    if verdict not in ("supported", "partial", "unsupported"):
        verdict = "error"
    return {"verdict": verdict, "reason": str(reply.get("reason", reply.get("error", "")))[:300]}


def judge_relevance(question, answer, model=None):
    reply = _ask_json(f"Question: {question}\n\nAnswer: {answer}", RELEVANCE_JUDGE,
                      model or config.JUDGE_MODEL)
    try:
        score = int(reply.get("score"))
    except (TypeError, ValueError):
        score = None
    return score if score in (1, 2, 3) else None


def judge_record(rec, model=None):
    """Add claim verdicts and a relevance score to one answer record (from run_answers.py)."""
    rec = dict(rec)
    rec["claims"] = []
    rec["relevance"] = None
    if rec["refused"]:
        return rec
    by_n = {s["n"]: s["text"] for s in rec["sources"]}
    for c in split_claims(rec["answer"]):
        valid = [n for n in c["cited"] if n in by_n]
        # check a cited claim against what it cites; an uncited claim against everything
        evidence = [by_n[n] for n in valid] if valid else list(by_n.values())
        c.update(judge_claim(c["plain"], evidence, model))
        rec["claims"].append(c)
    if rec["paper_ids"]:
        rec["relevance"] = judge_relevance(rec["question"], rec["answer"], model)
    return rec


def _mean(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else float("nan")


def aggregate(records):
    """Summary metrics over judged records."""
    for r in records:
        relevant = set(r["paper_ids"])
        r["_hit"] = bool(relevant & {s["paper_id"] for s in r["sources"]})
    answerable = [r for r in records if r["paper_ids"]]
    unanswerable = [r for r in records if not r["paper_ids"]]
    hit = [r for r in answerable if r["_hit"]]
    miss = [r for r in answerable if not r["_hit"]]
    answered = [r for r in records if not r["refused"]]
    claims = [c for r in answered for c in r.get("claims", []) if c.get("verdict") != "error"]

    def cites_relevant(r):
        cited_papers = {s["paper_id"] for s in r["sources"] if s["n"] in r["cited"]}
        return bool(cited_papers & set(r["paper_ids"]))

    timings = [r["timings_ms"] for r in records]
    return {
        "n_answerable": len(answerable),
        "n_unanswerable": len(unanswerable),
        "retrieval_hit_rate": len(hit) / len(answerable) if answerable else float("nan"),
        "refusal_rate_unanswerable": _mean([r["refused"] for r in unanswerable]),
        "false_refusal_rate": _mean([r["refused"] for r in hit]),
        "answered_without_evidence": _mean([not r["refused"] for r in miss]),
        "n_claims": len(claims),
        "faithfulness": _mean([c["verdict"] == "supported" for c in claims]),
        "partial_rate": _mean([c["verdict"] == "partial" for c in claims]),
        "citation_coverage": _mean([bool(c["cited"]) for c in claims]),
        "invalid_citation_rate": _mean([bool(r["invalid_citations"]) for r in answered]),
        "cites_relevant": _mean([cites_relevant(r) for r in hit if not r["refused"]]),
        "relevance_full": _mean([r["relevance"] == 3 for r in answerable
                                 if not r["refused"] and r.get("relevance")]),
        "p50_total_ms": float(np.median([t["total"] for t in timings])) if timings else float("nan"),
        "p50_generate_ms": float(np.median([t["generate"] for t in timings])) if timings else float("nan"),
        "p50_retrieve_rerank_ms": float(np.median([t["retrieve"] + t["rerank"] for t in timings]))
                                  if timings else float("nan"),
        "mean_prompt_tokens": _mean([r.get("prompt_tokens") for r in records]),
        "mean_tokens_per_s": _mean([r.get("tokens_per_s") for r in records]),
    }


def cohen_kappa(a, b):
    """Agreement between two raters on yes/no labels, corrected for chance agreement."""
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    observed = float(np.mean(a == b))
    pa, pb = a.mean(), b.mean()
    expected = pa * pb + (1 - pa) * (1 - pb)
    return float("nan") if expected == 1 else (observed - expected) / (1 - expected)