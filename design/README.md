# Design Reference

These files are the visual source of truth for the frontend.
They are Stitch-generated HTML using Tailwind + Material Symbols.
Do not run them as-is. Use them as pixel-perfect references only.

## File map

### HTML source files (pixel-perfect reference)
- landing.html → app/page.tsx
- create-step-1.html → app/events/new/page.tsx (step 1)
- create-step-2.html → app/events/new/page.tsx (step 2)
- create-step-3.html → app/events/new/page.tsx (step 3)
- event-details.html → app/events/[uid]/page.tsx
- settings.html → app/settings/page.tsx

### PNG screenshots (quick visual reference)
- landing.png → app/page.tsx
- dashboard.png → app/dashboard/page.tsx
- create-step-1.png → app/events/new/page.tsx (step 1)
- create-step-2.png → app/events/new/page.tsx (step 2)
- create-step-3.png → app/events/new/page.tsx (step 3)
- event-detail.png → app/events/[uid]/page.tsx (view mode)
- event-detail-edit.png → app/events/[uid]/page.tsx (edit mode)
- settings.png → app/settings/page.tsx

## Design system
Read DESIGN.md before building any component.
Key rules:
- Primary color: #9b4428 (terracotta)
- Fonts: Plus Jakarta Sans (headlines) + Be Vietnam Pro (body)
- No 1px borders — use background shifts for separation
- Rounded corners everywhere, minimum 0.5rem
- Shadows tinted with primary color, never gray
- Status chips: planning=gray, confirmed=green, cancelled=red