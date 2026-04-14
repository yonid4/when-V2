# When.

Group scheduling without the back-and-forth. Create an event, invite participants, sync Google Calendars, and get the best meeting time automatically — ranked by real availability and stated preferences.

## Key Features

- **Google Calendar sync** — participants connect their Google account once; busy slots are pulled automatically and refreshed hourly in the background
- **Availability heatmap** — interactive grid shows where everyone is free across the scheduling window
- **Preferred-slot marking** — participants swipe to highlight their ideal times, not just their open ones
- **Smart proposal ranking** — algorithm scores candidate windows by conflict count (ascending) and preferred-slot overlap (descending), surfaces the top 5
- **Email invitations** — coordinator invites participants by email; invitees receive a join link and RSVP flow
- **Real-time updates** — Supabase Realtime pushes participant changes, busy-slot syncs, and proposal refreshes live to all viewers
- **Event finalization** — coordinator picks the winning proposal and closes the event

## Tech Stack

- **Backend:** Python 3.12 · FastAPI · Supabase (PostgreSQL + Realtime) · Google OAuth 2.0 / Calendar API · APScheduler
- **Frontend:** Next.js 14 (App Router) · TypeScript · TanStack Query · Zustand · shadcn/ui · Tailwind CSS

## Getting Started

### Prerequisites

- Python 3.12
- Node.js 18+
- A Supabase project (PostgreSQL database + Realtime enabled)
- A Google Cloud project with OAuth 2.0 credentials and the Calendar API enabled

### Installation

**Backend**

```bash
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Supabase keys, Google OAuth credentials, JWT secret
```

**Frontend**

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in Supabase public key, API URL
```

## Database Setup

The project uses Supabase (PostgreSQL). To build the database from scratch:

1. Create a new [Supabase](https://supabase.com) project.
2. In the Supabase dashboard, open **SQL Editor**.
3. Copy the contents of [`schema.sql`](schema.sql) and run it in the SQL Editor.
   This creates all extensions, enums, tables, indexes, Row Level Security policies, and triggers.
4. If you have existing migrations to apply on top of the base schema, run each file in [`supabase/migrations/`](supabase/migrations/) in chronological order (filename prefix determines order).
5. Copy your Supabase project URL and `anon`/`service_role` keys into `backend/.env` and `frontend/.env.local`.

> **Note:** `schema.sql` assumes Supabase Auth is already enabled — the `auth.users` table is provided automatically by Supabase and does not need to be created manually.

## Usage

Run the backend and frontend in separate terminals.

```bash
# Terminal 1 — API server (port 8000)
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --reload-dir app --port 8000

# Terminal 2 — Next.js dev server (port 3000)
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), sign in with Google, and create your first event.

## Visuals

![Landing page](./docs/screenshots/landing.png)
*Landing page — hero section with availability grid mockup*

![Dashboard](./docs/screenshots/dashboard.png)
*Dashboard — event cards and calendar connect prompt*

![Event detail](./docs/screenshots/event_detail.png)
*Event detail — availability grid, participant list, and ranked proposals*

## Tests

**Backend**

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

**Frontend**

```bash
cd frontend
npm run test
```

---

See [`docs/`](docs/) for architecture, data model, and sprint plan documentation.
