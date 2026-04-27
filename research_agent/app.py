import sys
import os
import json
import queue
import threading
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from graph import build_graph
from state import ResearchState

st.set_page_config(
    page_title="AI Agents Research Assistant",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 AI Agents Academic Research Assistant")
st.caption("Powered by LangGraph · Semantic Scholar · ArXiv · Claude")

research_question = st.text_input(
    "Research question",
    placeholder="e.g., How do large language model agents handle tool use and planning?",
)

run_button = st.button("Run Research Pipeline", type="primary", disabled=not research_question.strip())

if run_button and research_question.strip():
    initial_state: ResearchState = {
        "research_question": research_question.strip(),
        "raw_papers": [],
        "relevant_papers": [],
        "snowballed_papers": [],
        "synthesis": {},
        "hypotheses": [],
        "hypothesis_critiques": [],
        "experiment_design": {},
        "error": None,
        "retry_count": 0,
    }

    event_queue: queue.Queue = queue.Queue()

    def run_graph():
        try:
            graph = build_graph()
            state = dict(initial_state)
            node_order = [
                "search_node", "critic_node", "snowball_node",
                "synthesis_node", "hypothesis_node", "advocate_node", "experiment_node",
            ]
            completed_nodes = set()

            for event in graph.stream(state, stream_mode="updates"):
                for node_name, node_state in event.items():
                    if node_name in node_order and node_name not in completed_nodes:
                        completed_nodes.add(node_name)
                        state.update(node_state)
                        event_queue.put(("node_done", node_name, dict(state)))

            event_queue.put(("done", None, dict(state)))
        except Exception as e:
            event_queue.put(("error", str(e), {}))

    thread = threading.Thread(target=run_graph, daemon=True)
    thread.start()

    node_labels = {
        "search_node": "Searching papers (Semantic Scholar + ArXiv)",
        "critic_node": "Evaluating paper relevance (Claude critic)",
        "snowball_node": "Expanding corpus via citation graph (snowball)",
        "synthesis_node": "Synthesizing literature with grounded citations (Claude)",
        "hypothesis_node": "Generating hypotheses (Claude)",
        "advocate_node": "Adversarial hypothesis review (devil's advocate)",
        "experiment_node": "Designing experiment for top-surviving hypothesis (Claude)",
    }

    accumulated_state: dict = dict(initial_state)

    raw_placeholder = st.empty()
    relevant_placeholder = st.empty()
    snowball_placeholder = st.empty()
    synthesis_placeholder = st.empty()
    hypotheses_placeholder = st.empty()
    critiques_placeholder = st.empty()
    experiment_placeholder = st.empty()

    def _paper_title(index_map: dict, idx: int) -> str:
        title = index_map.get(idx, f"Paper {idx}")
        return title[:60] + "…" if len(title) > 60 else title

    def render_raw_papers(state):
        with raw_placeholder.container():
            with st.expander(f"📚 Raw Papers ({len(state.get('raw_papers', []))} found)", expanded=False):
                if state.get("raw_papers"):
                    display = [
                        {
                            "Title": p["title"],
                            "Year": p.get("year", ""),
                            "Citations": p.get("citation_count", 0),
                            "Source": p.get("source", ""),
                            "Authors": ", ".join(p.get("authors", [])[:3]),
                        }
                        for p in state["raw_papers"]
                    ]
                    st.dataframe(display, use_container_width=True)

    def render_relevant_papers(state):
        with relevant_placeholder.container():
            with st.expander(
                f"✅ Relevant Papers ({len(state.get('relevant_papers', []))} selected by critic)",
                expanded=bool(state.get("relevant_papers")),
            ):
                for p in state.get("relevant_papers", []):
                    score = p.get("relevance_score", "?")
                    reason = p.get("relevance_reason", "")
                    st.markdown(f"**{p['title']}** — Score: `{score}/10`")
                    st.caption(reason)
                    st.markdown("---")

    def render_snowball(state):
        snow = state.get("snowballed_papers", [])
        with snowball_placeholder.container():
            with st.expander(
                f"❄️ Snowballed Papers ({len(snow)} via citation graph)",
                expanded=bool(snow),
            ):
                if snow:
                    display = [
                        {
                            "Title": p["title"],
                            "Year": p.get("year", ""),
                            "Citations": p.get("citation_count", 0),
                            "Authors": ", ".join(p.get("authors", [])[:3]),
                        }
                        for p in snow
                    ]
                    st.dataframe(display, use_container_width=True)
                else:
                    st.caption("No additional papers found via citation snowballing.")

    def render_synthesis(state):
        with synthesis_placeholder.container():
            with st.expander("🔍 Literature Synthesis (grounded)", expanded=bool(state.get("synthesis"))):
                syn = state.get("synthesis", {})
                if not syn:
                    return
                index_map = syn.get("_paper_index_map", {})

                def _cite_badge(indices):
                    if not indices:
                        return ""
                    titles = [f"`[{i}] {_paper_title(index_map, i)}`" for i in indices]
                    return "  \n_Supported by: " + ", ".join(titles) + "_"

                if syn.get("themes"):
                    st.subheader("Major Themes")
                    for item in syn["themes"]:
                        claim = item.get("claim", item) if isinstance(item, dict) else item
                        indices = item.get("paper_indices", []) if isinstance(item, dict) else []
                        st.markdown(f"- {claim}{_cite_badge(indices)}")

                if syn.get("gaps"):
                    st.subheader("Research Gaps")
                    for item in syn["gaps"]:
                        claim = item.get("claim", item) if isinstance(item, dict) else item
                        indices = item.get("paper_indices", []) if isinstance(item, dict) else []
                        st.markdown(f"- {claim}{_cite_badge(indices)}")

                if syn.get("contradictions"):
                    st.subheader("Contradictions")
                    for c in syn["contradictions"]:
                        if isinstance(c, dict):
                            indices = c.get("paper_indices", [])
                            st.markdown(
                                f"**{c.get('paper_a', '')}** vs **{c.get('paper_b', '')}**: "
                                f"{c.get('description', '')}{_cite_badge(indices)}"
                            )
                        else:
                            st.markdown(f"- {c}")

                if syn.get("open_questions"):
                    st.subheader("Open Questions")
                    for item in syn["open_questions"]:
                        claim = item.get("claim", item) if isinstance(item, dict) else item
                        indices = item.get("paper_indices", []) if isinstance(item, dict) else []
                        st.markdown(f"- {claim}{_cite_badge(indices)}")

    def render_hypotheses(state):
        with hypotheses_placeholder.container():
            with st.expander("💡 Research Hypotheses", expanded=bool(state.get("hypotheses"))):
                for i, h in enumerate(state.get("hypotheses", []), 1):
                    viability = h.get("viability_score")
                    viability_str = f" — Viability: `{viability}/10`" if viability is not None else ""
                    st.markdown(f"### Hypothesis {i}{viability_str}")
                    col1, col2 = st.columns(2)
                    with col1:
                        refined = h.get("refined_claim", "")
                        original = h.get("claim", "")
                        if refined and refined != original:
                            st.markdown(f"**Original claim:** {original}")
                            st.markdown(f"**Refined claim (post-review):** {refined}")
                        else:
                            st.markdown(f"**Claim:** {original}")
                        st.markdown(f"**Motivation:** {h.get('motivation', '')}")
                    with col2:
                        st.markdown(f"**Falsification:** {h.get('falsification', '')}")
                        feasibility = h.get("feasibility", "")
                        color = {"high": "green", "medium": "orange", "low": "red"}.get(
                            str(feasibility).lower().split()[0], "gray"
                        )
                        st.markdown(f"**Feasibility:** :{color}[{feasibility}]")
                    st.markdown("---")

    def render_critiques(state):
        critiques = state.get("hypothesis_critiques", [])
        with critiques_placeholder.container():
            with st.expander(
                f"⚔️ Adversarial Review ({len(critiques)} hypotheses critiqued)",
                expanded=bool(critiques),
            ):
                for c in critiques:
                    idx = c.get("hypothesis_index", "?")
                    score = c.get("viability_score", "?")
                    st.markdown(f"#### Hypothesis {int(idx) + 1} — Viability after critique: `{score}/10`")

                    if c.get("counterarguments"):
                        st.markdown("**Counterarguments:**")
                        for arg in c["counterarguments"]:
                            st.markdown(f"- {arg}")

                    if c.get("logical_flaws"):
                        st.markdown("**Logical flaws:**")
                        for flaw in c["logical_flaws"]:
                            st.markdown(f"- {flaw}")

                    if c.get("refined_claim"):
                        st.markdown(f"**Refined claim:** {c['refined_claim']}")

                    st.markdown("---")

    def render_experiment(state):
        with experiment_placeholder.container():
            with st.expander("🧪 Experiment Design", expanded=bool(state.get("experiment_design"))):
                exp = state.get("experiment_design", {})
                if exp:
                    if exp.get("methodology"):
                        st.subheader("Methodology")
                        for i, step in enumerate(exp["methodology"], 1):
                            st.markdown(f"{i}. {step}")
                    if exp.get("baseline"):
                        st.subheader("Baseline")
                        st.write(exp["baseline"])
                    if exp.get("metrics"):
                        st.subheader("Metrics")
                        for m in exp["metrics"]:
                            st.markdown(f"- {m}")
                    if exp.get("datasets"):
                        st.subheader("Datasets")
                        for d in exp["datasets"]:
                            st.markdown(f"- {d}")
                    if exp.get("failure_modes"):
                        st.subheader("Failure Modes")
                        for fm in exp["failure_modes"]:
                            if isinstance(fm, dict):
                                st.markdown(
                                    f"**{fm.get('mode', '')}**: {fm.get('detection', '')}"
                                )
                            else:
                                st.markdown(f"- {fm}")

    def render_all(s):
        render_raw_papers(s)
        render_relevant_papers(s)
        render_snowball(s)
        render_synthesis(s)
        render_hypotheses(s)
        render_critiques(s)
        render_experiment(s)

    with st.status("Running research pipeline...", expanded=True) as status_box:
        running = True

        while running:
            try:
                event = event_queue.get(timeout=180)
            except queue.Empty:
                status_box.update(label="Pipeline timed out", state="error")
                st.error("The pipeline timed out. Please try again.")
                break

            kind, payload, state_snapshot = event

            if kind == "node_done":
                node_name = payload
                accumulated_state.update(state_snapshot)
                st.write(f"✅ {node_labels.get(node_name, node_name)} — done")
                render_all(accumulated_state)

                if accumulated_state.get("error"):
                    status_box.update(
                        label=f"Pipeline stopped: {accumulated_state['error']}",
                        state="error",
                    )
                    st.error(f"Error in {node_name}: {accumulated_state['error']}")
                    running = False

            elif kind == "done":
                accumulated_state.update(state_snapshot)
                status_box.update(label="Research pipeline complete!", state="complete")
                running = False

            elif kind == "error":
                status_box.update(label=f"Pipeline error: {payload}", state="error")
                st.error(f"Unexpected error: {payload}")
                running = False

    render_all(accumulated_state)

    if accumulated_state.get("experiment_design") and not accumulated_state.get("error"):
        st.markdown("---")

        def _build_markdown_report(state: dict) -> str:
            q = state.get("research_question", "")
            lines = [f"# Research Report\n\n**Question:** {q}\n"]

            lines.append("## Relevant Papers\n")
            for p in state.get("relevant_papers", []):
                lines.append(
                    f"- **{p['title']}** (Score: {p.get('relevance_score', '?')}/10) — "
                    f"{p.get('relevance_reason', '')}"
                )

            snow = state.get("snowballed_papers", [])
            if snow:
                lines.append("\n## Snowballed Papers (via citation graph)\n")
                for p in snow:
                    lines.append(f"- **{p['title']}** ({p.get('year', 'N/A')})")

            syn = state.get("synthesis", {})
            index_map = syn.get("_paper_index_map", {})
            lines.append("\n## Synthesis\n")

            def _cite_refs(indices):
                if not indices:
                    return ""
                return " [" + ", ".join(str(i) for i in indices) + "]"

            if syn.get("themes"):
                lines.append("### Themes")
                for item in syn["themes"]:
                    claim = item.get("claim", item) if isinstance(item, dict) else item
                    indices = item.get("paper_indices", []) if isinstance(item, dict) else []
                    lines.append(f"- {claim}{_cite_refs(indices)}")
            if syn.get("gaps"):
                lines.append("\n### Gaps")
                for item in syn["gaps"]:
                    claim = item.get("claim", item) if isinstance(item, dict) else item
                    indices = item.get("paper_indices", []) if isinstance(item, dict) else []
                    lines.append(f"- {claim}{_cite_refs(indices)}")
            if syn.get("contradictions"):
                lines.append("\n### Contradictions")
                for c in syn["contradictions"]:
                    if isinstance(c, dict):
                        indices = c.get("paper_indices", [])
                        lines.append(
                            f"- **{c.get('paper_a','')}** vs **{c.get('paper_b','')}**: "
                            f"{c.get('description','')}{_cite_refs(indices)}"
                        )
            if syn.get("open_questions"):
                lines.append("\n### Open Questions")
                for item in syn["open_questions"]:
                    claim = item.get("claim", item) if isinstance(item, dict) else item
                    indices = item.get("paper_indices", []) if isinstance(item, dict) else []
                    lines.append(f"- {claim}{_cite_refs(indices)}")

            if index_map:
                lines.append("\n### Paper Index\n")
                for i, title in sorted(index_map.items(), key=lambda x: x[0]):
                    lines.append(f"[{i}] {title}")

            lines.append("\n## Hypotheses\n")
            for i, h in enumerate(state.get("hypotheses", []), 1):
                viability = h.get("viability_score", "")
                lines.append(f"### Hypothesis {i}" + (f" (viability: {viability}/10)" if viability else ""))
                refined = h.get("refined_claim", "")
                original = h.get("claim", "")
                if refined and refined != original:
                    lines.append(f"**Original:** {original}")
                    lines.append(f"**Refined:** {refined}")
                else:
                    lines.append(f"**Claim:** {original}")
                lines.append(f"**Motivation:** {h.get('motivation','')}")
                lines.append(f"**Falsification:** {h.get('falsification','')}")
                lines.append(f"**Feasibility:** {h.get('feasibility','')}\n")

            critiques = state.get("hypothesis_critiques", [])
            if critiques:
                lines.append("## Adversarial Review\n")
                for c in critiques:
                    idx = c.get("hypothesis_index", "?")
                    lines.append(f"### Hypothesis {int(idx)+1} — Viability: {c.get('viability_score','?')}/10")
                    for arg in c.get("counterarguments", []):
                        lines.append(f"- Counterargument: {arg}")
                    for flaw in c.get("logical_flaws", []):
                        lines.append(f"- Flaw: {flaw}")
                    if c.get("refined_claim"):
                        lines.append(f"- Refined: {c['refined_claim']}\n")

            exp = state.get("experiment_design", {})
            lines.append("\n## Experiment Design\n")
            if exp.get("methodology"):
                lines.append("### Methodology")
                for i, s in enumerate(exp["methodology"], 1):
                    lines.append(f"{i}. {s}")
            if exp.get("baseline"):
                lines.append(f"\n**Baseline:** {exp['baseline']}")
            if exp.get("metrics"):
                lines.append("\n### Metrics\n" + "\n".join(f"- {m}" for m in exp["metrics"]))
            if exp.get("datasets"):
                lines.append("\n### Datasets\n" + "\n".join(f"- {d}" for d in exp["datasets"]))
            if exp.get("failure_modes"):
                lines.append("\n### Failure Modes")
                for fm in exp["failure_modes"]:
                    if isinstance(fm, dict):
                        lines.append(f"- **{fm.get('mode','')}**: {fm.get('detection','')}")

            return "\n".join(lines)

        report_md = _build_markdown_report(accumulated_state)
        st.download_button(
            label="⬇️ Export Markdown Report",
            data=report_md,
            file_name="research_report.md",
            mime="text/markdown",
        )
