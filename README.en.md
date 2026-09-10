# Bottle Code: Build a Tool-Calling AI Agent from Scratch

[中文](README.md) | **English**

This project is a **minimal but fully working** AI Agent scaffold, written for beginners (the full teaching syllabus lives in AGENTS.md).
It deliberately avoids heavy frameworks (LangChain / CrewAI / AutoGen) and instead spells out the Agent's **core loop** by hand —
only once you understand that layer do the frameworks stop looking like magic.

From that foundation it grew into **a finished product that runs real tasks and has an interactive UI** — writing code, querying a
knowledge base, multi-agent division of labour, MCP integration, a coding loop, and a web UI. Here's what it looks like.

## 🚀 Showcase (Bottle Code Web)

A hand-written Agent loop, polished into an **interactive web app**: streaming output · observable traces · persistent sessions.

| Chat | Session trace | Session list |
|---|---|---|
| ![Chat page](docs/screenshots/homepage.png) | ![Trace drawer](docs/screenshots/trace-panel.png) | ![Session list](docs/screenshots/sessions-panel.png) |
| Dark terminal look · tool-event timeline · streaming typewriter · markdown-rendered answers | Each step — «prompt injection / model thinking / tool call / tool result / answer» — its own collapsible block | Switch / rename / delete sessions; refresh and keep chatting |

> The screenshots above were taken against a **real API** (Anthropic Messages API), which is why the trace shows the model's
> **thinking blocks** and actual reasoning. To try it offline: `start.bat mock` (no API key needed, but replies are fixed text and there are no thinking blocks).

## Mapping what you already know

| What you've seen in Claude Code / vibe coding | Where it lives in this project | Notes |
|---|---|---|
| Skill | A tool's (or tool group's) **description + trigger words** | The `@tool(...)` decorator and its `description` are the "skill manual" |
| Prompt / system prompt | `DEFAULT_SYSTEM_PROMPT` in `agent.py` | Tells the model who it is, how to use tools, and when to stop |
| Tool | Every function registered in `tools.py` | The model "calls" these abilities via function calling |
| Context | `Agent.history` (short-term memory) | Each turn plus the last tool result gets appended |
| Human multi-step reasoning | The `for` loop inside `run()` | Model calls a tool → gets a result → thinks again → calls again / stops |

In one line: **ChatGPT only "talks"; an Agent "talks + does".** The difference isn't the model — it's whether you gave it tools, and whether you wrote a loop.

## The core loop (Agent Loop)

```
user input
   ↓
[system prompt + history + user message]  →  LLM
   ↓
Model asks to call a tool? — yes → run tool → append result to history → back to the LLM
   ↓                                          (this step can repeat many times)
Model answers with text?   ———→ emit the final answer
```

This loop is the "magic" LangChain / AutoGen wrap up for you. Understand this diagram and you understand 80% of how Agents work.

## Directory layout

```
agent-learn/
├── mini_agent/
│   ├── __init__.py
│   ├── agent.py      # Agent main loop (the heart of it all)
│   ├── llm.py        # Model backend abstraction (real API / mock + streaming)
│   ├── tools.py      # Tool registry + implementations (incl. the run_python sandbox)
│   ├── knowledge.py  # Minimal RAG (chunking + vectors + retrieval)
│   ├── knowledge_embed.py  # Lesson 9 production RAG (embeddings + Chroma + hybrid retrieval)
│   ├── roles.py      # Multi-agent division of labour (planner / executor / reviewer + orchestrator)
│   ├── mcp_client.py # MCP client adapter (plug external MCP tools into the Agent)
│   ├── audit.py      # Audit log (append-only JSONL + trace rendering)
│   ├── codeops.py    # ★ Bottle Code composition layer (Orchestrator + MCP + audit)
│   └── main.py       # CLI entry point
├── web/              # ★ Bottle Code web app (Lesson 10)
│   ├── server.py     #   FastAPI + SSE backend (/api/chat · session/trace endpoints)
│   └── src/          #   Vue 3 + Vite frontend (chat page / trace drawer / session drawer)
├── start.bat         # ★ One-click launcher (backend :8000 + frontend :5173, one window each)
├── knowledge/        # Knowledge-base documents (index them with build_kb.py)
├── examples/
│   ├── mock_demo.py        # Offline demo script
│   ├── build_kb.py         # Build the knowledge-base vector index
│   ├── multi_agent_demo.py # Multi-agent division-of-labour demo
│   ├── mcp_server.py       # Custom MCP server (repo stats)
│   ├── mcp_demo.py         # Demo of wiring MCP tools into the Agent
│   ├── eval_harness.py     # Evaluation set: score the Agent (4 tasks × 5 dimensions)
│   ├── lesson7a_hole.py    # Lesson 7A vuln demo: an out-of-scope call gets blocked
│   ├── rag_eval.py         # Lesson 9 retrieval evaluation (hit@k across three approaches)
│   ├── codeops_demo.py     # ★ Bottle Code demo (MCP + RAG + multi-agent + file writes)
│   ├── lesson11_demo.py    # Lesson 11 coding-loop demo (write code → run tests → fix)
│   ├── lesson11_eval.py    # Exercise 11A coding-loop evaluator (hidden tests verify the artifact)
│   └── stream_demo.py      # Lesson 10A streaming demo (typewriter effect)
├── docs/             # Showcase assets (screenshots/)
├── memory/           # Long-term memory storage (notebook.md)
├── scripts/          # Helper scripts (e.g. secret scanning)
├── .githooks/        # Pre-commit hooks
├── .env.example
├── LICENSE
└── requirements.txt
```

