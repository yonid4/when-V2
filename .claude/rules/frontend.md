# Frontend Rules — When. v2

## Core principle

Frontend is a **presentation + orchestration layer only**.

It does NOT own business logic.

---

## Architecture rules

### Server Components

* Use for data fetching
* Must call backend directly
* Must not include client state

### Client Components

* Only for interactivity
* Must use hooks for all API access

---

## Data fetching rules

### NEVER

* call fetch directly in components
* bypass hooks
* duplicate API logic

### ALWAYS

* use TanStack Query hooks from `/hooks`
* invalidate queries after mutations

---

## State management

### Zustand allowed only for:

* auth state
* notification badge count
* transient UI state

### Forbidden:

* storing server data in Zustand
* duplicating API state

---

## API rules

* All requests go through `/lib/api.ts`
* Never use raw fetch in components
* JWT must be attached automatically

---

## Real-time rules

* Supabase subscriptions live ONLY in hooks
* Realtime events must:

  * invalidate TanStack Query cache
  * never mutate state directly

---

## UI rules

* shadcn/ui is the only component system
* No custom CSS files
* Tailwind only
* No direct DOM manipulation

---

## Date/time rules

* Never use `new Date()` in UI logic
* Always use `lib/dates.ts`
* Display always derived from UTC

---

## Type safety

* No `any`
* All API responses must match backend Pydantic models
* Types must live in `/types/index.ts`

---

## Testing rules

* Mock API layer (`lib/api`)
* Mock navigation (`next/navigation`)
* Never hit backend in tests

---

## Anti-patterns

* No business logic in components
* No duplicate query logic
* No inline fetch calls
* No state duplication between hooks and components
