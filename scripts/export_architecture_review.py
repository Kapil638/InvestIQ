#!/usr/bin/env python3
"""Export InvestIQ source for external architecture review (no secrets)."""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

SOURCE_ROOT = Path(r"C:\Users\Kapil\InvestIQ")
EXPORT_ROOT = Path(r"C:\Users\Kapil\InvestIQ_Architecture_Review_build")
ZIP_PATH = Path(r"C:\Users\Kapil\InvestIQ_Architecture_Review.zip")

EXCLUDE_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    "coverage",
    ".next",
    ".cache",
    ".idea",
    ".vscode",
    "chroma_data",
    "InvestIQ_Architecture_Review",
}

EXCLUDE_FILE_PATTERNS = [
    re.compile(r"\.env$", re.I),
    re.compile(r"\.env\.(local|production)$", re.I),
    re.compile(r"\.log$", re.I),
    re.compile(r"\.sqlite$", re.I),
    re.compile(r"\.db$", re.I),
    re.compile(r"\.pyc$", re.I),
]

INCLUDE_TOP_LEVEL = {
    "backend",
    "frontend",
    "docs",
    "README.md",
    "render.yaml",
}

INCLUDE_FRONTEND_ROOT_FILES = {
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "vite.config.ts",
    "vitest.config.ts",
    "index.html",
    "oxlint.json",
    "components.json",
}

INCLUDE_BACKEND_ROOT_FILES = {
    "requirements.txt",
    "requirements-prod.txt",
    "Dockerfile",
    ".env.example",
    ".env.production.example",
}

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
]


def should_exclude(path: Path, relative: Path) -> bool:
    for part in relative.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    name = path.name
    for pat in EXCLUDE_FILE_PATTERNS:
        if pat.search(name):
            return True
    return False


def should_include_file(relative: Path) -> bool:
    if len(relative.parts) == 1:
        return relative.name in INCLUDE_TOP_LEVEL
    top = relative.parts[0]
    if top == "backend":
        if len(relative.parts) == 2 and relative.name in INCLUDE_BACKEND_ROOT_FILES:
            return True
        if relative.name in {".env", ".env.local"}:
            return False
        return True
    if top == "frontend":
        if len(relative.parts) == 2 and relative.name in INCLUDE_FRONTEND_ROOT_FILES:
            return True
        if relative.name in {".env"}:
            return False
        return True
    if top == "docs":
        return True
    return False


def _ignore_patterns(directory: str, names: list[str]) -> list[str]:
    ignored = set(EXCLUDE_DIR_NAMES)
    for name in names:
        if name in ignored:
            continue
        if name == ".env" or name.endswith(".log") or name.endswith(".sqlite") or name.endswith(".db"):
            ignored.add(name)
    return list(ignored)


def copy_tree() -> tuple[int, int, list[str]]:
    if EXPORT_ROOT.exists():
        shutil.rmtree(EXPORT_ROOT)
    EXPORT_ROOT.mkdir(parents=True)

    copied = 0
    excluded = 0
    excluded_samples: list[str] = []

    for root, dirs, files in os.walk(SOURCE_ROOT):
        root_path = Path(root)
        rel_root = root_path.relative_to(SOURCE_ROOT)

        if rel_root.parts and rel_root.parts[0] not in {"backend", "frontend", "docs"}:
            if rel_root != Path("."):
                dirs.clear()
                continue

        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]

        if rel_root == Path("."):
            for name in INCLUDE_TOP_LEVEL:
                src = SOURCE_ROOT / name
                if not src.exists():
                    continue
                dst = EXPORT_ROOT / name
                if src.is_dir():
                    shutil.copytree(
                        src,
                        dst,
                        ignore=_ignore_patterns,
                        dirs_exist_ok=True,
                    )
                else:
                    shutil.copy2(src, dst)
                    copied += 1
            continue

        for fname in files:
            src = root_path / fname
            rel = src.relative_to(SOURCE_ROOT)
            if not should_include_file(rel):
                excluded += 1
                if len(excluded_samples) < 30:
                    excluded_samples.append(str(rel))
                continue
            if should_exclude(src, rel):
                excluded += 1
                if len(excluded_samples) < 30:
                    excluded_samples.append(str(rel))
                continue
            dst = EXPORT_ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1

    # Ensure .env.example at export root (backend copy only)
    backend_example = EXPORT_ROOT / "backend" / ".env.example"
    frontend_example = EXPORT_ROOT / "frontend" / ".env.example"
    if not backend_example.exists() and (SOURCE_ROOT / "backend" / ".env.example").exists():
        shutil.copy2(SOURCE_ROOT / "backend" / ".env.example", backend_example)
    if not frontend_example.exists() and (SOURCE_ROOT / "frontend" / ".env.example").exists():
        shutil.copy2(SOURCE_ROOT / "frontend" / ".env.example", frontend_example)

    return copied, excluded, excluded_samples