## Quick start

### 1. Run it offline first (no API key needed)

```
python -m mini_agent.main --provider mock --prompt "帮我计算 2+3 的结果"
```

Or drop into interactive mode:

```
python -m mini_agent.main --provider mock
# Input: 帮我计算 2+3 的结果
# Watch it call `calculator` first, then answer based on the result
```

### 2. Switch to a real model

```
pip install -r requirements.txt
cp .env.example .env    # then fill in OPENAI_API_KEY
python -m mini_agent.main --provider openai --model gpt-4o-mini
```

`--provider openai` talks to any OpenAI-compatible `/chat/completions` endpoint.
If your provider speaks that protocol (DeepSeek / Qwen / a local Ollama, etc.), just point
`OPENAI_BASE_URL` in `.env` at it and the same code works.

### 3. Launch the web app (Lesson 10 · interactive UI)

From the **repository root**:

```
start.bat              # default: anthropic (real API, needs a key in .env)
start.bat mock         # offline, no key needed
start.bat openai       # OpenAI-compatible backend
```

It checks for `.venv` and frontend deps, starts the FastAPI backend (:8000) and the Vite frontend (:5173),
and opens a window for each. Open http://localhost:5173 in your browser, type a task, and you'll see
**streaming output + the tool-event timeline**. You can also start them by hand:

```
.venv/Scripts/python.exe web/server.py --provider mock --port 8000   # backend
cd web && npm install && npm run dev                                  # frontend (proxies /api → :8000)
```

## How it works (file-by-file)

### 1. `tools.py` — giving the Agent hands and feet

A tool is: **a function + a name + a description + a JSON Schema for its arguments**. The description matters most,
because the model decides whether to call it by **reading the description**, not the source code.

The `@tool(...)` decorator registers a function into a global table; `get_tool_schemas()` translates that whole table into
`function calling` declarations the model understands; `execute_tool(name, args)` dispatches by name and runs it.

> Exercise: add your own `@tool("search_weather", ...)`. You'll immediately feel that adding an ability to an Agent =
> adding a function + writing a clear description.

### 2. `llm.py` — the model backend

`LLM.chat(messages, tools)` is the only interface. The Agent depends on nothing else, so you can swap in OpenAI,
another compatible service, or a free mock at any time.

- `OpenAIChatLLM`: real function calling, returns a structure carrying `tool_calls`.
- `MockLLM`: offline and deterministic. See the word "计算" and it pretends to call `calculator`; once it has a result it
  "pretends to think" and answers. **Its value is letting you watch the full loop with your own eyes — no key, no network.**

### 3. `agent.py` — the main loop

This is the heart of the project, and it's only a few steps:

```
1. Assemble messages: system + history
2. Call the model
3. If the model requested tools → run them → append results to history → back to step 1
4. If the model answered with text → return; done
```

Every real Agent framework — however complex — runs this same loop. It just bolts on extras: planning, memory,
verification, parallelism, sub-agents.

### 4. Two kinds of "memory"

- **Short-term**: `Agent.history` + a sliding window (`max_context_messages`). When a conversation gets long, only the most
  recent N messages go to the model — keeps the context from blowing up and stops it from "forgetting the beginning".
- **Long-term (single facts)**: `remember` / `recall`. Important facts are written to `memory/notebook.md` and stay searchable across sessions.
- **Long-term (RAG)**: `kb_search` + `knowledge.py`. Documents are chunked, vectorised, and retrieved by similarity, so the Agent
  can answer from source material and cite where it came from.

> The three work together: single facts go through `remember`, whole document sets through `kb_search`, and the sliding window
> keeps long conversations from overloading the context.

### 5. Multi-agent division of labour (`roles.py`)

