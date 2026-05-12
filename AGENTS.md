# Net-Top-Staging Agent Guide

A lightweight staging app for team data entry — SQLite backend, plain HTML frontend.

## Purpose

This app allows team members to populate network infrastructure data without access to the production PostgreSQL database. When data entry is complete, a migration script transfers all data to the production Net-Top-1 database.

## Tech Stack

- **Backend:** FastAPI 0.124.4 + SQLAlchemy 2.0.35 + SQLite
- **Frontend:** Plain HTML + CSS (no build step, no framework)
- **Auth:** Shared password with simple token-based sessions

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit SHARED_PASSWORD
python main.py
```

Open `http://localhost:5001/` — frontend served directly by FastAPI.

## Directory Structure

```
net-top-staging/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── .env.example
│   ├── src/
│   │   ├── models.py        # SQLAlchemy ORM (same schema as Net-Top-1)
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── db.py             # SQLite engine + session + Ramla seed
│   │   ├── auth.py           # Token-based shared password auth
│   │   └── pathfinding/      # BFS/DFS pathfinding (copied from Net-Top-1)
│   └── routes/
│       ├── nodes.py, racks.py, panels.py, devices.py
│       ├── ports.py, connections.py, sub_panels.py
│       ├── pathfinding.py, hdf_panels.py, sites.py, auth.py
├── frontend/
│   ├── index.html, login.html
│   ├── nodes.html, racks.html, panels.html, devices.html
│   ├── connections.html, pathfinding.html
│   ├── common.js, style.css
├── migrate.py                # SQLite → PostgreSQL migration
├── seed_test_data.py         # Dev/test data seeder
├── README.md
└── AGENTS.md                 # This file
```

## Database Schema

Identical to Net-Top-1 production schema:

- **sites** → **nodes** → **racks** → **panels/devices**
- **panels** → **sub_panels** → **ports**
- **devices** → **ports**
- **ports** ↔ **ports** (connections)

## Pre-seeded Data

- Site: **Ramla** (created automatically on first startup)

## Stages

1. **Stage 1** — Create infrastructure (nodes, racks, panels, devices)
2. **Stage 2** — Panel-to-panel connections
3. **Stage 3** — Device-to-panel connections + pathfinding

## Key Files

### `backend/src/db.py`
- SQLite engine: `DATABASE_URL` env var or `sqlite:///./net_top_staging.db`
- `seed_ramla_site()` — creates "Ramla" site if not exists
- `init_db()` — creates all tables
- Session via `get_db_session()` context manager

### `backend/src/auth.py`
- `SHARED_PASSWORD` env var (default: `changeme`)
- Token TTL: 24 hours (`TOKEN_TTL_HOURS` env var)
- Tokens stored in memory (not persistent — restarts clear tokens)

### `migrate.py`
- Reads from SQLite, writes to PostgreSQL
- Deduplicates by name + parent (e.g., same node name + same site = skip)
- Safe to run multiple times — won't create duplicates
- Set `PRODUCTION_DATABASE_URL` env var or edit line 30

### `frontend/common.js`
- `checkAuth()` — redirects to login.html if no token
- `apiGet()`, `apiPost()`, `apiPut()`, `apiDelete()` — all authenticated
- `showMessage(msg, type)` — displays error/success messages
- Token stored in `localStorage`

## Known Issues / Bugs

1. **No port creation UI** — Ports are only created as part of HDF panels or when devices are created. There's no standalone UI to add ports to an existing panel. Workaround: create a new panel with the required ports.

2. **No sub-panel creation UI** — Same as above. Sub-panels are auto-created by HDF panel creation, but there's no UI to manually add sub-panels to a regular panel.

3. **Token memory storage** — Auth tokens are stored in Python dict memory. Server restart clears all tokens, forcing re-login.

4. **SQLite concurrency** — SQLite has write-lock limitations. Only one team member should write at a time. For multi-user concurrent writes, consider switching to a multi-user setup (not currently implemented).

5. **No port status color-coding** — Ports show status as text badge but no visual color coding on the connections page.

6. **No HDF preview in form** — The panel creation form shows both regular and HDF options, but there's no "preview" button to visualize the HDF port layout before creating.

7. **Connections page loads all ports** — The dropdown for selecting ports on the connections page loads ALL ports (could be slow with thousands of ports). Consider filtering by node/panel/device.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./net_top_staging.db` | SQLite DB path |
| `SHARED_PASSWORD` | `changeme` | Login password |
| `TOKEN_TTL_HOURS` | `24` | Token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |
| `PRODUCTION_DATABASE_URL` | (none) | PostgreSQL for migration |

## Migration to Production

1. Set `PRODUCTION_DATABASE_URL` to your PostgreSQL connection string
2. Stop the staging app
3. Run: `python migrate.py`
4. Verify data in production Net-Top-1

The migration script skips duplicates by name + parent relationships. Safe to run multiple times.

## If You Need to Add Port Creation UI

1. Add a route in `backend/routes/ports.py` (already exists, just needs frontend)
2. Add port creation form to `panels.html` or a new `ports.html`
3. Use `apiPost('/ports', {panel_id, name, port_number, ...})` to create
4. Update `migrate.py` if new fields need deduplication logic

## If You Need to Add Sub-Panel Creation UI

1. Route already exists: `POST /api/sub-panels`
2. Add sub-panel creation form to `panels.html`
3. Work with `sub_panel_id` when creating ports

## Docker Note

This app runs **outside Docker** (SQLite on local file). The production Net-Top-1 uses Docker with PostgreSQL. Migration script connects directly to PostgreSQL container via network.

If the production DB is only accessible via Docker network, run migration from a machine that can reach the Docker host's port 5432.