# Changes since architecture review

**Review baseline:** external zip export `InvestIQ_Architecture_Review` (pre-fix findings for chat memory,
RAG cache keying, extended guardrails, rating parser, `model_used`, snapshot hash ticker,
`scores_estimated`, dead agent/tool removal). A quality dashboard was scoped afterward.

**Caveat on git:** as of this handoff, the local repo reports `No commits yet on master` with the
entire tree untracked. There is **no reliable `git log` range** between a review commit and HEAD.
Statuses below are from **current codebase inspection** plus known Cursor session work after the review.

---

## A. The 8 recommended fixes + quality dashboard

### 1. Report chat conversation history
**Status:** Applied fully

- `ReportChatRequest.history: list[ChatTurn]` in `backend/app/schemas/chat.py`
- `ReportChatService.chat(..., history=...)` formats last 10 turns into the prompt
  (`backend/app/services/report_chat_service.py`)
- Route passes `body.history` (`backend/app/api/routes/reports.py`)
- Frontend accumulates messages and sends them (`frontend/src/components/research/ReportChat.tsx`,
  `frontend/src/lib/api.ts`)
- Covered by `backend/tests/test_report_chat.py`

### 2. Chat context cache keyed by question (not just `report_id`)
**Status:** Applied with modifications (intentional split cache)

- **Report body + prior summaries:** still cached by `report_id` only
  (`_get_cached_report_context` → `ttl_cache` key `"{report_id}"`) — correct, because that block
  does not depend on the question.
- **RAG snippets:** cached by `report_id` + `sha256(question)[:12]`
  (`_get_rag_context_block`) — this is the question-sensitive path fixed per review intent.
- Files: `backend/app/services/report_chat_service.py`

### 3. Guardrails coverage for Risk + Recommendation narratives
**Status:** Applied fully

- Schema fields: `risk_guardrails`, `recommendation_guardrails` on `ResearchReportResponse`
  (`backend/app/schemas/research.py`)
- Orchestration validates risk + recommendation narratives in
  `backend/app/services/research_crew_service.py`
- UI: `GuardrailPanel` on risk/recommendation in
  `frontend/src/components/research/ProfessionalReport.tsx`, `ReportViewer.tsx`
- Types: `frontend/src/types/api.ts`
- Tests: `backend/tests/test_research_crew_service.py`

### 4. Recommendation rating parser anchored to `Rating:` label
**Status:** Applied fully (regex slightly generalized)

- Primary: `\brating\s*[:\-]?\s*(buy|hold|avoid|watchlist)\b` before first-match fallback scan
- File: `backend/app/guardrails/recommendation_parser.py`
- Logs warning when falling back

### 5. `model_used` field
**Status:** Applied fully

- Captured from LLM object after `build_llm` in `research_crew_service.py`
- Stored on `ResearchReportResponse.model_used`
- Shown in UI (`ProfessionalReport.tsx`) and PDF (`report_pdf_service.py`)
- Tests assert model string in `test_research_crew_service.py`

### 6. Ticker included in `compute_data_snapshot_hash`
**Status:** Applied fully

- Payload includes `"ticker": ticker.strip().upper()`
- File: `backend/app/services/data_snapshot.py`
- Tests: `backend/tests/test_data_snapshot.py`

### 7. `scores_estimated` flag for JSON parse fallbacks
**Status:** Applied fully

- `AnalysisOutput.scores_estimated`, `RiskOutput.scores_estimated`
  (`backend/app/schemas/agent_outputs.py`)
- Set in `backend/app/guardrails/structured_output_parser.py` when heuristic fallback used
- UI badge when estimated (`ProfessionalReport.tsx`)
- Tests: `backend/tests/test_structured_output_parser.py`

### 8. Removal of dead agent/tool files
**Status:** Applied fully

- Missing (deleted): `financial_data_agent.py`, `news_researcher_agent.py`,
  `tools/financial_tools.py`, `tools/news_tools.py`
- Remaining agents: `financial_analyst_agent.py`, `risk_analyst_agent.py`,
  `financial_expert_agent.py`, plus `execution.py`, `llm.py`
- `backend/app/tools/` now only `__init__.py`

### Quality dashboard (post-review scope)
**Status:** Not applied

- No `quality_metrics_service.py`
- No `/api/v1/quality/metrics` route
- No `QualityPage.tsx`
- No aggregation of guardrail pass rates / `model_used` distribution / `scores_estimated` frequency
  in a dedicated metrics surface

---

## B. Other features / changes since the review (not in the 8 + dashboard)

Inferred from session work and files that post-date / extend the architecture snapshot in
`scripts/export_architecture_review.py` (which still mentioned unused legacy agents). **Not** from
git log (unavailable).

| Area | What | Why |
|------|------|-----|
| PDF export | `report_pdf_service.py`, `POST /reports/{id}/pdf` | Download institutional PDF |
| Google Drive save | `google_drive_api_client.py`, `google_drive_service.py`, `report_export_service.py`, `POST /reports/{id}/drive`, migration `003_report_export_metadata.sql`, frontend Drive buttons on `ReportCard.tsx` | Persist PDFs to shared Drive folder via service account |
| Drive UI helpers | `frontend/src/lib/reportExportState.ts` (+ test) | Enable/disable Drive button states |
| Institutional memory wiring | `RagService.get_context_for_ticker` injected into crew; richer `_summarize_previous_report` | Agents reuse prior thesis / Chroma neighbors |
| Portfolio research context | `portfolio_research_context.py`; Kite holdings into `ResearchCrewService.run` | Allocation language aware of existing holdings |
| Agent prompt updates | `tasks/research_tasks.py` | Instruct compare-vs-prior + portfolio add/hold/trim |
| Neural network loading UI | `NeuralNetworkField.tsx`; `MissionStatusPanel` reduced to neural-only stage | Visual “gathering intelligence” animation |
| Mission UI theme | `avengersTheme.ts`, `AvengersPipeline.tsx`, related CSS in `index.css` | Branded research progress experience |
| Tests added | `test_institutional_memory.py`, `test_portfolio_research_context.py`, `test_report_export.py` | Cover memory / portfolio / export |

**Likely pre-existing relative to the 8 fixes but still part of current product surface**
(confirmed present; may have existed at review time): Advisor pipeline services, Tapetide/Kite
providers, Investment Committee deterministic enrich, Ask endpoint (`research_ask_service`),
company master / symbol resolver, market history routes, portfolio analyze.

---

## C. Known incomplete follow-ups after the above

1. Place real Google service-account JSON and share Drive folder (local Drive uploads broken until then).
2. Implement quality dashboard if still desired.
3. Optional next intelligence upgrades discussed: real multi-agent committee debate; outcome feedback loop; deeper Tapetide filings/screener data.
4. README still describes legacy 4-agent CrewAI data collectors — out of date vs service-backed pipeline.
