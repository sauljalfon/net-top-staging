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