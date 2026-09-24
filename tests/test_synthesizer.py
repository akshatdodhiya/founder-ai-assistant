from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.connectors import MockCalendarConnector, MockGmailConnector
from src.engine.classifier import JevClassifier
from src.engine.openrouter import MissingAPIKeyError, ResponseError, TransportError
from src.engine.router import Router
from src.engine.synthesizer import (
    FALLBACK,
    OpenRouterChat,
    SynthesisFailure,
    Synthesizer,
    build_prompt,
)
from src.models import ContextItem
from src.storage import ContextStore


class FakeChat:
    def __init__(self, results: list[str | Exception]) -> None:
        self._results = list(results)
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        self.prompts.append((system, user))
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _item(
    *,
    item_id: str,
    source: str,
    title: str,
    hour: int,
    content: str,
    sender: str | None = None,
) -> ContextItem:
    metadata: dict[str, str | int | bool] = {
        "source": source,
        "timestamp_epoch": int(datetime(2026, 9, 23, hour, tzinfo=timezone.utc).timestamp()),
    }
    if sender is not None:
        metadata["sender"] = sender
    return ContextItem(
        id=item_id,
        source=source,  # type: ignore[arg-type]
        timestamp=datetime(2026, 9, 23, hour, tzinfo=timezone.utc),
        title=title,
        content=content,
        metadata=metadata,
    )


def test_empty_context_skips_the_model() -> None:
    client = FakeChat(["should not be used"])

    text = Synthesizer(client, sleep=lambda _seconds: None).answer("What should I focus on today?", [])

    assert text == FALLBACK
    assert client.calls == 0


def test_prompt_lists_only_retrieved_items_in_time_order() -> None:
    later = _item(
        item_id="cal_002",
        source="calendar",
        title="Acme checkout call",
        hour=16,
        content="Meeting: Acme checkout call\nAttendees: Jordan Hale\nNotes: Hotfix timeline",
    )
    earlier = _item(
        item_id="email_205",
        source="email",
        title="Deck and August metrics before the partner meeting",
        hour=8,
        content="Subject: Deck and August metrics\nFrom: Maya Chen\n\nPlease send the deck.",
        sender="Maya Chen (Northstar Ventures)",
    )

    prompt = build_prompt("What should I focus on today?", [later, earlier])

    assert earlier.title in prompt
    assert later.title in prompt
    assert "Investor dinner" not in prompt
    assert prompt.index(earlier.title) < prompt.index(later.title)


def test_prompt_delimits_each_item() -> None:
    email = _item(
        item_id="email_203",
        source="email",
        title="Customers blocked on checkout before today's call",
        hour=12,
        content="Subject: Checkout\n\nThe retry failure is still live.",
        sender="Jordan Hale (Acme)",
    )
    meeting = _item(
        item_id="cal_001",
        source="calendar",
        title="Engineering standup",
        hour=13,
        content="Meeting: Engineering standup\nAttendees: Alex\nNotes: ",
    )

    prompt = build_prompt("What should I focus on today?", [email, meeting])

    assert "email_203" in prompt
    assert "source: email" in prompt
    assert email.timestamp.isoformat() in prompt
    assert f"<untrusted>\n{email.content}\n</untrusted>" in prompt
    assert "sender: Jordan Hale (Acme)" in prompt
    assert "cal_001" in prompt
    assert "source: calendar" in prompt
    assert meeting.timestamp.isoformat() in prompt
    assert f"<untrusted>\n{meeting.content}\n</untrusted>" in prompt
    assert "sender:" not in prompt.split("cal_001", 1)[1]


def test_model_text_is_unchanged() -> None:
    canned = "Send the deck [Email from Maya Chen (Northstar Ventures)]."
    client = FakeChat([canned])
    item = _item(
        item_id="email_205",
        source="email",
        title="Deck and August metrics before the partner meeting",
        hour=8,
        content="Please send the deck.",
        sender="Maya Chen (Northstar Ventures)",
    )

    text = Synthesizer(client, sleep=lambda _seconds: None).answer("What follow-ups am I missing?", [item])

    assert text == canned
    system, user = client.prompts[0]
    assert "Chief of Staff" in system
    assert "[Calendar: <title>]" in system
    assert "[Email from <sender>]" in system
    assert "using the title exactly" in system
    assert "using the sender line exactly" in system
    assert "Do not reproduce email headers" in system
    assert "do not quote the body" in system
    assert "no Markdown" in system
    assert "numbered list in time order" in system
    assert "13:00 UTC, Engineering standup" in system
    assert "one numbered item for every context item" in system
    assert "not a complete calendar or inbox" in system
    assert FALLBACK in system
    assert "<untrusted>" in system
    assert item.title in user


