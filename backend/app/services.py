import sqlite3
from collections.abc import Callable
from pathlib import Path

from backend.app.schemas import Suggestion


class SuggestionServiceUnavailable(Exception):
    """Raised when the pipeline or ranking dependencies are not ready."""


SuggestionProvider = Callable[[str], list[Suggestion]]


def unavailable_suggestions(_policy: str) -> list[Suggestion]:
    raise SuggestionServiceUnavailable(
        "The verified snapshot and eligibility outputs are not connected yet."
    )


def read_snapshot_summary(database_path: Path) -> tuple[bool, dict[str, int] | None]:
    """Read table counts from a processed SQLite store without creating or modifying it."""
    if not database_path.is_file():
        return False, None

    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            tables = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            if not tables:
                return False, None
            counts: dict[str, int] = {}
            for (name,) in tables:
                quoted_name = '"' + name.replace('"', '""') + '"'
                counts[name] = connection.execute(f"SELECT COUNT(*) FROM {quoted_name}").fetchone()[
                    0
                ]
            return True, counts
    except sqlite3.Error:
        return False, None
