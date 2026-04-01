# When.

Group scheduling without the back-and-forth. Create an event, invite participants, sync Google Calendars, and get the best meeting time automatically.

## Stack

- **Backend:** FastAPI + Supabase (PostgreSQL) + Google OAuth/Calendar API
- **Frontend:** Next.js 14 (App Router) + shadcn/ui + TanStack Query + Zustand

---

## Dev setup

Run backend and frontend in separate terminals. No Docker.

### Backend

```bash
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your values
uvicorn app.main:app --reload --reload-dir app --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local  # fill in your values
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Running tests

### Backend

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm run test
```

---

## Env vars

See `backend/.env.example` and `frontend/.env.local.example` for required variables (Supabase keys, Google OAuth credentials, JWT secret).

---

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Tech stack](docs/TECH_STACK.md)
- [Sprint plan](docs/SPRINT%20PLAN.md)
- [Lessons learned](docs/LESSONS_LEARNED.md)
- [Project rules](docs/CLAUDE.md)
- [Stitch Design](docs/STITCH_DESIGN.md)