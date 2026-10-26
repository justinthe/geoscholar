"""The full RAG pipeline: retrieve -> (rerank) -> order and trim -> prompt -> answer with citations."""
import re
import subprocess
import time

from geoscholar import config
from geoscholar.llm import chat_full, chat_stream

REFUSAL = "I could not find this in the indexed papers."

SYSTEM_PROMPT = f"""You answer questions about remote sensing research using ONLY the numbered sources provided.
Rules:
1. End every sentence that states a fact with the source number(s) it comes from, like [S1] or [S2][S4].
2. Use only information stated in the sources. Do not add outside knowledge.
3. If the sources do not contain the answer, reply with exactly this sentence and nothing else:
{REFUSAL}
4. If the sources answer only part of the question, answer that part and say what is missing.
5. Be concise: at most 5 sentences."""

BRACKET_RE = re.compile(r"\[([^\]]*)\]")
SOURCE_NUM_RE = re.compile(r"S\s*(\d+)", re.I)


def order_sources(hits, order="relevance"):
    """'relevance': best first. 'sandwich': best at both ends, weakest in the middle.

    With hits ranked 1..5, sandwich gives 1, 3, 5, 4, 2.
    """
    if order == "relevance":
        return list(hits)
    if order == "sandwich":
        return list(hits[0::2]) + list(hits[1::2])[::-1]
    raise ValueError("order must be 'relevance' or 'sandwich'")


def approx_tokens(text):
    return len(text) // 4                 # rough rule of thumb for English text


def trim_to_budget(hits, max_tokens):
    """Keep the highest-ranked passages that fit in the token budget (always keep one)."""
    kept, used = [], 0
    for score, p in hits:
        cost = approx_tokens(p["text"]) + 30          # + header line
        if kept and used + cost > max_tokens:
            break
        kept.append((score, p))
        used += cost
    return kept


def build_prompt(question, sources):
    blocks = [f"[S{s['n']}] {s['title']} ({s['year']}), section: {s['section']}\n{s['text']}"
              for s in sources]
    return "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}\nAnswer:"


def cited_numbers(text):
    """All source numbers cited in the text, in order of first appearance: '[S2][S1, S3]' -> [2, 1, 3]."""
    nums = []
    for inside in BRACKET_RE.findall(text):
        for n in SOURCE_NUM_RE.findall(inside):
            if int(n) not in nums:
                nums.append(int(n))
    return nums


def is_refusal(answer):
    norm = " ".join(answer.lower().split())
    return "could not find this in the indexed papers" in norm


def format_citations(answer, sources):
    """Replace [S2] with [2410.01234, 3 Method] for display."""
    by_n = {s["n"]: s for s in sources}

    def repl(m):
        nums = [int(n) for n in SOURCE_NUM_RE.findall(m.group(1))]
        if not nums:
            return m.group(0)
        parts = [f"{by_n[n]['paper_id']}, {by_n[n]['section']}" if n in by_n else f"S{n}?" for n in nums]
        return "[" + "; ".join(parts) + "]"

    return BRACKET_RE.sub(repl, answer)


def gpu_memory_mb():
    """(used, total) MiB for GPU 0 from nvidia-smi, or None if unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True).stdout
        used, total = out.strip().splitlines()[0].split(",")
        return int(used), int(total)
    except Exception:
        return None


class RAGPipeline:
    def __init__(self, retriever, mode=config.RETRIEVAL_MODE, rerank=config.USE_RERANK,
                 k=config.TOP_K, order=config.CONTEXT_ORDER,
                 max_context_tokens=config.MAX_CONTEXT_TOKENS, model=None):
        self.retriever = retriever
        self.mode, self.rerank, self.k, self.order = mode, rerank, k, order
        self.max_context_tokens = max_context_tokens
        self.model = model

    def retrieve(self, question, year_from=None):
        """Returns (hits, retrieve_ms, rerank_ms)."""
        t0 = time.perf_counter()
        n = config.CANDIDATES if self.rerank else self.k
        hits = self.retriever.search(question, k=n, mode=self.mode, rerank=False, year_from=year_from)
        t1 = time.perf_counter()
        if self.rerank:
            hits = self.retriever.reranker.rerank(question, hits, self.k)
        t2 = time.perf_counter()
        return hits[: self.k], (t1 - t0) * 1000, (t2 - t1) * 1000

    def prepare(self, question, year_from=None):
        """Everything before the LLM call: retrieve, order, number the sources, build the prompt."""
        hits, retrieve_ms, rerank_ms = self.retrieve(question, year_from)
        hits = order_sources(trim_to_budget(hits, self.max_context_tokens), self.order)
        sources = [{"n": i, "score": round(float(score), 4), **{key: p[key] for key in
                    ("paper_id", "title", "year", "section", "text", "chunk_id")}}
                   for i, (score, p) in enumerate(hits, start=1)]
        return {"question": question, "sources": sources, "prompt": build_prompt(question, sources),
                "retrieve_ms": retrieve_ms, "rerank_ms": rerank_ms}

    def finish(self, prep, answer, stats, generate_ms):
        """Everything after the LLM call: parse citations, detect refusal, collect timings."""
        answer = answer.strip()
        sources = prep["sources"]
        cited = cited_numbers(answer)
        valid = {s["n"] for s in sources}
        return {
            "question": prep["question"],
            "answer": answer,
            "answer_display": format_citations(answer, sources),
            "refused": is_refusal(answer),
            "cited": cited,
            "invalid_citations": [n for n in cited if n not in valid],
            "sources": sources,
            "timings_ms": {
                "retrieve": round(prep["retrieve_ms"], 1),
                "rerank": round(prep["rerank_ms"], 1),
                "generate": round(generate_ms, 1),
                "total": round(prep["retrieve_ms"] + prep["rerank_ms"] + generate_ms, 1),
            },
            "prompt_tokens": stats.get("prompt_tokens"),
            "output_tokens": stats.get("output_tokens"),
            "tokens_per_s": round(stats["tokens_per_s"], 1) if stats.get("tokens_per_s") else None,
        }

    def answer(self, question, year_from=None):
        prep = self.prepare(question, year_from)
        t0 = time.perf_counter()
        out = chat_full(prep["prompt"], system=SYSTEM_PROMPT, temperature=0.1, model=self.model)
        return self.finish(prep, out["content"], out, (time.perf_counter() - t0) * 1000)

    def stream(self, question, year_from=None):
        """Yield ("sources", [...]) first, then ("token", text) pieces, then ("done", result)."""
        prep = self.prepare(question, year_from)
        yield "sources", prep["sources"]
        t0 = time.perf_counter()
        parts, stats = [], {}
        for kind, value in chat_stream(prep["prompt"], system=SYSTEM_PROMPT,
                                       temperature=0.1, model=self.model):
            if kind == "token":
                parts.append(value)
                yield "token", value
            else:
                stats = value
        yield "done", self.finish(prep, "".join(parts), stats, (time.perf_counter() - t0) * 1000)