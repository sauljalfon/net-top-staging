"""Net-Top-Staging - FastAPI backend with SQLite for team data entry."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db import init_db, get_db, seed_ramla_site
from routes.sites import router as sites_router
from routes.nodes import router as nodes_router
from routes.racks import router as racks_router
from routes.panels import router as panels_router
from routes.devices import router as devices_router
from routes.ports import router as ports_router
from routes.connections import router as connections_router
from routes.pathfinding import router as pathfinding_router
from routes.sub_panels import router as sub_panels_router
from routes.hdf_panels import router as hdf_panels_router
from routes.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing SQLite database...")
    init_db()
    seed_ramla_site()
    print("Database ready.")
    yield


app = FastAPI(
    title="Net-Top-Staging",
    description="Staging app for team data entry - SQLite backend",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc.orig) if hasattr(exc, 'orig') else "Database integrity error"}
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


@app.get("/api/health")
async def health_check():
    try:
        from src.db import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "disconnected", "detail": str(e)})


FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/login.html")
async def login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@app.get("/index.html")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/nodes.html")
async def nodes():
    return FileResponse(os.path.join(FRONTEND_DIR, "nodes.html"))

@app.get("/racks.html")
async def racks():
    return FileResponse(os.path.join(FRONTEND_DIR, "racks.html"))

@app.get("/panels.html")
async def panels():
    return FileResponse(os.path.join(FRONTEND_DIR, "panels.html"))

@app.get("/devices.html")
async def devices():
    return FileResponse(os.path.join(FRONTEND_DIR, "devices.html"))

@app.get("/ports.html")
async def ports():
    return FileResponse(os.path.join(FRONTEND_DIR, "ports.html"))

@app.get("/connections.html")
async def connections():
    return FileResponse(os.path.join(FRONTEND_DIR, "connections.html"))

@app.get("/pathfinding.html")
async def pathfinding():
    return FileResponse(os.path.join(FRONTEND_DIR, "pathfinding.html"))

@app.get("/common.js")
async def common_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "common.js"))

@app.get("/style.css")
async def style_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))


app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(sites_router, prefix="/api/sites", tags=["Sites"])
app.include_router(nodes_router, prefix="/api/nodes", tags=["Nodes"])
app.include_router(racks_router, prefix="/api/racks", tags=["Racks"])
app.include_router(panels_router, prefix="/api/panels", tags=["Panels"])
app.include_router(devices_router, prefix="/api/devices", tags=["Devices"])
app.include_router(ports_router, prefix="/api/ports", tags=["Ports"])
app.include_router(connections_router, prefix="/api/connections", tags=["Connections"])
app.include_router(pathfinding_router, prefix="/api/pathfinding", tags=["Pathfinding"])
app.include_router(sub_panels_router, prefix="/api/sub-panels", tags=["SubPanels"])
app.include_router(hdf_panels_router, prefix="/api/panels", tags=["HDF Panels"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5001, reload=True)
