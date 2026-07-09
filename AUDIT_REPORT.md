# When. v2 — Security & Bug Audit Report

**Date:** 2026-07-05
**Scope:** Full codebase — FastAPI backend, Next.js frontend, Supabase schema/RLS, Google/Microsoft calendar integration, dependencies.
**Method:** Six parallel deep-read audits (backend services, routers/auth, Supabase/RLS, calendar/OAuth, frontend, cross-cutting), each verifying every finding against live code before reporting. The coordinator then deduplicated across streams, personally re-read and confirmed all Critical/High findings against the actual source, and ranked by severity.
**Status:** Report only — no code was modified.

---

## Executive summary

The codebase is disciplined on fundamentals: no committed secrets, consistent Pydantic validation, no stack-trace/PII leakage in logs, UTC-everywhere in the schema, sound uniqueness/FK constraints, deterministic proposal *ranking*, and textbook-clean frontend data-layer discipline (TanStack Query invalidation, realtime confined to hooks, Zustand scoped correctly, zero `any` on API boundaries). Authorization is generally enforced correctly at the service layer.

The serious exposure is concentrated in a few areas:

1. **OAuth account-linking CSRF (Critical)** — the calendar-connect callback trusts an unsigned `user_id` as OAuth `state`, allowing cross-user calendar attachment.
2. **Client-reachable authorization gaps in RLS (High)** — the frontend uses the public anon key for realtime, and two policies are effectively open (`realtime.messages` broadcasts, `event_participants` self-update), enabling cross-user data exposure and permission self-escalation that the backend's app-level checks do not backstop.
3. **An XSS→token-theft chain (High)** — an unvalidated `javascript:`-capable link sink combined with a `localStorage`-resident JWT.
4. **Data-consistency bugs that silently corrupt scheduler inputs/outputs (High)** — unbounded stale-slot deletion, missing proposal-regeneration propagation, and a login-breaking pagination bug.
5. **Dependency backlog (High)** — Next.js two majors behind with multiple High advisories, plus `ws`, `python-jose`, and `starlette` CVEs.

### Findings by severity

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High     | 11 |
| Medium   | 17 |
| Low      | 20 |

Findings corroborated by more than one audit stream are marked **⨯N streams** — higher confidence. Findings the coordinator personally re-verified against source are marked **✓ verified**.

---

## Remediation status

Remediation was carried out on branch **`audit-fixes`** (off `main`). Every Critical, High, and Medium finding was addressed except **H9** (deferred — see below), plus the schema-truth Low **L18** and dependency Low **L17**. One fix per commit; finding IDs appear in each commit message. Test status after remediation: **backend 299 passed / 0 failed** (includes the live-DB integration tests); **frontend 187 passed / 7 failed** — the 7 failures are pre-existing (unrelated `sprint9` realtime hook tests) and are unchanged by this work.

**⚠ Database migrations are committed but NOT yet applied to the live project.** The RLS/grant fixes ship as SQL migrations under `supabase/migrations/` and must be applied at deploy time (Supabase SQL editor or `psql`), in this order:
`20260706000001` (H2), `20260706000002` (H3), `20260706000003` (M3), `20260707000001` (M2). Each carries verification queries. `schema.sql` already reflects their post-apply state.

| ID | Severity | Status | Commit / note |
|----|----------|--------|---------------|
| C1 | Critical | ✅ Fixed | `9ac46ae` — signed/bound OAuth `state` |
| H1 | High | ✅ Fixed | `6fdf185` — protocol-allowlist `video_call_link` (server+client) |
| H2 | High | ✅ Fixed | `8411024` — scope `realtime.messages` (migration `20260706000001`) |
| H3 | High | ✅ Fixed | `8b67d1c` — `WITH CHECK` + column grant (migration `20260706000002`) |
| H4 | High | ✅ Fixed | `228f46b` — login OAuth state bound to browser session |
| H5 | High | ✅ Fixed | `66f7240` — lower bound on stale-slot deletion |
| H6 | High | ✅ Fixed | `a0e6294` — `proposals_needs_regeneration` on sync |
| H7 | High | ✅ Fixed | `0163382` — returning-user lookup via profiles, not paging |
| H8 | High | ✅ Fixed | `20c543f` — atomic claim before provider writes |
| H9 | High | ⏸ Deferred | Next.js 14→16 is a two-major upgrade; out of scope for this security pass — track as a dedicated framework-upgrade effort (also clears the transitive `postcss` XSS). |
| H10 | High | ✅ Fixed | `33f39d0` — `npm audit fix` (`ws`, `qs`) |
| H11 | High | ✅ Fixed | `3effeea` — drop mass-assignable `status` from `EventUpdate` |
| M1 | Medium | ✅ Fixed | `33773bd` — nullable `coordinator_id` |
| M2 | Medium | ✅ Fixed | `c28ab6f` — self-delete RLS policy (migration `20260707000001`) |
| M3 | Medium | ✅ Fixed | `b58fedf` — revoke `clear_write_calendar_for_user` (migration `20260706000003`) |
| M4 | Medium | ✅ Fixed | `2d15652` — JWT via HttpOnly cookie, not URL |
| M5 | Medium | ✅ Fixed | `2d15652` — JWT off `localStorage` |
| M6 | Medium | ◑ Partially fixed | `e0a70f0` — credential-clobbering closed via compare-and-swap on the refresh token at both write sites. **Deferred:** per-account sync serialization (advisory lock / claim flag) — an invasive schema + control-flow change to the calendar-sync integrity path; warrants explicit sign-off per the repo safety rule. H5 already mitigates the overlapping-delete effect. |
| M7 | Medium | ✅ Fixed | `910bb7f` — Google `list_calendars` raises instead of returning `[]` |
| M8 | Medium | ✅ Fixed | `8e90a41` — clamp wrap-around candidates to window |
| M9 | Medium | ✅ Fixed | `8e90a41` — explicit `reference_time_utc` (determinism restored) |
| M10 | Medium | ✅ Fixed | `a0e6294` — regeneration flag on preferred-slot delete |
| M11 | Medium | ✅ Fixed | `cf30c71` — lowercase in `normalize_email` |
| M12 | Medium | ✅ Fixed | `156398d` — `python-jose` 3.5.0, `fastapi`/`starlette` bump |
| M13 | Medium | ✅ Fixed | `56b2180` — static OAuth-exchange error detail |
| M14 | Medium | ✅ Fixed | `32dad1b` — `EmailStr` + recipient cap on finalize |
| M15 | Medium | ✅ Fixed | `c3293f8` — proposal-notes check moved to service; 404 |
| M16 | Medium | ✅ Fixed | `14e4c26` — align `notification_type` (enum/model/docs) |
| M17 | Medium | ✅ Fixed | `2d15652` — cookie set server-side HttpOnly+Secure |
| L1 | Low | ✅ Fixed (incidental) | `20c543f` — `finalized_at` now populated on finalize |
| L17 | Low | ✅ Fixed | `33f39d0` — dev-tree advisories cleared |
| L18 | Low | ✅ Fixed | `53b74e1` — `DATA_MODEL.md` reconciled to live schema (foundation: `a015cd3` reconciled `schema.sql` to live) |
| L2–L16, L19, L20 | Low | ⏸ Deferred | Out of scope for this pass (posture/consistency items). L10 — the systemic `service_client`/RLS posture — is the largest structural follow-up and is best addressed incrementally. |

