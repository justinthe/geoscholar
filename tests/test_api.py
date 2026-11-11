from fastapi.testclient import TestClient

from geoscholar import api, config


class FakeIndex:
    def __init__(self, ok=True):
        self.ok = ok

    def count(self):
        if not self.ok:
            raise RuntimeError("down")
        return 3


class FakePipeline:
    def __init__(self, ok=True, refused=False):
        self.retriever = type("R", (), {"index": FakeIndex(ok)})()
        self.refused = refused

    def answer(self, question, year_from=None):
        return {"question": question, "answer": "a", "answer_display": "a", "refused": self.refused,
                "cited": [], "invalid_citations": [], "sources": [],
                "timings_ms": {"retrieve": 1.0, "total": 2.0}, "prompt_tokens": None,
                "output_tokens": 5, "tokens_per_s": None}


def client(monkeypatch, ollama=True, **kw):
    monkeypatch.setattr(api, "ollama_ok", lambda: ollama)
    return TestClient(api.create_app(pipeline=FakePipeline(**kw)))


def test_health_and_ready(monkeypatch):
    with client(monkeypatch) as c:
        assert c.get("/health").json()["status"] == "ok"
        assert c.get("/ready").status_code == 200


def test_ready_503_names_failed_dependency(monkeypatch):
    with client(monkeypatch, ollama=False, ok=False) as c:
        r = c.get("/ready")
        assert r.status_code == 503 and r.json()["failed"] == ["qdrant", "ollama"]


def test_query_outcomes_and_metrics(monkeypatch):
    def n(outcome):
        return api.QUERIES.labels(outcome)._value.get()
    a, r = n("answered"), n("refused")
    with client(monkeypatch) as c:
        assert c.post("/query", json={"question": "what is sar"}).status_code == 200
    with client(monkeypatch, refused=True) as c:
        c.post("/query", json={"question": "what is sar"})
        text = c.get("/metrics").text
    assert (n("answered"), n("refused")) == (a + 1, r + 1)
    for name in ("geoscholar_http_request_duration_seconds", "geoscholar_stage_duration_seconds",
                 "geoscholar_queries_total", "geoscholar_tokens_total"):
        assert name in text
    assert 'route="/query"' in text


def test_ingest_disabled_returns_404(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_INGEST", False)
    with client(monkeypatch) as c:
        assert c.post("/ingest", json={}).status_code == 404
        assert c.get("/ingest/abc").status_code == 404