A single Agent has "one brain". When a task gets complex enough to need **several things done at once, with mutual review**,
split it into roles:

```
user task
   ↓
[Planner]    only decomposes, never executes → plan steps
   ↓
[Executor]   actually does the work (compute / read / write / run commands)
   ↓
[Reviewer]   only inspects the result, returns ok / retry
   ↓  (on retry, feedback goes back to the executor)
structured result
```

- **The essence of the split**: different `system_prompt` (persona + rules) and different `allowed_tools` (allowlist) per role.
- **Message protocol**: roles exchange JSON carrying `task / steps / result / verdict / feedback`, not loose prose.
- **Reusing the Lesson 2 loop**: planner, executor and reviewer are all the same `Agent` class — only the persona and tools differ.

> Try it: `python examples/multi_agent_demo.py --provider mock` (offline skeleton) or swap in `openai-compatible` for a real model.

### 6. MCP integration (`mcp_client.py` + `examples/mcp_server.py`)

**MCP (Model Context Protocol)** is the open protocol standardising how LLM apps connect to external tools and data — "USB-C for AI".
It decouples **providing** a capability from **using** it:

```
Agent (Host/Client)  ⇄  MCP Server (exposes tools / resources / prompts)
```

- Our **client adapter** (`mcp_client.py`) runs an MCP server as a subprocess and exchanges **newline-delimited JSON-RPC** over stdio:
  `initialize` → `tools/list` (discover tools) → `tools/call` (invoke a tool).
- It **translates each MCP tool into a `Tool` this project's Agent understands** (name gets an `mcp_` prefix, arguments reuse the MCP JSON Schema as-is).
- So the **`Agent` main loop barely changes** — it just sees a few more tools. That's the payoff of reusing the Lesson 2 loop.

```
# Start the custom MCP server (repo stats)
python examples/mcp_demo.py --provider openai-compatible
```

> Why it matters: to give Bottle Code a new ability (git / databases / the filesystem) you **mount an MCP server** rather than edit Agent code.

### 7. Bottle Code (`codeops.py`) — sections 1–6 combined

Wires every earlier part into one complete, runnable product: read the codebase + query the knowledge base + multi-agent split + automatic execution.

```
user task ("count lines of code" / "look up deploy steps" / "write a checklist")
   ↓
┌─────────────────────────────────────────────────┐
│ CodeOpsAgent (composition layer: wires, doesn't rewrite) │
│  ┌───────────────────────────────────────────┐  │
│  │ Orchestrator (multi-agent split)          │  │
│  │  Planner → Executor → Reviewer → ok/retry │  │
│  └───────────────────────────────────────────┘  │
│  Reliability layer: allowed_tools allowlist + audit │
└─────────────────────────────────────────────────┘
   ↓ tool layer
┌──────────┬──────────┬──────────┬──────────────┐
│ read repo│ query KB │ execute  │ MCP abilities │
│ list_dir │ kb_search│ write_file│ mcp_count_loc│
│ read_file│ (RAG)    │ run_shell│ mcp_git_status│
│ run_shell│          │ calculator│ mcp_list_files│
└──────────┴──────────┴──────────┴──────────────┘
```

- The **composition layer** (`codeops.py`) is only ~50 lines: register MCP tools → add them to the executor's allowlist →
  attach auditing to each role → expose a single `run(task)` entry point. **No new algorithm, only composition** — that's what "reuse, don't rewrite" means.
- **Demo**: `python examples/codeops_demo.py --provider anthropic` — one task exercises MCP (count lines) + RAG (look up deploy steps) +
  file writing (produce a deploy checklist) + multi-agent split + auditing.

### 8. The web app (`web/`) — letting the Agent "work in the open"

The CLI shows you only the final result; the web app turns the Agent's **intermediate process** into a visible interface:

```
Browser (Vue 3 + Element Plus)
   │  POST /api/chat  { message, session_id }
   ▼
FastAPI (web/server.py)
   │  agent.run(stream=True)          ← the Lesson 10A streaming events
   ▼
SSE event stream: delta (text increment) / tool (tool call) / result (tool result) / done (final answer)
   │
   ▼
Frontend renders per event type → timeline (thinking / tool / result interleaved in order) + markdown final answer
```

Three design points:

- **Streaming is an event protocol, not raw text**: `run(stream=True)` yields structured events like `{"type": "delta" | "tool" | "result"}`.
  With plain text the frontend couldn't tell whether a chunk is reasoning or the answer — hence the **pending buffer**: deltas are
  buffered until a later event decides (a tool event → it was reasoning; `done` → it was the answer).
