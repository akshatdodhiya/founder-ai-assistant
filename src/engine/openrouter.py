import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import TypeVar

from dotenv import load_dotenv
from pydantic import SecretStr

T = TypeVar("T")
_TIMEOUT_SECONDS = 30
_DETAIL_LIMIT = 300


class MissingAPIKeyError(Exception):
    """OPENROUTER_API_KEY is not set."""


class TransportError(Exception):
    """An OpenRouter call timed out or was rate limited. Retried once."""


class ResponseError(Exception):
    """An OpenRouter call failed in a way that retrying cannot fix."""


def require_key(api_key: str | None) -> SecretStr:
    if api_key is None or api_key == "":
        raise MissingAPIKeyError("OPENROUTER_API_KEY is not set")
    return SecretStr(api_key)


def key_from_env() -> str | None:
    load_dotenv()
    return os.getenv("OPENROUTER_API_KEY")


def post_json(url: str, api_key: SecretStr, payload: dict, *, label: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key.get_secret_value()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            body = json.load(response)
    except TimeoutError as exc:
        raise TransportError(f"{label} timed out") from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise TransportError(f"{label} rate limited") from exc
        detail = exc.read().decode("utf-8", errors="replace")[:_DETAIL_LIMIT]
        raise ResponseError(f"{label} HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TransportError(f"{label} timed out") from exc
        raise ResponseError(f"{label} request failed") from exc
    except ValueError as exc:
        raise ResponseError(f"{label} response is not JSON") from exc
    if not isinstance(body, dict):
        raise ResponseError(f"{label} response is not a JSON object")
    return body


def retry_once(
    call: Callable[[], T],
    sleep: Callable[[float], None],
    failure: Callable[[str], Exception],
    label: str,
) -> T:
    try:
        return call()
    except TransportError:
        sleep(1)
    except ResponseError as exc:
        raise failure(f"{label} failed: {exc}") from exc
    try:
        return call()
    except TransportError as exc:
        raise failure(f"{label} failed after one retry") from exc
    except ResponseError as exc:
        raise failure(f"{label} failed: {exc}") from exc
