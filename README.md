# AgentTrace

**Local step-by-step visual debugger for AI agents — trace your LLM runs, inspect spans, understand behavior.**

---

## Why AgentTrace?

AI agents are hard to debug. When your agent loops infinitely, returns unexpected results, or makes confusing tool calls, you need visibility into what happened — step by step.

Existing observability tools (Langfuse, LangSmith, etc.) are built for production monitoring: dashboards, metrics, team collaboration. They're heavy, require external services, and aren't optimized for the rapid iteration of local development.

**AgentTrace is different:**

- **Local-first** — SQLite database, no external services, works entirely offline
- **Developer-focused** — built for understanding your agent during development, not monitoring in prod
- **Step-by-step** — interactive tree view of every span, tool call, prompt, and response
- **Zero-config start** — `make docker-up` and you're running
- **Clean architecture** — decoupled domain layer, extensible to other databases or transports

If you've ever wished for a "debugger for agents" while developing an LLM app, AgentTrace is for you.

---

## Key Features

- **Python SDK**
  - `@trace_agent_run` decorator — wrap any function and get traces automatically
  - `Tracer` context manager — manual control for complex flows
  - Batch span processor — efficient event delivery
  - HTTP exporter — send traces to your local AgentTrace backend
  - ContextVar-based span tracking — thread-safe, supports nested spans

- **Web UI**
  - Run list — see all your agent runs with timestamps and metadata
  - Trace tree — expand/collapse nodes to inspect the execution hierarchy
  - Details panel — view type, timing, prompts, responses, attributes for any span

- **Local-first architecture**
  - SQLite database — no Postgres, no external services
  - Single binary backend — FastAPI + async SQLAlchemy
  - Works offline — no internet required after setup

- **Clean architecture**
  - Domain layer decoupled from infrastructure
  - Repository pattern — swap SQLite for Postgres later
  - Interface-based design — extend with custom exporters or transports

- **Docker-based quick start**
  - `docker-compose up` — backend, frontend, and database in one command
  - Health checks and proper startup ordering

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Your Agent Code                        │
│                   (Python / LangChain / etc.)                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              │ SDK traces spans
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AgentTrace SDK                            │
│  @trace_agent_run  │  Tracer context manager  │  Exporter    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              │ HTTP POST /api/v1/ingest/events
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AgentTrace Backend                        │
│          FastAPI + SQLAlchemy + SQLite                      │
│   ┌─────────────┬──────────────┬───────────────────────┐    │
│   │   Domain    │  Application │    Infrastructure     │    │
│   │  Entities   │   Services   │   Repositories / DB   │    │
│   └─────────────┴──────────────┴───────────────────────┘    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   AgentTrace Frontend                        │
│            React + TypeScript + TraceTree UI                 │
└─────────────────────────────────────────────────────────────┘
```

The backend follows clean architecture principles — domain entities have no framework dependencies, making it straightforward to add new storage backends or API transports in the future.

---

## Getting Started

### Prerequisites

- **Python 3.12+** (for backend and SDK)
- **Node.js 18+** (for frontend development)
- **Docker & Docker Compose** (recommended for quick start)
- **Make** (optional, for convenience commands)

### Quick Start

**Option 1: Docker (recommended)**

```bash
# Clone the repository
git clone https://github.com/yourusername/agenttrace.git
cd agenttrace

# Start all services
make docker-up

# Access:
# - Backend:    http://localhost:8000
# - API Docs:   http://localhost:8000/docs
# - Frontend:   http://localhost:3000
```

**Option 2: Local development**

```bash
# Install dependencies
make install

# Or manually:
cd backend && pip install -e ".[dev]"
cd ../sdk && pip install -e ".[dev]"
cd ../frontend && npm install

# Start backend (terminal 1)
cd backend
uvicorn agent_trace.main:app --reload --port 8000

