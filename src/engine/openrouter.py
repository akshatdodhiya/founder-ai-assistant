import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import TypeVar

from dotenv import load_dotenv

T = TypeVar("T")
_TIMEOUT_SECONDS = 30
_DETAIL_LIMIT = 300


class MissingAPIKeyError(Exception):
    """OPENROUTER_API_KEY is not set."""


class TransportError(Exception):
    """An OpenRouter call failed in a way that is retried once."""


def require_key(api_key: str | None) -> str:
    if api_key is None or api_key == "":
        raise MissingAPIKeyError("OPENROUTER_API_KEY is not set")
    return api_key


def key_from_env() -> str:
    load_dotenv()
    return require_key(os.getenv("OPENROUTER_API_KEY"))


def post_json(url: str, api_key: str, payload: dict, *, label: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except TimeoutError as exc:
        raise TransportError(f"{label} timed out") from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise TransportError(f"{label} rate limited") from exc
        detail = exc.read().decode("utf-8", errors="replace")[:_DETAIL_LIMIT]
        raise TransportError(f"{label} HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise TransportError(f"{label} request failed") from exc


def retry_once(
    call: Callable[[], T],
    sleep: Callable[[float], None],
    failure: Callable[[str], Exception],
    message: str,
) -> T:
    try:
        return call()
    except TransportError:
        sleep(1)
    try:
        return call()
    except TransportError as exc:
        raise failure(message) from exc
