# Net-Top-Staging

Staging app for team data entry — SQLite backend, plain HTML frontend.

## Quick Start

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit SHARED_PASSWORD
python main.py
```

Frontend at `http://localhost:5001` — open `frontend/index.html` in browser.

Default password: `changeme` (change in `.env`)

## Default Login
- Site "Ramla" is pre-created
- Default password: `changeme`

## Stages

1. **Create infrastructure** — nodes, racks, panels (including HDF), devices
2. **Panel-to-panel connections** — connect ports between panels
3. **Device-to-panel connections + pathfinding** — connect devices, trace paths

## Migration to Production

1. Edit `migrate.py` — set `PRODUCTION_DATABASE_URL` to your PostgreSQL instance
2. Stop the staging app
3. Run:
```bash
python migrate.py
```

This reads all data from SQLite and bulk-inserts into PostgreSQL. Duplicate records (by name/unique fields) are skipped.

## Project Structure

```
net-top-staging/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── src/
│   │   ├── models.py, schemas.py, db.py, auth.py
│   │   └── pathfinding/
│   └── routes/
│       ├── nodes.py, racks.py, panels.py, devices.py
│       ├── ports.py, connections.py, sub_panels.py
│       ├── pathfinding.py, hdf_panels.py, sites.py, auth.py
├── frontend/
│   ├── index.html, login.html, nodes.html, racks.html
│   ├── panels.html, devices.html, connections.html
│   ├── pathfinding.html, common.js, style.css
├── migrate.py
└── README.md
```