def scan_secrets() -> list[str]:
    findings: list[str] = []
    for path in EXPORT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.name in {".env", ".env.local", ".env.production"}:
            continue
        if ".env.example" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                findings.append(f"{path.relative_to(EXPORT_ROOT)}: matched {pat.pattern}")
    return findings


def count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file())


def make_zip() -> int:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in EXPORT_ROOT.rglob("*"):
            if path.is_file():
                arcname = Path("InvestIQ_Architecture_Review") / path.relative_to(EXPORT_ROOT)
                zf.write(path, arcname)
    return ZIP_PATH.stat().st_size


def write_docs() -> None:
    (EXPORT_ROOT / "PROJECT_STRUCTURE.md").write_text(PROJECT_STRUCTURE, encoding="utf-8")
    (EXPORT_ROOT / "ARCHITECTURE_NOTES.md").write_text(ARCHITECTURE_NOTES, encoding="utf-8")
    (EXPORT_ROOT / "REVIEW_CONTEXT.md").write_text(REVIEW_CONTEXT, encoding="utf-8")
    (EXPORT_ROOT / "EXPORT_MANIFEST.txt").write_text(
        f"Exported: {datetime.now(UTC).isoformat()}\nSource: {SOURCE_ROOT}\n",
        encoding="utf-8",
    )


