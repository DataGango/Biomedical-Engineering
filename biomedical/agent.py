class BiomedicalAgent:
    """Retrieve biomedical reference passages without generating clinical advice."""

    NOTICE = (
        "Research support only; this is not a diagnosis or treatment recommendation. "
        "Consult a qualified healthcare professional for medical decisions."
    )

    def __init__(self, retriever):
        self.retriever = retriever

    def research(self, question, top_k=5):
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        evidence = self.retriever.retrieve(question.strip(), top_k=top_k)
        return {
            "question": question.strip(),
            "evidence": evidence,
            "evidence_found": bool(evidence),
            "notice": self.NOTICE,
        }