---

## CRITICAL

### C1. OAuth calendar-connect trusts unsigned `state` as `user_id` — cross-user account linking ✓ verified · ⨯2 streams
- **Files:** `backend/app/routers/calendar_accounts.py:32,51-52,70-93`; `backend/app/providers/google.py:58`; `backend/app/services/calendar_service.py` (`connect_account`)
- **Category:** security
- **What:** `connect_url` sets `state=current_user.id`. Both OAuth callbacks (`google_calendar_callback`, `microsoft_calendar_callback`) have **no** `Depends(get_current_user)` and pass the raw `state` straight into `calendar_service.connect_account(user_id=state, ...)`. The Google provider actively disables oauthlib's built-in CSRF check via `object.__setattr__(flow, "_state", state)`. There is no HMAC/signature/session binding anywhere (grep for `hmac|sign|nonce|csrf|state_store` returns nothing).
- **Impact:** A victim's `user_id` is a UUID routinely exposed to co-participants (participant lists, `inviter_id`, busy-slot rows, JWT `sub`). An attacker completes OAuth consent with *their own* Google/Microsoft account but sets `state=<victim_id>`, attaching the attacker's calendar to the victim's account. This pollutes the victim's availability and — if the victim has no write calendar yet — can route the victim's finalized events onto the attacker's calendar. `service_role` writes bypass the `calendar_accounts_own` RLS policy, so RLS provides no backstop.
- **Fix:** Carry `user_id` in a short-lived signed/HMAC `state` (or a server-side random-state→user map) and verify it in the callback; never trust the raw value, and do not override oauthlib's state validation.
- **Note:** The *login* OAuth callback (`routers/auth.py`) is a distinct flow that derives identity from the exchanged `code`, not `state` — see H5 for its separate (different) CSRF gap.

---

## HIGH

### H1. Stored XSS via `video_call_link` href + `localStorage` JWT → account-takeover chain ✓ verified
- **Files:** `frontend/app/events/[uid]/EventDetailClient.tsx:662` (sink); `backend/app/models/event.py:19` (no server-side validation); `frontend/lib/api.ts:9`, `frontend/stores/authStore.ts:26` (token in `localStorage`)
- **Category:** security
- **What:** `event.video_call_link` (user-supplied by the coordinator) is rendered directly into `href={event.video_call_link}` with no protocol allowlist, so a `javascript:` URL executes on click. The only validation is client-side Zod `z.string().url()`, which accepts `javascript:...` and is not a security boundary; the backend stores the field as a bare `str`. React 18 renders `javascript:` hrefs (warns only). Because the session JWT lives in `localStorage`, the executing script can exfiltrate it → full account takeover.
- **Impact:** Any participant who opens a confirmed event and clicks "Join video call" runs attacker JS in their origin and leaks their session token.
- **Fix:** Render the link only if it starts with `http://`/`https://` (protocol allowlist), else show plain text; add the same validation server-side on `EventCreate`/`EventUpdate`. Separately, move the session token to an HttpOnly, Secure cookie (see M6).

