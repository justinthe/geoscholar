# GeoScholar

Question answering with citations over arXiv papers on remote sensing and geospatial AI. You ask a question, the system retrieves passages from the indexed papers, and a local LLM writes an answer that cites them. It refuses when the retrieved passages do not support an answer.

Corpus: 405 papers indexed (count from the papers database; 1 additional paper failed ingestion and is not indexed).

## Architecture

```
Ingestion:  arXiv metadata -> PDF download -> GROBID (PDF to structured text)
            -> chunking (300 tokens, 50 overlap) -> embeddings -> Qdrant

Query:      UI (Streamlit) -> API (FastAPI) -> hybrid retrieval (dense + BM25)
            -> optional cross-encoder rerank -> top-k passages -> Ollama LLM
            -> answer with citations
```

- Embeddings: `BAAI/bge-small-en-v1.5`. Reranker: `BAAI/bge-reranker-base`. Both are downloaded from Hugging Face on first start.
- Defaults: retrieval mode `hybrid`, rerank on, top-k 5, LLM `llama3.1:8b`. All settings are `GEOSCHOLAR_*` environment variables, see `src/geoscholar/config.py` and `.env.example`.
- Local compose: qdrant, grobid, ollama, api, ui as containers.
- Production-shaped local setup (k3d): Qdrant, API and UI run in the cluster. Ollama stays outside the cluster, in the compose network, and uses the host GPU. Prometheus and Grafana run in the `monitoring` namespace.

## Quick start (docker compose)

```bash
cp .env.example .env            # optional, defaults work
docker compose up -d --build    # CPU only
# NVIDIA GPU:
# docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

First start pulls the LLM (`ollama-init` job) and downloads the embedding and reranker models; the API healthcheck allows up to 10 minutes for this.

```bash
curl localhost:8000/health
```

- UI: http://localhost:8501
- API docs: http://localhost:8000/docs

The Qdrant collection is empty until you ingest papers (or restore a snapshot of an existing one). Ingestion uses `scripts/ingest.py`, which needs GROBID (`docker compose up -d grobid qdrant`) and the package installed (`pip install -e .`):

```bash
python scripts/ingest.py --stage fetch
python scripts/ingest.py --stage download --limit 20
python scripts/ingest.py --stage index
python scripts/ingest.py --stage all
python scripts/ingest.py --status
```

The API also exposes `POST /ingest` and `GET /ingest/{job_id}` when `GEOSCHOLAR_ENABLE_INGEST` is true (the default in compose).

## Production-shaped local setup (k3d + OpenTofu + Helm)

Prerequisites: `docker`, `k3d`, `kubectl`, `helm`, `tofu` installed.

Ollama runs on the host through compose, so start it first. The k3d cluster joins the compose network and reaches it as `http://ollama:11434`.

```bash
docker compose up -d ollama qdrant
docker compose exec ollama ollama pull llama3.1:8b   # once; the local platform uses this model
```

Create the cluster and deploy the platform (Qdrant, API, UI, monitoring):

```bash
make up
```

Port-forward the services (runs until interrupted):

```bash
make pf
```

| Service | URL |
|---|---|
| API | http://localhost:18000 |
| UI | http://localhost:18501 |
| Grafana | http://localhost:13000 |

Tear down (best-effort platform destroy, then cluster delete):

```bash
make down
```

Redeploy with a specific image tag (default `latest`):

```bash
make deploy TAG=sha-<git sha>
```

Image repositories default to `ghcr.io/OWNER/geoscholar-{api,ui}` in `infra/platform/variables.tf` and `charts/geoscholar/values.yaml`. Override `api_image_repository` and `ui_image_repository` for a real registry.

The kubeconfig is written to `infra/cluster-local/.state/kubeconfig`; the Makefile exports it as `KUBECONFIG`.

### Models: local vs CI

- Local platform: `llama3.1:8b` (`llm_model` in `infra/platform/variables.tf`).
- CI and the chart default: `qwen2.5:0.5b` (`GEOSCHOLAR_LLM` in `charts/geoscholar/values.yaml`). It is small enough to pull and run on a CPU-only GitHub runner. Answer quality is not comparable to the 8B model.

## Data load

The cluster Qdrant starts empty. `scripts/snapshot.sh` snapshots collection `papers_c300` from compose Qdrant (`127.0.0.1:6333`), uploads it to the cluster Qdrant through a temporary port-forward, checks the point counts match, and restarts the API (BM25 is built at startup). Compose Qdrant must be running and the cluster must be up.

