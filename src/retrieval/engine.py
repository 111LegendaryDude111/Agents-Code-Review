from ..domain import Evidence, EvidenceType


class DocRetriever:
    def __init__(self, docs_path: str | None = None):
        self.docs_path = docs_path
        self.index: dict[str, str] = {}

    def index_documents(self, docs: list[str]) -> None:
        """
        Index documentation files.
        For MVP, we just store them.
        """
        for doc in docs:
            try:
                with open(doc, encoding="utf-8") as f:
                    self.index[doc] = f.read()
            except Exception as e:
                print(f"Failed to read doc {doc}: {e}")

    def retrieve_relevant_docs(self, query: str, top_k: int = 3) -> list[Evidence]:
        """
        Retrieve relevant documentation snippets.
        For MVP, naive keyword matching.
        """
        results: list[Evidence] = []
        query_terms = query.lower().split()

        if not query_terms:
            return results

        for doc_path, content in self.index.items():
            # Very naive scoring
            score = sum(content.lower().count(term) for term in query_terms)
            if score > 0:
                # Find a relevant excerpt
                idx = content.lower().find(query_terms[0])
                start = max(0, idx - 50)
                end = min(len(content), idx + 200)
                excerpt = content[start:end] + "..."

                results.append(
                    Evidence(
                        type=EvidenceType.DOC,
                        source=doc_path,
                        excerpt=excerpt,
                    )
                )

        return results[:top_k]
