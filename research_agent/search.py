import threading
import requests
import arxiv
from typing import List


SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = "title,abstract,year,authors,citationCount"


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def _deduplicate(papers: List[dict]) -> List[dict]:
    seen = set()
    result = []
    for p in papers:
        key = _normalize_title(p.get("title", ""))
        if key and key not in seen:
            seen.add(key)
            result.append(p)
    return result


def _search_semantic_scholar(query: str, results: dict) -> None:
    try:
        params = {
            "query": query,
            "limit": 20,
            "fields": SEMANTIC_SCHOLAR_FIELDS,
        }
        resp = requests.get(SEMANTIC_SCHOLAR_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        papers = []
        for item in data:
            authors = [a.get("name", "") for a in item.get("authors", [])]
            papers.append({
                "title": item.get("title", ""),
                "abstract": item.get("abstract", "") or "",
                "year": item.get("year"),
                "authors": authors,
                "citation_count": item.get("citationCount", 0),
                "source": "semantic_scholar",
            })
        results["semantic_scholar"] = papers
    except Exception as e:
        results["semantic_scholar"] = []
        results["semantic_scholar_error"] = str(e)


def _search_arxiv(query: str, results: dict) -> None:
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=20,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers = []
        for result in client.results(search):
            papers.append({
                "title": result.title,
                "abstract": result.summary or "",
                "year": result.published.year if result.published else None,
                "authors": [a.name for a in result.authors],
                "citation_count": 0,
                "source": "arxiv",
                "arxiv_id": result.entry_id,
            })
        results["arxiv"] = papers
    except Exception as e:
        results["arxiv"] = []
        results["arxiv_error"] = str(e)


def broaden_query(query: str) -> str:
    """Strip the most specific (longest) term from the query."""
    terms = query.split()
    if len(terms) <= 2:
        return query
    longest = max(terms, key=len)
    terms.remove(longest)
    return " ".join(terms)


def search_papers(query: str, max_total: int = 20) -> List[dict]:
    """Search Semantic Scholar and ArXiv in parallel, deduplicate, return top max_total."""
    results: dict = {}
    t1 = threading.Thread(target=_search_semantic_scholar, args=(query, results))
    t2 = threading.Thread(target=_search_arxiv, args=(query, results))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    combined = results.get("semantic_scholar", []) + results.get("arxiv", [])
    deduplicated = _deduplicate(combined)
    return deduplicated[:max_total]
