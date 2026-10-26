"""Central settings.

Every setting that differs between machines or runs can be overridden with an
environment variable named GEOSCHOLAR_<NAME>. For local development, put them in a
.env file in the project root (see .env.example); inside Docker, Compose sets them.
"""
import os
from pathlib import Path

ROOT = Path(os.environ.get("GEOSCHOLAR_ROOT", Path(__file__).resolve().parents[2]))

try:                                   # optional: load ROOT/.env for local development
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)    # real environment variables win
except ImportError:
    pass


def env_str(name, default):
    return os.environ.get(f"GEOSCHOLAR_{name}", default)


def env_int(name, default):
    return int(env_str(name, str(default)))


def env_bool(name, default):
    return env_str(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


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
TARGET_PAPERS = env_int("TARGET_PAPERS", 400)
ARXIV_DELAY_S = 3.0                 # pause between arXiv requests (be polite)
USER_AGENT = "geoscholar-learning-project (personal research tool)"

# Services
GROBID_URL = env_str("GROBID_URL", "http://localhost:8070")
QDRANT_URL = env_str("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = env_str("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = env_str("LLM", "llama3.1:8b")             # exact name from `ollama list`

# Embeddings and chunking
EMBED_MODEL = env_str("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIM = 384
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
CHUNK_TOKENS = env_int("CHUNK_TOKENS", 300)
CHUNK_OVERLAP = env_int("CHUNK_OVERLAP", 50)
COLLECTION = f"papers_c{CHUNK_TOKENS}"

# Retrieval
RERANK_MODEL = env_str("RERANK_MODEL", "BAAI/bge-reranker-base")
CANDIDATES = 30                     # how many chunks each retriever passes to fusion / reranking
RRF_K = 60                          # standard constant in reciprocal rank fusion

# Answering (defaults from your week 3 and 4 decisions)
RETRIEVAL_MODE = env_str("RETRIEVAL_MODE", "hybrid")    # "dense", "bm25" or "hybrid"
USE_RERANK = env_bool("USE_RERANK", True)
TOP_K = env_int("TOP_K", 5)                             # passages given to the LLM
CONTEXT_ORDER = env_str("CONTEXT_ORDER", "relevance")   # "relevance" or "sandwich"
MAX_CONTEXT_TOKENS = env_int("MAX_CONTEXT_TOKENS", 3000)
LLM_NUM_CTX = env_int("LLM_NUM_CTX", 8192)  # Ollama context window; too small silently cuts the prompt
JUDGE_MODEL = env_str("JUDGE", LLM_MODEL)