# Start frontend (terminal 2)
cd frontend
npm run dev
```

### Configuration

Create a `.env` file from the example:

```bash
cp frontend/.env.example frontend/.env
```

Configure the backend URL for the frontend:

```bash
# frontend/.env
VITE_API_URL=http://localhost:8000
```

Backend environment variables (optional):

```bash
# backend/.env
DATABASE_URL=sqlite+aiosqlite:///data/agent_trace.db
LOG_LEVEL=INFO
```

---

## Using the Python SDK

### Quick Start: Decorator

The simplest way to trace your agent:

```python
from agent_trace_sdk import trace_agent_run

@trace_agent_run(name="my_agent")
def my_agent_function(user_input: str) -> str:
    # Your agent logic here
    result = call_llm(user_input)
    return result

# Run it — traces are sent to AgentTrace automatically
my_agent_function("What is the weather?")
```

### Manual Control: Context Manager

For more control over spans and attributes:

```python
from agent_trace_sdk import Tracer

with Tracer(name="my_agent") as span:
    span.set_attribute("model", "gpt-4")
    span.set_attribute("temperature", 0.7)
    
    # Your agent logic
    result = agent.run(user_input)
    
    # Add custom events
    span.add_event("output", {"result": result})
```

### Nested Spans

Trace individual steps within your agent:

```python
from agent_trace_sdk import trace_agent_run, trace_span

@trace_agent_run(name="research_agent")
def research_agent(query: str):
    @trace_span(name="search", span_type="tool_call")
    def search_tool(q):
        return search_api(q)
    
    @trace_span(name="summarize", span_type="llm_call")
    def summarize(results):
        return llm.summarize(results)
    
    results = search_tool(query)
    summary = summarize(results)
    return summary
```

### What Gets Collected

The SDK automatically captures:

- **Spans** — each unit of work with start/end timestamps
- **Span types** — `agent_run`, `step`, `tool_call`, `llm_call`
- **Attributes** — key-value pairs you set on spans
- **Events** — custom events like `input`, `output`, `error`
- **Parent-child relationships** — nested spans form a tree

---

## Inspecting Traces in the UI

1. **Run your agent** with tracing enabled (using SDK decorator or context manager)

2. **Open the web UI** at `http://localhost:3000`

3. **Select a run** from the run list table — you'll see:
   - Run name and ID
   - Start/end timestamps
   - Duration
   - Status (running/completed/failed)

4. **Explore the trace tree** — click nodes to expand:
   - Root span shows the overall agent run
   - Child spans show steps, tool calls, LLM calls
   - Timing is displayed for each span

5. **View details** — click any node to see:
   - Span type and name
   - Start/end timestamps and duration
   - Attributes (JSON)
   - Events (prompts, responses, errors)

---

## Development and Tests

### Run Backend Tests

```bash
cd backend
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v
```

### Run SDK Tests

```bash
cd sdk
pytest tests/ -v
```

SDK tests include E2E format validation to ensure events are compatible with the backend API.

### Run Frontend

```bash
cd frontend
npm run dev
```

---

## Roadmap / Future Work

These are ideas for future development — **not currently implemented**:

- **Framework integrations**
  - LangChain callback handler for automatic tracing
  - LlamaIndex integration
  - OpenAI SDK wrapper

- **Enhanced visualization**
  - Timeline view (waterfall chart)
  - Filter by span type, duration, status
  - Search across runs by name or attributes

- **Run comparison**
  - Side-by-side diff of two runs
  - Highlight differences in steps or outputs

- **Evaluations**
  - Simple scoring for runs (e.g., did it complete?)
  - Custom evaluation hooks

- **Persistence options**
  - PostgreSQL backend for larger deployments
  - Export to JSON for archival

If any of these interest you, see [Contributing](#contributing) below.

---

## Contributing

Contributions are welcome! Here's how to get started:

1. **Open an issue** — describe a bug, feature request, or documentation improvement
2. **Fork the repo** — create your branch from `main`
3. **Write tests** — ensure your changes don't break existing functionality
4. **Submit a PR** — describe what you changed and why

For larger changes, consider opening a discussion issue first to align on the approach.

**Code style:**
- Python: follow PEP 8, use type hints
- TypeScript: use the existing ESLint/Prettier config
- Write docstrings for public functions

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

**Built for developers who want to understand their AI agents, step by step.**