### H2. `realtime.messages` broadcast policies are open to every authenticated user — cross-user data exposure ✓ verified
- **File:** `schema.sql:1183-1187`
- **Category:** security
- **What:** `CREATE POLICY "authenticated can receive broadcasts" ON realtime.messages FOR SELECT TO authenticated USING (true);` (and the matching INSERT `WITH CHECK (true)`). The frontend subscribes with the public anon key, so any logged-in user can subscribe to any topic (`user:<uuid>:notifications`, `event:<id>`, `...:busy_slots`, `...:preferred_slots`) and receive full-row payloads — all these tables are `REPLICA IDENTITY FULL`, so the broadcast carries complete rows. This bypasses the per-table SELECT RLS entirely.
- **Impact:** Cross-user leak of another user's notifications, event details, busy slots, and preferred slots in real time.
- **Fix:** Scope the `realtime.messages` policies to topic ownership (match `realtime.topic()` against `auth.uid()` / event membership) instead of `true`.

### H3. `event_participants_update_self` has no `WITH CHECK` — self-escalation of `can_invite` ✓ verified
- **File:** `schema.sql:1048`
- **Category:** security
- **What:** `FOR UPDATE USING (user_id = auth.uid())` with no `WITH CHECK` and no column restriction. A participant hitting Supabase directly with the anon key + their own JWT can set `can_invite = true` on their own row; `event_invitations_insert` then permits them to invite arbitrary emails, bypassing the coordinator control that the backend's `participant_service.update_permissions` (coordinator-only) enforces.
- **Impact:** Any participant can grant themselves invite rights and invite arbitrary people to an event they don't coordinate. RLS is the only enforcement layer for a direct-to-Supabase client, and it fails here.
- **Fix:** Split the policy so self-update only permits `rsvp_status`/`status`, or add a trigger/column grant preventing self-escalation of `can_invite`.

### H4. Login OAuth flow uses constant `state="stateless"` — no CSRF protection ✓ verified
- **Files:** `backend/app/services/auth_service.py:39-47`; `backend/app/routers/auth.py:19`
- **Category:** security
- **What:** `get_authorization_url` hard-codes `state="stateless"`; `exchange_code_and_upsert_user` forces `flow._state = state` and sets `flow.oauth2session.scope = None` (also disabling scope validation); `google_callback` defaults `state="stateless"` and never checks it.
- **Impact:** Login CSRF / session fixation — an attacker can initiate an auth flow and complete it in a victim's browser with no state binding to detect it.
- **Fix:** Generate a random `state` bound to the browser session and verify it in the callback before exchanging the code; don't null out scope validation.

