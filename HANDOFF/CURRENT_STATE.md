# Current state (handoff snapshot)

Captured for Claude Code takeover. **No secrets.** Env var **names** only.

---

## Git

### `git status -sb` (verbatim summary)

```
## No commits yet on master
?? .gitignore
?? README.md
?? backend/
?? docs/
?? downloads/
?? frontend/
?? render.yaml
?? scripts/
```

Also present on disk (may be ignored / not listed depending on ignore rules): `HANDOFF/`, `secrets/`,
local `backend/.env`, `backend/chroma_data/`, `frontend/node_modules/`, `frontend/dist/`.

### `git log --oneline -30`

```
fatal: your current branch 'master' does not have any commits yet
```

**Implication:** there is no commit history in this clone. All application code is currently
**untracked**. Claude Code should treat the working tree as the source of truth and ask the owner
before creating the initial commit / importing history from elsewhere.

### Branches

| Branch | Note |
|--------|------|
| `master` | Only local branch; no commits; not tracking remote at handoff time |
| (no other branches) | — |

`git branch -a` effectively shows empty history state (`HEAD` ambiguous).

---

## Backend tests

Command: `cd backend && python -m pytest -q --tb=no`

**Result:** **247 passed**, **2 failed**, 1 warning (Starlette TestClient deprecation).

### Failing tests

1. `tests/test_report_export.py::test_drive_endpoint_handles_missing_google_drive_config`
2. `tests/test_report_export.py::test_google_drive_not_connected_without_credentials`

**Observed cause:** local `backend/.env` sets `GOOGLE_DRIVE_ENABLED=true` and
`GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` to a path whose file does not exist
(`secrets/google-drive-sa.json` missing). Settings load from `.env` during tests; code attempts
`from_service_account_file` → `FileNotFoundError`, or fails the “not connected” expectation because
credentials *appear* configured. **Not fixed in this handoff** (report-only).

---

## Frontend build

Command: `cd frontend && npm run build`

**Result:** **Success** (`tsc -b && vite build`). Client bundle produced under `frontend/dist/`.
Warning: chunk > 500 kB (Vite size notice only).

---

## External integrations (local `.env` presence)

Checked via env **names** in `backend/.env` (values never copied).

| Integration | Feature flags / keys | Local state |
|-------------|----------------------|-------------|
| **OpenRouter / LLM** | `LLM_PROVIDER`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (etc.) | Configured — `LLM_PROVIDER` set, `OPENROUTER_API_KEY` **SET** |
| **Yahoo / yfinance** | `YFINANCE_ENABLED` | Live — **true** |
| **Tavily** | `TAVILY_API_KEY` | Configured — **SET** |
| **Supabase** | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `STORAGE_ENABLED` | Configured — URL/key **SET**, `STORAGE_ENABLED=true`. Note: host must DNS-resolve; past session saw `getaddrinfo` failures if project paused/deleted |
| **ChromaDB** | `CHROMA_ENABLED`, `CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION_NAME` | Enabled — `CHROMA_ENABLED=true` (local persist dir) |
| **Kite** | `KITE_MCP_ENABLED`, `KITE_API_KEY`, `KITE_API_SECRET`, redirect URLs | Enabled — MCP **true**, API key/secret **SET** (OAuth still required at runtime for holdings) |
| **Tapetide MCP** | `TAPETIDE_MCP_ENABLED`, `TAPETIDE_MCP_URL`, `TAPETIDE_API_TOKEN` | Enabled in env — MCP **true**, token **SET** (local MCP process must be running when URL is localhost) |
| **Google Drive** | `GOOGLE_DRIVE_ENABLED`, `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE`, `GOOGLE_DRIVE_ROOT_FOLDER_ID` | Flag **true** and path/folder id **SET**, but **JSON key file missing on disk** → uploads fail until file is added |

Also relevant names in `.env.example` (may or may not be set locally): `NSE_BSE_MCP_*` (deprecated),
`FMP_API_KEY`, `CACHE_ENABLED`, `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`.

Dev servers historically used: backend **:8002**, frontend **:5173**.

---

## TODO / FIXME / HACK

Grep across `backend/app` and `frontend/src` for `TODO`, `FIXME`, `HACK`, `XXX`:

**No matches** in application source (false positives only in company master data symbol `THACKER`).

Known incomplete work is tracked in docs/session rather than inline markers — see
`CHANGES_SINCE_LAST_REVIEW.md` §C and Drive key missing above.

---

## Manual / local-only setup beyond README

1. Create `backend/.env` from `.env.example`; fill OpenRouter + Tavily at minimum for full reports.
2. For persistence: set Supabase URL/anon key; run migrations under `backend/database/migrations/`
   (`001_research_reports.sql`, `002_research_reports_rls.sql`, `003_report_export_metadata.sql`).
3. Chroma: enable `CHROMA_ENABLED`; data lives in `CHROMA_PERSIST_DIRECTORY` (default `./chroma_data`).
4. Kite portfolio: set API key/secret + redirects; complete OAuth via Kite routes; holdings require
   authenticated session.
5. Tapetide: if `TAPETIDE_MCP_URL=http://localhost:3000/mcp`, start Tapetide MCP locally and set token.
6. Google Drive: place service-account JSON under `secrets/` (keep out of git); set
   `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE`; share Drive folder with SA email; use folder **ID** not full URL
   in `GOOGLE_DRIVE_ROOT_FOLDER_ID`.
7. Typical start:
   - `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8002`
   - `cd frontend && npm run dev`
8. Company symbol resolution uses bundled master data under `backend/app/data/company_master.json`
   (loaded at startup).
9. PDF/Drive deps: ensure `fpdf2`, `google-api-python-client`, `google-auth` installed from
   `requirements.txt` if Drive/PDF features are used.

---

## Recent unfinished product threads (non-code markers)

- Institutional memory + portfolio context: **implemented** in crew (restart backend to load).
- Quality dashboard: **not started**.
- Real LLM committee debate: **not started**.
- Drive end-to-end: blocked on missing SA JSON on disk despite env flag.
