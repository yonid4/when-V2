# Design Reference

These files are the visual source of truth for the frontend.
They are Stitch-generated HTML using Tailwind + Material Symbols.
Do not run them as-is. Use them as pixel-perfect references only.

## File map
- landing.html → app/page.tsx
- dashboard.png → app/dashboard/page.tsx
- create-step1.html → app/events/new/page.tsx (step 1)
- create-step2.html → app/events/new/page.tsx (step 2)
- create-step3.html → app/events/new/page.tsx (step 3)
- event-detail.html → app/events/[uid]/page.tsx
- settings.html → app/settings/page.tsx

## Design system
Read DESIGN.md before building any component.
Key rules:
- Primary color: #9b4428 (terracotta)
- Fonts: Plus Jakarta Sans (headlines) + Be Vietnam Pro (body)
- No 1px borders — use background shifts for separation
- Rounded corners everywhere, minimum 0.5rem
- Shadows tinted with primary color, never gray
- Status chips: planning=gray, confirmed=green, cancelled=red