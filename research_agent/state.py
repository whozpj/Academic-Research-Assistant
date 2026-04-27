from typing import TypedDict, List, Optional


class ResearchState(TypedDict):
    research_question: str
    raw_papers: List[dict]
    relevant_papers: List[dict]
    snowballed_papers: List[dict]
    synthesis: dict
    hypotheses: List[dict]
    hypothesis_critiques: List[dict]
    experiment_design: dict
    error: Optional[str]
    retry_count: int
    hypothesis_iteration: int
