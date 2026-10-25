"""Turn PDFs into a list of sections: [{"heading": ..., "text": ...}, ...].

Primary parser: GROBID (understands scientific papers: title, abstract, sections,
references). Fallback: PyMuPDF plain text, used when GROBID fails.
"""
import logging
import re
import xml.etree.ElementTree as ET

import pymupdf
import requests

from geoscholar import config

log = logging.getLogger(__name__)
NS = {"tei": "http://www.tei-c.org/ns/1.0"}
MIN_SECTION_CHARS = 200           # drop tiny fragments (captions, stray lines)


def _text(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


# ---------- GROBID ----------

def grobid_tei(pdf_path, paper_id):
    """Return GROBID's TEI XML for a PDF, using a cached copy if present."""
    config.TEI_DIR.mkdir(parents=True, exist_ok=True)
    cache = config.TEI_DIR / f"{paper_id.replace('/', '_')}.tei.xml"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    with open(pdf_path, "rb") as f:
        resp = requests.post(f"{config.GROBID_URL}/api/processFulltextDocument",
                             files={"input": f}, timeout=300)
    resp.raise_for_status()
    cache.write_text(resp.text, encoding="utf-8")
    return resp.text


def sections_from_tei(tei_xml):
    root = ET.fromstring(tei_xml)
    sections = []
    abstract = _text(root.find(".//tei:profileDesc/tei:abstract", NS))
    if abstract:
        sections.append({"heading": "Abstract", "text": abstract})
    body = root.find(".//tei:text/tei:body", NS)
    if body is None:
        return sections
    for div in body.findall("tei:div", NS):
        head = div.find("tei:head", NS)
        heading = _text(head) or "Untitled section"
        if head is not None and head.get("n"):
            heading = f"{head.get('n')} {heading}"          # e.g. "3.2 Dataset"
        paragraphs = [_text(p) for p in div.findall("tei:p", NS)]
        text = "\n\n".join(p for p in paragraphs if p)
        if len(text) >= MIN_SECTION_CHARS:
            sections.append({"heading": heading, "text": text})
    return sections


# ---------- PyMuPDF fallback ----------

def sections_from_pymupdf(pdf_path):
    with pymupdf.open(pdf_path) as doc:
        text = "\n".join(page.get_text() for page in doc)
    # Cut the reference list: everything after the last line that is just "References"
    matches = list(re.finditer(r"\n\s*(References|REFERENCES|Bibliography)\s*\n", text))
    if matches:
        text = text[: matches[-1].start()]
    text = re.sub(r"-\n(\w)", r"\1", text)          # re-join words hyphenated at line ends
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    text = "\n\n".join(p for p in paragraphs if len(p) > 40)
    return [{"heading": "Full text", "text": text}] if text else []


# ---------- entry point ----------

def parse_pdf(pdf_path, paper_id, use_grobid=True):
    """Returns (sections, parser_name). Raises if both parsers fail."""
    if use_grobid:
        try:
            sections = sections_from_tei(grobid_tei(pdf_path, paper_id))
            if len(sections) >= 2:                  # abstract + at least one body section
                return sections, "grobid"
            log.info("GROBID found too few sections for %s, falling back", paper_id)
        except Exception as exc:
            log.warning("GROBID failed for %s: %s", paper_id, exc)
    sections = sections_from_pymupdf(pdf_path)
    if not sections:
        raise ValueError("no text extracted (scanned PDF?)")
    return sections, "pymupdf"