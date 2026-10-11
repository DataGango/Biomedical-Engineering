import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import pytest

from biomedical import dashboard


@pytest.fixture
def running_dashboard(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "SEARCH_STORE", dashboard.SavedSearchStore(tmp_path / "searches.sqlite3"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.DashboardHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request_json(url, method="GET"):
    try:
        with urlopen(Request(url, method=method), timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as response:
        return response.code, json.loads(response.read())


def test_robotic_surgery_route_serves_page_and_searches_all_years(running_dashboard, monkeypatch):
    calls = []

    class FakeEuropePMCClient:
        def search_publications_with_count(self, query, max_results, date_range_days):
            calls.append((query, max_results, date_range_days))
            return {
                "total_matches": 12,
                "extracted_count": 1,
                "abstract_count": 1,
                "publications": [{"title": "Robot-assisted procedure", "abstract": "Study abstract", "url": "https://europepmc.org/article/MED/1"}],
            }

    monkeypatch.setattr(dashboard, "EuropePMCClient", FakeEuropePMCClient)
    with urlopen(f"{running_dashboard}/robotic-surgery", timeout=5) as response:
        page = response.read().decode()
    status, result = request_json(f"{running_dashboard}/api/robotic-surgery?years=all&limit=15&q=prostatectomy")

    assert "Robotic procedure research" in page
    assert status == 200
    assert result["total_matches"] == 12
    assert result["publications"][0]["url"].startswith("https://europepmc.org/")
    assert calls[0][1:] == (15, None)
    assert "prostatectomy" in calls[0][0]


@pytest.mark.parametrize(("topic", "title"), [("oncology", "Oncology"), ("neurosurgery", "Neurosurgery")])
def test_specialty_pages_and_searches_are_linked(running_dashboard, monkeypatch, topic, title):
    calls = []

    class FakeEuropePMCClient:
        def search_publications_with_count(self, query, max_results, date_range_days):
            calls.append((query, max_results, date_range_days))
            return {"total_matches": 3, "extracted_count": 1, "abstract_count": 1, "publications": []}

    monkeypatch.setattr(dashboard, "EuropePMCClient", FakeEuropePMCClient)
    with urlopen(f"{running_dashboard}/{topic}", timeout=5) as response:
        page = response.read().decode()
    status, result = request_json(f"{running_dashboard}/api/specialty?topic={topic}&years=all&limit=12")

    assert f"{title}," in page
    assert all(f'href="/{path}"' in page for path in ("", "robotic-surgery", "oncology", "neurosurgery"))
    assert status == 200
    assert result["topic"] == topic
    assert result["total_matches"] == 3
    assert calls[0][1:] == (12, None)


def test_landing_page_links_to_all_research_pages(running_dashboard):
    with urlopen(f"{running_dashboard}/", timeout=5) as response:
        page = response.read().decode()

    assert all(f'href="/{path}"' in page for path in ("robotic-surgery", "oncology", "neurosurgery"))


def test_specialty_search_rejects_unknown_topic(running_dashboard):
    status, payload = request_json(f"{running_dashboard}/api/specialty?topic=unknown")

    assert status == 400
    assert "error" in payload


def test_nobel_endpoint_returns_official_source_data(running_dashboard, monkeypatch):
    class FakeNobelClient:
        def latest_prizes(self, limit):
            return {"total_matches": 126, "prizes": [{"year": "2026", "url": "https://www.nobelprize.org/prizes/medicine/2026/summary/"}], "source": "Nobel Prize official API"}

    monkeypatch.setattr(dashboard, "NobelMedicineClient", FakeNobelClient)
    status, result = request_json(f"{running_dashboard}/api/nobel-medicine?limit=4")

    assert status == 200
    assert result["source"] == "Nobel Prize official API"
    assert result["prizes"][0]["year"] == "2026"


@pytest.mark.parametrize("url", [
    "/api/robotic-surgery?years=0",
    "/api/robotic-surgery?years=all&limit=31",
    "/api/nobel-medicine?limit=100",
])
def test_dashboard_rejects_out_of_range_research_parameters(running_dashboard, url):
    status, payload = request_json(f"{running_dashboard}{url}")

    assert status == 400
    assert "error" in payload