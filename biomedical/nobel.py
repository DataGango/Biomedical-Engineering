import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class NobelMedicineClient:
    """Read official Nobel Prize in Physiology or Medicine award data."""

    BASE_URL = "https://api.nobelprize.org/2.1/nobelPrizes"

    def __init__(self, session=None, timeout=20):
        self.session = session
        self.timeout = timeout

    def latest_prizes(self, limit=10):
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")

        params = {
            "nobelPrizeCategory": "med",
            "sort": "desc",
            "limit": limit,
        }
        if self.session is not None:
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        else:
            request_url = f"{self.BASE_URL}?{urlencode(params)}"
            request = Request(request_url, headers={"User-Agent": "FieldnotesBiomedicalDashboard/1.0"})
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))

        prizes = payload.get("nobelPrizes", [])
        return {
            "total_matches": int(payload.get("meta", {}).get("count", len(prizes))),
            "prizes": [_normalize_prize(prize) for prize in prizes],
            "source": "Nobel Prize official API",
            "source_url": "https://www.nobelprize.org/developer-zone-2/",
        }


def _normalize_prize(prize):
    year = str(prize.get("awardYear", ""))
    laureates = []
    for laureate in prize.get("laureates", []):
        name = laureate.get("knownName", {}).get("en") or laureate.get("fullName", {}).get("en", "")
        motivation = laureate.get("motivation", {}).get("en", "")
        if name:
            laureates.append({"name": name, "motivation": motivation})

    api_link = next(
        (link.get("href", "") for link in prize.get("links", []) if link.get("rel") == "nobelPrize"),
        "",
    )
    return {
        "year": year,
        "category": prize.get("categoryFullName", {}).get("en", "The Nobel Prize in Physiology or Medicine"),
        "laureates": laureates,
        "url": f"https://www.nobelprize.org/prizes/medicine/{year}/summary/" if year else "https://www.nobelprize.org/prizes/medicine/",
        "source_url": api_link or f"https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeCategory=med&awardYear={year}",
    }