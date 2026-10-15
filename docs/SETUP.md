# Setup Guide — When.

Step-by-step instructions for running When. locally. For a high-level overview, see the [README](../README.md).

---

## Prerequisites

- Python 3.12
- Node.js 18+
- Docker & Docker Compose (optional, for containerised dev)
- A [Supabase](https://supabase.com) project (PostgreSQL + Realtime enabled)
- A Google Cloud project with OAuth 2.0 credentials and the Google Calendar API enabled
- _(optional)_ A Microsoft Entra app registration to enable Outlook calendars

---

## 1. Database (Supabase)

[`schema.sql`](../schema.sql) is the **complete, self-contained snapshot** of the database: extensions, enums, tables, indexes, Row Level Security policies, functions and triggers. Running it on a fresh project is the only query you need.

1. Create a new Supabase project.
2. In the Supabase dashboard, open **SQL Editor**.
3. Paste the contents of [`schema.sql`](../schema.sql) and run it.
4. Copy your project URL plus the `anon` and `service_role` keys. You'll need them in step 4.

> **Do not also run the files in [`supabase/migrations/`](../supabase/migrations/) on a fresh build.** Their changes are already folded into `schema.sql`, and several are non-idempotent (e.g. a `RENAME COLUMN`), so running them on top of `schema.sql` will fail. They exist only to **upgrade an existing database** that predates them. Run each one in filename order against that database.
>
> `schema.sql` assumes Supabase Auth is enabled. Supabase provides the `auth.users` table automatically.

---

## 2. Google OAuth & Calendar API

Google is used both for sign-in and as a calendar provider.

1. In the [Google Cloud Console](https://console.cloud.google.com), create (or pick) a project and enable the **Google Calendar API**.
2. Configure the **OAuth consent screen** with these scopes:
   - `userinfo.email`, `userinfo.profile`
   - `https://www.googleapis.com/auth/calendar.readonly`
   - `https://www.googleapis.com/auth/calendar.events`
3. Create an **OAuth 2.0 Client ID** (type: *Web application*) and add both redirect URIs:
   - `http://localhost:8000/auth/google/callback` (sign-in)
   - `http://localhost:8000/api/calendar-accounts/callback` (calendar connect)
4. Copy the client ID and secret into `backend/.env` (step 4).

---

## 3. Microsoft (Outlook) Calendar — optional

To run Google-only, leave `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET` blank. To enable Outlook:

1. In the [Microsoft Entra admin center](https://entra.microsoft.com), go to **App registrations** → **New registration**.
2. **Supported account types:** _Accounts in any organizational directory and personal Microsoft accounts_. This uses the `/common` endpoint, so both Outlook.com and Microsoft 365 work/school accounts are covered.
3. **Redirect URI (Web):** `http://localhost:8000/api/calendar-accounts/callback/microsoft` (must match `MICROSOFT_CALENDAR_REDIRECT_URI`).
4. Under **Certificates & secrets**, create a client secret.
5. Under **API permissions**, add the delegated Microsoft Graph permissions `User.Read` and `Calendars.ReadWrite`. Users can consent to both themselves, so no tenant admin grant is needed. Some locked-down corporate tenants still require an admin to approve user consent. In that case the OAuth callback fails and the user is sent back to Settings with a readable error.
6. Put the **Application (client) ID** and **client secret** into `backend/.env`.

> Microsoft rotates the OAuth **refresh token** on every refresh, and this flow has no token-revocation endpoint. Disconnecting an Outlook account just drops the stored credentials. The provider layer handles both behaviours.

---

## 4. Environment variables

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env        # for Docker Compose
cp frontend/.env.example frontend/.env.local  # for local `npm run dev`
```

**`backend/.env`**

| Variable | Description |
|---|---|
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | From your Supabase project settings |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | From the Google OAuth client |
| `GOOGLE_REDIRECT_URI` | Sign-in callback (default `http://localhost:8000/auth/google/callback`) |
| `GOOGLE_CALENDAR_REDIRECT_URI` | Calendar connect callback |
| `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` / `MICROSOFT_CALENDAR_REDIRECT_URI` | Optional: Outlook support |
| `JWT_SECRET_KEY` | A long random string |
| `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | Defaults: `HS256`, `10080` (7 days) |

**`frontend/.env` / `frontend/.env.local`**

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public Supabase keys (used for Realtime subscriptions) |
| `NEXT_PUBLIC_API_URL` | API URL as seen by the browser |
| `API_URL` | API URL as seen by the Next.js server (`http://backend:8000` inside Docker) |

---

## 5. Run it

### Option A: Docker Compose (recommended)

```bash
docker compose up --build
```

- Frontend: <http://localhost:3000>
- API: <http://localhost:8000> (interactive docs at `/docs`)

### Option B: Local dev servers

```bash
# Terminal 1: API (port 8000)
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-dir app --port 8000

# Terminal 2: Next.js (port 3000)
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>, sign in with Google, and create your first event.

The API also exposes an unauthenticated `GET /health` endpoint (returns `{"status": "ok"}`) for container health checks and uptime monitoring.

---

## 6. Tests

**Backend (pytest)**

```bash
cd backend && source venv/bin/activate
pytest tests/ -v --ignore=tests/integration   # unit tests, fully mocked
pytest tests/integration -v                   # RLS integration tests, needs a live Supabase project
```

**Frontend (Vitest + Testing Library)**

```bash
cd frontend
npm run test
```

See [`TESTS.md`](TESTS.md) for the test strategy.
