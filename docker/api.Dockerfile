FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GEOSCHOLAR_ROOT=/app
WORKDIR /app

# 1. torch first: the biggest, slowest layer, and it rarely changes, so Docker caches it.
#    CPU build by default; docker-compose.gpu.yml switches this to a CUDA build.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install torch --index-url ${TORCH_INDEX_URL}

# 2. the other libraries
COPY requirements-app.txt .
RUN pip install -r requirements-app.txt

# 3. our code last: it changes most often, so only these layers rebuild on edits
COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-deps -e .

EXPOSE 8000
CMD ["uvicorn", "geoscholar.api:app", "--host", "0.0.0.0", "--port", "8000"]