# CLAUDE.md — When. v2 (Agent Operating System)

This file defines how Claude Code should behave in this repository. It does not describe the system architecture or business logic — those live in `/docs`.

---

## Core principle

When. is a production-grade full-stack scheduling system.
Claude must prioritize:

1. Correctness over completeness
2. Deterministic logic over assumptions
3. Existing patterns over new abstractions
4. Schema alignment over inferred behavior

Never guess architecture. Always verify against `/docs`.

---

## Source of truth hierarchy

When in doubt, follow this order:

1. `docs/DATA_MODEL.md` → database truth
2. `docs/ARCHITECTURE.md` → system structure
3. `docs/TECH_STACK.md` → tool constraints
4. Codebase implementation
5. This file (behavior rules only)

---

## Repo mental model

* Backend = FastAPI service layer over Supabase
* Frontend = Next.js server-first + client islands
* Supabase = source of truth for persistence + real-time
* All business logic lives in backend services
* Frontend never directly owns business rules

---

## Global rules for Claude

### Always

* Follow existing patterns in code before introducing new ones
* Check `/docs` before implementing anything non-trivial
* Keep changes minimal and localized unless refactoring is explicitly requested
* Preserve deterministic behavior (especially scheduling logic)
* Respect RLS boundaries defined in DATA_MODEL.md

### Never

* Invent new architectural patterns
* Bypass service layer in backend
* Introduce new state systems on frontend
* Modify schema without updating DATA_MODEL.md
* Assume missing behavior — ask or inspect instead

---

## Cross-domain boundaries

If unsure where logic belongs:

* Database rule → Supabase / RLS / schema
* Business rule → backend service layer
* UI state → frontend component/hook
* Shared logic → backend services + typed API contract

---

## Critical invariants

These must NEVER be broken:

* Scheduling algorithm is deterministic (no AI/LLM)
* Supabase is the persistence layer of record
* One write-calendar per user across providers
* All times stored in UTC
* Coordinator-only finalization
* RLS enforced for all user-facing queries

---

## Development workflow awareness

Claude should assume:

* Tests exist and must be updated when logic changes
* API changes must update TypeScript interfaces
* Backend changes must preserve Pydantic models
* Real-time events must invalidate TanStack Query caches where relevant

---

## File navigation guidance

If unsure where logic lives:

* backend/app/services/ → business logic
* backend/app/routers/ → HTTP layer only
* frontend/hooks/ → server state access
* frontend/components/ → UI only
* docs/ → canonical system truth

---

## Debugging approach

When fixing issues:

1. Identify layer (UI / API / DB / sync)
2. Trace data flow from Supabase → backend → frontend
3. Verify schema alignment first
4. Only then modify implementation

---

## Safety rule

If a change could affect:

* scheduling correctness
* calendar sync integrity
* cross-user data consistency

→ prefer conservative fix + ask for confirmation if uncertain