PROJECT_STRUCTURE = r"""# InvestIQ — Project Structure

> Export for external architecture review. Generated from production codebase snapshot.

## Folder tree (major paths)

```
InvestIQ_Architecture_Review/
├── README.md
├── PROJECT_STRUCTURE.md
├── ARCHITECTURE_NOTES.md
├── REVIEW_CONTEXT.md
├── render.yaml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-prod.txt
│   ├── .env.example
│   ├── database/migrations/
│   ├── tests/
│   └── app/
│       ├── api/              # FastAPI routes & dependencies
│       ├── agents/           # CrewAI agent definitions
│       ├── core/             # Pydantic Settings (config.py)
│       ├── database/         # Supabase repos, ChromaDB store
│       ├── guardrails/       # Validation engine, parsers
│       ├── llm/              # OpenRouter LLM factory & caller
│       ├── models/           # Domain models (ResearchContext, StoredReport)
│       ├── providers/        # Yahoo, Tapetide MCP, Kite MCP
│       ├── schemas/          # Pydantic API models
│       ├── services/         # Business logic & orchestration
│       ├── tasks/            # CrewAI task definitions
│       ├── tools/            # CrewAI tools (legacy; data via services)
│       └── utils/            # Cache, timing, exceptions
├── docs/
│   └── DEPLOYMENT.md
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── .env.example
    └── src/
        ├── components/       # UI (research, advisor, portfolio, chart)
        ├── pages/            # Routes: Home, Reports, Portfolio
        ├── hooks/            # Kite/Tapetide status
        ├── lib/              # API client, utilities
        └── types/            # TypeScript API types
```

## Purpose of major folders

| Folder | Purpose |
|--------|---------|
| `backend/app/api` | HTTP layer: research, reports, financials, advisor, portfolio, kite, search |
| `backend/app/services` | Core business logic; `research_crew_service.py` orchestrates the pipeline |
| `backend/app/agents` | CrewAI agent builders (Analysis, Risk, Recommendation) |
| `backend/app/providers` | External data: Yahoo Finance, Tapetide MCP, Kite MCP |
| `backend/app/database` | Supabase PostgreSQL persistence + ChromaDB vector index |
| `backend/app/guardrails` | Deterministic output validation; structured JSON parsers |
| `backend/tests` | Pytest suite (~224 tests) |
| `frontend/src` | React SPA: research UI, report history, portfolio, advisor |

## Backend architecture

- **FastAPI** application (`app/main.py`) with versioned routes under `/api/v1`
- **Pydantic Settings** central config (`app/core/config.py`)
- **Service layer** pattern: routes → services → providers/repositories
- **Dependency injection** via `app/api/dependencies.py`

## Frontend architecture

- **React 19 + Vite 8 + TypeScript**
- **React Router** for `/`, `/reports`, `/reports/:id`, `/portfolio`
- **Tailwind CSS 4** + shadcn-style UI components
- API client in `frontend/src/lib/api.ts` → `VITE_API_URL`

## Agent architecture (current)

| Stage | Type | Implementation |
|-------|------|----------------|
| Financial | Service | `FinancialDataService.collect()` — Yahoo/Tapetide/Kite |
| News | Service | `NewsResearchService.collect()` — Tavily (parallel with financial) |
| Context | Model | `ResearchContext` — immutable shared input |
| Analysis | CrewAI | Financial Analyst agent — JSON scores + narrative |
| Guardrails | Python | `GuardrailEngine` — staleness, hallucination checks |
| Risk | CrewAI | Risk Analyst agent — structured risk scores |
| Recommendation | CrewAI | Financial Expert agent — uses context + scores only |
| Committee | Python | `InvestmentScoringService` v2 — deterministic confidence |

Unused legacy agent files (`financial_data_agent`, `news_researcher_agent`) remain for tool definitions but are **not** invoked in the pipeline.

## Data flow

```
User → Frontend → POST /research/{ticker}/report
  → FinancialDataService ∥ NewsResearchService
  → build_research_context()
  → Analysis Crew → Guardrails → Risk Crew → Recommendation Crew
  → InvestmentScoringService (deterministic)
  → InvestmentCommitteeService.enrich()
  → ReportStorageService → Supabase + ChromaDB
  → ResearchReportResponse JSON
```

## CrewAI flow

- Only **3 reasoning crews** are kicked off (single agent + single task each, `Process.sequential`)
- `build_reasoning_agent_pairs()` in `app/tasks/research_tasks.py`
- Kickoff via `research_crew_service._kickoff_crew()` (`akickoff` or threaded `kickoff`)
- Agent execution limits in `app/agents/execution.py` (`max_iter=2`, `max_execution_time=75`)

## ChromaDB usage

- `app/database/chroma_store.py` — indexes report text + chunks for RAG
- Used by `RagService` for `/reports/search/similar`
- Used by Advisor retrieval (`advisor_retrieval.py`)
- Local persist dir: `CHROMA_PERSIST_DIRECTORY` (not included in export)

## Supabase usage

- `app/database/repositories/supabase_repository.py` — PostgreSQL via PostgREST
- Migration: `backend/database/migrations/001_research_reports.sql`
- Stores full `report_json` + denormalized rating/confidence columns
- Falls back to `InMemoryReportRepository` when credentials absent

## MCP integrations

| Integration | Provider | Purpose |
|-------------|----------|---------|
| Tapetide MCP | `tapetide_mcp_provider.py` | NSE/BSE exchange data, live prices |
| Kite MCP | `kite_mcp_provider.py` | Portfolio holdings, live quotes (read-only) |

OAuth for Kite Connect: `kite_auth_service.py`, `kite_token_store.py` (tokens never in repo).

## Yahoo / NSE / Kite providers

- **Primary:** `YahooFinanceProvider` via `yfinance` — Indian tickers normalized to `.NS`
- **Tapetide:** Optional MCP overlay for exchange-native data
- **Kite:** Optional MCP + Connect OAuth for portfolio features
- **Symbol resolution:** `symbol_resolver_service.py`, `company_master_service.py`

## Current execution pipeline

See `backend/app/services/research_crew_service.py` and `pipeline_tracer.py` for traced stages:

`financial` → `news` → `analysis` → `guardrails` → `risk` → `recommendation` → `committee`

Stage caching: `stage_cache.py` (analysis/risk/recommendation keyed by data snapshot hash).
"""

