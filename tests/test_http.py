import pytest
import requests

from geoscholar import http


class FakeResp:
    def __init__(self, status, headers=None):
        self.status_code, self.headers = status, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def test_retries_rate_limit_then_succeeds(monkeypatch):
    replies = iter([FakeResp(429, {"Retry-After": "7"}), FakeResp(503), FakeResp(200)])
    waits = []
    monkeypatch.setattr(http.requests, "get", lambda *a, **k: next(replies))
    monkeypatch.setattr(http.time, "sleep", waits.append)
    assert http.polite_get("https://example.org", base_delay=10).status_code == 200
    assert waits == [7.0, 20.0]          # Retry-After honoured, then exponential backoff


def test_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(http.requests, "get", lambda *a, **k: FakeResp(429))
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(requests.HTTPError):
        http.polite_get("https://example.org", retries=2)


def test_other_errors_fail_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(http.requests, "get", lambda *a, **k: calls.append(1) or FakeResp(404))
    with pytest.raises(requests.HTTPError):
        http.polite_get("https://example.org")
    assert len(calls) == 1