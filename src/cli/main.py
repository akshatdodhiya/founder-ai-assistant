import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from src.connectors import BaseConnector, MockCalendarConnector, MockGmailConnector, NormalizationError
from src.engine.classifier import JevClassifier
from src.engine.openrouter import MissingAPIKeyError
from src.engine.router import PlanningFailure, Router, resolve_reference_time
from src.engine.synthesizer import OpenRouterChat, SynthesisFailure, Synthesizer
from src.models import ContextItem
from src.storage import ContextStore, StorageError

EVALUATION_QUERIES = (
    "What should I focus on today?",
    "What follow-ups am I missing?",
    "What customer issues are showing up repeatedly?",
)
DATA_DIR = Path("data")
STORE_PATH = Path("chroma_db")
_EXIT_COMMANDS = {"exit", "quit"}
_QUESTION_ERRORS = (PlanningFailure, SynthesisFailure, StorageError)
_KEY_HELP = "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your OpenRouter key."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Founder assistant grounded in calendar and email context.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="run the three evaluation questions and exit",
    )
    return parser.parse_args(argv)


def load_sources(data_dir: Path) -> list[ContextItem]:
    connectors: tuple[BaseConnector, ...] = (
        MockCalendarConnector(data_dir / "calendar.json"),
        MockGmailConnector(data_dir / "emails.json"),
    )
    items: list[ContextItem] = []
    for connector in connectors:
        items.extend(connector.fetch_records())
    return items


def ingest(store: ContextStore, data_dir: Path) -> int:
    return _store_items(store, load_sources(data_dir))


def _store_items(store: ContextStore, items: list[ContextItem]) -> int:
    store.upsert(items)
    return store.count()


def run_repl(
    ask: Callable[[str], str],
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> int:
    write("Ask about your calendar and email. Type exit to quit.")
    while True:
        try:
            line = read("> ")
        except (EOFError, KeyboardInterrupt):
            write("")
            return 0
        query = line.strip()
        if query == "":
            continue
        if query.lower() in _EXIT_COMMANDS:
            return 0
        try:
            write(ask(query))
        except KeyboardInterrupt:
            write("")
            return 0
        except _QUESTION_ERRORS as exc:
            write(f"Error: {exc}")


def run_evaluation(
    ask: Callable[[str], tuple[list[ContextItem], str]],
    write: Callable[[str], None] = print,
) -> int:
    failures = 0
    for query in EVALUATION_QUERIES:
        write(f"\nQuestion: {query}")
        try:
            items, answer = ask(query)
        except _QUESTION_ERRORS as exc:
            failures += 1
            write(f"Error: {exc}")
            continue
        ids = ", ".join(item.id for item in items) or "none"
        write(f"Retrieved: {ids}")
        write("Answer:")
        write(answer)
    return 1 if failures else 0


def main(
    argv: list[str] | None = None,
    *,
    data_dir: Path = DATA_DIR,
    store_path: Path = STORE_PATH,
) -> int:
    args = parse_args(argv)
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    try:
        classifier = JevClassifier(api_key)
        chat = OpenRouterChat(api_key)
    except MissingAPIKeyError:
        print(_KEY_HELP, file=sys.stderr)
        return 1
    try:
        reference = resolve_reference_time()
    except ValueError as exc:
        print(f"Invalid FOUNDER_REFERENCE_TIME: {exc}", file=sys.stderr)
        return 1
    try:
        items = load_sources(data_dir)
    except NormalizationError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1

    store = ContextStore(store_path)
    try:
        count = _store_items(store, items)
        print(f"Loaded {count} context items. Reference time: {reference.isoformat()}")
        router = Router(classifier)
        synthesizer = Synthesizer(chat)

        def retrieve_and_answer(query: str) -> tuple[list[ContextItem], str]:
            found = router.retrieve(query, store, reference)
            return found, synthesizer.answer(query, found)

        if args.test:
            return run_evaluation(retrieve_and_answer)
        return run_repl(lambda query: retrieve_and_answer(query)[1])
    finally:
        store.close()
