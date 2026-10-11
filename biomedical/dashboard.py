import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from biomedical.pubmed import EuropePMCClient
from biomedical.nobel import NobelMedicineClient
from biomedical.saved_searches import (
    SavedSearchStore,
    refresh_saved_search,
    start_refresh_scheduler,
)


ROOT = Path(__file__).parent
ASSETS = {
    "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
    "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
    "/robotic-surgery.css": ("robotic_surgery.css", "text/css; charset=utf-8"),
    "/robotic-surgery.js": ("robotic_surgery.js", "text/javascript; charset=utf-8"),
    "/specialty.css": ("specialty.css", "text/css; charset=utf-8"),
    "/specialty.js": ("specialty.js", "text/javascript; charset=utf-8"),
}
SPECIALTIES = {
    "oncology": {
        "title": "Oncology",
        "query": 'TITLE_ABS:(cancer OR oncology OR neoplasm OR tumor OR tumour)',
        "description": "Explore indexed cancer research, clinical oncology, tumor biology, and emerging evidence.",
    },
    "neurosurgery": {
        "title": "Neurosurgery",
        "query": 'TITLE_ABS:(neurosurgery OR "neurosurgical procedures" OR "brain surgery" OR "spinal surgery")',
        "description": "Explore indexed research on neurosurgical procedures, brain and spine surgery, and perioperative evidence.",
    },
}
SEARCHES = {
    "nature": 'JOURNAL:"Nature"',
    "medical": 'TITLE_ABS:(medicine OR medical OR clinical)',
    "bioengineering": 'TITLE_ABS:("biomedical engineering" OR bioengineering OR "tissue engineering" OR "medical devices")',
}
SEARCH_STORE = SavedSearchStore(
    os.getenv("BIOMEDICAL_SEARCH_DB", str(ROOT.parent / "data" / "biomedical_searches.sqlite3"))
)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlparse(self.path)
        if request.path == "/":
            self._send_file("dashboard.html", "text/html; charset=utf-8")
        elif request.path == "/robotic-surgery":
            self._send_file("robotic_surgery.html", "text/html; charset=utf-8")
        elif request.path in ("/oncology", "/neurosurgery"):
            self._send_specialty_page(request.path.lstrip("/"))
        elif request.path in ASSETS:
            filename, content_type = ASSETS[request.path]
            self._send_file(filename, content_type)
        elif request.path == "/api/search":
            self._search(parse_qs(request.query))
        elif request.path == "/api/searches":
            self._send_json({"searches": SEARCH_STORE.list()})
        elif request.path == "/api/robotic-surgery":
            self._robotic_surgery_search(parse_qs(request.query))
        elif request.path == "/api/specialty":
            self._specialty_search(parse_qs(request.query))
        elif request.path == "/api/nobel-medicine":
            self._nobel_medicine(parse_qs(request.query))
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        request = urlparse(self.path)
        if request.path == "/api/searches":
            self._add_search()
            return
        parts = request.path.strip("/").split("/")
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "searches" and parts[3] == "refresh":
            self._refresh_search(parts[2])
            return
        self._send_json({"error": "Not found"}, status=404)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ValueError("Request body must be between 1 and 4096 bytes.")
            return json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Send a valid JSON request with a body under 4 KB.") from exc

    def _add_search(self):
        try:
            payload = self._read_json()
            saved = SEARCH_STORE.add(payload.get("name"), payload.get("query"))
        except (ValueError, AttributeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        saved = refresh_saved_search(SEARCH_STORE, saved["id"])
        self._send_json({"search": saved}, status=201)

    def _refresh_search(self, search_id):
        if not SEARCH_STORE.get(search_id):
            self._send_json({"error": "Saved search not found."}, status=404)
            return
        self._send_json({"search": refresh_saved_search(SEARCH_STORE, search_id)})

    def _search(self, params):
        category = params.get("category", [""])[0]
        if category not in SEARCHES:
            self._send_json({"error": "Choose nature, medical, or bioengineering."}, status=400)
            return

        try:
            limit = int(params.get("limit", ["10"])[0])
            if not 1 <= limit <= 30:
                raise ValueError
        except ValueError:
            self._send_json({"error": "limit must be a number from 1 to 30."}, status=400)
            return

        query = SEARCHES[category]
        extra_query = params.get("q", [""])[0].strip()
        if extra_query:
            if len(extra_query) > 200:
                self._send_json({"error": "Search text must be 200 characters or fewer."}, status=400)
                return
            query = f"({query}) AND ({extra_query})"

        try:
            results = EuropePMCClient().search_publications_with_count(query, max_results=limit)
            self._send_json({"category": category, **results})
        except Exception as exc:
            self._send_json({"error": f"PubMed request failed: {exc}"}, status=502)

    def _robotic_surgery_search(self, params):
        try:
            limit = int(params.get("limit", ["20"])[0])
            if not 1 <= limit <= 30:
                raise ValueError
            years_value = params.get("years", ["all"])[0]
            if years_value == "all":
                date_range_days = None
            else:
                years = int(years_value)
                if not 1 <= years <= 120:
                    raise ValueError
                date_range_days = years * 365
        except ValueError:
            self._send_json({"error": "limit must be 1-30; years must be all or a number from 1 to 120."}, status=400)
            return

        extra_query = params.get("q", [""])[0].strip()
        if len(extra_query) > 200:
            self._send_json({"error": "Search text must be 200 characters or fewer."}, status=400)
            return
        base_query = 'TITLE_ABS:("robotic surgery" OR "robot-assisted surgery" OR "robot assisted surgery" OR "surgical robot" OR "robotic surgical")'
        query = f"({base_query}) AND ({extra_query})" if extra_query else base_query
        try:
            result = EuropePMCClient().search_publications_with_count(
                query,
                max_results=limit,
                date_range_days=date_range_days,
            )
            self._send_json({"query": query, "years": years_value, "source": "Europe PMC", **result})
        except Exception as exc:
            self._send_json({"error": f"Europe PMC request failed: {exc}"}, status=502)

    def _specialty_search(self, params):
        topic = params.get("topic", [""])[0]
        if topic not in SPECIALTIES:
            self._send_json({"error": "Choose oncology or neurosurgery."}, status=400)
            return
        try:
            limit = int(params.get("limit", ["20"])[0])
            if not 1 <= limit <= 30:
                raise ValueError
            years_value = params.get("years", ["all"])[0]
            if years_value == "all":
                date_range_days = None
            else:
                years = int(years_value)
                if not 1 <= years <= 120:
                    raise ValueError
                date_range_days = years * 365
        except ValueError:
            self._send_json({"error": "limit must be 1-30; years must be all or a number from 1 to 120."}, status=400)
            return

        extra_query = params.get("q", [""])[0].strip()
        if len(extra_query) > 200:
            self._send_json({"error": "Search text must be 200 characters or fewer."}, status=400)
            return
        base_query = SPECIALTIES[topic]["query"]
        query = f"({base_query}) AND ({extra_query})" if extra_query else base_query
        try:
            result = EuropePMCClient().search_publications_with_count(
                query,
                max_results=limit,
                date_range_days=date_range_days,
            )
            self._send_json({"topic": topic, "query": query, "years": years_value, "source": "Europe PMC", **result})
        except Exception as exc:
            self._send_json({"error": f"Europe PMC request failed: {exc}"}, status=502)

    def _send_specialty_page(self, topic):
        specialty = SPECIALTIES[topic]
        body = (ROOT / "specialty.html").read_text(encoding="utf-8")
        body = body.replace("__SPECIALTY__", topic)
        body = body.replace("__SPECIALTY_TITLE__", specialty["title"])
        body = body.replace("__SPECIALTY_DESCRIPTION__", specialty["description"])
        self._send_body(body.encode("utf-8"), "text/html; charset=utf-8")

    def _nobel_medicine(self, params):
        try:
            limit = int(params.get("limit", ["10"])[0])
            result = NobelMedicineClient().latest_prizes(limit=limit)
            self._send_json(result)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": f"Nobel Prize API request failed: {exc}"}, status=502)

    def _send_file(self, filename, content_type):
        body = (ROOT / filename).read_bytes()
        self._send_body(body, content_type)

    def _send_body(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="Run the biomedical literature dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    scheduler_stop = start_refresh_scheduler(SEARCH_STORE)
    print(f"Biomedical literature dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        scheduler_stop.set()
        server.server_close()


if __name__ == "__main__":
    main()