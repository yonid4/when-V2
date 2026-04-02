# Stitch Design Reference — When. v2

This file maps every design file in `design/` to the pages and components that should implement it. Claude Code must read this file and the relevant HTML files before building any frontend component.

> **Rule:** Never copy Stitch HTML directly into the Next.js codebase. Always rebuild using shadcn/ui primitives that match the visual output. Replace Material Symbols icons with lucide-react equivalents. All colors must come from CSS variables in `globals.css`, not hardcoded hex values.

---

## Design system foundation

**File:** `design/DESIGN.md`

Read this before touching any frontend file. It defines:
- Creative direction: "Tactile Hospitality" — warm, editorial, not corporate
- Color palette: Terracotta primary (`#9b4428`), warm earth tones throughout
- The "No-Line" rule: no 1px borders — use background shifts for separation
- Surface hierarchy: `surface` (base) → `surface-container-low` (cards) → `surface-container-lowest` (elevated/active)
- Typography: Plus Jakarta Sans (headlines) + Be Vietnam Pro (body)
- Elevation: tinted ambient shadows using a fraction of primary color, never gray
- Motion: `translate-y-[-4px]` hover lifts, `duration-500` ease-out transitions
- Component rules: buttons use primary-to-container gradient, inputs use high border-radius with no box border, status chips use soft fills

---

## Page → design file map

### Landing / Login
**Route:** `app/page.tsx`
**Design file:** `design/landing.html`

Key elements to replicate:
- Large "When." wordmark centered, terracotta color
- Tagline: "Find a time that works for everyone."
- Single "Sign in with Google" button with real Google SVG logo
- Stacked invitation card decoration below the button (purely visual)
- Ambient gradient blobs in background (subtle, pointer-events-none)
- Footer micro-copy: "Making moments happen, one calendar at a time."
- No nav bar on this page

---

### Dashboard
**Route:** `app/dashboard/page.tsx`
**Design file:** No HTML export available — implement from the screenshot description below. No design file to reference.

#### Layout
- Top nav: "When." logo left, nav links center (Events / Calendar / Groups), notification bell + avatar right
- Page heading "Your events" large (`text-4xl font-extrabold`), left-aligned
- Subtext below heading: "Select an upcoming gathering or create a new one to start coordinating schedules with your favorite people." in `text-on-surface-variant`
- "New event" button top-right: terracotta gradient, pill-shaped, `+ New event` with Plus icon

#### Event card grid
- 3-column responsive grid (desktop), 2-column (tablet), 1-column (mobile)
- Cards use `surface-container-lowest` background, subtle rounded corners, no visible border
- Hover: `translate-y-[-4px]` lift with `duration-500`
- Each card contains:
  - **Top row:** event type badge left (e.g. "SOCIAL", "BIRTHDAY", "MEETING") in small caps, muted `surface-container-high` pill + status badge right (Confirmed / Planning / Cancelled)
  - **Event name:** large, bold, `text-on-surface`, 2–3 lines max
  - **Date window:** small calendar icon + date range (e.g. "Apr 10 – Apr 20") in `text-on-surface-variant`
  - **Bottom row:** stacked participant avatars (overlapping circles, `ring-2` white ring) with `+N` overflow bubble + arrow icon (`ArrowRight`) right-aligned

#### Status badge colors
| Status | Background | Text |
|---|---|---|
| Confirmed | `secondary-container` (`#c8e7d9`) | `on-secondary-container` (`#4c685d`) |
| Planning | `surface-container-high` (`#ece7e4`) | `on-surface-variant` (`#55423d`) |
| Cancelled | `error-container` (`#ffdad6`) | `on-error-container` (`#93000a`) |

#### "More to plan?" promo card
- Same size as an event card, `surface-container-low` background, dashed or flat style
- Centered content: calendar check icon (terracotta), "More to plan?" heading, subtext "Coordinate with your social circles effortlessly.", "Explore templates" link with external link icon

