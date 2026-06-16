# Ops & Workflow Rules — When. v2

## Purpose

Defines how Claude should behave during:

* development
* refactoring
* debugging
* git operations
* cross-file changes

---

## Git workflow (strict)

### Before any commit:

1. Identify logical change groups
2. Propose commit plan
3. Wait for approval

### Never:

* `git add .`
* auto-push
* combine unrelated changes

### Commit format:

```
<type>: <description>
```

---

## Change discipline

### Small changes preferred

Claude should:

* modify minimal surface area
* avoid sweeping refactors unless requested

---

## Cross-file changes

If modifying:

* backend logic → check services + routers + tests
* frontend logic → hooks + components + types
* schema change → MUST update:

  * DATA_MODEL.md
  * backend models
  * frontend types

---

## Debug workflow

1. Identify layer (frontend / backend / DB / sync)
2. Trace data flow:
   Supabase → backend → frontend
3. Validate schema mismatch first
4. Reproduce issue before fixing

---

## Refactoring rules

Only refactor when:

* duplication is real
* behavior is unchanged
* tests still pass

Never refactor:

* “for cleanliness”
* without functional reason

---

## Documentation rules

When making changes:

* update relevant docs immediately
* never leave docs outdated
* prefer updating docs over explaining in chat

---

## Safety rules

Do NOT:

* modify scheduling logic without explicit intent
* break RLS assumptions
* change calendar sync behavior silently

Always flag:

* cross-user data impact
* authentication changes
* schema modifications

---

## Performance mindset

Prefer:

* incremental changes
* reuse existing patterns
* minimal abstraction

Avoid:

* premature optimization
* new architecture layers
* unnecessary abstractions
