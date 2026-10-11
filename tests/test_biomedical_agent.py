import pytest

from biomedical import BiomedicalAgent


class StubRetriever:
    def __init__(self, passages):
        self.passages = passages
        self.query = None
        self.top_k = None

    def retrieve(self, query, top_k=5):
        self.query = query
        self.top_k = top_k
        return self.passages[:top_k]


def test_research_returns_retrieved_evidence_and_notice():
    retriever = StubRetriever(["Study passage"])
    agent = BiomedicalAgent(retriever)

    result = agent.research("  vaccine efficacy  ", top_k=2)

    assert retriever.query == "vaccine efficacy"
    assert retriever.top_k == 2
    assert result["evidence"] == ["Study passage"]
    assert result["evidence_found"] is True
    assert "not a diagnosis" in result["notice"]


def test_research_marks_when_no_evidence_is_found():
    result = BiomedicalAgent(StubRetriever([])).research("rare disease")

    assert result["evidence"] == []
    assert result["evidence_found"] is False


@pytest.mark.parametrize("question", ["", "   ", None])
def test_research_rejects_empty_or_invalid_questions(question):
    agent = BiomedicalAgent(StubRetriever([]))

    with pytest.raises(ValueError, match="non-empty string"):
        agent.research(question)