# harnessed-agent

A financial research agent built with Python and LangGraph that takes a stock ticker and price, researches it from multiple sources, and produces a structured markdown report.

This project was built deliberately as a learning exercise in **agent harness design** — the idea that building a reliable agent is less about the model and more about the infrastructure that wraps it.

---

## The Harness Concept

The term "harness" comes from work by [Phil Schmid](https://www.philschmid.de/agent-harness-2026) and [LangChain](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness) (2026), who independently arrived at the same framing:

> **Agent = Model + Harness**
> If you're not the model, you're the harness.

The analogy is to an operating system. The model is the CPU — powerful but passive. The harness is the OS: it manages the loop, controls context, handles errors, logs execution, and enforces completion. Your agent logic is the application running on top.

This matters because model capability alone doesn't determine agent reliability. LangChain demonstrated that changing only the harness — not the model — moved their coding agent from Top 30 to Top 5 on Terminal Bench 2.0. The harness is the competitive moat, not the prompt.

In this project the harness lives in `harness/` and the application (what the agent actually does) lives in `agent.py`. When the model changes, `agent.py` barely changes.

---

## Architecture

```
harnessed-agent/
├── agent.py              # Entry point — builds the graph, runs the agent
├── harness/
│   ├── state.py          # AgentState — single source of truth for run progress
│   ├── nodes.py          # ResearchNodes class — all LangGraph node functions
│   ├── tools.py          # Tool definitions (web_search, fetch_financials, etc.)
│   ├── prompts.py        # System prompt and nudge template
│   ├── context.py        # Context compaction — truncates large tool outputs
│   └── trajectory.py     # Step-by-step JSONL logging
├── workspace/            # Agent scratch space (gitignored)
├── reports/              # Final report output (gitignored)
├── trajectories/         # Execution traces (gitignored)
├── .env.example
└── pyproject.toml
```

---

## Harness Primitives Implemented

### 1. Boot Sequence — System Prompt as Configuration

The system prompt is harness configuration, not afterthought. It is injected exactly once at the start of the run and establishes the agent's persona, required tool-call sequence, filesystem layout, and output format. The nudge template is a separate harness-level message, also defined in `harness/prompts.py`, keeping all model-steering text in one place.

### 2. Filesystem as Durable State

The agent is given a structured workspace (`workspace/` for scratch, `reports/` for output). Raw tool results are written to disk before summarisation, which means large intermediate data never accumulates in the context window. The final report lands in `reports/` as a real file — not a model response, not a variable.

### 3. Context Compaction

Tool outputs can be large (web search results, financial data). `harness/context.py` truncates oversized outputs by keeping the head and tail and dropping the middle, with a note to the model that the full output is available on disk. This is applied in the harness layer (in `nodes.py`), not inside the tools themselves — the harness controls context, not the tools.

### 4. Completion Hook — `finish()` as a Verified Gate

The agent cannot simply stop — it must call the `finish` tool with a report filepath. The harness intercepts this call and verifies the file actually exists before accepting completion. If the model calls `finish` without having written the file, the harness rejects it and forces a `write_file` call first. This eliminates the most common small-model failure mode: hallucinated completion.

### 5. Nudge Loop — Detecting and Breaking Stalls

When the model produces two consecutive responses with no tool calls, the harness injects a `SystemMessage` nudge that restates the required next steps explicitly. This is a lightweight version of the "Ralph loop" described in the LangChain harness post: detect stall, reinject direction, continue. Using `SystemMessage` (rather than `HumanMessage`) keeps harness control signals semantically distinct from user input in the trajectory.

### 6. Trajectory Logging — The Harness as Dataset

Every model call, tool call, tool result, error, nudge, and completion event is written to a JSONL file in `trajectories/`. This is not just debugging tooling — it is the foundation for future fine-tuning. Every run where the agent succeeds or fails is a labeled training trajectory. Phil Schmid's framing: _the harness is the dataset; every failure is a row_.

### 7. Checkpointing — Resumable Runs

LangGraph's `MemorySaver` checkpointer is wired in at compile time. Each run is scoped to a thread ID (the ticker symbol), meaning an interrupted run can be resumed rather than restarted from scratch. For long-running agents against slow local models this is significant.

---

## Best Practices Applied

### Explicit Dependency Injection over Closures

LangGraph node functions are methods on the `ResearchNodes` class (`harness/nodes.py`) rather than closures capturing variables from a parent function. Dependencies (`llm`, `ticker`, `logger`, `tool_map`) are passed into the constructor explicitly. This makes each node independently unit-testable without constructing a full graph.

### Rich State as Single Source of Truth

`AgentState` (`harness/state.py`) tracks not just messages but structured progress: `step_count`, `nudge_count`, `sources_gathered`, and `errors`. The agent's state at any point fully describes what has happened — you don't need to mine the trajectory JSONL to understand where a run is. This also means the nudge router can make decisions based on state rather than message-list inspection alone.

### Per-Tool Error Handling with Model Recovery

Every tool call in `nodes.py` is wrapped in a `try/except`. On failure the error is logged to the trajectory, appended to `state["errors"]`, and returned to the model as a `ToolMessage` describing what failed and suggesting an alternative. Small models can often recover from reported failures; they cannot recover from Python exceptions that kill the run.

### Harness / Application Separation

`harness/` contains everything that is not the agent's task: state, nodes, tools, prompts, context management, logging. `agent.py` contains only graph construction and the entry point. This separation means replacing the model, swapping a tool, or changing context compaction strategy requires touching exactly one file.

### Build to Delete

Following Phil Schmid's advice: the harness is modular by design. The nudge logic, compaction threshold, prompt templates, and tool set are each in their own file. New models may make some of this logic unnecessary — removing it should require deleting one file, not refactoring three.

---

## Setup

```bash
# 1. Copy and fill in the env file
cp .env.example .env

# 2. Install dependencies
uv sync

# 3. Start Ollama and pull the model
ollama serve
ollama pull qwen2.5:3b

# 4. Run
uv run python agent.py
```

The report will be written to `reports/AAPL_report.md`. The execution trace will be in `trajectories/`.

---

## Further Reading

- [Phil Schmid — Agent Harness 2026](https://www.philschmid.de/agent-harness-2026)
- [LangChain — The Anatomy of an Agent Harness](https://www.langchain.com/blog/the-anatomy-of-an-agent-harness)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
