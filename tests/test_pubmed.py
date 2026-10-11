import pytest

from biomedical.pubmed import EuropePMCClient, PubMedClient, parse_publications


PUBMED_XML = """<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <Journal><Title>Journal of Test Medicine</Title><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
        <ArticleTitle>Effects of Example Therapy</ArticleTitle>
        <AuthorList><Author><ForeName>Alex</ForeName><LastName>Researcher</LastName></Author></AuthorList>
        <Abstract><AbstractText Label="BACKGROUND">A study background.</AbstractText><AbstractText Label="RESULTS">A study result.</AbstractText></Abstract>
        <PublicationTypeList><PublicationType>Clinical Trial</PublicationType></PublicationTypeList>
      </Article>
      <KeywordList><Keyword>example therapy</Keyword></KeywordList>
    </MedlineCitation>
    <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/example</ArticleId></ArticleIdList></PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""


def test_parse_publications_extracts_citation_and_abstract_fields():
    result = parse_publications(PUBMED_XML)

    assert result == [{
        "pmid": "12345",
        "title": "Effects of Example Therapy",
        "authors": ["Alex Researcher"],
        "journal": "Journal of Test Medicine",
        "year": "2025",
        "doi": "10.1000/example",
        "abstract": "BACKGROUND: A study background.\n\nRESULTS: A study result.",
        "keywords": ["example therapy"],
        "publication_types": ["Clinical Trial"],
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
    }]


def test_search_publications_searches_then_fetches_records():
    class FakeResponse:
        def __init__(self, payload=None, text=""):
            self.payload = payload
            self.text = text

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, url, params, timeout):
            self.calls.append((url, params, timeout))
            if url.endswith("esearch.fcgi"):
                return FakeResponse({"esearchresult": {"count": "1", "idlist": ["12345"]}})
            return FakeResponse(text=PUBMED_XML)

    session = FakeSession()
    client = PubMedClient(session=session, email="research@example.org")

    papers = client.search_publications("example therapy", max_results=7)

    assert papers[0]["pmid"] == "12345"
    assert len(session.calls) == 2
    assert session.calls[0][1]["retmax"] == 7
    assert session.calls[0][1]["sort"] == "date"
    assert session.calls[0][1]["email"] == "research@example.org"


def test_search_publications_with_count_reports_hits_records_and_abstracts():
    class FakeResponse:
        def __init__(self, payload=None, text=""):
            self.payload = payload
            self.text = text

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeSession:
        def get(self, url, params, timeout):
            if url.endswith("esearch.fcgi"):
                return FakeResponse({"esearchresult": {"count": "42", "idlist": ["12345"]}})
            return FakeResponse(text=PUBMED_XML)

    result = PubMedClient(session=FakeSession()).search_publications_with_count(
        "example therapy", max_results=1
    )

    assert result["total_matches"] == 42
    assert result["extracted_count"] == 1
    assert result["abstract_count"] == 1
    assert result["publications"][0]["pmid"] == "12345"


def test_europe_pmc_returns_recent_records_with_clean_abstract_and_counts():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "hitCount": 37,
                "resultList": {"result": [{
                    "id": "87654",
                    "pmid": "87654",
                    "pmcid": "PMC7654321",
                    "doi": "10.1000/recent",
                    "title": "Recent biomedical study",
                    "authorList": {"author": [{"firstName": "Ari", "lastName": "Scientist"}]},
                    "journalInfo": {"journal": {"title": "Nature"}},
                    "pubYear": "2026",
                    "abstractText": "<h4>BACKGROUND</h4>New <i>evidence</i>.",
                }]},
            }

    class FakeSession:
        def __init__(self):
            self.params = None

        def get(self, url, params, timeout):
            self.params = params
            return FakeResponse()

    session = FakeSession()
    result = EuropePMCClient(session=session).search_publications_with_count("JOURNAL:Nature")

    assert result["total_matches"] == 37
    assert result["extracted_count"] == 1
    assert result["abstract_count"] == 1
    assert result["publications"][0]["abstract"] == "BACKGROUND: New evidence."
    assert result["publications"][0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/87654/"
    assert "FIRST_PDATE:[" in session.params["query"]


def test_europe_pmc_can_search_all_years_without_date_filter():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"hitCount": 0, "resultList": {"result": []}}

    class FakeSession:
        def __init__(self):
            self.params = None

        def get(self, url, params, timeout):
            self.params = params
            return FakeResponse()

    session = FakeSession()
    result = EuropePMCClient(session=session).search_publications_with_count(
        'TITLE_ABS:"robotic surgery"', date_range_days=None
    )

    assert "FIRST_PDATE:" not in session.params["query"]
    assert result["total_matches"] == 0


@pytest.mark.parametrize("query", ["", "  ", None])
def test_search_rejects_empty_query(query):
    with pytest.raises(ValueError, match="non-empty string"):
        PubMedClient().search(query)


def test_search_rejects_result_count_outside_api_limit():
    with pytest.raises(ValueError, match="between 1 and 100"):
        PubMedClient().search("oncology", max_results=101)