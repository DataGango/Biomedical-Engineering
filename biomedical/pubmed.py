import json
import re
import time
from threading import Lock
from datetime import date, timedelta
from urllib.parse import urljoin
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

_REQUEST_LOCK = Lock()
_LAST_REQUEST_AT = 0.0
_MIN_REQUEST_INTERVAL = 0.42


class PubMedClient:
    """Search PubMed and extract structured publication records via NCBI E-utilities."""

    def __init__(self, session=None, email=None, api_key=None, timeout=20, base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"):
        self.session = session
        self.email = email
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = base_url.rstrip("/") + "/"

    def search(self, query, max_results=20, sort="date"):
        return self._search(query, max_results, sort)["pmids"]

    def _search(self, query, max_results, sort):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= 100:
            raise ValueError("max_results must be between 1 and 100")
        if sort not in {"date", "relevance"}:
            raise ValueError("sort must be 'date' or 'relevance'")

        response = self._get("esearch.fcgi", {
            "db": "pubmed",
            "term": query.strip(),
            "retmax": max_results,
            "sort": sort,
            "retmode": "json",
        })
        response.raise_for_status()
        search_result = response.json().get("esearchresult", {})
        return {
            "count": int(search_result.get("count", 0)),
            "pmids": search_result.get("idlist", []),
        }

    def fetch(self, pmids):
        if not pmids:
            return []

        response = self._get("efetch.fcgi", {
            "db": "pubmed",
            "id": ",".join(str(pmid) for pmid in pmids),
            "retmode": "xml",
        })
        response.raise_for_status()
        return parse_publications(response.text)

    def search_publications(self, query, max_results=20, sort="date"):
        return self.fetch(self.search(query, max_results=max_results, sort=sort))

    def search_publications_with_count(self, query, max_results=20, sort="date"):
        search_result = self._search(query, max_results, sort)
        publications = self.fetch(search_result["pmids"])
        return {
            "total_matches": search_result["count"],
            "extracted_count": len(publications),
            "abstract_count": sum(bool(paper["abstract"]) for paper in publications),
            "publications": publications,
        }

    def _params(self, params):
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _get(self, endpoint, params):
        global _LAST_REQUEST_AT
        url = urljoin(self.base_url, endpoint)
        params = self._params(params)
        with _REQUEST_LOCK:
            for attempt in range(3):
                delay = _MIN_REQUEST_INTERVAL - (time.monotonic() - _LAST_REQUEST_AT)
                if delay > 0:
                    time.sleep(delay)
                try:
                    if self.session is not None:
                        response = self.session.get(url, params=params, timeout=self.timeout)
                        response.raise_for_status()
                        _LAST_REQUEST_AT = time.monotonic()
                        return response

                    request_url = f"{url}?{urlencode(params)}"
                    request = Request(request_url, headers={"User-Agent": "BiomedicalLiteratureDashboard/1.0"})
                    with urlopen(request, timeout=self.timeout) as response:
                        body = response.read().decode("utf-8")
                    _LAST_REQUEST_AT = time.monotonic()
                    return _Response(body)
                except Exception as exc:
                    _LAST_REQUEST_AT = time.monotonic()
                    status_code = getattr(exc, "code", None) or getattr(
                        getattr(exc, "response", None), "status_code", None
                    )
                    if status_code != 429 or attempt == 2:
                        raise
                    headers = getattr(exc, "headers", None) or getattr(
                        getattr(exc, "response", None), "headers", {}
                    )
                    retry_after = headers.get("Retry-After") if headers else None
                    try:
                        wait_seconds = min(float(retry_after), 30) if retry_after else 2 ** (attempt + 1)
                    except ValueError:
                        wait_seconds = 2 ** (attempt + 1)
                    time.sleep(max(wait_seconds, _MIN_REQUEST_INTERVAL))


class EuropePMCClient:
    """Search Europe PMC for recent citations and abstract records."""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, session=None, timeout=20):
        self.session = session
        self.timeout = timeout

    def search_publications_with_count(self, query, max_results=10, date_range_days=365):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not 1 <= max_results <= 30:
            raise ValueError("max_results must be between 1 and 30")
        if date_range_days is not None and date_range_days < 1:
            raise ValueError("date_range_days must be positive or None")

        search_query = query.strip()
        if date_range_days is not None:
            date_from = (date.today() - timedelta(days=date_range_days)).isoformat()
            date_to = date.today().isoformat()
            search_query = f"({search_query}) AND FIRST_PDATE:[{date_from} TO {date_to}]"
        params = {
            "query": search_query,
            "format": "json",
            "resultType": "core",
            "pageSize": max_results,
            "sort_date": "y",
        }
        if self.session is not None:
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        else:
            request_url = f"{self.BASE_URL}?{urlencode(params)}"
            request = Request(request_url, headers={"User-Agent": "BiomedicalLiteratureDashboard/1.0"})
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))

        result_list = payload.get("resultList", {}).get("result", [])
        publications = [_europe_pmc_publication(record) for record in result_list]
        return {
            "total_matches": int(payload.get("hitCount", 0)),
            "extracted_count": len(publications),
            "abstract_count": sum(bool(paper["abstract"]) for paper in publications),
            "publications": publications,
        }


