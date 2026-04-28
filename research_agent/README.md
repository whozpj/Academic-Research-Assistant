# AI Agents Research Assistant

AI Agents Research Assistant is a Streamlit app that helps turn a research question into a structured research workflow. It searches papers from Semantic Scholar and ArXiv, filters the results with an LLM critic, expands the corpus through citation snowballing, synthesizes grounded themes and gaps, generates testable hypotheses, stress-tests them with a devil's advocate pass, and finishes by proposing an experiment design.

## Features

- Search Semantic Scholar and ArXiv in parallel.
- Rank papers by relevance to a user question.
- Expand the corpus using references and citations from relevant papers.
- Produce grounded synthesis output with themes, gaps, contradictions, and open questions.
- Generate three research hypotheses and refine them after critique.
- Design a reproducible experiment for the strongest hypothesis.
- Export the final workflow as a Markdown report.

## Project Flow

1. The user enters a research question in the Streamlit app.
2. `search_node` retrieves candidate papers.
3. `critic_node` scores papers for relevance.
4. `snowball_node` expands the paper set through citation links.
5. `synthesis_node` builds a grounded literature summary.
6. `hypothesis_node` generates novel hypotheses.
7. `advocate_node` critiques and refines those hypotheses.
8. `experiment_node` proposes an experiment plan.

## Requirements

- Python 3.10+ recommended
- An Anthropic API key

## Installation

Create and activate a virtual environment, then install the dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Set your Anthropic key before running the app:

```bash
export ANTHROPIC_API_KEY="your_api_key_here"
```

If you use a `.env` file, the app loads it automatically through `python-dotenv`.

## Run the App

From the `research_agent` directory, start Streamlit:

```bash
streamlit run app.py
```

Then open the local URL printed in the terminal.

## Repository Structure

- `app.py` - Streamlit UI, pipeline runner, and report export
- `graph.py` - LangGraph workflow definition and routing logic
- `nodes.py` - LLM-powered pipeline nodes
- `search.py` - Semantic Scholar and ArXiv search helpers
- `state.py` - Typed state shared across the graph
- `prompts.py` - System prompts for each LLM role
- `requirements.txt` - Python dependencies

## Output

The app renders:

- Raw search results
- Relevant papers selected by the critic
- Snowballed papers from citations and references
- A grounded literature synthesis
- Hypotheses with adversarial critique
- A final experiment design

When the pipeline completes successfully, you can download a Markdown report from the UI.

## Demo / Reference Video

YouTube link: [https://youtu.be/L5CmQiINj3g](https://youtu.be/L5CmQiINj3g)

## Notes

- The app expects a working internet connection for paper search and citation expansion.
- Some API requests may fail or return partial results; the pipeline is designed to continue where possible.
- The hypothesis refinement loop stops after a small number of iterations to keep runs bounded.
