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
        "synthesis": {},
        "hypotheses": [],
        "experiment_design": {},
        "error": None,
        "retry_count": 0,
    }

    event_queue: queue.Queue = queue.Queue()
    final_state_container: dict = {}

    def run_graph():
        try:
            graph = build_graph()
            state = dict(initial_state)
            node_order = ["search_node", "critic_node", "synthesis_node", "hypothesis_node", "experiment_node"]
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
        "synthesis_node": "Synthesizing literature (Claude synthesis)",
        "hypothesis_node": "Generating hypotheses (Claude)",
        "experiment_node": "Designing experiment (Claude)",
    }

    accumulated_state: dict = dict(initial_state)

    raw_placeholder = st.empty()
    relevant_placeholder = st.empty()
    synthesis_placeholder = st.empty()
    hypotheses_placeholder = st.empty()
    experiment_placeholder = st.empty()

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
                f"✅ Relevant Papers ({len(state.get('relevant_papers', []))} selected)",
                expanded=bool(state.get("relevant_papers")),
            ):
                for p in state.get("relevant_papers", []):
                    score = p.get("relevance_score", "?")
                    reason = p.get("relevance_reason", "")
                    st.markdown(f"**{p['title']}** — Score: `{score}/10`")
                    st.caption(f"{reason}")
                    st.markdown("---")

    def render_synthesis(state):
        with synthesis_placeholder.container():
            with st.expander("🔍 Literature Synthesis", expanded=bool(state.get("synthesis"))):
                syn = state.get("synthesis", {})
                if syn:
                    if syn.get("themes"):
                        st.subheader("Major Themes")
                        for t in syn["themes"]:
                            st.markdown(f"- {t}")
                    if syn.get("gaps"):
                        st.subheader("Research Gaps")
                        for g in syn["gaps"]:
                            st.markdown(f"- {g}")
                    if syn.get("contradictions"):
                        st.subheader("Contradictions")
                        for c in syn["contradictions"]:
                            if isinstance(c, dict):
                                st.markdown(
                                    f"**{c.get('paper_a', '')}** vs **{c.get('paper_b', '')}**: "
                                    f"{c.get('description', '')}"
                                )
                            else:
                                st.markdown(f"- {c}")
                    if syn.get("open_questions"):
                        st.subheader("Open Questions")
                        for q in syn["open_questions"]:
                            st.markdown(f"- {q}")

    def render_hypotheses(state):
        with hypotheses_placeholder.container():
            with st.expander("💡 Research Hypotheses", expanded=bool(state.get("hypotheses"))):
                for i, h in enumerate(state.get("hypotheses", []), 1):
                    st.markdown(f"### Hypothesis {i}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Claim:** {h.get('claim', '')}")
                        st.markdown(f"**Motivation:** {h.get('motivation', '')}")
                    with col2:
                        st.markdown(f"**Falsification:** {h.get('falsification', '')}")
                        feasibility = h.get("feasibility", "")
                        color = {"high": "green", "medium": "orange", "low": "red"}.get(
                            str(feasibility).lower().split()[0], "gray"
                        )
                        st.markdown(f"**Feasibility:** :{color}[{feasibility}]")
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

    with st.status("Running research pipeline...", expanded=True) as status_box:
        running = True
        final_state: dict = {}

        while running:
            try:
                event = event_queue.get(timeout=120)
            except queue.Empty:
                status_box.update(label="Pipeline timed out", state="error")
                st.error("The pipeline timed out. Please try again.")
                break

            kind, payload, state_snapshot = event

            if kind == "node_done":
                node_name = payload
                accumulated_state.update(state_snapshot)
                st.write(f"✅ {node_labels.get(node_name, node_name)} — done")

                render_raw_papers(accumulated_state)
                render_relevant_papers(accumulated_state)
                render_synthesis(accumulated_state)
                render_hypotheses(accumulated_state)
                render_experiment(accumulated_state)

                if accumulated_state.get("error"):
                    status_box.update(
                        label=f"Pipeline stopped: {accumulated_state['error']}",
                        state="error",
                    )
                    st.error(f"Error in {node_name}: {accumulated_state['error']}")
                    running = False

            elif kind == "done":
                accumulated_state.update(state_snapshot)
                final_state = accumulated_state
                status_box.update(label="Research pipeline complete!", state="complete")
                running = False

            elif kind == "error":
                status_box.update(label=f"Pipeline error: {payload}", state="error")
                st.error(f"Unexpected error: {payload}")
                running = False

    render_raw_papers(accumulated_state)
    render_relevant_papers(accumulated_state)
    render_synthesis(accumulated_state)
    render_hypotheses(accumulated_state)
    render_experiment(accumulated_state)

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

            syn = state.get("synthesis", {})
            lines.append("\n## Synthesis\n")
            if syn.get("themes"):
                lines.append("### Themes\n" + "\n".join(f"- {t}" for t in syn["themes"]))
            if syn.get("gaps"):
                lines.append("\n### Gaps\n" + "\n".join(f"- {g}" for g in syn["gaps"]))
            if syn.get("contradictions"):
                lines.append("\n### Contradictions")
                for c in syn["contradictions"]:
                    if isinstance(c, dict):
                        lines.append(
                            f"- **{c.get('paper_a','')}** vs **{c.get('paper_b','')}**: "
                            f"{c.get('description','')}"
                        )
            if syn.get("open_questions"):
                lines.append("\n### Open Questions\n" + "\n".join(f"- {q}" for q in syn["open_questions"]))

            lines.append("\n## Hypotheses\n")
            for i, h in enumerate(state.get("hypotheses", []), 1):
                lines.append(f"### Hypothesis {i}")
                lines.append(f"**Claim:** {h.get('claim','')}")
                lines.append(f"**Motivation:** {h.get('motivation','')}")
                lines.append(f"**Falsification:** {h.get('falsification','')}")
                lines.append(f"**Feasibility:** {h.get('feasibility','')}\n")

            exp = state.get("experiment_design", {})
            lines.append("## Experiment Design\n")
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
