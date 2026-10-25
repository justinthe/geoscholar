"""Section-aware chunking with token-based sizes and overlap.

Rules:
1. Never mix two sections in one chunk (a chunk should be about one thing).
2. Prefer to break at paragraph boundaries, then sentences, then words.
3. Repeat the last ~CHUNK_OVERLAP tokens of a chunk at the start of the next,
   so a fact that straddles a boundary is still retrievable.
"""
import re

from geoscholar import config

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def word_count(text):
    """Rough stand-in for a tokenizer (used in tests). Real runs pass a tokenizer."""
    return len(text.split())


def _units(text, max_tokens, count):
    """Split text into pieces that each fit in max_tokens: paragraphs > sentences > words."""
    units = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if count(para) <= max_tokens:
            units.append(para)
            continue
        for sent in SENTENCE_SPLIT.split(para):
            if count(sent) <= max_tokens:
                units.append(sent)
            else:                                    # a monster sentence: cut by words
                words, piece = sent.split(), []
                for w in words:
                    if piece and count(" ".join(piece + [w])) > max_tokens:
                        units.append(" ".join(piece))
                        piece = []
                    piece.append(w)
                if piece:
                    units.append(" ".join(piece))
    return units


def chunk_section(text, max_tokens, overlap, count):
    units = _units(text, max_tokens, count)
    sizes = [count(u) for u in units]
    chunks, current, current_sizes = [], [], []
    for unit, size in zip(units, sizes):
        if current and sum(current_sizes) + size > max_tokens:
            chunks.append(" ".join(current))
            # carry trailing units into the next chunk as overlap
            carry, carry_sizes = [], []
            for u, s in zip(reversed(current), reversed(current_sizes)):
                if sum(carry_sizes) + s > overlap:
                    break
                carry.insert(0, u)
                carry_sizes.insert(0, s)
            current, current_sizes = carry, carry_sizes
            # if overlap + new unit is still too big, drop the overlap
            if sum(current_sizes) + size > max_tokens:
                current, current_sizes = [], []
        current.append(unit)
        current_sizes.append(size)
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_paper(paper, sections, max_tokens=config.CHUNK_TOKENS,
                overlap=config.CHUNK_OVERLAP, count=word_count):
    """paper: a row/dict with id, title, year. Returns a list of chunk dicts."""
    out = []
    for sec in sections:
        for body in chunk_section(sec["text"], max_tokens, overlap, count):
            idx = len(out)
            out.append({
                "chunk_id": f"{paper['id']}:{idx}",
                "paper_id": paper["id"],
                "chunk_index": idx,
                "title": paper["title"],
                "year": paper["year"],
                "section": sec["heading"],
                "text": body,
                # what actually gets embedded: a small header gives each chunk context
                "embed_text": f"{paper['title']}\nSection: {sec['heading']}\n\n{body}",
                "n_tokens": count(body),
            })
    return out