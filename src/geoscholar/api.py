"""GeoScholar HTTP API.

    uvicorn geoscholar.api:app --host 0.0.0.0 --port 8000

Endpoints
    GET  /health              is the service ready? Qdrant and Ollama status, chunk count
    POST /query               answer a question (whole answer at once, JSON)
    POST /query/stream        answer a question as Server-Sent Events: sources, tokens, done
    POST /ingest              start a background ingestion job (fetch, download, index)
    GET  /ingest/{job_id}     progress of an ingestion job
Interactive docs: http://localhost:8000/docs
"""
import json
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from geoscholar import config, db
from geoscholar.llm import ollama_ok

log = logging.getLogger("api")


# ---------- request and response shapes (these also generate the /docs page) ----------

class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    year_from: int | None = Field(default=None, ge=1990, le=2100)


class Source(BaseModel):
    n: int
    paper_id: str
    title: str
    year: int | None
    section: str
    text: str
    score: float
    url: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    answer_display: str
    refused: bool
    cited: list[int]
    invalid_citations: list[int]
    sources: list[Source]
    timings_ms: dict[str, float]
    prompt_tokens: int | None
    output_tokens: int | None
    tokens_per_s: float | None


class IngestRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=500, description="number of new papers to fetch")
    use_grobid: bool = True


def with_urls(result):
    for s in result["sources"]:
        s["url"] = f"https://arxiv.org/abs/{s['paper_id']}"
    return result


# ---------- building the pipeline once, at startup ----------

def build_pipeline(retries=30, delay=2.0):
    """Load the models and connect to Qdrant, retrying while Qdrant is still starting."""
    from geoscholar.index import Embedder, Index
    from geoscholar.rag import RAGPipeline
    from geoscholar.retrieval import Reranker, Retriever

    embedder = Embedder()
    reranker = Reranker() if config.USE_RERANK else None
    for attempt in range(1, retries + 1):
        try:
            index = Index(embedder)
            index.ensure_collection()
            retriever = Retriever(index, reranker=reranker)
            return RAGPipeline(retriever)
        except Exception as exc:
            log.warning("Qdrant not ready (attempt %d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to Qdrant at {config.QDRANT_URL}")


def refresh_retriever(pipeline):
    """Rebuild the retriever so BM25 sees newly ingested chunks."""
    from geoscholar.retrieval import Retriever
    old = pipeline.retriever
    pipeline.retriever = Retriever(old.index, reranker=old.reranker)


def create_app(pipeline=None):
    """pipeline=None loads the real models at startup; tests pass a fake one."""

    @asynccontextmanager
    async def lifespan(app):
        app.state.pipeline = pipeline or build_pipeline()
        app.state.jobs = {}
        app.state.job_lock = threading.Lock()
        yield

    app = FastAPI(title="GeoScholar", version="0.1.0", lifespan=lifespan,
                  description="Question answering over remote sensing papers, with citations.")

    @app.get("/health")
    def health():
        p = app.state.pipeline
        try:
            chunks, qdrant = p.retriever.index.count(), True
        except Exception:
            chunks, qdrant = None, False
        ollama = ollama_ok()
        return {"status": "ok" if qdrant and ollama else "degraded", "qdrant": qdrant,
                "ollama": ollama, "llm": config.LLM_MODEL, "collection": config.COLLECTION,
                "chunks": chunks}

    # plain `def` (not async): FastAPI runs these in a thread pool, so slow model
    # calls don't block other requests
    @app.post("/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        try:
            return with_urls(app.state.pipeline.answer(req.question, year_from=req.year_from))
        except RuntimeError as exc:                     # e.g. Ollama down or model missing
            raise HTTPException(status_code=503, detail=str(exc))

    @app.post("/query/stream")
    def query_stream(req: QueryRequest):
        def events():
            try:
                for kind, value in app.state.pipeline.stream(req.question, year_from=req.year_from):
                    if kind == "sources":
                        data = with_urls({"sources": value})["sources"]
                    elif kind == "token":
                        data = {"text": value}
                    else:
                        data = with_urls(value)
                    yield f"event: {kind}\ndata: {json.dumps(data)}\n\n"
            except Exception as exc:
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/ingest", status_code=202)
    def start_ingest(req: IngestRequest):
        with app.state.job_lock:
            if any(j["status"] == "running" for j in app.state.jobs.values()):
                raise HTTPException(status_code=409, detail="An ingestion job is already running")
            job_id = uuid.uuid4().hex[:8]
            job = {"id": job_id, "status": "running", "stage": "starting", "done": 0, "total": None,
                   "limit": req.limit, "result": None, "error": None}
            app.state.jobs[job_id] = job
        threading.Thread(target=run_ingest_job, args=(app, job, req), daemon=True).start()
        return {"job_id": job_id}

    @app.get("/ingest/{job_id}")
    def ingest_status(job_id: str):
        job = app.state.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Unknown job")
        return job

    return app


def run_ingest_job(app, job, req):
    # from geoscholar.ingest import pipeline as ingest

    def progress(stage, done, total):
        job.update(stage=stage, done=done, total=total)

    try:
        from geoscholar.ingest import pipeline as ingest
        conn = db.connect()                       # SQLite connections can't cross threads
        embedder = getattr(app.state.pipeline.retriever.index, "embedder", None)
        job["result"] = ingest.run(conn, limit=req.limit, use_grobid=req.use_grobid,
                                   embedder=embedder, progress=progress)
        job["stage"] = "refreshing search index"
        refresh_retriever(app.state.pipeline)
        job["status"] = "finished"
    except Exception as exc:
        log.exception("ingest job failed")
        job.update(status="failed", error=str(exc))


app = create_app()