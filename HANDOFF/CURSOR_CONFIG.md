# Cursor configuration handoff

This document captures Cursor-local config and session conventions so another coding tool
(Claude Code) can continue without losing implicit guidance. **No secrets included.**

---

## 1. Project `.cursorrules` / `.cursor/rules/`

**Status in this repository:** none present.

- No `.cursorrules` at repo root
- No `.cursor/` directory in the project tree
- No `.mdc` rule files checked into InvestIQ

Cursor behavior for this project has been driven by **Cursor user-level rules / chat instructions**
(not repo-committed files). Reconstruct those below.

---

## 2. Cursor product / MCP (session environment, not in-repo)

Available MCP servers observed in Cursor for this workspace (names/purposes only):

| Server | Purpose |
|--------|---------|
| `cursor-app-control` | Move workspace root, open resources, Automations UI, rename chat, user rules dialog |
| `cursor-ide-browser` | Browser tab automation / CDP for UI verification |
| `plugin-figma-figma` | Figma plugin MCP (present; not used for InvestIQ core work in recent sessions) |

Agent skills available under user Cursor skills (examples): canvas, create-rule, create-skill,
create-hook, babysit, review-bugbot, review-security, SDK skill, Figma-related skills.
These are **user Cursor installs**, not part of InvestIQ.

---

## 3. Coding conventions from chat / user rules (reconstructed)

These were actively followed by the Cursor agent during InvestIQ sessions. Treat them as
project working agreements unless Claude Code / the owner overrides them.

### Git safety
- Only commit when the user explicitly asks.
- Never update `git config`.
- Never force-push to main/master; warn if requested.
- Never skip hooks (`--no-verify`) unless explicitly asked.
- Prefer new commits over `--amend` except the strict amend conditions in the user rule.
- Prefer HEREDOC for commit messages when committing.
- Prefer `gh` for GitHub PR/issue work when asked to create PRs.
- Never use interactive git (`-i`) flags.

### Scope & code quality
- Only modify code required by the task; no drive-by refactors or unrelated files.
- Prefer focused diffs; match existing naming, imports, and patterns.
- Prefer reusing existing helpers over inventing parallel abstractions.
- Prefer simple solutions over speculative “enterprise” frameworks.
- Avoid verbose comments / docstrings on obvious code; comment non-obvious intent only.
- Do not proactively create markdown docs the user did not ask for (handoff docs are an exception when requested).
- Do not mention the tool’s system/policy prompt in user-facing replies.

### Communication
- Be direct and concise; lead with the key finding.
- Prefer absolute paths in tool calls.
- Use fenced code for citations in `startLine:endLine:filepath` format when citing existing code.
- Don’t over-bold or inflate length.

### Frontend design (when designing UIs)
- Avoid generic “AI purple / cream / broadsheet” default aesthetics when creating branded surfaces.
- Prefer expressive typography; avoid Inter/Roboto/Arial/system as default on greenfield marketing pages.
- Prefer real visual anchors; one purpose per section; reduce card clutter.
- **Exception:** when working inside InvestIQ’s existing Avengers/research UI, preserve the established dark purple/blue mission aesthetic (already the design language of Mission Status / pipeline).

### Shell / environment
- Prefer running commands yourself rather than only instructing the user.
- Backend local default in practice: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8002` from `backend/`
- Frontend: `npm run dev` from `frontend/` → `http://localhost:5173` (proxies API to 8002)

### Secrets / safety
- Never commit `.env`, service-account JSON keys, or tokens.
- Never print secret values in docs or chat.
- Google Drive SA file expected path (local only): `secrets/google-drive-sa.json` (directory may exist empty).

### Architecture principles already in the codebase (reinforce, don’t reverse)
- Facts via services; opinions via LLMs over immutable `ResearchContext`.
- Recommendation confidence is deterministic (`InvestmentScoringService`); LLM confidence is audit-only.
- Kite is read-only in InvestIQ (order tools excluded).
- Prefer wiring unused existing fields (`chroma_context`, `portfolio_context`) over inventing parallel context channels.

---

## 4. Unfinished local setup known from session (not in README)

- **Google Drive save** may be enabled in local `.env` (`GOOGLE_DRIVE_ENABLED=true`) but the
  service-account JSON file at `secrets/google-drive-sa.json` was still missing at handoff time.
  Drive upload fails with `FileNotFoundError` until the JSON is placed and the Drive folder is shared
  with the service account email.
- **Supabase** hostname must resolve (project active/not deleted). DNS failures surface as
  `[Errno 11001] getaddrinfo failed` on Report History.
- Repo git history: working tree was **uncommitted on a fresh `master` with “No commits yet”** at
  handoff time — all source was untracked. Claude Code should not assume a pristine git ancestry or
  tagged “architecture review” commit unless the owner re-inits/imports history elsewhere.
- Institutional memory (Chroma + richer prior reports) and Kite portfolio context were recently
  wired into `ResearchCrewService.run` — see `HANDOFF/CHANGES_SINCE_LAST_REVIEW.md`.
- **Quality dashboard** (scoped after architecture review) was **not implemented**.
- **Real multi-agent committee debate** was discussed but **not implemented** (committee remains
  deterministic persona mapping).
