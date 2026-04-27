# Presentation Script
## AI Agents Academic Research Assistant
*~15 minutes total · ~60–90 seconds per slide*

---

### Slide 1 — Title
*(~30 seconds)*

Thanks everyone. Today I'm presenting the AI Agents Academic Research Assistant — a project I built to automate the most painful parts of literature research in the AI agents field.

Instead of spending days reading papers just to form a single hypothesis, this system takes a research question and returns a full research brief: relevant papers, synthesized themes, novel hypotheses that have already been stress-tested, and a concrete experiment design.

Let me walk you through how it works.

---

### Slide 2 — The Problem
*(~90 seconds)*

The motivation came from a very real set of frustrations.

First, information overload. AI agents is one of the hottest subfields right now — which sounds great until you realize it means thousands of new papers every month. Nobody can keep up.

Second, keyword search is fundamentally shallow. You search for "tool-using LLM agents" and you get papers containing those words — but you miss the 2018 paper that introduced the concept everyone else is building on, and the 2024 paper that just showed the whole approach doesn't generalize outside benchmarks.

Third, even if you find the right papers, synthesizing them is slow. Identifying themes, spotting contradictions, figuring out what's actually unsolved — that's days of deep reading before you can write a single hypothesis.

And the fourth problem — the one people don't talk about — is that hypotheses go unchallenged. You come up with an idea, it sounds good, and you start building. Nobody tells you that a paper from last year already partially answered it, or that your key assumption doesn't hold.

---

### Slide 3 — What We Built
*(~60 seconds)*

So what did we build?

A fully automated multi-agent pipeline — seven specialized agents, two reasoning loops, and three paper sources. You give it a research question — something like "how do LLM agents handle multi-step tool use?" — and it returns a complete research brief.

The three numbers here matter: seven agents, each with a different role and system prompt, not just one LLM doing everything. Two loops — not a linear pipeline — where the system backtracks and retries based on quality signals. And three sources: Semantic Scholar, ArXiv, and the citation graph itself, which no keyword search gives you access to.

---

### Slide 4 — The Pipeline
*(~90 seconds)*

Here's the full architecture.

Reading left to right: Search retrieves papers from both sources in parallel. Critic scores them for relevance and filters. Snowball expands the corpus by crawling the citation graph. Synthesis identifies grounded themes and gaps. Hypotheses generates three research hypotheses. Advocate challenges them. Experiment designs a study for the winner.

The two amber arrows are the loops — and they're worth calling out.

The first, between Critic and Search, fires if fewer than five papers survive the relevance filter. The query automatically broadens and we try again, up to twice.

The second loop — between Advocate and Hypotheses — is the more interesting one. If any hypothesis scores below six on a viability scale, it doesn't just get flagged — the entire hypothesis generation reruns, but this time with the critiques as input. The system literally uses its own feedback to improve. I'll come back to this.

---

### Slide 5 — Finding the Right Papers
*(~90 seconds)*

Let's go deeper on the first three nodes.

Search fires two API calls simultaneously using Python threads — Semantic Scholar and ArXiv — then deduplicates by normalized title. On a retry, the system strips the longest term from the query automatically. "Multi-agent reinforcement learning cooperation" becomes "multi-agent learning cooperation" — broader, without any user input.

Critic sends all twenty papers to Claude alongside the research question and asks for a score from one to ten with a one-line reason for each. Papers scoring below six are dropped. This is the first quality gate — we only want papers that actually address the question, not papers that are tangentially related.

Snowball is the most novel piece at this stage. For the top four relevant papers, we hit Semantic Scholar's graph API and fetch both their references — what they cite — and their citations — who cites them. These are papers that keyword search would never surface, because they might not even contain your search terms. But they're the papers the field is actually built on.

---

### Slide 6 — Grounded Synthesis
*(~90 seconds)*

The synthesis node is where we had to solve a real problem: LLM hallucination.

If you just ask Claude to synthesize themes from a set of papers, it will — and it sounds convincing. But some of those themes will be plausible-sounding ideas that weren't actually in the papers. They'll be things Claude knows from training data. That's a fundamental issue for research, because you might build a hypothesis on a theme that no paper in your corpus actually supports.

Our solution is mandatory citation indices. The prompt tells Claude it must include `paper_indices` in every claim — a list of integers pointing to papers in the list we passed in. After Claude responds, we run a validation step: each claim's indices are checked against the actual paper list. If all the indices are out of range — meaning Claude invented paper references — the claim is silently dropped.

