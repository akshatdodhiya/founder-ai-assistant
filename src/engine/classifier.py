import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from dotenv import load_dotenv

_SYSTEMONE_URL = "https://openrouter.ai/api/v1/systemone"
_MODEL = "typesafe/jev-1.13"
_QUESTIONS = {
    "intent": {
        "type": "choice",
        "instructions": "What is the founder asking for?",
        "criteria": {
            "focus_today": "What to focus on today, including meetings and urgent email.",
            "follow_ups": "Missing follow-ups or replies still owed.",
            "repeated_customer": "Customer issues that show up more than once.",
            "next_meeting": "The next meeting on the calendar.",
            "general": "Any other question about calendar or email.",
        },
    },
    "window": {
        "type": "choice",
        "instructions": "Which time window does the question name? Choose none if it names none.",
        "criteria": {
            "today": "Today.",
            "yesterday": "Yesterday.",
            "tomorrow": "Tomorrow.",
            "this_week": "This week.",
            "next_meeting": "The next meeting, with no other day named.",
            "none": "No time window is named.",
        },
    },
}


class MissingAPIKeyError(Exception):
    """OPENROUTER_API_KEY is not set."""


class ClassifierTransportError(Exception):
    """The classifier call timed out or was rate limited."""


@dataclass(frozen=True)
class Classification:
    intent: str
    window: str


def _post_systemone(api_key: str, payload: dict) -> dict:
    request = urllib.request.Request(
        _SYSTEMONE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except TimeoutError as exc:
        raise ClassifierTransportError("classifier timed out") from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise ClassifierTransportError("classifier rate limited") from exc
        raise ClassifierTransportError(f"classifier HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ClassifierTransportError("classifier request failed") from exc


class JevClassifier:
    def __init__(self, api_key: str | None, post: Callable[[str, dict], dict] | None = None) -> None:
        if api_key is None or api_key == "":
            raise MissingAPIKeyError("OPENROUTER_API_KEY is not set")
        self._api_key = api_key
        self._post = post or _post_systemone

    @classmethod
    def from_env(cls) -> "JevClassifier":
        load_dotenv()
        return cls(os.getenv("OPENROUTER_API_KEY"))

    def classify(self, query: str) -> Classification:
        body = self._post(
            self._api_key,
            {"model": _MODEL, "state": query, "questions": _QUESTIONS},
        )
        answers = body.get("answers")
        if not isinstance(answers, dict):
            raise ClassifierTransportError("classifier response has no answers")
        return Classification(
            intent=_choice(answers, "intent"),
            window=_choice(answers, "window"),
        )


def _choice(answers: dict, name: str) -> str:
    answer = answers.get(name)
    if not isinstance(answer, dict):
        raise ClassifierTransportError(f"classifier response missing {name}")
    choice = answer.get("choice")
    if not isinstance(choice, str) or choice == "":
        raise ClassifierTransportError(f"classifier response missing {name} choice")
    return choice
