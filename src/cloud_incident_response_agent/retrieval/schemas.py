from dataclasses import dataclass


@dataclass(frozen=True)
class RunbookChunk:
    runbook_name: str
    file_name: str
    heading: str
    content: str


@dataclass(frozen=True)
class RunbookSearchResult:
    runbook_name: str
    file_name: str
    heading: str
    content: str
    semantic_score: float
    reranker_score: float

    def to_dict(
        self,
    ) -> dict[str, str | float]:
        return {
            "runbook_name": self.runbook_name,
            "file_name": self.file_name,
            "heading": self.heading,
            "content": self.content,
            "semantic_score": round(
                self.semantic_score,
                4,
            ),
            "reranker_score": round(
                self.reranker_score,
                4,
            ),
        }