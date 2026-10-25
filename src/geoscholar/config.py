"""Central settings. Change values here, not scattered through the code.

A few settings can be overridden with environment variables, so experiments
don't require editing this file (e.g. GEOSCHOLAR_CHUNK_TOKENS=500).
"""
import os
from pathlib import Path

# Project root = two folders above this file (src/geoscholar/config.py -> project root)
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
TEI_DIR = DATA_DIR / "tei"          # GROBID output (XML), cached so we parse each PDF once
DB_PATH = DATA_DIR / "papers.db"
LOG_DIR = ROOT / "logs"
EVAL_DIR = ROOT / "eval"

# arXiv
ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_TOPICS = [
    "remote sensing",
    "synthetic aperture radar",
    "hyperspectral",
    "land cover",
    "change detection",
    "satellite imagery",
]
ARXIV_CATEGORIES = ["cs.CV", "eess.IV"]
TARGET_PAPERS = 400
ARXIV_DELAY_S = 3.0                 # pause between arXiv requests (be polite)
USER_AGENT = "geoscholar-learning-project (personal research tool)"

# Services
GROBID_URL = "http://localhost:8070"
QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = os.environ.get("GEOSCHOLAR_LLM", "llama3.1:8b")   # exact name from `ollama list`

# Embeddings and chunking
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
CHUNK_TOKENS = int(os.environ.get("GEOSCHOLAR_CHUNK_TOKENS", "300"))
CHUNK_OVERLAP = int(os.environ.get("GEOSCHOLAR_CHUNK_OVERLAP", "50"))
COLLECTION = f"papers_c{CHUNK_TOKENS}"

# Retrieval
RERANK_MODEL = "BAAI/bge-reranker-base"
CANDIDATES = 30                     # how many chunks each retriever passes to fusion / reranking
RRF_K = 60                          # standard constant in reciprocal rank fusion


# Answering (set the first three from your week 3 decision in docs/decisions.md)
RETRIEVAL_MODE = "hybrid"           # "dense", "bm25" or "hybrid"
USE_RERANK = True
TOP_K = 5                           # passages given to the LLM
CONTEXT_ORDER = "relevance"         # "relevance" or "sandwich"
MAX_CONTEXT_TOKENS = 3000           # rough budget for all passages together
LLM_NUM_CTX = 8192                  # Ollama context window; too small silently cuts the prompt
JUDGE_MODEL = os.environ.get("GEOSCHOLAR_JUDGE", LLM_MODEL)