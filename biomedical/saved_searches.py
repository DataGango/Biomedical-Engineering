import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from biomedical.pubmed import EuropePMCClient


REFRESH_INTERVAL = timedelta(days=2)
RETRY_INTERVAL = timedelta(minutes=15)


def utc_now():
    return datetime.now(timezone.utc)


class SavedSearchStore:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    query TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    refreshed_at TEXT,
                    next_refresh_at TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT
                )
            """)

    def add(self, name, query):
        name = _validate_text(name, "name", 80)
        query = _validate_text(query, "query", 300)
        now = utc_now()
        search_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO saved_searches (id, name, query, created_at, next_refresh_at) VALUES (?, ?, ?, ?, ?)",
                (search_id, name, query, now.isoformat(), now.isoformat()),
            )
        return self.get(search_id)

    def get(self, search_id):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM saved_searches WHERE id = ?", (search_id,)
            ).fetchone()
        return _row_to_search(row) if row else None

    def list(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM saved_searches ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_search(row) for row in rows]

    def due(self, now=None):
        now = (now or utc_now()).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM saved_searches WHERE next_refresh_at <= ? ORDER BY next_refresh_at",
                (now,),
            ).fetchall()
        return [_row_to_search(row) for row in rows]

    def record_result(self, search_id, result, now=None):
        now = now or utc_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE saved_searches SET refreshed_at = ?, next_refresh_at = ?, result_json = ?, error = NULL WHERE id = ?",
                ((now).isoformat(), (now + REFRESH_INTERVAL).isoformat(), json.dumps(result), search_id),
            )

    def record_error(self, search_id, error, now=None):
        now = now or utc_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE saved_searches SET next_refresh_at = ?, error = ? WHERE id = ?",
                ((now + RETRY_INTERVAL).isoformat(), str(error)[:500], search_id),
            )


def _validate_text(value, field, max_length):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise ValueError(f"{field} must be {max_length} characters or fewer")
    return value


def _row_to_search(row):
    result = dict(row)
    result["results"] = json.loads(result.pop("result_json")) if result.get("result_json") else None
    return result


def refresh_saved_search(store, search_id, client_factory=EuropePMCClient):
    saved_search = store.get(search_id)
    if saved_search is None:
        raise KeyError(search_id)
    try:
        result = client_factory().search_publications_with_count(saved_search["query"])
    except Exception as exc:
        store.record_error(search_id, exc)
        return store.get(search_id)
    store.record_result(search_id, result)
    return store.get(search_id)


def refresh_due_searches(store, client_factory=EuropePMCClient):
    refreshed = []
    for search in store.due():
        refreshed.append(refresh_saved_search(store, search["id"], client_factory))
    return refreshed


def start_refresh_scheduler(store, client_factory=EuropePMCClient, poll_seconds=60):
    stop_event = threading.Event()

    def run():
        while not stop_event.is_set():
            refresh_due_searches(store, client_factory)
            stop_event.wait(poll_seconds)

    thread = threading.Thread(target=run, name="biomedical-search-refresh", daemon=True)
    thread.start()
    return stop_event