def _europe_pmc_publication(record):
    pmid = record.get("pmid", "")
    pmcid = record.get("pmcid", "")
    doi = record.get("doi", "")
    if pmid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    elif pmcid:
        url = f"https://europepmc.org/articles/{pmcid}"
    else:
        url = f"https://europepmc.org/article/MED/{record.get('id', '')}"

    raw_authors = record.get("authorList", {}).get("author", [])
    authors = [
        " ".join(filter(None, [author.get("firstName", ""), author.get("lastName", "")]))
        for author in raw_authors
    ]
    if not authors and record.get("authorString"):
        authors = [name.strip() for name in record["authorString"].split(",") if name.strip()]

    return {
        "pmid": pmid,
        "title": record.get("title", ""),
        "authors": authors,
        "journal": record.get("journalInfo", {}).get("journal", {}).get("title", ""),
        "year": record.get("pubYear", ""),
        "doi": doi,
        "abstract": _clean_abstract(record.get("abstractText", "")),
        "keywords": record.get("keywordList", {}).get("keyword", []),
        "publication_types": record.get("pubTypeList", {}).get("pubType", []),
        "url": url,
    }


def _clean_abstract(value):
    value = re.sub(r"</h\d\s*>", ": ", value, flags=re.IGNORECASE)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split())


class _Response:
    def __init__(self, body):
        self.text = body

    def raise_for_status(self):
        return None

    def json(self):
        return json.loads(self.text)


def parse_publications(xml_text):
    """Convert PubMed EFetch XML into citation records without dropping abstracts."""
    root = ET.fromstring(xml_text)
    publications = []

    for article in root.findall(".//PubmedArticle"):
        citation = article.find("MedlineCitation")
        article_data = citation.find("Article") if citation is not None else None
        if article_data is None:
            continue

        pmid_node = citation.find("PMID")
        pmid = _text(pmid_node)
        title = _text(article_data.find("ArticleTitle"))
        journal = _text(article_data.find("Journal/Title"))
        year = _publication_year(article_data)
        authors = _authors(article_data)
        abstract = _abstract(article_data)
        doi = _doi(article)
        keywords = [
            _text(keyword)
            for keyword in article.findall(".//KeywordList/Keyword")
            if _text(keyword)
        ]
        publication_types = [
            _text(item)
            for item in article_data.findall(".//PublicationType")
            if _text(item)
        ]

        publications.append({
            "pmid": pmid,
            "title": title,
            "authors": authors,
            "journal": journal,
            "year": year,
            "doi": doi,
            "abstract": abstract,
            "keywords": keywords,
            "publication_types": publication_types,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        })

    return publications


def _text(node):
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _publication_year(article_data):
    year = _text(article_data.find("Journal/JournalIssue/PubDate/Year"))
    if year:
        return year
    medline_date = _text(article_data.find("Journal/JournalIssue/PubDate/MedlineDate"))
    return medline_date[:4] if medline_date[:4].isdigit() else ""


def _authors(article_data):
    authors = []
    for author in article_data.findall("AuthorList/Author"):
        collective_name = _text(author.find("CollectiveName"))
        name = " ".join(filter(None, [
            _text(author.find("ForeName")),
            _text(author.find("LastName")),
        ])) or collective_name
        if name:
            authors.append(name)
    return authors


def _abstract(article_data):
    sections = []
    for section in article_data.findall("Abstract/AbstractText"):
        text = _text(section)
        label = section.attrib.get("Label") or section.attrib.get("NlmCategory")
        if text:
            sections.append(f"{label}: {text}" if label else text)
    return "\n\n".join(sections)


def _doi(article):
    for identifier in article.findall(".//ArticleIdList/ArticleId"):
        if identifier.attrib.get("IdType") == "doi":
            return _text(identifier)
    return ""