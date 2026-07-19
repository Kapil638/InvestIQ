# InvestIQ — Project Structure

```
InvestIQ/
├── README.md
├── render.yaml
├── .gitignore
├── HANDOFF/                      # Tool-handoff docs (this pack)
├── docs/
│   └── DEPLOYMENT.md
├── scripts/
│   └── export_architecture_review.py
├── secrets/                      # Local-only credentials (not committed); e.g. Drive SA JSON
├── backend/
│   ├── .env.example
│   ├── .env.production.example
│   ├── requirements.txt
│   ├── requirements-prod.txt
│   ├── Dockerfile
│   ├── database/migrations/
│   │   ├── 001_research_reports.sql
│   │   ├── 002_research_reports_rls.sql
│   │   └── 003_report_export_metadata.sql
│   ├── tests/                    # Pytest suite (~249 collected)
│   └── app/
│       ├── main.py               # FastAPI app factory + lifespan
│       ├── api/                  # Routes & dependencies
│       │   └── routes/           # research, reports, financials, advisor, portfolio,
│       │                         # kite, tapetide, market, search, health
│       ├── agents/               # CrewAI reasoning agents only
│       │   ├── financial_analyst_agent.py
│       │   ├── risk_analyst_agent.py
│       │   ├── financial_expert_agent.py
│       │   ├── execution.py
│       │   └── llm.py
│       ├── core/                 # Pydantic Settings (config.py)
│       ├── database/             # Supabase repos, Chroma store, factory
│       ├── guardrails/           # Engine, evidence, parsers
│       ├── llm/                  # OpenRouter factory / caller / models
│       ├── models/               # ResearchContext, StoredResearchReport
│       ├── providers/            # Yahoo, Tapetide MCP, Kite MCP/Connect, Google Drive API
│       ├── schemas/              # Pydantic API / report / chat / portfolio models
│       ├── services/             # Business logic & orchestration (see below)
│       ├── tasks/                # CrewAI task builders (analysis/risk/recommendation)
│       ├── tools/                # Empty package (__init__ only); legacy tools removed
│       ├── data/                 # company_master.json / csv
│       └── utils/                # Cache, timing, exceptions, candle helpers
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── .env.example
    └── src/
        ├── pages/                # Home, Reports, ReportDetail, Portfolio
        ├── components/
        │   ├── research/         # MissionStatus, NeuralNetworkField, ProfessionalReport,
        │   │                     # AvengersPipeline, ReportChat, committee UI
        │   ├── advisor/
        │   ├── portfolio/
        │   ├── chart/
        │   └── ui/               # shadcn-style primitives
        ├── hooks/                # useKiteStatus, useTapetideStatus
        ├── lib/                  # api.ts, reportExportState, utils
        ├── data/
        └── types/
```

## Purpose of major folders

| Folder | Purpose |
|--------|---------|
| `backend/app/api` | HTTP layer under `/api/v1` |
| `backend/app/services` | Core business logic; `research_crew_service.py` orchestrates the pipeline |
| `backend/app/agents` | CrewAI agent builders (Analysis, Risk, Recommendation) — **no** data-collection agents |
| `backend/app/providers` | External systems: Yahoo, Tapetide, Kite, Google Drive |
| `backend/app/database` | Supabase PostgreSQL + ChromaDB |
| `backend/app/guardrails` | Deterministic validation + structured parsers |
| `backend/tests` | Pytest |
| `frontend/src` | React SPA: research, reports, portfolio, advisor |
| `HANDOFF/` | Cursor → Claude Code continuity docs |

## Notable backend services (non-exhaustive)

