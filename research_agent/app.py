import sys
import os
import html
import queue
import threading
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from graph import build_graph
from state import ResearchState

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ---- base ---- */
.stApp { background: #0a0e1a; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem; max-width: 1100px; }

/* ---- input ---- */
.stTextInput > div > div > input {
    background: #0f1729 !important;
    border: 1px solid #1e2d45 !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-size: 1rem !important;
    padding: 0.75rem 1rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #00d4ff !important;
    box-shadow: 0 0 0 2px rgba(0,212,255,0.15) !important;
}

/* ---- primary button ---- */
.stButton > button[kind="primary"] {
    background: #00d4ff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 2rem !important;
    color: #fff !important;
    transition: opacity 0.2s !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.85 !important; }

/* ---- expanders ---- */
.streamlit-expanderHeader {
    background: #0f1729 !important;
    border: 1px solid #1e2d45 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    color: #e2e8f0 !important;
}
.streamlit-expanderContent {
    background: #0a0e1a !important;
    border: 1px solid #1e2d45 !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
}

/* ---- dataframe ---- */
.stDataFrame { border-radius: 10px; overflow: hidden; }

/* ---- status widget ---- */
[data-testid="stStatusWidget"] { background: #0f1729 !important; border-color: #1e2d45 !important; }

/* ---- pipeline ---- */
.pipeline-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 28px 24px;
    background: rgba(255,255,255,0.025);
    border: 1px solid #1e2d45;
    border-radius: 16px;
    margin: 20px 0;
    flex-wrap: wrap;
}
.p-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    min-width: 74px;
}
.p-bubble {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    transition: all 0.3s ease;
}
.p-bubble.pending  {
    background: rgba(255,255,255,0.04);
    border: 2px solid rgba(255,255,255,0.1);
    opacity: 0.4;
    filter: grayscale(1);
}
.p-bubble.running  {
    background: rgba(0,212,255,0.12);
    border: 2px solid #00d4ff;
    box-shadow: 0 0 18px rgba(0,212,255,0.5);
    animation: nodePulse 1.4s ease-in-out infinite;
}
.p-bubble.complete {
    background: rgba(16,185,129,0.12);
    border: 2px solid #10b981;
    box-shadow: 0 0 12px rgba(16,185,129,0.3);
}
.p-bubble.error    {
    background: rgba(239,68,68,0.12);
    border: 2px solid #ef4444;
}
.p-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    text-align: center;
    color: #475569;
}
.p-label.running  { color: #00d4ff; }
.p-label.complete { color: #10b981; }
.p-label.error    { color: #ef4444; }
.p-sublabel {
    font-size: 9px;
    color: #334155;
    text-align: center;
    margin-top: -6px;
}
.p-sublabel.running  { color: rgba(0,212,255,0.6); }
.p-sublabel.complete { color: rgba(16,185,129,0.6); }
.p-arrow { color: #1e2d45; font-size: 18px; flex-shrink: 0; }

@keyframes nodePulse {
    0%,100% { box-shadow: 0 0 18px rgba(0,212,255,0.5); transform: scale(1); }
    50%      { box-shadow: 0 0 30px rgba(0,212,255,0.9); transform: scale(1.07); }
}

/* ---- cards ---- */
.paper-card {
    background: #0f1729;
    border: 1px solid #1e2d45;
    border-left: 3px solid #00d4ff;
    border-radius: 10px;
    padding: 14px 16px;
    margin: 8px 0;
}
.paper-title { font-weight: 600; color: #e2e8f0; font-size: 0.9rem; }
.paper-meta  { color: #64748b; font-size: 0.8rem; margin-top: 4px; }
.score-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    margin-left: 8px;
}
.score-high { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.4); }
.score-mid  { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.4); }
.score-low  { background: rgba(239,68,68,0.15);  color: #ef4444; border: 1px solid rgba(239,68,68,0.4); }

.cite-badge {
    display: inline-block;
    background: rgba(124,58,237,0.15);
    color: #a78bfa;
    border: 1px solid rgba(124,58,237,0.3);
    border-radius: 6px;
    padding: 1px 7px;
    font-size: 10px;
    font-weight: 600;
    margin: 2px 3px;
    font-family: monospace;
}

.syn-item {
    background: rgba(255,255,255,0.03);
    border: 1px solid #1e2d45;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 6px 0;
    color: #cbd5e1;
    font-size: 0.88rem;
    line-height: 1.55;
}
.syn-section-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 18px 0 8px;
}
.syn-section-label.themes  { color: #00d4ff; }
.syn-section-label.gaps    { color: #f59e0b; }
.syn-section-label.contra  { color: #f472b6; }
.syn-section-label.open    { color: #a78bfa; }

.hyp-card {
    background: rgba(124,58,237,0.06);
    border: 1px solid rgba(124,58,237,0.25);
    border-radius: 14px;
    padding: 20px 22px;
    margin: 12px 0;
}
.hyp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
}
.hyp-num {
    background: #7c3aed;
    color: #fff;
    font-weight: 800;
    font-size: 0.8rem;
    padding: 3px 12px;
    border-radius: 20px;
}
.viability-wrap { display: flex; align-items: center; gap: 10px; }
.viability-bar-outer {
    width: 100px;
    height: 5px;
    background: rgba(255,255,255,0.08);
    border-radius: 3px;
    overflow: hidden;
}
.viability-bar-inner {
    height: 100%;
    border-radius: 3px;
    background: #00d4ff;
}
.viability-score { color: #00d4ff; font-weight: 700; font-size: 0.85rem; }

.field-label { color: #64748b; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 3px; margin-top: 12px; }
.field-value { color: #cbd5e1; font-size: 0.88rem; line-height: 1.55; }
.refined-tag {
    display: inline-block;
    background: rgba(0,212,255,0.1);
    color: #00d4ff;
    border: 1px solid rgba(0,212,255,0.3);
    border-radius: 6px;
    padding: 1px 8px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}
.feasibility-high { color: #10b981; font-weight: 600; }
.feasibility-medium { color: #f59e0b; font-weight: 600; }
.feasibility-low  { color: #ef4444; font-weight: 600; }

.critique-card {
    background: rgba(239,68,68,0.04);
    border: 1px solid rgba(239,68,68,0.15);
    border-left: 3px solid #ef4444;
    border-radius: 10px;
    padding: 16px 18px;
    margin: 10px 0;
}
.critique-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.critique-title { color: #f1f5f9; font-weight: 700; font-size: 0.92rem; }
.viability-chip {
    padding: 3px 12px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.8rem;
}
.bullet-list { list-style: none; padding: 0; margin: 6px 0; }
.bullet-list li {
    color: #94a3b8;
    font-size: 0.85rem;
    padding: 4px 0;
    padding-left: 16px;
    position: relative;
    line-height: 1.5;
}
.bullet-list li::before { content: "›"; position: absolute; left: 0; color: #475569; }

.exp-step {
    display: flex;
    gap: 14px;
    align-items: flex-start;
    padding: 10px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.exp-step:last-child { border-bottom: none; }
.step-num {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: rgba(0,212,255,0.1);
    border: 1px solid rgba(0,212,255,0.3);
    color: #00d4ff;
    font-weight: 700;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
}
.step-text { color: #cbd5e1; font-size: 0.88rem; line-height: 1.55; }

.tag {
    display: inline-block;
    background: rgba(255,255,255,0.06);
    color: #94a3b8;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.8rem;
    margin: 3px 4px 3px 0;
}
.tag.dataset { background: rgba(0,212,255,0.08); color: #67e8f9; border-color: rgba(0,212,255,0.2); }
.tag.metric  { background: rgba(16,185,129,0.08); color: #6ee7b7; border-color: rgba(16,185,129,0.2); }

.failure-row {
    background: rgba(245,158,11,0.05);
    border: 1px solid rgba(245,158,11,0.15);
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
}
.failure-mode { color: #fbbf24; font-weight: 600; font-size: 0.85rem; }
.failure-detect { color: #94a3b8; font-size: 0.82rem; margin-top: 3px; }

.divider { border: none; border-top: 1px solid #1e2d45; margin: 20px 0; }

.section-title {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #475569;
    margin: 16px 0 8px;
}
</style>
""", unsafe_allow_html=True)


# ── Pipeline definition ───────────────────────────────────────────────────────
PIPELINE = [
    ("search_node",    "🔍", "Search",     "S2 + ArXiv"),
    ("critic_node",    "⚖️", "Critic",     "Relevance"),
    ("snowball_node",  "❄️", "Snowball",   "Citations"),
    ("synthesis_node", "🧠", "Synthesis",  "Grounded"),
    ("hypothesis_node","💡", "Hypotheses", "Novel"),
    ("advocate_node",  "⚔️", "Advocate",  "Critique"),
    ("experiment_node","🧪", "Experiment", "Design"),
]
PIPELINE_IDS = [n[0] for n in PIPELINE]


def _pipeline_next(node_id: str) -> str | None:
    idx = PIPELINE_IDS.index(node_id) if node_id in PIPELINE_IDS else -1
    return PIPELINE_IDS[idx + 1] if idx >= 0 and idx + 1 < len(PIPELINE_IDS) else None


def render_pipeline(statuses: dict) -> str:
    parts = []
    for i, (nid, icon, label, sub) in enumerate(PIPELINE):
        s = statuses.get(nid, "pending")
        parts.append(
            f'<div class="p-node">'
            f'  <div class="p-bubble {s}">{icon}</div>'
            f'  <div class="p-label {s}">{label}</div>'
            f'  <div class="p-sublabel {s}">{sub}</div>'
            f'</div>'
        )
        if i < len(PIPELINE) - 1:
            parts.append('<div class="p-arrow">›</div>')
    return f'<div class="pipeline-wrap">{"".join(parts)}</div>'


# ── HTML card helpers ─────────────────────────────────────────────────────────
def _h(text) -> str:
    return html.escape(str(text)) if text else ""


def _score_class(score) -> str:
    try:
        s = int(score)
        if s >= 8: return "score-high"
        if s >= 6: return "score-mid"
        return "score-low"
    except Exception:
        return "score-mid"


def _viability_color(score) -> str:
    try:
        s = int(score)
        if s >= 7: return "#10b981"
        if s >= 4: return "#f59e0b"
        return "#ef4444"
    except Exception:
        return "#94a3b8"


def _cite_badges(indices: list, index_map: dict) -> str:
    if not indices:
        return ""
    badges = "".join(
        f'<span class="cite-badge" title="{_h(index_map.get(i, ""))}">[{i}]</span>'
        for i in indices
    )
    return f'<div style="margin-top:6px">{badges}</div>'


def render_paper_card(p: dict, show_score: bool = False) -> str:
    title = _h(p.get("title", ""))
    year = _h(p.get("year", ""))
    src = _h(p.get("source", ""))
    authors = _h(", ".join(p.get("authors", [])[:3]))
    cites = p.get("citation_count", 0)
    score_html = ""
    reason_html = ""
    if show_score and "relevance_score" in p:
        sc = p["relevance_score"]
        cls = _score_class(sc)
        score_html = f'<span class="score-badge {cls}">{sc}/10</span>'
        reason_html = f'<div class="paper-meta" style="margin-top:6px;font-style:italic">{_h(p.get("relevance_reason",""))}</div>'
    return (
        f'<div class="paper-card">'
        f'  <div class="paper-title">{title}{score_html}</div>'
        f'  <div class="paper-meta">{authors} · {year} · {src}'
        + (f' · {cites:,} citations' if cites else "") +
        f'  </div>{reason_html}'
        f'</div>'
    )


def render_synthesis_section(syn: dict) -> str:
    index_map = syn.get("_paper_index_map", {})
    out = []

    def _items(key, label, css_class, contra=False):
        items = syn.get(key, [])
        if not items:
            return
        out.append(f'<div class="syn-section-label {css_class}">{label}</div>')
        for item in items:
            if not isinstance(item, dict):
                out.append(f'<div class="syn-item">{_h(item)}</div>')
                continue
            if contra:
                claim = f'<strong>{_h(item.get("paper_a",""))}</strong> vs <strong>{_h(item.get("paper_b",""))}</strong>: {_h(item.get("description",""))}'
            else:
                claim = _h(item.get("claim", ""))
            badges = _cite_badges(item.get("paper_indices", []), index_map)
            out.append(f'<div class="syn-item">{claim}{badges}</div>')

    _items("themes", "⬡ Major Themes", "themes")
    _items("gaps", "◎ Research Gaps", "gaps")
    _items("contradictions", "⚡ Contradictions", "contra", contra=True)
    _items("open_questions", "? Open Questions", "open")
    return "".join(out)


def render_hypothesis_card(h: dict, idx: int) -> str:
    viability = h.get("viability_score")
    refined = h.get("refined_claim", "")
    original = h.get("claim", "")
    feasibility = str(h.get("feasibility", "")).lower()
    feas_cls = "feasibility-" + (
        "high" if "high" in feasibility else
        "medium" if "medium" in feasibility else
        "low" if "low" in feasibility else "medium"
    )

    viab_html = ""
    if viability is not None:
        pct = min(int(viability) * 10, 100)
        color = _viability_color(viability)
        viab_html = (
            f'<div class="viability-wrap">'
            f'  <div class="viability-bar-outer"><div class="viability-bar-inner" style="width:{pct}%"></div></div>'
            f'  <span class="viability-score" style="color:{color}">{viability}/10</span>'
            f'</div>'
        )

    claim_html = ""
    if refined and refined != original:
        claim_html = (
            f'<div class="field-label">Original Claim</div>'
            f'<div class="field-value" style="color:#64748b;text-decoration:line-through;">{_h(original)}</div>'
            f'<div style="margin-top:8px"><span class="refined-tag">Refined after review</span></div>'
            f'<div class="field-value">{_h(refined)}</div>'
        )
    else:
        claim_html = (
            f'<div class="field-label">Claim</div>'
            f'<div class="field-value">{_h(original)}</div>'
        )

    return (
        f'<div class="hyp-card">'
        f'  <div class="hyp-header">'
        f'    <span class="hyp-num">H{idx}</span>'
        f'    {viab_html}'
        f'  </div>'
        f'  {claim_html}'
        f'  <div class="field-label">Motivation</div>'
        f'  <div class="field-value">{_h(h.get("motivation",""))}</div>'
        f'  <div class="field-label">Falsification criterion</div>'
        f'  <div class="field-value">{_h(h.get("falsification",""))}</div>'
        f'  <div class="field-label">Feasibility</div>'
        f'  <div class="field-value"><span class="{feas_cls}">{_h(h.get("feasibility",""))}</span></div>'
        f'</div>'
    )


def render_critique_card(c: dict) -> str:
    idx = c.get("hypothesis_index", 0)
    score = c.get("viability_score", "?")
    color = _viability_color(score)

    counter_html = "".join(
        f'<li>{_h(a)}</li>' for a in c.get("counterarguments", [])
    )
    flaws_html = "".join(
        f'<li>{_h(f)}</li>' for f in c.get("logical_flaws", [])
    )
    refined_html = (
        f'<div class="field-label" style="margin-top:10px">Refined claim</div>'
        f'<div class="field-value" style="color:#a5b4fc">{_h(c["refined_claim"])}</div>'
        if c.get("refined_claim") else ""
    )

    return (
        f'<div class="critique-card">'
        f'  <div class="critique-header">'
        f'    <span class="critique-title">Hypothesis {int(idx)+1}</span>'
        f'    <span class="viability-chip" style="background:rgba(0,0,0,0.3);color:{color};border:1px solid {color}">'
        f'      Viability {score}/10</span>'
        f'  </div>'
        + (f'<div class="section-title">Counterarguments</div><ul class="bullet-list">{counter_html}</ul>' if counter_html else "")
        + (f'<div class="section-title">Logical flaws</div><ul class="bullet-list">{flaws_html}</ul>' if flaws_html else "")
        + refined_html +
        f'</div>'
    )


def render_experiment_section(exp: dict) -> str:
    out = []

    steps = exp.get("methodology", [])
    if steps:
        out.append('<div class="section-title">Methodology</div>')
        for i, step in enumerate(steps, 1):
            out.append(
                f'<div class="exp-step">'
                f'  <div class="step-num">{i}</div>'
                f'  <div class="step-text">{_h(step)}</div>'
                f'</div>'
            )

    if exp.get("baseline"):
        out.append('<div class="section-title">Baseline</div>')
        out.append(f'<div class="syn-item">{_h(exp["baseline"])}</div>')

    metrics = exp.get("metrics", [])
    if metrics:
        out.append('<div class="section-title">Metrics</div>')
        tags = "".join(f'<span class="tag metric">{_h(m)}</span>' for m in metrics)
        out.append(f'<div style="padding:4px 0">{tags}</div>')

    datasets = exp.get("datasets", [])
    if datasets:
        out.append('<div class="section-title">Datasets</div>')
        tags = "".join(f'<span class="tag dataset">{_h(d)}</span>' for d in datasets)
        out.append(f'<div style="padding:4px 0">{tags}</div>')

    fms = exp.get("failure_modes", [])
    if fms:
        out.append('<div class="section-title">Failure Modes</div>')
        for fm in fms:
            if isinstance(fm, dict):
                out.append(
                    f'<div class="failure-row">'
                    f'  <div class="failure-mode">⚠ {_h(fm.get("mode",""))}</div>'
                    f'  <div class="failure-detect">{_h(fm.get("detection",""))}</div>'
                    f'</div>'
                )

    return "".join(out)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:10px 0 24px">
  <div style="font-size:2.6rem;font-weight:900;color:#00d4ff;letter-spacing:-0.02em">
    AI Agents Research Assistant
  </div>
  <div style="color:#475569;font-size:0.95rem;margin-top:6px;letter-spacing:0.04em">
    LangGraph · Semantic Scholar · ArXiv · Claude
  </div>
</div>
""", unsafe_allow_html=True)

# ── Input ─────────────────────────────────────────────────────────────────────
col_input, col_btn = st.columns([5, 1])
with col_input:
    research_question = st.text_input(
        "research_question",
        label_visibility="collapsed",
        placeholder="Enter a research question — e.g. How do LLM agents handle multi-step tool use?",
    )
with col_btn:
    run_button = st.button("Run ›", type="primary", use_container_width=True,
                           disabled=not research_question.strip())

# ── Run ───────────────────────────────────────────────────────────────────────
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
            completed = set()
            for event in graph.stream(state, stream_mode="updates"):
                for node_name, node_state in event.items():
                    if node_name in PIPELINE_IDS and node_name not in completed:
                        completed.add(node_name)
                        state.update(node_state)
                        event_queue.put(("node_done", node_name, dict(state)))
            event_queue.put(("done", None, dict(state)))
        except Exception as e:
            event_queue.put(("error", str(e), {}))

    thread = threading.Thread(target=run_graph, daemon=True)
    thread.start()

    # placeholders
    pipeline_ph = st.empty()
    status_ph   = st.empty()
    raw_ph      = st.empty()
    relevant_ph = st.empty()
    snow_ph     = st.empty()
    syn_ph      = st.empty()
    hyp_ph      = st.empty()
    crit_ph     = st.empty()
    exp_ph      = st.empty()

    node_statuses = {nid: "pending" for nid in PIPELINE_IDS}
    node_statuses["search_node"] = "running"
    accumulated = dict(initial_state)

    pipeline_ph.markdown(render_pipeline(node_statuses), unsafe_allow_html=True)

    def refresh_sections(s):
        # Raw papers
        raw = s.get("raw_papers", [])
        if raw:
            cards = "".join(render_paper_card(p) for p in raw)
            raw_ph.markdown(
                f'<details><summary style="cursor:pointer;color:#64748b;font-size:0.85rem;'
                f'font-weight:600;padding:8px 0">📚 Raw Papers ({len(raw)} retrieved)</summary>'
                f'<div style="padding-top:8px">{cards}</div></details>',
                unsafe_allow_html=True,
            )

        # Relevant papers
        rel = s.get("relevant_papers", [])
        if rel:
            cards = "".join(render_paper_card(p, show_score=True) for p in rel)
            relevant_ph.markdown(
                f'<details open><summary style="cursor:pointer;color:#00d4ff;font-size:0.9rem;'
                f'font-weight:700;padding:8px 0">✅ Relevant Papers — {len(rel)} selected by critic</summary>'
                f'<div style="padding-top:8px">{cards}</div></details>',
                unsafe_allow_html=True,
            )

        # Snowballed
        snow = s.get("snowballed_papers", [])
        if snow:
            cards = "".join(render_paper_card(p) for p in snow)
            snow_ph.markdown(
                f'<details><summary style="cursor:pointer;color:#67e8f9;font-size:0.9rem;'
                f'font-weight:700;padding:8px 0">❄️ Snowballed Papers — {len(snow)} via citation graph</summary>'
                f'<div style="padding-top:8px">{cards}</div></details>',
                unsafe_allow_html=True,
            )

        # Synthesis
        syn = s.get("synthesis", {})
        if syn:
            content = render_synthesis_section(syn)
            syn_ph.markdown(
                f'<details open><summary style="cursor:pointer;color:#a78bfa;font-size:0.9rem;'
                f'font-weight:700;padding:8px 0">🧠 Literature Synthesis (grounded)</summary>'
                f'<div style="padding-top:8px">{content}</div></details>',
                unsafe_allow_html=True,
            )

        # Hypotheses
        hyps = s.get("hypotheses", [])
        if hyps:
            cards = "".join(render_hypothesis_card(h, i+1) for i, h in enumerate(hyps))
            hyp_ph.markdown(
                f'<details open><summary style="cursor:pointer;color:#c084fc;font-size:0.9rem;'
                f'font-weight:700;padding:8px 0">💡 Research Hypotheses — {len(hyps)} generated</summary>'
                f'<div style="padding-top:8px">{cards}</div></details>',
                unsafe_allow_html=True,
            )

        # Critiques
        crits = s.get("hypothesis_critiques", [])
        if crits:
            cards = "".join(render_critique_card(c) for c in crits)
            crit_ph.markdown(
                f'<details open><summary style="cursor:pointer;color:#f87171;font-size:0.9rem;'
                f'font-weight:700;padding:8px 0">⚔️ Adversarial Review — {len(crits)} hypotheses critiqued</summary>'
                f'<div style="padding-top:8px">{cards}</div></details>',
                unsafe_allow_html=True,
            )

        # Experiment
        exp = s.get("experiment_design", {})
        if exp:
            content = render_experiment_section(exp)
            exp_ph.markdown(
                f'<details open><summary style="cursor:pointer;color:#34d399;font-size:0.9rem;'
                f'font-weight:700;padding:8px 0">🧪 Experiment Design</summary>'
                f'<div style="padding-top:8px">{content}</div></details>',
                unsafe_allow_html=True,
            )

    node_display = {
        "search_node":    "Searching Semantic Scholar + ArXiv",
        "critic_node":    "Evaluating paper relevance",
        "snowball_node":  "Expanding via citation graph",
        "synthesis_node": "Synthesizing literature",
        "hypothesis_node":"Generating hypotheses",
        "advocate_node":  "Running adversarial review",
        "experiment_node":"Designing experiment",
    }

    running = True
    while running:
        try:
            event = event_queue.get(timeout=180)
        except queue.Empty:
            status_ph.error("Pipeline timed out.")
            break

        kind, payload, snap = event

        if kind == "node_done":
            node_name = payload
            accumulated.update(snap)

            node_statuses[node_name] = "complete" if not snap.get("error") else "error"
            nxt = _pipeline_next(node_name)
            if nxt and not snap.get("error"):
                node_statuses[nxt] = "running"

            pipeline_ph.markdown(render_pipeline(node_statuses), unsafe_allow_html=True)
            status_ph.markdown(
                f'<div style="color:#64748b;font-size:0.82rem;text-align:center;padding:4px 0">'
                f'⟳ {node_display.get(node_name, node_name)} — done</div>',
                unsafe_allow_html=True,
            )
            refresh_sections(accumulated)

            if snap.get("error"):
                status_ph.error(f"Error in {node_name}: {snap['error']}")
                running = False

        elif kind == "done":
            accumulated.update(snap)
            pipeline_ph.markdown(render_pipeline(node_statuses), unsafe_allow_html=True)
            status_ph.markdown(
                '<div style="color:#10b981;font-size:0.85rem;text-align:center;padding:6px 0;font-weight:600">'
                '✓ Pipeline complete</div>',
                unsafe_allow_html=True,
            )
            refresh_sections(accumulated)
            running = False

        elif kind == "error":
            status_ph.error(f"Unexpected error: {payload}")
            running = False

    # ── Export ────────────────────────────────────────────────────────────────
    if accumulated.get("experiment_design") and not accumulated.get("error"):
        st.markdown('<hr class="divider">', unsafe_allow_html=True)

        def _build_report(s: dict) -> str:
            q = s.get("research_question", "")
            lines = [f"# Research Report\n\n**Question:** {q}\n"]

            lines.append("## Relevant Papers\n")
            for p in s.get("relevant_papers", []):
                lines.append(f"- **{p['title']}** ({p.get('relevance_score','?')}/10) — {p.get('relevance_reason','')}")

            snow = s.get("snowballed_papers", [])
            if snow:
                lines.append("\n## Snowballed Papers\n")
                for p in snow:
                    lines.append(f"- {p['title']} ({p.get('year','N/A')})")

            syn = s.get("synthesis", {})
            im = syn.get("_paper_index_map", {})
            lines.append("\n## Synthesis\n")
            for section, label in [("themes","Themes"),("gaps","Gaps"),("contradictions","Contradictions"),("open_questions","Open Questions")]:
                items = syn.get(section, [])
                if not items: continue
                lines.append(f"### {label}")
                for item in items:
                    if not isinstance(item, dict): lines.append(f"- {item}"); continue
                    if section == "contradictions":
                        refs = " [" + ",".join(str(i) for i in item.get("paper_indices",[])) + "]" if item.get("paper_indices") else ""
                        lines.append(f"- **{item.get('paper_a','')}** vs **{item.get('paper_b','')}**: {item.get('description','')}{refs}")
                    else:
                        refs = " [" + ",".join(str(i) for i in item.get("paper_indices",[])) + "]" if item.get("paper_indices") else ""
                        lines.append(f"- {item.get('claim','')}{refs}")
            if im:
                lines.append("\n### Paper Index")
                for i, t in sorted(im.items(), key=lambda x: x[0]): lines.append(f"[{i}] {t}")

            lines.append("\n## Hypotheses\n")
            for i, h in enumerate(s.get("hypotheses",[]), 1):
                v = h.get("viability_score","")
                lines.append(f"### H{i}" + (f" (viability {v}/10)" if v else ""))
                refined = h.get("refined_claim","")
                original = h.get("claim","")
                if refined and refined != original:
                    lines.append(f"**Original:** {original}")
                    lines.append(f"**Refined:** {refined}")
                else:
                    lines.append(f"**Claim:** {original}")
                lines.append(f"**Motivation:** {h.get('motivation','')}")
                lines.append(f"**Falsification:** {h.get('falsification','')}")
                lines.append(f"**Feasibility:** {h.get('feasibility','')}\n")

            crits = s.get("hypothesis_critiques", [])
            if crits:
                lines.append("## Adversarial Review\n")
                for c in crits:
                    lines.append(f"### H{int(c.get('hypothesis_index',0))+1} — viability {c.get('viability_score','?')}/10")
                    for a in c.get("counterarguments",[]): lines.append(f"- Counter: {a}")
                    for f in c.get("logical_flaws",[]): lines.append(f"- Flaw: {f}")
                    if c.get("refined_claim"): lines.append(f"- Refined: {c['refined_claim']}\n")

            exp = s.get("experiment_design", {})
            lines.append("\n## Experiment Design\n")
            if exp.get("methodology"):
                lines.append("### Methodology")
                for i, step in enumerate(exp["methodology"],1): lines.append(f"{i}. {step}")
            if exp.get("baseline"): lines.append(f"\n**Baseline:** {exp['baseline']}")
            if exp.get("metrics"): lines.append("\n### Metrics\n" + "\n".join(f"- {m}" for m in exp["metrics"]))
            if exp.get("datasets"): lines.append("\n### Datasets\n" + "\n".join(f"- {d}" for d in exp["datasets"]))
            if exp.get("failure_modes"):
                lines.append("\n### Failure Modes")
                for fm in exp["failure_modes"]:
                    if isinstance(fm, dict): lines.append(f"- **{fm.get('mode','')}**: {fm.get('detection','')}")
            return "\n".join(lines)

        st.download_button(
            label="⬇️ Export Markdown Report",
            data=_build_report(accumulated),
            file_name="research_report.md",
            mime="text/markdown",
        )