```bash
scripts/snapshot.sh
# other collection:
COLLECTION=<name> scripts/snapshot.sh
```

Snapshots are saved under `data/snapshots/`. Re-running overwrites the cluster collection.

## Tests

```bash
pip install -r requirements-dev.txt -r requirements-app.txt
pip install --no-deps -e .
pytest -q
```

Tests use fakes and do not need torch. `sentence-transformers` (which pulls torch) is imported lazily, so CI installs `requirements-app.txt` without it. To skip it locally, filter that line out:

```bash
grep -v '^sentence-transformers' requirements-app.txt > /tmp/req-ci.txt
pip install -r /tmp/req-ci.txt -r requirements-dev.txt
```

## CI/CD

`.github/workflows/ci.yml`, Python 3.12.

| Job | Trigger | What it does |
|---|---|---|
| `test` | PR to main, push to main | Installs deps without sentence-transformers, runs `pytest -q`. |
| `build` | PR only, after `test` | Builds the API and UI images (`docker/api.Dockerfile`, `docker/ui.Dockerfile`) without pushing. |
| `push` | Push to main only, after `test` | Builds and pushes both images to GHCR as `ghcr.io/justinthe/geoscholar-{api,ui}:sha-<commit sha>` and `:latest`. |

One-time manual step: GHCR packages are created private. After the first push, open each package (`geoscholar-api`, `geoscholar-ui`) on GitHub, Package settings, and change visibility to public so a cluster can pull without credentials.

## Load test

k6 (run through the `grafana/k6` container) sends questions from `eval/questions.jsonl` and `eval/questions_manual.jsonl` to `/query` on `localhost:18000`. Requires the platform up and `make pf` running, plus the data loaded.

```bash
make load            # baseline: 1 VU, 5 min
make load-headline   # 4 VUs, 10 min
```

Results are written to `eval/results/load_*.json` (gitignored). The script is `load/query.js`.

Measured 2026-11-11 on an RTX 3060 12 GB, model `llama3.1:8b`, hybrid retrieval with rerank, through the k3d topology above. These are HTTP-level numbers (client to API, including retrieval and generation):

| Scenario | p50 | p95 | Throughput | HTTP failures | Refusals |
|---|---|---|---|---|---|
| baseline, 1 VU, 5 min | 7.9 s | 9.7 s | 0.13 req/s | 0 | 1 of 38 |
| headline, 4 VUs, 10 min | 16.4 s | 19.3 s | 0.24 req/s | 0 | 9 of 150 |

Going from 1 to 4 VUs roughly doubles throughput and doubles latency; requests queue behind the GPU (see limits).

## Known limits

- Ollama serializes requests on one GPU. Concurrency adds queueing latency, not throughput.
- `/ingest` is disabled in the cluster (`GEOSCHOLAR_ENABLE_INGEST: "false"`); the cluster has no GROBID or `data/`. Ingest locally and load with `scripts/snapshot.sh`.
- No authentication on `/query` or `/ingest`. Keep the API service `ClusterIP` and reach it by port-forward only.
- The API runs as a single replica: ingest job state and the BM25 index are in memory, and the HF cache is a ReadWriteOnce volume.
- The cloud demo is not done. Only the local k3d setup is working.

## Repo layout

```
src/geoscholar/    package: config, db, ingest pipeline, retrieval, rag, llm, api, evaluation
ui/                Streamlit app
scripts/           ingest.py, eval/judging scripts, snapshot.sh
tests/             pytest suite (API, HTTP helper)
eval/              question sets, eval and load results (results/ gitignored in part)
load/              k6 load script (query.js)
docker/            api.Dockerfile, ui.Dockerfile
charts/geoscholar/ Helm chart (API, UI, Qdrant, optional in-cluster Ollama, ServiceMonitor)
infra/             OpenTofu: cluster-local (k3d cluster), platform (Helm releases, monitoring)
.github/workflows/ CI: test, build, push to GHCR
notebooks/         exploration notebooks for each project week
lessons/           notes on findings (chunking, eval, GPU, GROBID vs PyMuPDF, ...)
docs/              figures
article-draft/     article draft
data/              papers database, PDFs, GROBID cache, snapshots (local, not for git)
```

## License

License: to be added
