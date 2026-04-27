import json
import os
import anthropic
from typing import Any

from state import ResearchState
from search import search_papers, broaden_query
from prompts import CRITIC_SYSTEM, SYNTHESIS_SYSTEM, HYPOTHESIS_SYSTEM, EXPERIMENT_SYSTEM

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


MODEL = "claude-sonnet-4-20250514"


def _call_claude(system: str, user: str, retry_json: bool = True) -> Any:
    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if retry_json:
            retry_prompt = user + "\n\nRespond only in valid JSON, no markdown fences."
            response2 = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": retry_prompt}],
            )
            text2 = response2.content[0].text.strip()
            # Strip markdown fences if present
            if text2.startswith("```"):
                lines = text2.split("\n")
                text2 = "\n".join(lines[1:-1]) if len(lines) > 2 else text2
            return json.loads(text2)
        raise


def search_node(state: ResearchState) -> ResearchState:
    try:
        query = state["research_question"]
        retry_count = state.get("retry_count", 0)

        if retry_count > 0:
            query = broaden_query(query)

        papers = search_papers(query)
        return {**state, "raw_papers": papers}
    except Exception as e:
        return {**state, "error": f"search_node failed: {e}"}


def critic_node(state: ResearchState) -> ResearchState:
    try:
        papers = state.get("raw_papers", [])
        question = state["research_question"]
        retry_count = state.get("retry_count", 0)

        papers_text = "\n\n".join(
            f"[{i}] Title: {p['title']}\nAbstract: {p['abstract'][:500]}"
            for i, p in enumerate(papers)
        )

        user_prompt = f"""Research question: {question}

Papers to evaluate:
{papers_text}

Return a JSON object with key "evaluations" containing a list of objects, one per paper, with:
- index: the paper index (integer)
- score: relevance score 1-10 (integer)
- reason: one-line reason (string)"""

        result = _call_claude(CRITIC_SYSTEM, user_prompt)
        evaluations = result.get("evaluations", [])

        score_map = {e["index"]: e for e in evaluations if e.get("score", 0) >= 6}

        relevant = []
        for i, paper in enumerate(papers):
            if i in score_map:
                relevant.append({
                    **paper,
                    "relevance_score": score_map[i]["score"],
                    "relevance_reason": score_map[i]["reason"],
                })

        relevant.sort(key=lambda x: x["relevance_score"], reverse=True)

        new_retry_count = retry_count
        if len(relevant) < 5 and retry_count < 2:
            new_retry_count = retry_count + 1

        return {**state, "relevant_papers": relevant, "retry_count": new_retry_count}
    except Exception as e:
        return {**state, "error": f"critic_node failed: {e}"}


def synthesis_node(state: ResearchState) -> ResearchState:
    try:
        papers = state.get("relevant_papers", [])
        question = state["research_question"]

        papers_text = "\n\n".join(
            f"Title: {p['title']}\nYear: {p.get('year', 'N/A')}\n"
            f"Abstract: {p['abstract'][:600]}"
            for p in papers
        )

        user_prompt = f"""Research question: {question}

Relevant papers:
{papers_text}

Return a JSON object with exactly these keys:
- themes: list of 3-5 strings, each a major theme across the papers
- gaps: list of strings, each an open problem not addressed by existing work
- contradictions: list of objects with keys "paper_a", "paper_b", "description" (papers that disagree)
- open_questions: list of strings, specific unanswered questions in the literature"""

        result = _call_claude(SYNTHESIS_SYSTEM, user_prompt)
        return {**state, "synthesis": result}
    except Exception as e:
        return {**state, "error": f"synthesis_node failed: {e}"}


def hypothesis_node(state: ResearchState) -> ResearchState:
    try:
        synthesis = state.get("synthesis", {})
        question = state["research_question"]

        user_prompt = f"""Research question: {question}

Synthesis of existing literature:
{json.dumps(synthesis, indent=2)}

Generate exactly 3 novel, testable research hypotheses.
Return a JSON object with key "hypotheses" containing a list of exactly 3 objects, each with:
- claim: the hypothesis statement (string)
- motivation: why existing literature doesn't answer it (string)
- falsification: what result would disprove it (string)
- feasibility: "high", "medium", or "low" with a one-line reason (string)"""

        result = _call_claude(HYPOTHESIS_SYSTEM, user_prompt)
        hypotheses = result.get("hypotheses", [])
        return {**state, "hypotheses": hypotheses}
    except Exception as e:
        return {**state, "error": f"hypothesis_node failed: {e}"}


def experiment_node(state: ResearchState) -> ResearchState:
    try:
        hypotheses = state.get("hypotheses", [])
        if not hypotheses:
            return {**state, "error": "experiment_node failed: no hypotheses available"}

        top_hypothesis = hypotheses[0]
        question = state["research_question"]

        user_prompt = f"""Research question: {question}

Top hypothesis to test:
{json.dumps(top_hypothesis, indent=2)}

Design a concrete, reproducible experiment to test this hypothesis.
Return a JSON object with exactly these keys:
- methodology: list of strings, each a step in the approach
- baseline: string describing what to compare against
- metrics: list of strings describing how to measure success
- datasets: list of strings naming specific suggested datasets
- failure_modes: list of objects with keys "mode" and "detection" (what could go wrong and how to detect it)"""

        result = _call_claude(EXPERIMENT_SYSTEM, user_prompt)
        return {**state, "experiment_design": result}
    except Exception as e:
        return {**state, "error": f"experiment_node failed: {e}"}
