"""Central settings. Change values here, not scattered through the code."""
from pathlib import Path

# Project root = two folders above this file (src/geoscholar/config.py -> project root)
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
TEI_DIR = DATA_DIR / "tei"          # GROBID output (XML), cached so we parse each PDF once
DB_PATH = DATA_DIR / "papers.db"
LOG_DIR = ROOT / "logs"

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

# Services (running in Docker)
GROBID_URL = "http://localhost:8070"
QDRANT_URL = "http://localhost:6333"

# Embeddings and chunking
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
CHUNK_TOKENS = 300                  # target chunk size in model tokens
CHUNK_OVERLAP = 50                  # tokens repeated between neighbouring chunks
COLLECTION = f"papers_c{CHUNK_TOKENS}"