| Service | Role |
|---------|------|
| `research_crew_service.py` | Full report pipeline orchestration |
| `research_context_builder.py` | Builds immutable `ResearchContext` (+ prior/chroma/portfolio) |
| `financial_data_service.py` | Deterministic financial collect (+ history priority) |
| `news_research_service.py` | Tavily news collect |
| `rag_service.py` | Chroma similar-report search / institutional memory string |
| `portfolio_research_context.py` | Formats Kite holdings for research prompts |
| `portfolio_holdings_service.py` | Normalize Kite holdings for UI/API |
| `report_storage_service.py` | Persist + index reports |
| `report_chat_service.py` | Follow-up Q&A on a saved report |
| `report_export_service.py` | PDF + Drive orchestration |
| `report_pdf_service.py` | fpdf2 rendering |
| `google_drive_service.py` | Drive upload wrapper |
| `investment_scoring_service.py` | Deterministic confidence / rating overwrite |
| `investment_committee_service.py` | Deterministic persona enrichment (no extra LLM) |
| `advisor_service.py` (+ intent/retrieval/scoring/guardrails) | Lightweight advisor path |
| `research_ask_service.py` | Single-shot ask (not full crew) |

## Backend architecture

- **FastAPI** (`app/main.py`) — versioned `/api/v1`
- **Pydantic Settings** — `app/core/config.py`
- **Routes → services → providers/repositories**
- **DI** — `app/api/dependencies.py`

## Frontend architecture

- **React + Vite + TypeScript**
- Routes: `/`, `/reports`, `/reports/:id`, `/portfolio`
- Tailwind + shadcn-style UI
- API client: `frontend/src/lib/api.ts` → `VITE_API_URL` / proxy to backend

## Agent architecture (current)

| Stage | Type | Implementation |
|-------|------|----------------|
| Financial | Service | `FinancialDataService.collect()` — Yahoo / Tapetide / Kite overlays |
| News | Service | `NewsResearchService.collect()` — Tavily (parallel with financial) |
| Memory | Service | Prior report summary + optional Chroma RAG + optional Kite portfolio block |
| Context | Model | Immutable `ResearchContext` |
| Analysis | CrewAI | Financial Analyst — JSON scores + narrative |
| Guardrails | Python | `GuardrailEngine` on analysis (retryable) |
| Risk | CrewAI | Risk Analyst — structured risks + narrative |
| Risk guardrails | Python | Validates risk narrative |
| Recommendation | CrewAI | Financial Expert — context + scores only |
| Rec guardrails | Python | Validates recommendation narrative |
| Scoring | Python | `InvestmentScoringService` v2 — deterministic confidence |
| Committee | Python | `InvestmentCommitteeService.enrich()` — personas, no extra LLM |

Legacy `financial_data_agent` / `news_researcher_agent` / financial+news tools: **removed**.

## Data flow

```
User → Frontend → POST /research/{ticker}/report
  → FinancialDataService ∥ NewsResearchService
  → prior report (Supabase) + Chroma context + Kite portfolio context (best-effort)
  → build_research_context()
  → Analysis Crew → Guardrails → Risk Crew → (rec guardrails path) → Recommendation Crew
  → InvestmentScoringService (deterministic)
  → InvestmentCommitteeService.enrich()
  → ReportStorageService → Supabase + ChromaDB
  → ResearchReportResponse JSON (incl. pipeline_trace, model_used, *_guardrails)
```

## CrewAI flow

- Exactly **3** reasoning crew kickoffs (analysis, risk, recommendation)
- Built by `build_reasoning_agent_pairs()` in `app/tasks/research_tasks.py`
- Limits: `app/agents/execution.py` (`max_iter=2`, `max_execution_time=75`)

## ChromaDB usage

- Index on save; `/reports/search/similar`
- Advisor retrieval
- **Full research crew** institutional memory via `get_context_for_ticker`
- Report chat RAG snippets (question-keyed cache)

## Supabase usage

- `supabase_repository.py` + migrations `001`–`003`
- Fallback: `InMemoryReportRepository` if credentials absent

## MCP / OAuth integrations

| Integration | Provider | Purpose |
|-------------|----------|---------|
| Tapetide MCP | `tapetide_mcp_provider.py` | NSE/BSE exchange overlays |
| Kite MCP / Connect | `kite_mcp_provider.py`, `kite_connect_client.py` | Quotes + read-only portfolio |
| Google Drive API | `google_drive_api_client.py` | Service-account PDF upload |

## Current execution pipeline (traced stages)

`financial` → `news` → `analysis` → `guardrails` → `risk` → `recommendation` → `committee`

Stage caching via `stage_cache.py` (keyed by data snapshot hash including **ticker**).
