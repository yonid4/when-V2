# When.

Group scheduling without the back-and-forth. Create an event, invite participants, sync Google or Outlook calendars, and get the best meeting time automatically — ranked by real availability and stated preferences.

## Key Features

- **Google & Outlook Calendar sync** — participants connect a Google or Microsoft (Outlook) account; busy slots are pulled automatically on connect and refreshed hourly in the background. A user can connect multiple accounts across both providers.
- **Availability heatmap** — interactive grid shows where everyone is free across the scheduling window
- **Preferred-slot marking** — participants swipe to highlight their ideal times, not just their open ones
- **Smart proposal ranking** — algorithm generates candidate windows within each day's configured hours (including overnight windows that wrap past midnight), never proposes times in the past, scores them by conflict count (ascending) and preferred-slot overlap (descending), and surfaces the top 5
- **Email invitations** — coordinator invites participants by email; invitees receive a join link and RSVP flow
- **Real-time updates** — Supabase Realtime pushes participant changes, busy-slot syncs, and proposal refreshes live to all viewers
- **Event finalization** — coordinator picks the winning proposal and closes the event. The confirmed event is written directly onto **each participant's own write calendar** using that participant's provider and credentials (Google or Microsoft), so it lands reliably for everyone cross-provider without depending on invitation emails. Each user has exactly one write calendar across all connected accounts, regardless of provider (a DB trigger backs the rule). Participants without a connected calendar — and any external invitees — instead receive an emailed calendar invitation from the coordinator's calendar. Busy sources from any provider feed availability.
- **Credential expiry detection** — expired calendar tokens are detected and the UI prompts the user to reconnect without disrupting other participants
- **Account deletion** — authenticated users can permanently delete their account and all owned data (events, calendar tokens, preferences) from the Settings page; calendar OAuth tokens are revoked server-side (where the provider supports revocation) before any data is removed
- **Privacy Policy** — hosted at `/privacy`; covers data collection, retention, deletion rights, and third-party integrations
- **Terms of Service** — hosted at `/terms`; defines usage terms, liability limits, and Google API Services policy alignment

## Tech Stack

- **Backend:** Python 3.12 · FastAPI · Supabase (PostgreSQL + Realtime) · Google OAuth 2.0 / Calendar API · Microsoft Graph (MSAL) · APScheduler · provider abstraction (`app/providers/`)
- **Frontend:** Next.js 14 (App Router) · TypeScript · TanStack Query · Zustand · shadcn/ui · Tailwind CSS

## Getting Started

### Prerequisites

- Python 3.12
- Node.js 18+
- Docker & Docker Compose (optional, for containerised dev)
- A Supabase project (PostgreSQL database + Realtime enabled)
- A Google Cloud project with OAuth 2.0 credentials and the Calendar API enabled
- _(optional)_ A Microsoft Entra app registration to enable Outlook calendars — see [Microsoft (Outlook) Calendar setup](#microsoft-outlook-calendar-setup)

### Installation

**Option A — Docker Compose (recommended)**

Copy the env files, then run a single command:

```bash
cp backend/.env.example backend/.env   # fill in Supabase keys, Google OAuth credentials, JWT secret
cp frontend/.env.example frontend/.env # fill in NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
docker compose up --build
```

Both services start automatically; the frontend is available at [http://localhost:3000](http://localhost:3000) and the API at [http://localhost:8000](http://localhost:8000).

**Option B — local dev servers**

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

### Microsoft (Outlook) Calendar setup

Outlook support is optional — leave `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` blank in `backend/.env` to run Google-only. To enable it:

1. In the [Microsoft Entra admin center](https://entra.microsoft.com) → **App registrations** → **New registration**.
2. **Supported account types:** _Accounts in any organizational directory and personal Microsoft accounts_ (this uses the `/common` OAuth endpoint, covering both Outlook.com and Microsoft 365 work/school accounts).
3. **Redirect URI (Web):** set it to your `MICROSOFT_CALENDAR_REDIRECT_URI` (default `http://localhost:8000/api/calendar-accounts/callback/microsoft`).
4. Under **Certificates & secrets**, create a client secret.
5. Under **API permissions**, add the delegated Microsoft Graph permissions `User.Read` and `Calendars.ReadWrite`. These are user-consentable — no tenant admin grant is required for the app. (Some locked-down corporate tenants still require an admin to approve user consent; if so, the OAuth callback returns an error and the user is redirected back to Settings with a readable message.)
6. Put the **Application (client) ID** and **client secret** into `backend/.env` as `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET`.

> Microsoft rotates the OAuth **refresh token** on every refresh, and the Microsoft identity platform has no token-revocation endpoint for this flow — disconnecting an Outlook account simply drops the stored credentials. Both behaviours are handled by the provider layer.

## Database Setup

The project uses Supabase (PostgreSQL). [`schema.sql`](schema.sql) is the **complete, self-contained snapshot** of the current database — running it on a fresh project is the only query you need to build everything (all extensions, enums, tables, indexes, Row Level Security policies, functions, and triggers, including the multi-provider calendar support).

To build the database from scratch:

1. Create a new [Supabase](https://supabase.com) project.
2. In the Supabase dashboard, open **SQL Editor**.
3. Copy the contents of [`schema.sql`](schema.sql) and run it.
4. Copy your Supabase project URL and `anon`/`service_role` keys into `backend/.env` and `frontend/.env.local`.

> **Do not also run the files in [`supabase/migrations/`](supabase/migrations/) on a fresh build.** Their changes are already folded into `schema.sql`, and several migrations are non-idempotent (e.g. a `RENAME COLUMN`), so applying them on top of `schema.sql` will error. The migration files exist only to **upgrade an existing database** that predates them — run each, in filename order, against such a database.
>
> **Note:** `schema.sql` assumes Supabase Auth is already enabled — the `auth.users` table is provided automatically by Supabase and does not need to be created manually.

## Usage

**Docker Compose**

```bash
docker compose up --build
```

**Local dev servers** (two terminals)

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

The API exposes an unauthenticated `GET /health` endpoint (returns `{"status": "ok"}`) for container health checks and uptime monitoring.

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

**Frontend** (Vitest)

```bash
cd frontend
npm run test
```

---

See [`docs/`](docs/) for architecture, data model, and sprint plan documentation.
