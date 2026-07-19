# InvestIQ — Architecture Notes

## Overall architecture

InvestIQ is a **full-stack AI research platform** for Indian equities:

- **Frontend:** React SPA — research, report history, portfolio, stock advisor, export actions
- **Backend:** FastAPI hybrid pipeline — deterministic data services + CrewAI reasoning agents +
  deterministic scoring/committee
- **Storage:** Supabase (reports + export metadata) + ChromaDB (semantic index / RAG)
- **LLM:** OpenRouter only for full reports (`LLM_PROVIDER=openrouter`)

Design principle: **separate facts from opinions**. Financial/news collection is deterministic;
LLM agents reason only over an immutable `ResearchContext` (which may include prior-report text,
Chroma institutional memory, and Kite portfolio context when available).

## Current strengths

1. Clear service/repository layering with broad pytest coverage (~247 passing at handoff; see
   CURRENT_STATE for 2 Drive-related failures under live `.env`)
2. Immutable `ResearchContext` shared by analysis / risk / recommendation
3. Deterministic committee scoring (v2) — reproducible confidence; LLM confidence audit-only
4. Pipeline tracing (`pipeline_trace`) with timings / cache / errors
5. Guardrails on analysis, risk, and recommendation narratives
6. Provider abstraction — Yahoo primary; Tapetide / Kite optional
7. Institutional memory wired into crew (prior report + Chroma) and portfolio sizing context from Kite
8. Report chat with conversation history; RAG cache keyed by question
9. PDF + Google Drive export path (Drive requires valid SA JSON on disk)
10. Read-only trading posture for Kite (order tools excluded)

## Known limitations

1. **README partially outdated** — still narrates 4 CrewAI data agents; collection is service-backed
2. **Committee personas are deterministic remaps** — not independent debating LLM agents
3. **No streaming** — UI progress is reconstructed; request waits for full pipeline
4. **In-process caches only** — `ttl_cache` / `stage_cache` not distributed
5. **ChromaDB local** — not managed cloud vector DB in current setup
6. **Qualitative depth** — news via Tavily snippets; filings/transcripts not deeply parsed
7. **Structured output fallbacks** — `scores_estimated` when JSON parse fails
8. **Quality metrics dashboard** scoped but not built
9. **Git history absent** in current working copy (no commits yet) — operational risk for handoff
10. **Drive config fragile** — env can enable Drive while SA file missing; tests can fail if `.env` leaks into cases

## Performance bottlenecks

| Bottleneck | Impact | Notes |
|------------|--------|-------|
| LLM calls (3 agents) | High | Analysis / risk / recommendation sequential |
| Tavily news (parallel searches) | Medium | |
| Yahoo financial fan-out | Medium | |
| Optional Chroma + holdings fetch | Low | Best-effort; must not block |
| Supabase + Chroma index on save | Low | Post-generation |
| No HTTP streaming | UX | Full wait |

**Target experience:** ~25–35s with parallel financial+news and stage caching when `CACHE_ENABLED`.

## Existing caching

| Layer | Mechanism | Notes |
|-------|-----------|-------|
| Financial collect | `ttl_cache` | Controlled by `CACHE_ENABLED` |
| News / analysis / risk / rec | `stage_cache` | Keyed by snapshot hash |
| Report detail GET | `ttl_cache` `report` | |
| Report chat base context | `ttl_cache` `chat_context` by `report_id` | |
| Report chat RAG | `ttl_cache` `chat_context` by `report_id`+question hash | |
| Full report dedup | recent same ticker+hash ~120s | |
| Holdings | `ttl_cache` `holdings` | |

## AI pipeline

```
PARALLEL: FinancialDataService + NewsResearchService
    ↓
Optional memory: prior report + Chroma RAG + Kite portfolio context
    ↓
ResearchContext (immutable)
    ↓
Analysis Agent → structured scores + narrative
    ↓
Guardrails (validate analysis; optional retry)
    ↓
Risk Agent → structured risk scores + narrative
    ↓
Risk guardrails
    ↓
Recommendation Agent (if analysis guardrails pass)
    ↓
Recommendation guardrails
    ↓
InvestmentScoringService v2 (deterministic confidence / rating)
    ↓
InvestmentCommitteeService.enrich() (deterministic personas)
```

## Report generation flow

1. `POST /api/v1/research/{ticker}/report`
2. `ResearchCrewService.run(ticker, storage=, rag=, holdings_service=)`
3. Auto-save via `ReportStorageService` if `STORAGE_ENABLED`
4. Return `ResearchReportResponse` including `pipeline_trace`, `score_breakdown`,
   `confidence_score`, `model_used`, `risk_guardrails`, `recommendation_guardrails`

## Recommendation flow

- Agent receives ResearchContext + analysis/risk scores + guardrail status
- Parsed by `recommendation_parser.py` (label-anchored rating)
- **Confidence overwritten** by scoring service; `llm_suggested_confidence` audit-only
- Allocation text should respect `PORTFOLIO_CONTEXT` when present

## Investment committee flow

- Maps report fields → 5 analyst personas **without new LLM calls**
- Verdict confidence = deterministic `confidence_score`
- Not a multi-agent debate (upgrade candidate)

## Advisor / Ask flows (side paths)

- **Ask:** `research_ask_service` — one LLM call on snapshot + Tavily; no full crew
- **Advisor:** intent → retrieval/enrich → LLM rank + advisor guardrails; may use Chroma + holdings
- **Report chat:** grounded on saved report + optional RAG; history client-supplied

## Export flow

1. `POST /reports/{id}/pdf` → `report_pdf_service` (fpdf2)
2. `POST /reports/{id}/drive` → PDF then Google Drive API upload; metadata columns from migration `003`

## Frontend notable surfaces

- Research home + Avengers / Mission Status neural animation while generating
- Report detail with ProfessionalReport, guardrail panels, scores_estimated badge, model_used
- Report history + PDF / Drive actions on cards
- Portfolio (Kite) + Advisor panels
