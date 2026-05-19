"""Database configuration for SQLite staging environment."""

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from .models import Base

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./net_top_staging.db')

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _run_startup_migrations()


def _run_startup_migrations() -> None:
    """Apply lightweight in-place SQLite migrations for staging compatibility."""
    from sqlalchemy import text

    with engine.begin() as conn:
        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='ports'")
        ).fetchone()
        if not table_exists:
            return

        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(ports)")).fetchall()
        }

        if 'panel_position' not in columns:
            conn.execute(text("ALTER TABLE ports ADD COLUMN panel_position INTEGER"))
        if 'panel_side' not in columns:
            conn.execute(text("ALTER TABLE ports ADD COLUMN panel_side VARCHAR(10)"))

        # Backfill panel endpoints deterministically: per-panel order by sub-panel and numeric port_number.
        rows = conn.execute(
            text(
                """
                SELECT p.id, p.panel_id
                FROM ports p
                LEFT JOIN sub_panels sp ON sp.id = p.sub_panel_id
                WHERE p.panel_id IS NOT NULL
                ORDER BY p.panel_id,
                         COALESCE(sp.sub_panel_number, 0),
                         CASE WHEN p.port_number GLOB '[0-9]*' THEN CAST(p.port_number AS INTEGER) ELSE 2147483647 END,
                         p.id
                """
            )
        ).fetchall()

        current_panel = None
        position = 0
        for port_id, panel_id in rows:
            if panel_id != current_panel:
                current_panel = panel_id
                position = 1
            else:
                position += 1

            conn.execute(
                text(
                    """
                    UPDATE ports
                    SET panel_position = :position,
                        panel_side = 'front'
                    WHERE id = :port_id
                    """
                ),
                {"position": position, "port_id": port_id},
            )

        conn.execute(
            text(
                """
                UPDATE ports
                SET panel_position = NULL,
                    panel_side = NULL
                WHERE panel_id IS NULL
                """
            )
        )

        index_names = {
            row[1] for row in conn.execute(text("PRAGMA index_list(ports)")).fetchall()
        }
        if 'idx_port_panel_position_side' not in index_names:
            conn.execute(
                text("CREATE INDEX idx_port_panel_position_side ON ports (panel_id, panel_position, panel_side)")
            )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def check_db_connection() -> bool:
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def seed_ramla_site() -> None:
    """Create the Ramla site if it doesn't exist."""
    from .models import Site
    with get_db_session() as db:
        existing = db.query(Site).filter(Site.name == 'Ramla').first()
        if not existing:
            site = Site(
                name='Ramla',
                location='Ramla, Israel',
                site_type='data_center',
                description='Primary data center location'
            )
            db.add(site)
            db.commit()
            print("Created 'Ramla' site")
        else:
            print("'Ramla' site already exists")


if __name__ == '__main__':
    print("Initializing SQLite database...")
    init_db()
    seed_ramla_site()
    print("Database ready.")