- **Display record ≠ model context**: `Agent.history` holds the messages actually sent to the model (including `tool_calls` turns with
  `content=null`, and answers that `final_answer` returned directly) — unreadable to a human. So a separate `chat_logs` exists purely
  for people. Both are persisted to `sessions.json` (written via atomic replace), so after a restart you can both **see** the history and **continue** it.
- **Only the display layer changes, never the Agent core**: the backend cleans `final_answer`'s structured JSON down to plain text before
  sending it (`clean_final_answer`), while the `Orchestrator` still receives the full JSON for review — display and protocol stay decoupled,
  so UI work can't break the multi-agent layer.

> The trace drawer (the "轨迹" button) reads the **in-memory trace** of that session's Agent instance (the Lesson 7 observability data):
> each step's prompt injection / model thinking / tool call / tool result / final answer is its own block. All collapsed by default — click to expand.

## Hands-on exercises (increasing difficulty)

1. **Add a tool**: add `@tool("search_weather", ...)` and have it answer "what's the weather in Beijing?" (get it running under mock first, then a real model).
2. **Add a "planning" step**: in `run()`, the first time a complex task arrives, have the model emit a `计划：...` line before it starts executing.
3. **Add a verify/re-check loop**: have the model run something via `run_shell` and inspect the output; if it errored, make it fix it and try again. That's the seed of most "coding Agents".
4. **Wire long-term memory to vector search**: replace `recall`'s string matching with embedding-similarity retrieval.
5. **Switch to MCP**: upgrade tool definitions from hand-written schemas to an MCP (Model Context Protocol) server, so your Agent can use a standardised set of external tools.

## Advanced capabilities this project already covers (all runnable in `examples/`)

| Capability | Implementation | Demo |
|---|---|---|
| MCP tool ecosystem | `mcp_client.py` + `mcp_server.py` | `mcp_demo.py` |
| RAG retrieval augmentation | `knowledge.py` + `kb_search` | `build_kb.py` |
| Multi-agent collaboration | `roles.py` (planner / executor / reviewer) | `multi_agent_demo.py` |
| Observability | `audit.py` (trace + append-only JSONL) | run any demo, then read `logs/agent.jsonl` |
| Evaluation | `eval_harness.py` (4 tasks × 5 dimensions, exit code CI-ready) | `eval_harness.py --provider mock` |
| Safety & sandboxing | execution-layer allowlist + path sandbox + command allowlist | `lesson7a_hole.py` |
| Composition | `codeops.py` (the Bottle Code layer) | `codeops_demo.py` |
| Web app | streaming + FastAPI + SSE + Vue, observable traces, sessions on disk | `web/server.py` / `start.bat` |
| Production RAG | hybrid retrieval (BM25 + vector RRF) | `knowledge_embed.py` / `rag_eval.py` |
| Coding loop | `run_python` sandbox + hidden-test evaluator | `lesson11_demo.py` / `lesson11_eval.py` |

## Advanced lessons (9–11 · all complete)

- **Lesson 9 · Production RAG** ✅: embeddings (fastembed) + a vector store (Chroma) + hybrid retrieval (BM25 + vector RRF) + retrieval
  evaluation (`knowledge_embed.py` + `rag_eval.py`).
- **Lesson 10 · Bottle Code Web** ✅: streaming output + FastAPI backend + Vue frontend, turning Bottle Code into an interactive web app (`web/`).
- **Lesson 11 · Coding Agent Loop** ✅: the `run_python` sandbox + write code → run tests → fix until they pass + a hidden-test evaluator
  (`lesson11_demo.py` / `lesson11_eval.py`).

## What could come next (TODOs / ideas)

- **More MCP servers**: mount databases, browsers, CI — then Bottle Code can genuinely do ops.
- **Production hardening**: `sessions.json` → SQLite/Redis, on-demand Element Plus imports, auth, HTTPS (currently a teaching demo; these gaps are known and deliberate).
- **A stricter command sandbox**: `run_shell` still permits `cat` on arbitrary files and git repo operations; this could go deeper into a true command-level allowlist.

## Security notes (important)

- `calculator` uses `eval` purely as a teaching demo. In production, replace it with an AST allowlist parser or a dedicated calculation service.
- `write_file` / `read_file` enforce path limits (`_safe_path`), but that isn't enough. A real Agent needs **least privilege, human
  confirmation, sandboxed execution, and an audit log**.

## Wrap-up

You've now hand-built the core skeleton of an Agent. From here it's no longer "learning concepts" but "adding abilities + adding
constraints + adding evaluation". Have fun with it :)

## License

This project is licensed under [MIT](LICENSE).

> Before publishing, replace the copyright holder in `LICENSE` with your own name; keep real API keys only in a local `.env` (already gitignored).
> Run `python scripts/check_secrets.py` before committing to scan for sensitive information.