#### "Sync with your calendar" banner
- Full-width section below the card grid
- Wide card, `primary-fixed` (`#ffdbd0`) warm background
- Left side: "Sync with your calendar" heading + subtext "Connect your Google or Outlook account to automatically see where your free slots align with friends." + "Connect now" ghost button
- Right side: decorative heatmap grid (small colored squares in terracotta tones showing an availability pattern)

#### "Recent Groups" sidebar card
- Sits to the right of the sync banner
- "Recent Groups" heading with users icon
- Each group row: colored avatar circle with initials, group name bold, "X Active events" subtext

---

### Create Event — Step 1 (Details)
**Route:** `app/events/new/page.tsx` (step 1 state)
**Design file:** `design/create-step1.html`

Key elements to replicate:
- 3-step indicator at top: active step uses terracotta gradient circle, done steps use `secondary-container` with checkmark, future steps are muted
- Connecting line between steps
- Form heading: "Create a New Event" + subtext
- Event name input: pill-shaped, `surface-container-lowest` fill, no visible border
- Event type: 4 card-style selectors (Meeting / Social / Birthday / Other) with icons, selected state uses terracotta border
- Description textarea: same pill style
- Location + Video Call Link: side by side, pill inputs with icons
- Back to Dashboard + Next: Availability buttons

---

### Create Event — Step 2 (Availability)
**Route:** `app/events/new/page.tsx` (step 2 state)
**Design file:** `design/create-step2.html`

Key elements to replicate:
- Same 3-step indicator (step 1 done, step 2 active)
- Section heading: "Find the perfect window"
- Scheduling window: two pill date inputs connected by an arrow
- Time range: single pill with start → end time
- Duration: pill-shaped segmented selector (30 min / 1 hr / 1.5 hr / 2 hr / Custom), active option uses `primary-container` fill
- Participants section: email input + Add button, participant rows with avatar, name, email, status badge (INVITED / PENDING), remove X button
- Back + Next: Confirmation buttons

---

### Create Event — Step 3 (Confirm)
**Route:** `app/events/new/page.tsx` (step 3 state)
**Design file:** `design/create-step3.html`

Key elements to replicate:
- Same 3-step indicator (steps 1+2 done, step 3 active)
- Heading: "Almost there." + subtext
- Summary card: terracotta gradient top accent bar, event type badge, event name large, description, location, video link row, time details block (window / hours / duration), participant avatars + names
- "Create Event" CTA button: full width, terracotta gradient, prominent
- "Back to edit" ghost link below

---

### Event Detail
**Route:** `app/events/[uid]/page.tsx`
**Design file:** `design/event-detail.html`

Key elements to replicate:
- Two-column layout: grid (~65%) left, info panel (~35%) right
- **Left — Availability Grid:**
  - Title "Availability Grid" top-left
  - Legend top-right: BUSY (red) / PREFERRED (green) / PROPOSED (pink) / CONFLICT (dark red)
  - Intensity heatmap scale below legend
  - Week view: day columns with date headers, time rows (30-min slots)
  - Color overlays on cells: red = busy, green = preferred, pink/salmon = proposed, dark = conflict
  - Time labels on left, day names + dates on column headers
- **Right — Info panel:**
  - Event type badge + status badge at top
  - Event name large
  - Date window + location
  - "View proposed times" primary CTA button (full width, terracotta gradient)
  - Secondary actions row: "Sync calendar" + "Invite people" (icon + label, side by side)
  - "Top Proposals" section: each proposal shows day/time, participants free count, "Select" link
  - "Participants" section: avatar + name + role label + status badge per person

---

### Settings
**Route:** `app/settings/page.tsx`
**Design file:** `design/settings.html`

Key elements to replicate:
- Same top nav
- Page heading "Settings" + subtext
- Calendar Accounts section:
  - Google icon + account email + "Disconnect" button
  - "CALENDAR SOURCES" label above toggle list
  - Each source: colored dot + calendar name + toggle switch
  - "Connect another account" dashed border button