ARCHITECTURE_NOTES = r"""# InvestIQ — Architecture Notes

## Overall architecture

InvestIQ is a **full-stack AI research platform** for Indian equities:

- **Frontend:** React SPA for research, report history, portfolio, and stock advisor
- **Backend:** FastAPI with a hybrid pipeline — deterministic data services + CrewAI reasoning agents + deterministic scoring
- **Storage:** Supabase (reports) + ChromaDB (semantic search / RAG)
- **LLM:** OpenRouter (configurable model routing)

Design principle: **separate facts from opinions**. Financial/news collection is deterministic; LLM agents only reason over pre-collected `ResearchContext`.

## Current strengths

1. **Clear service/repository layering** — testable, 224+ pytest coverage
2. **ResearchContext** — single immutable input for all reasoning agents
3. **Deterministic committee scoring** (v2) — reproducible confidence from structured agent scores
4. **Pipeline tracing** — per-stage timings, cache hits, errors in `pipeline_trace`
5. **Guardrails** — staleness, hallucination, conclusion validation before recommendation
6. **Provider abstraction** — Yahoo primary; Tapetide/Kite optional overlays
7. **Graceful degradation** — in-memory storage, cache toggles, storage failure doesn't block report return
8. **Read-only trading** — Kite order tools explicitly excluded

## Known limitations

1. **README partially outdated** — still describes 4 CrewAI data agents; pipeline refactored to service-backed collection
2. **Legacy agent files** — `financial_data_agent`, `news_researcher_agent` exist but unused in orchestrator
3. **No streaming** — report generation is request/response; UI simulates progress until `pipeline_trace` returns
4. **In-process caches only** — `ttl_cache` and `stage_cache` are not distributed
5. **ChromaDB local** — not managed/cloud-hosted in current deployment
6. **Single LLM provider path** — OpenRouter required for full reports
7. **JSON parsing fallbacks** — agent structured output relies on prompt compliance + regex/JSON extraction

## Performance bottlenecks

| Bottleneck | Impact | Notes |
|------------|--------|-------|
| LLM calls (3 agents) | High | Analysis ~10–12s, Risk ~5s, Recommendation ~5s |
| Tavily news (3 parallel searches) | Medium | ~5s |
| Yahoo financial (7 parallel fetches) | Medium | ~5s |
| CrewAI startup / agent construction | Low–Medium | Per request |
| Supabase + Chroma indexing | Low | Post-report, async-safe |
| No HTTP streaming | UX | User waits for full pipeline |

**Target:** 25–35s total with parallel financial+news and stage caching.

## Existing caching

| Layer | Mechanism | TTL |
|-------|-----------|-----|
| Financial collect | `ttl_cache` namespace `financial` | 300s |
| News (pipeline) | `stage_cache` per ticker | 300s |
| Analysis/Risk/Recommendation | `stage_cache` keyed by data hash | 300s |
| Report detail GET | `ttl_cache` namespace `report` | 60s |
| Full report dedup | `find_recent_by_ticker_and_hash` | 120s |
| Search / advisor / holdings | Various `ttl_cache` namespaces | 60–600s |
| CrewAI agent | `cache=True` in execution controls | CrewAI internal |

Controlled by `CACHE_ENABLED` (default `false` in dev).

## AI pipeline

```
PARALLEL: FinancialDataService + NewsResearchService
    ↓
ResearchContext (immutable)
    ↓
Analysis Agent → structured scores + narrative
    ↓
Guardrails (validate, optional retry)
    ↓
Risk Agent → structured risk scores + narrative
    ↓
Recommendation Agent (if guardrails pass)
    ↓
InvestmentScoringService v2 (deterministic)
    ↓
InvestmentCommitteeService.enrich() (deterministic personas)
```

## Report generation flow

1. `POST /api/v1/research/{ticker}/report`
2. `ResearchCrewService.run()`
3. Auto-save via `ReportStorageService` if `STORAGE_ENABLED`
4. Returns `ResearchReportResponse` with `pipeline_trace`, `score_breakdown`, `confidence_score`

## Recommendation flow

- Recommendation agent receives **only** ResearchContext + analysis/risk scores + guardrail status
- Raw output parsed by `recommendation_parser.py` (rating, reasoning, risks)
- **Confidence overwritten** by deterministic `InvestmentScoringService`
- `llm_suggested_confidence` stored for audit only

## Investment committee flow

- `InvestmentCommitteeService` maps report fields to 5 analyst personas (no extra LLM calls)
- Verdict confidence = `report.confidence_score` (deterministic)
- Committee rating derived from confidence bands + recommendation mapping

## Advisor flow

- Separate from full report pipeline
- `AdvisorService` — intent classification, symbol resolution, grounded scoring
- Uses Chroma RAG + financial snapshots
- Single LLM call (not CrewAI multi-agent)
- Does **not** trigger full research crew
"""