Only claims that can be traced back to real papers survive. In the UI, you can hover over the citation badges and see exactly which papers support each theme. This turns a black-box LLM output into something you can verify.

---

### Slide 7 — Adversarial Hypothesis Refinement
*(~90 seconds)*

This is the part I'm most proud of — the adversarial refinement loop. This is what makes the graph genuinely non-linear.

Hypothesis node generates three research hypotheses from the synthesis. On the first pass, it reads the themes, gaps, and open questions and proposes novel ideas.

Then Advocate takes over. It plays devil's advocate — for each hypothesis it lists specific counterarguments, often citing papers by index number. It flags logical flaws: untestable assumptions, circular reasoning, scope issues. It produces a refined version of the claim. And it assigns a viability score from one to ten.

Here's the key: if any score comes back below six, the graph routes back to Hypothesis node. But on the second pass, it doesn't start fresh. It receives the previous hypotheses and their critiques side by side, and the prompt explicitly instructs Claude to generate "meaningfully different and stronger" replacements that address the specific counterarguments.

This is a real feedback loop between two agents — a generator and a critic — up to two iterations. The hypotheses that come out of iteration two are measurably more specific and harder to dismiss.

---

### Slide 8 — Experiment Design
*(~60 seconds)*

The final node designs a concrete, reproducible experiment.

The selection step is important: it doesn't take hypothesis number one. It takes `max(hypotheses, key=viability_score)` — the one that best survived adversarial review. So if hypothesis three turned out to be the most defensible, the experiment is designed around that.

The output covers five things: step-by-step methodology, a baseline to compare against, concrete measurable metrics, specific dataset recommendations, and failure modes — what could go wrong during the experiment and how you'd detect it early. All structured JSON, validated on parse.

---

### Slide 9 — Tech Stack
*(~60 seconds)*

A few words on the implementation.

LangGraph for the graph itself. The two loops are conditional edges defined in the graph — not if-statements buried in application code. That means the graph is inspectable, reproducible, and easy to modify.

Claude Sonnet for all reasoning. Every agent has a distinct system prompt. All structured outputs are requested as JSON, with a retry-on-parse-failure mechanism that appends "respond only in valid JSON, no markdown fences" and tries once more.

Semantic Scholar and ArXiv are both free with no API key required. Streamlit for the UI, with a live pipeline tracker that updates as each node completes — implemented with a background thread feeding a queue, so the graph and the UI run independently without blocking.

---

### Slide 10 — Three Rigor Improvements
*(~90 seconds)*

Three specific design decisions that moved this from a prototype to something you can trust.

Citation snowballing: the original version only used keyword search. Adding citation graph expansion was a single API addition to the search module — but it fundamentally changes the corpus quality. You stop being limited to papers that contain your exact query terms, and start pulling in the papers the field actually considers foundational.

Grounded synthesis: the original synthesis had no validation. The hallucination problem wasn't obvious in early tests because the output sounded plausible. Adding the index validation step costs nothing at runtime — it's pure post-processing — but it makes every claim in the synthesis traceable to a specific document.

The adversarial loop: the original version had a one-shot advocate that wrote critiques nobody acted on. Making those critiques feed back into a second hypothesis generation pass was the biggest architectural change, and it made the biggest difference to output quality. The hypotheses after iteration two are consistently more precise and more testable than the first-pass ones.

---

### Slide 11 — Future Work
*(~60 seconds)*

A few directions this could go next.

On the rigor side: a human-in-the-loop checkpoint right after the critic, so a researcher can prune false positives or inject a paper they know is relevant before synthesis runs. A synthesis quality loop that scores grounding density and retries if it's too vague. Multi-round debate between Hypothesis and Advocate — more than one challenge-and-refine cycle.

On the capability side: persistent sessions so you can save runs and compare outputs across different research questions. Additional academic sources — ACL Anthology for NLP-specific work, PubMed for bio-adjacent agent research. LaTeX export so the related work section can drop straight into a paper draft.

---

### Slide 12 — Close
*(~30 seconds)*

To summarize: seven specialized agents, two reasoning loops that make the system genuinely non-linear, citation grounding that prevents hallucination, and an adversarial review process that ensures the final experiment is designed around a hypothesis that survived real scrutiny.

The code is all on GitHub. Happy to take questions.

---

*Total estimated time: ~14–16 minutes*
