from collections.abc import Callable
from dataclasses import dataclass

from pydantic import SecretStr

from src.engine.openrouter import ResponseError, key_from_env, post_json, require_key

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


@dataclass(frozen=True)
class Classification:
    intent: str
    window: str


def _post_systemone(api_key: SecretStr, payload: dict) -> dict:
    return post_json(_SYSTEMONE_URL, api_key, payload, label="classifier")


class JevClassifier:
    def __init__(self, api_key: str | None, post: Callable[[SecretStr, dict], dict] | None = None) -> None:
        self._api_key = require_key(api_key)
        self._post = post or _post_systemone

    @classmethod
    def from_env(cls) -> "JevClassifier":
        return cls(key_from_env())

    def classify(self, query: str) -> Classification:
        body = self._post(
            self._api_key,
            {"model": _MODEL, "state": query, "questions": _QUESTIONS},
        )
        answers = body.get("answers") if isinstance(body, dict) else None
        if not isinstance(answers, dict):
            raise ResponseError("classifier response has no answers")
        return Classification(
            intent=_choice(answers, "intent"),
            window=_choice(answers, "window"),
        )


def _choice(answers: dict, name: str) -> str:
    answer = answers.get(name)
    if not isinstance(answer, dict):
        raise ResponseError(f"classifier response missing {name}")
    choice = answer.get("choice")
    if not isinstance(choice, str) or choice == "":
        raise ResponseError(f"classifier response missing {name} choice")
    return choice
