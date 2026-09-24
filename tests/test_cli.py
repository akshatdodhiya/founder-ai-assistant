import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.cli.main import (
    EVALUATION_QUERIES,
    ingest,
    main,
    parse_args,
    run_evaluation,
    run_repl,
)
from src.engine.router import PlanningFailure
from src.engine.synthesizer import SynthesisFailure
from src.models import ContextItem
from src.storage import ContextStore

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "test-secret-key"


@pytest.fixture
def no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.cli.main.load_dotenv", lambda: False)
    monkeypatch.delenv("FOUNDER_REFERENCE_TIME", raising=False)


def _meeting(item_id: str) -> ContextItem:
    timestamp = datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc)
    return ContextItem(
        id=item_id,
        source="calendar",
        timestamp=timestamp,
        title="Engineering standup",
        content="Meeting: Engineering standup",
        metadata={"source": "calendar", "timestamp_epoch": 1790168400, "category": "meeting"},
    )


def _scripted(lines: list[str]):
    pending = list(lines)

    def read(_prompt: str) -> str:
        if not pending:
            raise EOFError
        return pending.pop(0)

    return read


def test_parse_args_defaults_to_repl() -> None:
    assert parse_args([]).test is False


def test_parse_args_test_flag() -> None:
    assert parse_args(["--test"]).test is True


def test_missing_key_exits_with_setup_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_dotenv: None, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    code = main([], data_dir=ROOT / "data", store_path=tmp_path / "chroma")

    captured = capsys.readouterr()
    assert code != 0
    assert "OPENROUTER_API_KEY" in captured.err
    assert ".env" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "chroma").exists()


def test_invalid_reference_time_exits_with_setup_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_dotenv: None, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    monkeypatch.setenv("FOUNDER_REFERENCE_TIME", "2026-09-23T09:00:00")

    code = main([], data_dir=ROOT / "data", store_path=tmp_path / "chroma")

    captured = capsys.readouterr()
    assert code != 0
    assert "FOUNDER_REFERENCE_TIME" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "chroma").exists()


def test_normalization_error_stops_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_dotenv: None, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(ROOT / "data" / "calendar.json", data_dir / "calendar.json")
    bad_email = {
        "id": "901",
        "thread_id": "thr_bad",
        "sender": "Sam Ortiz (Harbor Capital)",
        "subject": "No body field",
        "date": "2026-09-23T08:00:00Z",
        "requires_action": True,
        "category": "investor",
    }
    (data_dir / "emails.json").write_text(json.dumps([bad_email]), encoding="utf-8")

    code = main(["--test"], data_dir=data_dir, store_path=tmp_path / "chroma")

    captured = capsys.readouterr()
    assert code != 0
    assert "emails.json" in captured.err
    assert "missing required fields: body" in captured.err
    assert "Traceback" not in captured.err
    assert FAKE_KEY not in captured.out + captured.err
    assert not (tmp_path / "chroma").exists()


def test_ingest_upserts_eleven_items(store: ContextStore) -> None:
    assert ingest(store, ROOT / "data") == 11
    assert len(store.fetch(where={"source": "calendar"})) == 5
    assert len(store.fetch(where={"source": "email"})) == 6


def test_ingest_twice_keeps_eleven_items(store: ContextStore) -> None:
    ingest(store, ROOT / "data")

    assert ingest(store, ROOT / "data") == 11


def test_repl_ignores_blank_lines_and_survives_failures() -> None:
    asked: list[str] = []
    written: list[str] = []

    def ask(query: str) -> str:
        asked.append(query)
        if query == "plan fails":
            raise PlanningFailure("classifier failed after one retry")
        if query == "chat fails":
            raise SynthesisFailure("chat failed after one retry")
        return f"Answer to {query}"

    code = run_repl(
        ask,
        read=_scripted(["", "   ", "What's my next meeting?", "plan fails", "chat fails", "Anything else?", "quit"]),
        write=written.append,
    )

    assert code == 0
    assert asked == ["What's my next meeting?", "plan fails", "chat fails", "Anything else?"]
    assert "Answer to What's my next meeting?" in written
    assert "Answer to Anything else?" in written
    assert any("classifier failed after one retry" in line for line in written)
    assert any("chat failed after one retry" in line for line in written)


@pytest.mark.parametrize("command", ["exit", "quit", "EXIT"])
def test_repl_exit_commands(command: str) -> None:
    asked: list[str] = []

    code = run_repl(asked.append, read=_scripted([command, "never asked"]), write=lambda _line: None)  # type: ignore[arg-type]

    assert code == 0
    assert asked == []


def test_repl_ctrl_c_exits_cleanly() -> None:
    def read(_prompt: str) -> str:
        raise KeyboardInterrupt

    assert run_repl(lambda query: query, read=read, write=lambda _line: None) == 0


def test_evaluation_prints_ids_and_answers() -> None:
    asked: list[str] = []
    written: list[str] = []

    def ask(query: str) -> tuple[list[ContextItem], str]:
        asked.append(query)
        return [_meeting("cal_001"), _meeting("cal_002")], f"Answer to {query}"

    code = run_evaluation(ask, write=written.append)

    output = "\n".join(written)
    assert code == 0
    assert asked == list(EVALUATION_QUERIES)
    for query in EVALUATION_QUERIES:
        assert query in output
        assert f"Answer to {query}" in output
    assert "cal_001, cal_002" in output


def test_evaluation_reports_empty_retrieval() -> None:
    written: list[str] = []

    code = run_evaluation(lambda query: ([], "no context"), write=written.append)

    assert code == 0
    assert "Retrieved: none" in "\n".join(written)


def test_evaluation_fails_when_a_question_fails_but_runs_the_rest() -> None:
    asked: list[str] = []
    written: list[str] = []

    def ask(query: str) -> tuple[list[ContextItem], str]:
        asked.append(query)
        if query == EVALUATION_QUERIES[1]:
            raise SynthesisFailure("chat failed after one retry")
        return [_meeting("cal_001")], f"Answer to {query}"

    code = run_evaluation(ask, write=written.append)

    output = "\n".join(written)
    assert code != 0
    assert asked == list(EVALUATION_QUERIES)
    assert "chat failed after one retry" in output
    assert f"Answer to {EVALUATION_QUERIES[2]}" in output
