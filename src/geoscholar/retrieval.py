"""Retrieval strategies: dense, BM25, hybrid (reciprocal rank fusion), plus optional reranking.

Every strategy returns the same shape: a list of (score, payload) pairs, best first,
where payload is the chunk dict stored in Qdrant (chunk_id, paper_id, section, text, ...).
"""
import re

import numpy as np
from rank_bm25 import BM25Okapi

from geoscholar import config

STOPWORDS = set("""a an and are as at be by for from has have in is it its of on or that the
their this to was were which with we our these those using used use can into than also
what how why when where who does do""".split())

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*")


def tokenize(text):
    """Lowercase word tokens that keep terms like 'sentinel-1', 'u-net', '2.5'.

    Hyphenated terms are also split into their parts, so 'Sentinel-1' matches 'Sentinel 1'.
    """
    tokens = []
    for tok in TOKEN_RE.findall(text.lower()):
        if tok in STOPWORDS:
            continue
        tokens.append(tok)
        if "-" in tok:
            tokens.extend(part for part in tok.split("-") if part and part not in STOPWORDS)
    return tokens


def bm25_text(payload):
    # Same information the dense model sees: title + section + chunk text
    return f"{payload['title']} {payload['section']} {payload['text']}"


class BM25Index:
    """Keyword index over every chunk in a Qdrant collection, held in memory."""
    
    def __init__(self, payloads):
        self.payloads = list(payloads)
        # an empty collection (fresh install, nothing ingested yet) gets no BM25 model
        self.bm25 = BM25Okapi([tokenize(bm25_text(p)) for p in self.payloads]) if self.payloads else None

    def search(self, query, k=10, year_from=None):
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        order = np.argsort(-scores)
        hits = []
        for i in order:
            if scores[i] <= 0:                       # no query term appears: stop
                break
            p = self.payloads[i]
            if year_from and (p.get("year") or 0) < year_from:
                continue
            hits.append((float(scores[i]), p))
            if len(hits) == k:
                break
        return hits

    # def __init__(self, payloads):
    #     self.payloads = list(payloads)
    #     self.bm25 = BM25Okapi([tokenize(bm25_text(p)) for p in self.payloads])

    # def search(self, query, k=10, year_from=None):
    #     scores = self.bm25.get_scores(tokenize(query))
    #     order = np.argsort(-scores)
    #     hits = []
    #     for i in order:
    #         if scores[i] <= 0:                       # no query term appears: stop
    #             break
    #         p = self.payloads[i]
    #         if year_from and (p.get("year") or 0) < year_from:
    #             continue
    #         hits.append((float(scores[i]), p))
    #         if len(hits) == k:
    #             break
    #     return hits


def rrf(result_lists, k=config.RRF_K, limit=None):
    """Reciprocal rank fusion: score(chunk) = sum over lists of 1 / (k + rank)."""
    scores, payloads = {}, {}
    for results in result_lists:
        for rank, (_, p) in enumerate(results, start=1):
            cid = p["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            payloads[cid] = p
    fused = sorted(scores, key=scores.get, reverse=True)[:limit]
    return [(scores[cid], payloads[cid]) for cid in fused]


class Reranker:
    """Cross-encoder: reads (query, passage) together and scores relevance directly."""

    def __init__(self, model_name=config.RERANK_MODEL):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name, max_length=512)

    def rerank(self, query, hits, k):
        if not hits:
            return []
        pairs = [(query, f"{p['title']}\n{p['section']}\n{p['text']}") for _, p in hits]
        scores = self.model.predict(pairs, batch_size=16, show_progress_bar=False)
        order = np.argsort(-np.asarray(scores))[:k]
        return [(float(scores[i]), hits[i][1]) for i in order]


class Retriever:
    """One object that can run any strategy, so the evaluation can compare them fairly."""

    MODES = ("dense", "bm25", "hybrid")

    def __init__(self, index, reranker=None):
        self.index = index                                # geoscholar.index.Index
        self.bm25 = BM25Index(index.all_payloads())
        self.reranker = reranker

    def search(self, query, k=5, mode="hybrid", rerank=False,
               candidates=config.CANDIDATES, year_from=None):
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}")
        n = candidates if (rerank or mode == "hybrid") else k
        if mode == "dense":
            hits = self.index.search(query, k=n, year_from=year_from)
        elif mode == "bm25":
            hits = self.bm25.search(query, k=n, year_from=year_from)
        else:
            dense = self.index.search(query, k=candidates, year_from=year_from)
            sparse = self.bm25.search(query, k=candidates, year_from=year_from)
            hits = rrf([dense, sparse], limit=n)
        if rerank:
            if self.reranker is None:
                raise ValueError("rerank=True but no reranker was given")
            return self.reranker.rerank(query, hits, k)
        return hits[:k]