- Preferences section:
  - Timezone selector (pill-shaped, no visible border)
  - Primary Provider selector
- Footer: "Last synced X minutes ago" left, "Save Changes" pill button right

---

## Shared components

### Top navigation
**Component:** `components/common/TopNav.tsx`
**Reference:** Header section present in `design/event-detail.html` and `design/settings.html`. For the dashboard, use the screenshot description in the Dashboard section above.

- "When." wordmark left: `text-2xl font-black text-primary tracking-tighter`
- Nav links center (desktop only): Events, Calendar, Groups — `text-on-surface-variant` with primary hover
- Right: notification bell button (lucide `Bell` icon) + avatar
- Sticky, `backdrop-blur-md`, `bg-surface/80`
- Active nav item uses `text-primary font-bold`

### Status badges
**Reference:** `design/DESIGN.md` — Status Chips section

| Status | Background | Text |
|---|---|---|
| Planning | `surface-container-high` | `on-surface-variant` |
| Confirmed | `secondary-container` | `on-secondary-container` |
| Cancelled | `error-container` | `on-error-container` |

### Notification bell
**Component:** `components/notifications/NotificationBell.tsx`
**Reference:** Top nav in `design/event-detail.html`

- lucide `Bell` icon, terracotta color
- Unread badge: small red dot or count pill overlaid top-right of icon
- Clicking opens `NotificationList` dropdown

---

## Icon library mapping

Stitch uses Material Symbols. Replace with lucide-react equivalents:

| Material Symbol | lucide-react |
|---|---|
| `notifications` | `Bell` |
| `account_circle` | `CircleUser` |
| `calendar_today` | `Calendar` |
| `calendar_month` | `CalendarDays` |
| `schedule` | `Clock` |
| `timer` | `Timer` |
| `location_on` | `MapPin` |
| `videocam` | `Video` |
| `notes` | `AlignLeft` |
| `celebration` | `PartyPopper` |
| `groups` | `Users` |
| `group_add` | `UserPlus` |
| `mail` | `Mail` |
| `settings` | `Settings` |
| `tune` | `SlidersHorizontal` |
| `add` | `Plus` |
| `check` | `Check` |
| `close` | `X` |
| `arrow_back` | `ArrowLeft` |
| `arrow_forward` | `ArrowRight` |
| `expand_more` | `ChevronDown` |
| `sync` | `RefreshCw` |
| `history` | `Clock` |
| `link` | `Link` |
| `auto_awesome` | `Sparkles` |
| `star` | `Star` |

---

## CSS variable → Tailwind class reference

The Stitch color names map to Tailwind classes via `tailwind.config.ts`:

| Stitch token | Tailwind class | Hex |
|---|---|---|
| `primary` | `text-primary` / `bg-primary` | `#9b4428` |
| `primary-container` | `bg-primary-container` | `#e67e5d` |
| `on-primary` | `text-on-primary` | `#ffffff` |
| `surface` | `bg-surface` | `#fdf8f5` |
| `surface-container-lowest` | `bg-surface-container-lowest` | `#ffffff` |
| `surface-container-low` | `bg-surface-container-low` | `#f7f3f0` |
| `surface-container` | `bg-surface-container` | `#f1edea` |
| `surface-container-high` | `bg-surface-container-high` | `#ece7e4` |
| `surface-container-highest` | `bg-surface-container-highest` | `#e6e2df` |
| `on-surface` | `text-on-surface` | `#1c1b1a` |
| `on-surface-variant` | `text-on-surface-variant` | `#55423d` |
| `secondary-container` | `bg-secondary-container` | `#c8e7d9` |
| `on-secondary-container` | `text-on-secondary-container` | `#4c685d` |
| `error-container` | `bg-error-container` | `#ffdad6` |
| `on-error-container` | `text-on-error-container` | `#93000a` |
| `outline-variant` | `border-outline-variant` | `#dcc1b9` |
| `outline` | `text-outline` | `#89726c` |