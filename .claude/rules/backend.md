# Backend Rules — When. v2

## Core principle

Backend is the **single source of truth for business logic**.

FastAPI = thin transport layer
Services = all logic
Supabase = persistence layer

---

## Structure rules

### Routers

* Must only:

  * parse input
  * call service
  * return response
* Never contain business logic

### Services

* All business logic lives here
* Must be stateless
* Must not depend on FastAPI internals

### Models

* Pydantic v2 only
* Must mirror Supabase schema exactly

---

## Supabase rules

### Client usage

* `anon_client`

  * default
  * respects RLS

* `service_client`

  * ONLY allowed in:

    * auth_service
    * invitation_service
    * notification_service
    * scheduler/jobs
  * NEVER used in routers

---

## Data rules

* All timestamps UTC
* Never store local time
* Never convert time in services (only in utils/dates.py)
* Always validate UUIDs and event ownership

---

## Scheduling system (critical)

* Must remain deterministic
* No external APIs
* No ML/LLM usage
* No randomness

Any change must preserve:

* same input → same output
* ordering stability
* scoring rules

---

## Calendar integration

* All Google/Microsoft API calls must go through:

  * `calendar_service.py`
* Never call external APIs from routers
* OAuth token handling only in auth/calendar services

---

## Real-time + sync

* Supabase realtime is read-only signal layer
* Never treat realtime as source of truth
* Always re-fetch authoritative data after events

---

## Error handling

* Use HTTPException only in routers
* Services should raise domain errors or return Result objects
* 401 / 403 must be explicit and consistent

---

## Anti-patterns

* No ORM (SQLAlchemy / Prisma)
* No direct Supabase calls in routers
* No business logic in dependencies.py
* No hidden side effects in models

---

## Testing expectations

* Every service must be unit-testable
* External APIs must be mocked
* No real Supabase calls in tests
