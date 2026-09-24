import io
import urllib.error

import pytest
from pydantic import SecretStr

from src.engine.openrouter import (
    MissingAPIKeyError,
    ResponseError,
    TransportError,
    post_json,
    require_key,
    retry_once,
)

URL = "https://openrouter.ai/api/v1/chat/completions"
KEY = SecretStr("sk-test-secret")


class Failure(Exception):
    pass


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, outcome: object) -> None:
    def fake_urlopen(request: object, timeout: float) -> io.BytesIO:
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, bytes)
        return io.BytesIO(outcome)

    monkeypatch.setattr("src.engine.openrouter.urllib.request.urlopen", fake_urlopen)


def _http_error(code: int, body: bytes = b"{}") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "error", None, io.BytesIO(body))  # type: ignore[arg-type]


def test_require_key_hides_the_value() -> None:
    key = require_key("sk-test-secret")

    assert key.get_secret_value() == "sk-test-secret"
    assert "sk-test-secret" not in repr(key)
    assert "sk-test-secret" not in str(key)


def test_require_key_rejects_missing_key() -> None:
    with pytest.raises(MissingAPIKeyError):
        require_key("")


def test_post_json_returns_object(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(monkeypatch, b'{"choices": []}')

    assert post_json(URL, KEY, {}, label="chat") == {"choices": []}


@pytest.mark.parametrize(
    "outcome",
    [
        _http_error(429),
        TimeoutError("slow"),
        urllib.error.URLError(TimeoutError("connect timed out")),
    ],
)
def test_timeouts_and_rate_limits_are_retryable(monkeypatch: pytest.MonkeyPatch, outcome: BaseException) -> None:
    _patch_urlopen(monkeypatch, outcome)

    with pytest.raises(TransportError):
        post_json(URL, KEY, {}, label="chat")


@pytest.mark.parametrize(
    "outcome",
    [
        _http_error(401),
        _http_error(404, b'{"error": {"message": "blocked by guardrail"}}'),
        _http_error(500),
        urllib.error.URLError(ConnectionRefusedError("refused")),
        b"not json",
        b"[1, 2, 3]",
    ],
)
def test_other_failures_are_not_retryable(monkeypatch: pytest.MonkeyPatch, outcome: object) -> None:
    _patch_urlopen(monkeypatch, outcome)

    with pytest.raises(ResponseError):
        post_json(URL, KEY, {}, label="chat")


def test_http_error_detail_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_urlopen(monkeypatch, _http_error(404, b"x" * 1000))

    with pytest.raises(ResponseError) as caught:
        post_json(URL, KEY, {}, label="chat")

    assert "chat HTTP 404" in str(caught.value)
    assert len(str(caught.value)) < 400


def test_retry_once_retries_a_transport_error() -> None:
    results: list[object] = [TransportError("429"), "ok"]
    sleeps: list[float] = []

    def call() -> str:
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return str(result)

    assert retry_once(call, sleeps.append, Failure, "chat") == "ok"
    assert sleeps == [1]


def test_retry_once_gives_up_after_two_transport_errors() -> None:
    calls = {"n": 0}

    def call() -> str:
        calls["n"] += 1
        raise TransportError("429")

    with pytest.raises(Failure, match="chat failed after one retry"):
        retry_once(call, lambda _seconds: None, Failure, "chat")

    assert calls["n"] == 2


def test_retry_once_does_not_retry_a_response_error() -> None:
    calls = {"n": 0}
    sleeps: list[float] = []

    def call() -> str:
        calls["n"] += 1
        raise ResponseError("chat HTTP 404: blocked by guardrail")

    with pytest.raises(Failure, match="blocked by guardrail"):
        retry_once(call, sleeps.append, Failure, "chat")

    assert calls["n"] == 1
    assert sleeps == []
