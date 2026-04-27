import json
import os
import anthropic
from typing import Any
from dotenv import load_dotenv

load_dotenv()

from state import ResearchState
from search import search_papers, broaden_query, fetch_snowball_papers
from prompts import (
    CRITIC_SYSTEM,
    SYNTHESIS_SYSTEM,
    HYPOTHESIS_SYSTEM,
    EXPERIMENT_SYSTEM,
    ADVOCATE_SYSTEM,
)

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


def snowball_node(state: ResearchState) -> ResearchState:
    """Expand the corpus via citation graph: fetch references + citations for top relevant papers."""
    try:
        relevant = state.get("relevant_papers", [])
        snowballed = fetch_snowball_papers(relevant, max_seed_papers=4)
        return {**state, "snowballed_papers": snowballed}
    except Exception as e:
        # Non-fatal: proceed with empty snowball rather than aborting pipeline
        return {**state, "snowballed_papers": [], "error": None}


def _validate_grounded_items(items: list, max_index: int) -> list:
    """Keep items that cite at least one valid paper index; strip out-of-range indices."""
    validated = []
    for item in items:
        indices = item.get("paper_indices", [])
        valid = [i for i in indices if isinstance(i, int) and 0 <= i < max_index]
        if valid:
            validated.append({**item, "paper_indices": valid})
    return validated


def synthesis_node(state: ResearchState) -> ResearchState:
    try:
        relevant = state.get("relevant_papers", [])
        snowballed = state.get("snowballed_papers", [])
        all_papers = relevant + snowballed
        question = state["research_question"]

        papers_text = "\n\n".join(
            f"[{i}] Title: {p['title']}\nYear: {p.get('year', 'N/A')}\n"
            f"Abstract: {p['abstract'][:500]}"
            for i, p in enumerate(all_papers)
        )

        user_prompt = f"""Research question: {question}

Papers (indexed 0 to {len(all_papers) - 1}):
{papers_text}

Return a JSON object with exactly these keys:
- themes: list of objects with keys:
    "claim" (string: the theme), "paper_indices" (list of ints supporting this theme)
- gaps: list of objects with keys:
    "claim" (string: the gap), "paper_indices" (list of ints that reveal this gap)
- contradictions: list of objects with keys:
    "paper_a" (title string), "paper_b" (title string), "description" (string),
    "paper_indices" (list of ints for the two contradicting papers)
- open_questions: list of objects with keys:
    "claim" (string: the question), "paper_indices" (list of ints that motivate it)

Use 3-5 themes. Every claim must cite at least one paper index from the list above."""

        result = _call_claude(SYNTHESIS_SYSTEM, user_prompt)
        max_idx = len(all_papers)

        # Validate and filter ungrounded claims
        result["themes"] = _validate_grounded_items(result.get("themes", []), max_idx)
        result["gaps"] = _validate_grounded_items(result.get("gaps", []), max_idx)
        result["contradictions"] = _validate_grounded_items(result.get("contradictions", []), max_idx)
        result["open_questions"] = _validate_grounded_items(result.get("open_questions", []), max_idx)

        # Attach paper titles to indices for UI rendering
        result["_paper_index_map"] = {i: p["title"] for i, p in enumerate(all_papers)}

        return {**state, "synthesis": result}
    except Exception as e:
        return {**state, "error": f"synthesis_node failed: {e}"}


def hypothesis_node(state: ResearchState) -> ResearchState:
    try:
        synthesis = state.get("synthesis", {})
        question = state["research_question"]

        # Exclude internal index map from the prompt
        synthesis_for_prompt = {k: v for k, v in synthesis.items() if not k.startswith("_")}

        user_prompt = f"""Research question: {question}

Synthesis of existing literature:
{json.dumps(synthesis_for_prompt, indent=2)}

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


def advocate_node(state: ResearchState) -> ResearchState:
    """Devil's advocate: challenge each hypothesis, score viability, produce refined claims."""
    try:
        hypotheses = state.get("hypotheses", [])
        relevant = state.get("relevant_papers", [])
        snowballed = state.get("snowballed_papers", [])
        all_papers = relevant + snowballed
        question = state["research_question"]

        papers_summary = "\n".join(
            f"[{i}] {p['title']} ({p.get('year', 'N/A')})"
            for i, p in enumerate(all_papers)
        )

        hypotheses_text = json.dumps(
            [{"index": i, **h} for i, h in enumerate(hypotheses)], indent=2
        )

        user_prompt = f"""Research question: {question}

Available papers:
{papers_summary}

Hypotheses to critique:
{hypotheses_text}

For each hypothesis, act as a rigorous peer reviewer. Return a JSON object with key "critiques"
containing a list of exactly {len(hypotheses)} objects, each with:
- hypothesis_index: integer (0-based)
- counterarguments: list of strings (cite paper indices where relevant, e.g. "Paper [3] already shows X")
- logical_flaws: list of strings (untestable assumptions, circular reasoning, scope issues)
- refined_claim: a stronger, more precise version of the hypothesis that addresses the critique
- viability_score: integer 1-10 (10 = extremely strong hypothesis that clearly survives critique)"""

        result = _call_claude(ADVOCATE_SYSTEM, user_prompt)
        critiques = result.get("critiques", [])

        # Merge viability scores back into hypotheses so experiment_node can rank
        critique_map = {c["hypothesis_index"]: c for c in critiques}
        enriched_hypotheses = []
        for i, h in enumerate(hypotheses):
            critique = critique_map.get(i, {})
            enriched_hypotheses.append({
                **h,
                "refined_claim": critique.get("refined_claim", h.get("claim", "")),
                "viability_score": critique.get("viability_score", 5),
            })

        return {**state, "hypotheses": enriched_hypotheses, "hypothesis_critiques": critiques}
    except Exception as e:
        return {**state, "error": f"advocate_node failed: {e}"}


def experiment_node(state: ResearchState) -> ResearchState:
    try:
        hypotheses = state.get("hypotheses", [])
        if not hypotheses:
            return {**state, "error": "experiment_node failed: no hypotheses available"}

        # Pick the hypothesis that best survived adversarial critique
        top_hypothesis = max(hypotheses, key=lambda h: h.get("viability_score", 5))
        question = state["research_question"]

        user_prompt = f"""Research question: {question}

Hypothesis to test (selected as most viable after adversarial review):
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
