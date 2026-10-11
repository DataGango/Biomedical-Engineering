from datetime import timedelta

import pytest

from biomedical.saved_searches import (
    REFRESH_INTERVAL,
    SavedSearchStore,
    refresh_due_searches,
    refresh_saved_search,
    utc_now,
)


def test_saved_search_is_persistent_and_due_until_first_refresh(tmp_path):
    database = tmp_path / "searches.sqlite3"
    store = SavedSearchStore(database)
    saved = store.add("Neural interfaces", "neural interface")

    reopened = SavedSearchStore(database)
    assert reopened.get(saved["id"])["query"] == "neural interface"
    assert [item["id"] for item in reopened.due()] == [saved["id"]]


def test_successful_refresh_records_results_and_schedules_two_days(tmp_path):
    store = SavedSearchStore(tmp_path / "searches.sqlite3")
    saved = store.add("Cardiac devices", "cardiac device")
    now = utc_now()

    class FakeClient:
        def search_publications_with_count(self, query):
            assert query == "cardiac device"
            return {"total_matches": 8, "extracted_count": 2, "abstract_count": 2, "publications": []}

    refreshed = refresh_saved_search(store, saved["id"], client_factory=FakeClient, )

    assert refreshed["results"]["total_matches"] == 8
    assert refreshed["error"] is None
    assert utc_now() - _parse_datetime(refreshed["refreshed_at"]) < timedelta(seconds=5)
    assert _parse_datetime(refreshed["next_refresh_at"]) - _parse_datetime(refreshed["refreshed_at"]) == REFRESH_INTERVAL


def test_due_refreshes_only_searches_due_now(tmp_path):
    store = SavedSearchStore(tmp_path / "searches.sqlite3")
    saved = store.add("Cancer biomarkers", "cancer biomarker")
    now = utc_now()

    class FakeClient:
        def search_publications_with_count(self, query):
            return {"total_matches": 0, "extracted_count": 0, "abstract_count": 0, "publications": []}

    results = refresh_due_searches(store, client_factory=FakeClient)

    assert [item["id"] for item in results] == [saved["id"]]
    assert store.due(now=now + REFRESH_INTERVAL - timedelta(seconds=1)) == []
    assert len(store.due(now=now + REFRESH_INTERVAL + timedelta(seconds=1))) == 1


def test_invalid_saved_search_values_are_rejected(tmp_path):
    store = SavedSearchStore(tmp_path / "searches.sqlite3")

    with pytest.raises(ValueError, match="name"):
        store.add("  ", "valid query")
    with pytest.raises(ValueError, match="query"):
        store.add("Valid name", "  ")
    with pytest.raises(ValueError, match="300 characters"):
        store.add("Valid name", "x" * 301)


def _parse_datetime(value):
    from datetime import datetime

    return datetime.fromisoformat(value)