### H5. Event-scoped sync deletes busy slots with no lower time bound — wipes weeks of availability ✓ verified
- **File:** `backend/app/services/sync_service.py:233-253`
- **Category:** bug
- **What:** In `_sync_source`, the stale-slot query filters only `end_time_utc < time_max` with **no** `.gte("end_time_utc", time_min)`. A narrow event-scoped sync (`routers/busy_slots.py` → `sync_event_participants_scoped`, passing the event's own `earliest/latest` window) fetches provider events only in `[time_min, time_max]`, but then treats *every* stored slot ending before `time_max` and not in this call's fetch set as stale and deletes it.
- **Impact:** A 2-hour scoped sync for a future event wipes weeks of previously-synced busy data — corrupting the exact input the scheduler reads, producing wrong proposals.
- **Fix:** Add `.gte("end_time_utc", time_min.isoformat())` so only slots inside the fetched window are eligible for staleness deletion.

### H6. Busy-slot sync never sets `proposals_needs_regeneration` — stale proposals served
- **File:** `backend/app/services/sync_service.py:224`
- **Category:** bug
- **What:** After upserting/deleting busy slots, `_sync_source` never flags affected events with `proposals_needs_regeneration = true`. `routers/proposals.py` serves cached proposals whenever the flag is false, and no DB trigger sets it (all busy_slots/preferred_slots triggers in `schema.sql` are broadcast-only). The flag is set only in `event_service.update_event` and `preferred_slots_service.create_preferred_slot`.
- **Impact:** After a sync changes availability, proposals remain stale until an unrelated write flips the flag — the scheduler's output silently lags its inputs. (The DATA_MODEL staleness rule requires this propagation.)
- **Fix:** After slot writes, set the flag on events whose participants' slots changed, mirroring `create_preferred_slot`.

### H7. `_upsert_profile` returning-user fallback has a pagination gap — breaks logins at scale
- **File:** `backend/app/services/auth_service.py:97-109`
- **Category:** bug
- **What:** The "user already exists" branch first calls `service_client.auth.admin.list_users()` with no args (library default page size, ~50), then the fallback loop starts at `page = 2` with `per_page=1000` (covering indices ~1001–2000). Auth users at indices ~51–1000 are never scanned, so `list_users` finds no match and the code raises 500.
- **Impact:** This branch runs on **every returning login** (admin `create_user` raises on duplicate email). Once the user base grows past the first page (~50 users), returning users at those indices can no longer log in.
- **Fix:** Paginate consistently from page 1 with a fixed `per_page`, or look the user up by email via the admin API instead of listing all users.

### H8. Finalization is a check-then-act with no lock — duplicate calendar events, orphaned `calendar_event_id` ✓ verified · ⨯2 streams
- **File:** `backend/app/services/finalize_service.py:133,296-301`
- **Category:** bug
- **What:** Line 133 reads `event["status"]` and rejects if `== "confirmed"`, but the confirming update at 296-301 is `.update(...).eq("id", event["id"])` with **no** status guard, and there is no status-transition trigger or partial-unique constraint in `schema.sql`. Two concurrent finalize requests (coordinator double-click / retry) both pass the guard, both create calendar events on the coordinator's and every participant's write calendar, and both insert `event_finalized` notifications; the second update overwrites `calendar_event_id`, orphaning the first external calendar event. The race window spans the slow external Google/MS API calls.
- **Impact:** Duplicate external calendar events and notifications; the app loses track of one of the created provider events. Directly violates the calendar-sync-integrity invariant.
- **Fix:** Claim the event atomically first — `UPDATE events SET status='confirmed' WHERE id=? AND status='planning'` — and only proceed to provider writes if a row was claimed (optimistic lock).

### H9. `next@14.2.35` — multiple High-severity advisories ✓ verified (npm audit)
- **File:** `frontend/package.json:24`
- **Category:** security
- **What:** Two majors behind. Carries High advisories: App Router CSP-nonce XSS (GHSA-ffhc-5mcf-pf4q), SSRF via WebSocket upgrades (GHSA-c4j6-fc7j-m34r), RSC cache poisoning, image-optimization DoS, and a middleware/proxy bypass. `npm audit` reports the fix only in `next@16.x`.
- **Impact:** Multiple network-reachable High-severity issues in the shipped web framework.
- **Fix:** Plan the upgrade to Next 16.x (also clears the transitive `postcss <8.5.10` XSS).

### H10. Transitive `ws@8.0.0–8.20.1` in the production tree — memory disclosure + DoS ✓ verified (npm audit)
- **File:** `frontend/package.json` (transitive)
- **Category:** security
- **What:** Uninitialized-memory disclosure (GHSA-58qx-3vcg-4xpx) and fragment-based DoS (GHSA-96hv-2xvq-fx4p). Non-breaking fix available.
- **Impact:** Exploitable in the production dependency tree.
- **Fix:** `npm audit fix` (bumps `ws`; also clears the prod-tree `qs@6.11.1–6.15.1` moderate DoS).

### H11. `EventUpdate.status` is mass-assignable — bypasses the finalize state machine ✓ verified
- **Files:** `backend/app/models/event.py:31`; `backend/app/services/event_service.py:229,244`
- **Category:** bug
- **What:** `EventUpdate` exposes `status`, and `update_event` applies `data.model_dump(exclude_none=True)` straight onto the row with no field allowlist. A coordinator can `PATCH /api/events/{uid}` with `status:"confirmed"`, marking the event confirmed while `finalized_start/end_time_utc` and `calendar_event_id` stay null and no calendar event is ever written.
- **Impact:** An event can be "confirmed" without going through coordinator finalization, leaving downstream calendar/notification state inconsistent. (Coordinator-only + RLS-scoped, so not cross-user — but it defeats the finalize invariant.)
- **Fix:** Drop `status` from `EventUpdate` (or strip it in `update_event`); route status changes only through finalize/cancel logic.

---

## MEDIUM

### M1. `EventResponse.coordinator_id` is non-nullable but the column is nullable — 500 on anonymized events ✓ verified
- **Files:** `backend/app/models/event.py` (`EventResponse.coordinator_id: str`); `schema.sql:538,934-935`; `backend/app/services/account_service.py:56-58`
- **Category:** bug
- **What:** The column is nullable with `ON DELETE SET NULL`, and `account_service.delete_account` sets `coordinator_id = NULL` for confirmed/cancelled events; but the Pydantic response model requires a non-null `str`. Fetching such an event (still visible to participants) makes `_row_to_event_response` construct `EventResponse(coordinator_id=None)` → Pydantic ValidationError → 500.
- **Fix:** Make it `coordinator_id: str | None`.

### M2. Non-coordinator "leave event" is silently broken — no matching RLS DELETE policy
- **Files:** `backend/app/services/participant_service.py:82-93`; `schema.sql:1032-1034`
- **Category:** bug
- **What:** `remove_participant` allows self-removal via the RLS (authed) client, but the only DELETE policy `event_participants_delete` permits the coordinator only. A non-coordinator "leave event" matches zero rows and silently raises 404.
- **Fix:** Add an RLS DELETE policy allowing `user_id = auth.uid()`, or route self-removal through `service_client`.

### M3. `clear_write_calendar_for_user` is `SECURITY DEFINER` and granted to `anon`/`authenticated` ✓ verified
- **File:** `schema.sql:234-243`, grants at `1379-1381`
- **Category:** security
- **What:** Takes an arbitrary `p_user_id`, runs as definer (bypassing RLS), and is `GRANT ALL ... TO anon, authenticated`, so any user can call it via PostgREST RPC to clear another user's write-calendar flags. It is dead code (no `.rpc` call in the backend); the real invariant is enforced by the `enforce_single_write_calendar` trigger.
- **Fix:** `REVOKE` from `anon`/`authenticated` (or drop the function).

### M4. Session JWT delivered as a URL query parameter ✓ verified · ⨯2 streams
- **Files:** `backend/app/routers/auth.py:21`; `frontend/app/auth/callback/page.tsx:17`
- **Category:** security
- **What:** After login the backend redirects to `/auth/callback?token=...` (a 7-day JWT). Tokens in URLs leak into browser history, `Referer` headers, and access logs. (`frontend_url` is a fixed setting, so there's no open-redirect — the issue is purely token-in-URL exposure.)
- **Fix:** Deliver the token via a short-lived one-time code exchanged by the SPA, or set it as a `Secure; HttpOnly` cookie instead of a query string.

### M5. Session JWT stored in `localStorage` / JS-readable cookie ✓ verified
- **Files:** `frontend/lib/api.ts:9`; `frontend/lib/supabase.ts:23`; `frontend/stores/authStore.ts:26`; `frontend/app/auth/callback/page.tsx:25`
- **Category:** security
- **What:** The token is read from `localStorage` (and a JS-readable cookie) everywhere, so any XSS in the origin can exfiltrate it — this is what turns H1 into full account takeover.
- **Fix:** Move the session token to an HttpOnly, Secure cookie set by the backend.

### M6. No concurrency guard around per-account sync — slot loss and credential clobbering ✓ verified (interleaving) · ⨯2 streams
- **Files:** `backend/app/services/sync_service.py:111-123,224-253`; `backend/app/services/finalize_service.py:76`; `backend/app/providers/microsoft.py:201-209`
- **Category:** bug
- **What:** `sync_busy_slots` runs both synchronously inside the OAuth connect callback and hourly via APScheduler, and a narrow per-event participant sync can overlap the wide 90-day sync for the same source. Two effects: (a) overlapping syncs compute stale-slot deletion from their own fetch sets and can delete slots a concurrent wider sync just wrote; (b) `_persist_account_after_sync` and `finalize_service` both do unconditional `.update({"credentials": ...})`, and Microsoft rotates its refresh token on every refresh — so last-writer-wins can persist a consumed/stale token, forcing a needless `needs_reauth`.
- **Fix:** Serialize per-account sync with a Postgres advisory lock (or a `syncing` flag) and use a conditional credentials update so refresh/rotate/persist is atomic.

### M7. Google `list_calendars` swallows all non-auth exceptions and returns `[]` — silent failed connect ✓ verified
- **File:** `backend/app/providers/google.py:81-83`
- **Category:** bug
- **What:** Google catches `Exception` and returns `[]`, diverging from Microsoft (which raises). In `connect_account`, an empty list means no source rows and no write-calendar designation, yet no exception propagates, so `_complete_connect` redirects `connected=true`. Finalize later fails with `no_write_calendar`.
- **Impact:** A transient failure during connect leaves the account saved with zero sources and no write calendar while the user is told the connection succeeded.
- **Fix:** Raise `ProviderAPIError` on unexpected list failures (matching Microsoft) so `_complete_connect` reports `calendar_save_failed`.

### M8. Wrap-around (overnight) windows can propose times outside the requested range ✓ verified
- **File:** `backend/app/services/proposal_service.py:138`
- **Category:** bug
- **What:** In `_build_day_candidates`, for wrap-around windows the last day still emits its evening `seg1 = [start_hour, next_midnight)`, which lies entirely after `latest_datetime_utc`, and nothing clamps candidates to `latest_dt`. Example: window Jul6 20:00→Jul10 03:00 UTC yields spurious Jul10 20:00–24:00 candidates.
- **Fix:** On `is_last`, skip/clamp `seg1` for wrap windows, or filter all candidates to `<= latest_dt`.

### M9. `datetime.now(timezone.utc)` clamp in candidate generation — determinism violation
- **File:** `backend/app/services/proposal_service.py:107,137,142,155`
- **Category:** pattern-violation
- **What:** `_build_day_candidates` clamps candidates to "now", so the same event produces a different candidate set over time. The scoring/sort is otherwise fully deterministic (unique `start` breaks ties, counts use sets, Python sort is stable) — this wall-clock dependency is the sole determinism break, and it violates the invariant even though the intent ("no past slots") is reasonable.
- **Fix:** Pass a caller-supplied reference time (or persist the generation instant) so output is a pure function of inputs; make past-filtering an explicit, testable parameter.

### M10. `delete_preferred_slot` doesn't set `proposals_needs_regeneration` (asymmetric with create) ✓ verified
- **File:** `backend/app/services/preferred_slots_service.py:93`
- **Category:** bug
- **What:** `create_preferred_slot` sets the regeneration flag; `delete_preferred_slot` does not, and no DB trigger compensates. Removing a preferred slot leaves stale proposals cached. (Same class as H6.)
- **Fix:** Set the flag on the event after deletion, symmetric with create.

### M11. `normalize_email` never lowercases — mixed-case invites fail to link on signup ✓ verified
- **File:** `backend/app/utils/email.py:9`
- **Category:** bug
- **What:** `normalize_email` strips Gmail dots but preserves original case, while invite matching uses exact `eq` on the address in both `invitation_service.invite_by_email` and `auth_service._process_pending_invitations`. A mixed-case invited address (e.g. `John.Smith@Gmail.com`) won't match the canonical lowercase provider email.
- **Impact:** A pending invite silently never links when the invitee signs up, so they don't get added to the event.
- **Fix:** Lowercase the address (at minimum the domain; practically the whole string) during normalization.

### M12. `python-jose==3.3.0` and `starlette==0.37.2` — known CVEs ✓ verified (pip list)
- **File:** `backend/requirements.txt`
- **Category:** security
- **What:** `python-jose 3.3.0` — CVE-2024-33663 (algorithm confusion) and CVE-2024-33664 (JWE decompression-bomb DoS), fixed in 3.4.0. Real-world exposure is reduced (decoding is pinned to `algorithms=[HS256]` and the app never parses JWE), but the pin is vulnerable. `starlette 0.37.2` (via `fastapi==0.111.0`) — CVE-2024-47874 (unbounded multipart memory DoS), fixed in 0.40.0. (`python-multipart 0.0.22` is **not** vulnerable.)
- **Fix:** Bump `python-jose>=3.4.0`; bump FastAPI to a release requiring `starlette>=0.40`.

### M13. Login OAuth error path returns the raw exception to the client ✓ verified · ⨯2 streams
- **File:** `backend/app/services/auth_service.py:64`
- **Category:** security
- **What:** `raise HTTPException(status_code=400, detail=f"Failed to exchange OAuth code: {exc}")` leaks internals of the OAuth exchange (library internals, upstream Google error bodies, possibly URLs) to the client. The calendar-connect path handles the same case correctly with a generic redirect error.
- **Fix:** Log `exc` server-side (already done) and return a static detail such as `"oauth_exchange_failed"`.

### M14. `FinalizeRequest.extra_emails` is unbounded and unvalidated — fan-out/spam vector ✓ verified
- **Files:** `backend/app/models/slot.py:44`; `backend/app/services/finalize_service.py:224-227`
- **Category:** security
- **What:** `extra_emails: list[str]` uses plain `str` (not `EmailStr`) with no `max_length`. Each entry becomes a calendar attendee, so the provider emails every address — a coordinator can pass thousands of arbitrary/invalid addresses. (The single-invite path correctly uses `EmailStr`.)
- **Fix:** Type as `list[EmailStr]` with `Field(max_length=...)`; apply the same cap to `excluded_user_ids`.

### M15. `proposal_notes.py` router uses `service_client` + direct Supabase + business logic ✓ verified · ⨯2 streams
- **File:** `backend/app/routers/proposal_notes.py:8,13-23`
- **Category:** pattern-violation
- **What:** The router itself imports `service_client` (RLS-bypassing), runs a direct Supabase query in `_check_proposed_time_belongs_to_event`, and `raise Exception(...)` on not-found (surfaces as a 500 rather than 404) — three explicit rule violations. Authorization itself is sound (`get_event_and_check_access` runs first on every endpoint), so this is a discipline/consistency issue, not an access hole.
- **Fix:** Move the belongs-to-event check into a service and raise `HTTPException(404)` there; remove `service_client` from the router.

### M16. Three-way `notification_type` drift (DB enum vs Pydantic vs docs) ✓ verified
- **Files:** `backend/app/models/notification.py`; `schema.sql:85-91`; `docs/DATA_MODEL.md:203-207`
- **Category:** bug
- **What:** The DB enum has 5 values including `event_time_changed` and `invite_accepted`; the Pydantic `NotificationResponse` Literal omits `event_time_changed` (would 500 if such a row is fetched); DATA_MODEL omits `invite_accepted`. Currently latent (no code writes `event_time_changed`).
- **Fix:** Align all three — add `event_time_changed` to the model and `invite_accepted` to the doc, or drop the unused enum value.

### M17. Cookie set without `Secure` flag ✓ verified
- **Files:** `frontend/stores/authStore.ts:15`; `frontend/app/auth/callback/page.tsx:27`
- **Category:** security
- **What:** The `token` cookie is set client-side with `SameSite=Lax` but no `Secure`, so on HTTPS it can still be sent over a plaintext downgrade.
- **Fix:** Add `Secure` (and ideally set it server-side as HttpOnly — see M5).

---

## LOW

### L1. `finalized_at` is never populated on finalize
- **File:** `backend/app/services/finalize_service.py:285-292`; column at `schema.sql:552`
- **Category:** bug — the update payload omits `finalized_at`, the column is nullable with no default and no trigger, so it stays null after confirmation (DATA_MODEL says it's set when confirmed). **Fix:** add `"finalized_at": <now-iso>` to the payload.

### L2. Availability intensity counts overlapping slots, not distinct users
- **File:** `backend/app/services/availability_service.py:69`
- **Category:** bug — `bc`/`pc` sum intervals (one row per calendar event) rather than deduping by `user_id`, inflating "participants busy/preferring" counts. Display-grid only, not the proposal path. **Fix:** dedupe by `user_id` as `proposal_service` does.

### L3. `OAUTHLIB_INSECURE_TRANSPORT=1` set unconditionally at import
- **File:** `backend/app/main.py:28`
- **Category:** security — disables HTTPS enforcement on OAuth redirects in every environment, not just local dev, despite the "for local development" comment. **Fix:** gate on an explicit dev/debug env flag.

### L4. Divergent naive-datetime parsing in `sync_event_participants_scoped`
- **File:** `backend/app/services/sync_service.py:139-140`
- **Category:** bug — parses event bounds with `datetime.fromisoformat(...).astimezone(timezone.utc)`, which misreads a tz-naive timestamp as server-local, inconsistent with the `_parse_iso_utc` helper used elsewhere in the file. Latent boundary bug. **Fix:** use `_parse_iso_utc`.

### L5. No 429 / `Retry-After` / backoff handling in either provider
- **Files:** `backend/app/providers/google.py`, `backend/app/providers/microsoft.py`
- **Category:** bug — the hourly all-user sync can hit rate limits and either silently skip sources (Google) or raise (Microsoft). **Fix:** honor `Retry-After` with bounded exponential backoff on 429/503.

### L6. Duplicate-invitation check-then-act with no unique constraint
- **File:** `backend/app/services/invitation_service.py:72-107`; `schema.sql` (no `(event_id, invitee_email)` unique)
- **Category:** bug — concurrent `invite_by_email` calls can both insert; the notifications partial index blocks the second notification for registered users (500) but the duplicate invitation row persists, and email-only invites have no guard. **Fix:** add a partial-unique index on pending invitations per `(event_id, invitee_email)` and upsert/ignore on conflict.

### L7. `is_event_participant` is a `SECURITY DEFINER` participation oracle
- **File:** `schema.sql:346-354`, grants `1403-1405`
- **Category:** security — granted to `authenticated`, so a user can probe arbitrary `(event_id, user_id)` pairs as a boolean. Must stay callable for the RLS policies that use it, so impact is minor. **Fix:** accept as-is, or restrict direct EXECUTE while keeping it usable inside policies.

### L8. Duplicate identical SELECT policies on `notifications`
- **File:** `schema.sql:1076,1079`
- **Category:** pattern-violation — `"Users can only read own notifications"` and `notifications_select_own` have the same predicate. **Fix:** drop the legacy one.

### L9. Services raise `HTTPException` throughout (routers-only rule)
- **Files:** `event_service`, `participant_service`, `invitation_service`, `finalize_service`, `proposal_service`, `preferred_slots_service`, `proposal_notes_service`, `calendar_service`, `notification_service`, `auth_service`
- **Category:** pattern-violation — systemic; couples the service layer to FastAPI (`backend.md` says services should raise domain errors). Functional and consistent. **Fix:** introduce domain exceptions mapped to HTTP in routers (larger refactor).

### L10. `service_client` (RLS-bypassing) used well outside the documented allowlist
- **Files:** `event_service`, `finalize_service`, `proposal_service`, `sync_service`, `calendar_service`, `account_service`, `busy_slots_service`, `preferred_slots_service`, `proposal_notes_service`, `availability_service`, `dependencies.py`
- **Category:** pattern-violation — flagged by three streams. Each use is paired with a manual ownership check (no active cross-user leak found), but it means RLS is not the enforcement layer, so any missed check has no backstop (see H2/H3 for where that matters). **Fix:** prefer the authed client where feasible for defense-in-depth; keep `service_client` to the sanctioned services.

### L11. `get_current_user` performs a `service_client` profile lookup inside the auth dependency
- **File:** `backend/app/dependencies.py:29`
- **Category:** pattern-violation — data access in `dependencies.py` (rules say no business logic there). Reasonable for identity resolution; JWT decode is sound (HS256, signature/exp verified). **Fix:** move the profile fetch behind an `auth_service` call if strict adherence is desired.

### L12. Empty dead file `routers/finalization.py`
- **File:** `backend/app/routers/finalization.py`
- **Category:** pattern-violation — 0 bytes, not imported/registered (only `finalize.py` is active). The "duplication" is benign. **Fix:** delete it.

### L13. Unbounded list endpoints (no pagination/limit)
- **Files:** `routers/notifications.py`, `routers/events.py`, `routers/busy_slots.py` list endpoints
- **Category:** pattern-violation — return all of the caller's rows. Scoped to the caller's own data (low risk) but grows unbounded over time. **Fix:** add a bounded `limit`/cursor.

### L14. Widespread `new Date(...)` outside `lib/dates.ts`
- **Files:** `frontend/app/events/new/page.tsx:38-39`, `components/event/wizard/Step2.tsx:47-48`, ~20 sites
- **Category:** pattern-violation — most hits merely parse UTC ISO strings for geometry (equivalent to the sanctioned `toDate()`); a few deliberately build local-time from wall-clock input (intentional). `lib/dates.ts` itself uses `new Date()`, so the rule is only loosely enforceable. No correctness bug found. **Fix:** optionally route through `lib/dates.ts` for consistency.

### L15. Dead `fetchEvent` uses raw `fetch()` (bypasses `lib/api.ts`)
- **File:** `frontend/app/events/[uid]/fetchers.ts:3-11`
- **Category:** pattern-violation — exported but never imported. **Fix:** delete it (or, if a server-side fetch is intended, note `lib/api.ts` is client-only and document the exception).

### L16. Outdated/unmaintained Python deps: `ecdsa`, `passlib`
- **File:** `backend/requirements.txt`
- **Category:** pattern — `ecdsa==0.19.2` (CVE-2024-23342 Minerva timing; maintainer "won't fix", not on the hot path since jose signs via `cryptography`), `passlib==1.7.4` (unmaintained since 2020). **Fix:** monitor; migrate off `passlib` if practical.

### L17. Dev-only frontend advisories
- **File:** `frontend/package.json` (dev tree)
- **Category:** pattern — `vite`, `undici`, `hono`, `fast-uri`, `glob`, `brace-expansion` (via vitest/eslint-config-next) carry High advisories but are not shipped to production. **Fix:** `npm audit fix` clears most.

### L18. `docs/DATA_MODEL.md` has not been reconciled against the live Supabase database
- **File:** `docs/DATA_MODEL.md:21-23`; missing `proposed_time_notes` section; `schema.sql` (comparison baseline used so far)
- **Category:** pattern-violation (doc)
- **What:** This audit compared `docs/DATA_MODEL.md` against `schema.sql` and found drift — three phantom `profiles` columns (`google_auth_token`, `microsoft_auth_token`, `google_calendar_id`) documented but absent from `schema.sql`, and a `proposed_time_notes` table present in `schema.sql` but undocumented. That comparison is only as good as its baseline: `schema.sql` is a checked-in, hand-reconciled snapshot, not a live read of the database, so it can itself have drifted from what's actually deployed. **This finding has not yet been re-verified against the live project.** Do that with the Supabase CLI before trusting either side of the diff:
  ```
  supabase link --project-ref <ref>
  supabase db dump --linked --schema public -f /tmp/live_schema.sql
  # or: supabase db diff --linked --schema public
  ```
  Then diff `/tmp/live_schema.sql` against both `schema.sql` and `docs/DATA_MODEL.md` — treat the live dump as ground truth for both.
- **Impact:** If `schema.sql` disagrees with the live database (e.g. a migration applied out-of-band, or a column dropped in the console but never reflected in the repo), fixing `DATA_MODEL.md` to match `schema.sql` would still leave the docs wrong. This also affects confidence in any other finding in this report that cites `schema.sql` as the schema/RLS source of truth (notably C1, H2, H3, M3) — those should be spot-checked against the live dump too, since they concern policies that are enforced by whatever is actually deployed, not by the file in the repo.
- **Fix:** Run the live-DB reconciliation above. If `schema.sql` matches the live project, proceed with the original fix (drop the phantom `profiles` columns from `DATA_MODEL.md`, add a `proposed_time_notes` section). If it doesn't match, first correct `schema.sql` (and any affected migration) to reflect the live project, then correct `DATA_MODEL.md` against the reconciled schema.

### L19. Calendar credentials stored as plaintext `jsonb`
- **File:** `schema.sql:473` (`calendar_accounts.credentials`)
- **Category:** security (posture) — plaintext OAuth tokens at rest, protected only by the `calendar_accounts_own` RLS policy. `DATA_MODEL.md` accurately describes it as plaintext (no false claim), and `pgcrypto`/`supabase_vault` are enabled but unused for this column. **Fix:** encryption-at-rest is a reasonable hardening follow-up, not a code/doc mismatch.

### L20. Presence-cookie route gating is forgeable (UX-only)
- **Files:** `frontend/middleware.ts`, server components
- **Category:** security (informational) — the middleware/server-component check reads a presence cookie that a client can forge, but it is only UX gating; real authorization is enforced by the backend on every data call, and a forged cookie fails fast at `/auth/me` → `clearAuth`. No fix required; noted for completeness.

---

## Areas verified clean

- **Auth coverage:** every non-OAuth, non-health endpoint injects `Depends(get_current_user)`; the only unauthenticated endpoints are the intended-public OAuth callbacks/login-start and `/health`.
- **CORS:** `allow_origins=[settings.frontend_url]` (single concrete origin) with credentials — no wildcard-with-credentials problem.
- **SQL injection:** no `.rpc()` with raw input and no f-string/`.format`/`%` query building in the backend; everything uses the parameterized PostgREST builder.
- **RLS enablement:** all 11 public tables have RLS enabled; the gaps above are policy-logic issues, not disabled RLS.
- **Schema fundamentals:** all timestamps are `timestamptz` (no naive columns); one-participant-per-event and other uniqueness constraints present; FK `ON DELETE` handling is complete; the one-write-calendar invariant is soundly enforced by the `enforce_single_write_calendar` trigger + CHECK constraint. (These conclusions are drawn from `schema.sql`, not a live Supabase CLI diff — see L18.)
- **Proposal ranking determinism:** the sort key `(conflict_count, -preferred_count, start)` is a total order; counts dedupe by user via sets; ranking is stable — the only nondeterminism is the `now` clamp (M9).
- **Token/secret hygiene:** no hardcoded secrets in tracked files (only `.example` placeholders); no tokens/PII in logs; `credentials` never serialized to the frontend; refresh/rotation implemented correctly per provider; JWT decode constrains `algorithms=[HS256]` (no `alg=none` bypass).
- **Frontend data layer:** all 15 hooks reviewed — every `useMutation` invalidates the correct query keys; realtime subscriptions live only in hooks and only invalidate caches (never mutate state); Zustand holds only auth + badge count (no server data); zero `any` on API boundaries; no `dangerouslySetInnerHTML`/`innerHTML`/unsanitized markdown; the `app/api/[...path]` proxy forwards to a fixed backend host (no SSRF) and delegates auth to the backend.
- **DB-guarded races:** double-accept of an invitation is prevented by the `event_participants` composite PK.

---

## Recommended remediation order

0. **L18** — reconcile `schema.sql`/`docs/DATA_MODEL.md` against the *live* Supabase project via CLI before acting on any schema/RLS finding below; if the live project disagrees with `schema.sql`, re-verify C1, H2, H3, and M3 against the live definitions first.
1. **C1** — sign/bind the OAuth `state` (cross-user account linking).
2. **H2, H3** — close the two client-reachable RLS holes (realtime broadcasts, participant self-update); these are exploitable with only the public anon key.
3. **H1 + M5** — protocol-allowlist the link sink and move the JWT off `localStorage`.
4. **H5, H4, H8, H11** — CSRF state on login, unbounded stale-slot deletion, finalize optimistic lock, mass-assignable status.
5. **H6, H7** — proposal-regeneration propagation and the login-breaking pagination bug.
6. **H9, H10, M12** — dependency upgrades (Next.js, `ws`, `python-jose`/`starlette`).
7. Medium/Low items as capacity allows; the systemic `service_client`/RLS posture (L10) is the largest structural item and is best addressed incrementally alongside H2/H3.