def test_chat_retries_once_then_succeeds() -> None:
    canned = "Standup at 13:00 [Calendar: Engineering standup]."
    client = FakeChat([TransportError("429"), canned])
    item = _item(
        item_id="cal_001",
        source="calendar",
        title="Engineering standup",
        hour=13,
        content="Meeting: Engineering standup",
    )

    text = Synthesizer(client, sleep=lambda _seconds: None).answer("What's my next meeting?", [item])

    assert client.calls == 2
    assert text == canned


def test_two_chat_failures_raise() -> None:
    client = FakeChat([TransportError("429"), TransportError("timeout")])
    item = _item(
        item_id="cal_001",
        source="calendar",
        title="Engineering standup",
        hour=13,
        content="Meeting: Engineering standup",
    )

    with pytest.raises(SynthesisFailure):
        Synthesizer(client, sleep=lambda _seconds: None).answer("What's my next meeting?", [item])

    assert client.calls == 2


def test_response_error_fails_without_retry() -> None:
    client = FakeChat([ResponseError("chat HTTP 404: blocked by guardrail"), "unused"])
    item = _item(
        item_id="cal_001",
        source="calendar",
        title="Engineering standup",
        hour=13,
        content="Meeting: Engineering standup",
    )

    with pytest.raises(SynthesisFailure, match="blocked by guardrail"):
        Synthesizer(client, sleep=lambda _seconds: None).answer("What's my next meeting?", [item])

    assert client.calls == 1


def test_missing_message_text_raises() -> None:
    def post(api_key: object, payload: dict) -> dict:
        return {"choices": []}

    chat = OpenRouterChat("test-key", post=post)

    with pytest.raises(ResponseError):
        chat.complete("system", "user")


def test_non_object_reply_raises_response_error() -> None:
    chat = OpenRouterChat("test-key", post=lambda _key, _payload: [])  # type: ignore[arg-type,return-value]

    with pytest.raises(ResponseError):
        chat.complete("system", "user")


def test_complete_sends_gpt_4o_mini_and_returns_message() -> None:
    seen: dict[str, object] = {}

    def post(api_key: SecretStr, payload: dict) -> dict:
        seen["key"] = api_key
        seen["payload"] = payload
        return {"choices": [{"message": {"content": "ok"}}]}

    chat = OpenRouterChat("test-key", post=post)

    assert chat.complete("sys", "user") == "ok"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "openai/gpt-4o-mini"
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]
    key = seen["key"]
    assert isinstance(key, SecretStr)
    assert key.get_secret_value() == "test-key"
    assert "test-key" not in repr(key)


def test_missing_api_key_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def post(api_key: str, payload: dict) -> dict:
        calls["n"] += 1
        return {}

    with pytest.raises(MissingAPIKeyError):
        OpenRouterChat(None, post=post)

    assert calls["n"] == 0

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("src.engine.openrouter.load_dotenv", lambda: False)

    with pytest.raises(MissingAPIKeyError):
        OpenRouterChat.from_env()


class _CountingChat:
    def __init__(self, inner: OpenRouterChat) -> None:
        self._inner = inner
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self._inner.complete(system, user)


ANCHOR = datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
EVAL_QUERIES = (
    "What should I focus on today?",
    "What follow-ups am I missing?",
    "What customer issues are showing up repeatedly?",
)
EXPECTED_IDS = {
    "What should I focus on today?": ["email_205", "email_203", "cal_001", "cal_002", "cal_003"],
    "What follow-ups am I missing?": ["email_204", "email_205", "email_203"],
}
REPEATED_ISSUE_IDS = {"email_201", "email_202", "email_203"}


@pytest.mark.live
def test_live_synthesis_evaluation_queries(tmp_path: Path, openrouter_key: str) -> None:
    chat = _CountingChat(OpenRouterChat(openrouter_key))
    synthesizer = Synthesizer(chat)

    assert synthesizer.answer("What should I focus on today?", []) == FALLBACK
    assert chat.calls == 0

    context_store = ContextStore(tmp_path / "chroma")
    try:
        meetings = MockCalendarConnector(ROOT / "data" / "calendar.json").fetch_records()
        emails = MockGmailConnector(ROOT / "data" / "emails.json").fetch_records()
        context_store.upsert(meetings + emails)
        router = Router(JevClassifier(openrouter_key))
        for query in EVAL_QUERIES:
            found = router.retrieve(query, context_store, ANCHOR)
            answer = synthesizer.answer(query, found)
            print(f"\nQuery: {query}")
            print("Retrieved:")
            for item in found:
                print(f"- {item.id}")
                print(f"  source: {item.source}")
                print(f"  title: {item.title}")
                print(f"  timestamp: {item.timestamp.isoformat()}")
            print("Answer:")
            print(answer)
            if query in EXPECTED_IDS:
                assert [item.id for item in found] == EXPECTED_IDS[query]
            else:
                assert REPEATED_ISSUE_IDS <= {item.id for item in found}
            assert answer != ""
    finally:
        context_store.close()