REVIEW_CONTEXT = r"""# InvestIQ — Review Context for Claude

## What InvestIQ is

**InvestIQ** is an AI-powered investment research platform focused on **Indian equities (NSE/BSE)**. It generates institutional-style research reports for individual stocks, combining:

- Structured financial data (Yahoo Finance, optional Tapetide/Kite MCP)
- News and sentiment (Tavily)
- Multi-stage AI reasoning (CrewAI via OpenRouter)
- Deterministic guardrails and committee scoring
- Persistent report history with semantic search (Supabase + ChromaDB)

It also provides a **Stock Advisor** (grounded recommendations without full crew pipeline) and **Portfolio** integration via Kite (read-only).

---

## Current features

- Company search with symbol resolution (NSE/BSE/Yahoo tickers)
- Financial snapshots and price history charts
- Full institutional report generation (multi-agent pipeline)
- Deterministic investment committee with score breakdown
- Report history, detail view, bulk delete
- Report chat (follow-up Q&A on saved reports, no crew re-run)
- RAG similarity search across past reports
- Stock Advisor with intent-based queries
- Kite portfolio holdings (OAuth, read-only)
- Tapetide MCP status integration
- Pipeline UI with real `pipeline_trace` after completion

---

## Current roadmap (from README + recent work)

| Phase | Status |
|-------|--------|
| Backend foundation | ✅ |
| Yahoo financial provider | ✅ |
| CrewAI pipeline | ✅ (refactored) |
| Guardrails | ✅ |
| Supabase + ChromaDB | ✅ |
| React frontend | ✅ |
| Deployment (Render + Vercel) | ✅ Ready |
| ResearchContext architecture | ✅ Recent |
| Risk as real CrewAI agent | ✅ Recent |
| Deterministic scoring v2 | ✅ Recent |
| Stage caching | ✅ Recent |

---

## Recently implemented work

1. **Pipeline architecture refactor**
   - Financial/News remain Python services (parallel `asyncio.gather`)
   - Removed unused CrewAI financial/news agent construction from orchestrator
   - Added immutable `ResearchContext` shared by all reasoning agents

2. **Structured agent outputs**
   - Analysis agent: JSON scores + narrative
   - Risk agent: CrewAI (replaced deterministic-only risk extraction in pipeline)
   - Recommendation agent: consumes context + scores only (no metric invention)

3. **Deterministic committee scoring v2**
   - Weights: Growth 20%, Profitability 20%, Valuation 15%, Financial Health 15%, Management 10%, Sector 10%, News 5%, Risk 5%
   - Same data hash → same confidence (within 1 point)
   - 2-minute dedup for identical snapshots

4. **Pipeline trace & caching**
   - Expanded `pipeline_trace` (cache_hit, tokens, error fields)
   - Per-stage cache for analysis/risk/recommendation

5. **Report history fixes**
   - Summary resolver aligns list view with committee verdict

6. **CrewAI execution controls**
   - `max_iter=2`, `max_execution_time=75`, `respect_context_window=True`, `cache=True`

---

## Current architecture decisions

| Decision | Rationale |
|----------|-----------|
| Services for data, CrewAI for reasoning | Speed, determinism, reduced hallucination on facts |
| ResearchContext as single source of truth | Prevents duplicate API calls; clearer agent inputs |
| Deterministic scoring after LLM recommendation | Stable confidence; explainable `score_breakdown` |
| OpenRouter as sole LLM provider | Unified routing, fallback models |
| In-memory fallback storage | Local dev without Supabase |
| Guardrails before recommendation | Block bad analysis from reaching final rating |
| Read-only Kite | Safety — no order placement |

---

## Areas where I want feedback

Please review critically and suggest improvements for:

### 1. CrewAI orchestration
- Is single-agent-per-crew the right pattern vs one multi-agent crew?
- Should we use `Process.hierarchical` or custom async orchestration instead?
- Dead code: legacy financial/news agent files still present

### 2. Agent design
- Prompt structure for JSON + narrative outputs
- Parser fallbacks when LLM omits JSON blocks
- Risk agent separation vs combining with analysis

### 3. Hallucination prevention
- Guardrails coverage gaps
- Whether ResearchContext is sufficient constraint
- Recommendation agent still has free-text reasoning — risks?

### 4. Performance
- Target 25–35s — realistic?
- Stage caching strategy
- Parallel LLM calls (risk + recommendation) — safe?

### 5. Parallel execution
- Financial + news already parallel
- Should analysis/risk ever parallelize?

### 6. ResearchContext
- Missing fields (portfolio context, chroma context underutilized)?
- Immutability vs enrichment during pipeline

### 7. Caching
- In-process only — production concerns
- Cache invalidation on partial data refresh
- `CACHE_ENABLED=false` by default — correct for prod?

### 8. Scalability
- Single FastAPI worker assumptions
- ChromaDB local persistence
- Supabase connection patterns

### 9. Production readiness
- Error handling, observability, rate limits
- Secret management
- Deployment (Render cold starts, timeout limits)

### 10. Code quality
- Service layer size (`research_crew_service.py`, `financial_data_service.py`)
- Test coverage gaps
- Type safety frontend/backend contract drift

---

## How to run this export

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # or Windows equivalent
pip install -r requirements.txt
cp .env.example .env   # fill keys locally — NOT included in this export
pytest -q

# Frontend
cd frontend
npm install
cp .env.example .env
npm run build
```

**No secrets are included in this export.** Use `.env.example` templates only.
"""


def main() -> None:
    copied, excluded, excluded_samples = copy_tree()
    write_docs()
    secret_findings = scan_secrets()
    file_count = count_files(EXPORT_ROOT)
    zip_size = make_zip()

    print(f"Export root: {EXPORT_ROOT}")
    print(f"Files exported: {file_count}")
    print(f"Copy operations (approx): {copied}")
    print(f"Excluded (approx): {excluded}")
    print(f"ZIP: {ZIP_PATH} ({zip_size / 1024:.1f} KB)")
    if secret_findings:
        print("WARNING - potential secrets:")
        for f in secret_findings:
            print(f"  {f}")
    else:
        print("Secret scan: CLEAN")
    if excluded_samples:
        print("Sample exclusions:", ", ".join(excluded_samples[:10]))


if __name__ == "__main__":
    main()
