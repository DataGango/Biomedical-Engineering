import pytest

from biomedical.nobel import NobelMedicineClient


def test_nobel_api_normalizes_recent_medicine_award_and_links():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "meta": {"count": 126},
                "nobelPrizes": [{
                    "awardYear": "2026",
                    "categoryFullName": {"en": "The Nobel Prize in Physiology or Medicine"},
                    "links": [{"rel": "nobelPrize", "href": "https://api.nobelprize.org/2/nobelPrize/med/2026"}],
                    "laureates": [{
                        "knownName": {"en": "A. Researcher"},
                        "motivation": {"en": "for a verified discovery"},
                    }],
                }],
            }

    class FakeSession:
        def __init__(self):
            self.params = None

        def get(self, url, params, timeout):
            self.params = params
            return FakeResponse()

    session = FakeSession()
    result = NobelMedicineClient(session=session).latest_prizes(limit=5)

    assert session.params == {"nobelPrizeCategory": "med", "sort": "desc", "limit": 5}
    assert result["total_matches"] == 126
    assert result["prizes"][0]["year"] == "2026"
    assert result["prizes"][0]["laureates"][0] == {
        "name": "A. Researcher",
        "motivation": "for a verified discovery",
    }
    assert result["prizes"][0]["url"] == "https://www.nobelprize.org/prizes/medicine/2026/summary/"
    assert result["prizes"][0]["source_url"] == "https://api.nobelprize.org/2/nobelPrize/med/2026"


def test_nobel_limit_is_validated():
    with pytest.raises(ValueError, match="between 1 and 50"):
        NobelMedicineClient().latest_prizes(limit=51)