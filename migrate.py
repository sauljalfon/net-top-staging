#!/usr/bin/env python3
"""Migration script: Net-Top-Staging (SQLite) -> Net-Top-1 (PostgreSQL)."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate staging SQLite data into production PostgreSQL")
    parser.add_argument("--source-db-url", help="Override source DB URL")
    parser.add_argument("--target-db-url", help="Override target DB URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing")
    parser.add_argument("--strict", action="store_true", help="Fail on first migration error")
    parser.add_argument("--report-file", help="Write JSON report to this path")
    return parser.parse_args()


def _load_urls(args: argparse.Namespace) -> Tuple[str, str]:
    load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))
    source_url = args.source_db_url or os.environ.get("DATABASE_URL")
    if not source_url:
        source_path = os.path.join(os.path.dirname(__file__), "backend", "net_top_staging.db")
        source_url = f"sqlite:///{source_path}"
    elif source_url.startswith("sqlite:///"):
        # Normalize relative sqlite paths so running from repo root works.
        raw_path = source_url.replace("sqlite:///", "", 1)
        if not os.path.isabs(raw_path):
            repo_relative = os.path.join(os.path.dirname(__file__), raw_path)
            backend_relative = os.path.join(os.path.dirname(__file__), "backend", os.path.basename(raw_path))
            if os.path.exists(repo_relative):
                source_url = f"sqlite:///{repo_relative}"
            elif os.path.exists(backend_relative):
                source_url = f"sqlite:///{backend_relative}"
    target_url = args.target_db_url or os.environ.get(
        "PRODUCTION_DATABASE_URL", "postgresql://user:password@localhost:5432/nettop"
    )
    return source_url, target_url


def _check_required_tables(session, db_kind: str) -> None:
    if db_kind == "sqlite":
        rows = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    else:
        rows = session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    names = {row[0] for row in rows.fetchall()}
    required = {"sites", "nodes", "racks", "panels", "sub_panels", "devices", "ports", "connections"}
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Missing required tables in {db_kind}: {missing}")


def _target_has_port_endpoint_columns(target_session) -> bool:
    cols = target_session.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='ports'
            """
        )
    ).fetchall()
    names = {row[0] for row in cols}
    return "panel_position" in names and "panel_side" in names


def _fetch_sqlite_table(session, table: str) -> Tuple[List[str], List[tuple]]:
    cols = [c[1] for c in session.execute(text(f"PRAGMA table_info({table})")).fetchall()]
    rows = session.execute(text(f"SELECT * FROM {table}")).fetchall()
    return cols, rows


def _build_panel_positions(staging_session) -> Dict[int, Dict[str, object]]:
    rows = staging_session.execute(
        text(
            """
            SELECT p.id, p.panel_id, p.sub_panel_id, p.port_number, p.device_id, sp.sub_panel_number
            FROM ports p
            LEFT JOIN sub_panels sp ON sp.id = p.sub_panel_id
            ORDER BY p.panel_id,
                     COALESCE(sp.sub_panel_number, 0),
                     CASE WHEN p.port_number GLOB '[0-9]*' THEN CAST(p.port_number AS INTEGER) ELSE 2147483647 END,
                     p.id
            """
        )
    ).fetchall()

    per_panel_position: Dict[int, int] = {}
    result: Dict[int, Dict[str, object]] = {}
    for row in rows:
        port_id = row[0]
        panel_id = row[1]
        device_id = row[4]
        if panel_id is not None:
            next_pos = per_panel_position.get(panel_id, 0) + 1
            per_panel_position[panel_id] = next_pos
            result[port_id] = {"panel_position": next_pos, "panel_side": "front"}
        elif device_id is not None:
            result[port_id] = {"panel_position": None, "panel_side": None}
        else:
            result[port_id] = {"panel_position": None, "panel_side": None}
    return result


def migrate() -> int:
    args = parse_args()
    source_url, target_url = _load_urls(args)

    source_engine = create_engine(source_url, echo=False)
    target_engine = create_engine(target_url, echo=False)
    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    report = {
        "started_at": _utcnow().isoformat(),
        "dry_run": args.dry_run,
        "strict": args.strict,
        "source_url": source_url,
        "target_url": target_url,
        "counts": {},
        "skips": {},
        "errors": [],
        "checks": {},
    }

    source_session = SourceSession()
    target_session = TargetSession()
    id_map = {k: {} for k in ["sites", "nodes", "racks", "panels", "sub_panels", "devices", "ports"]}
    now = _utcnow()

    try:
        _check_required_tables(source_session, "sqlite")
        _check_required_tables(target_session, "postgres")
        if not _target_has_port_endpoint_columns(target_session):
            raise RuntimeError("Target ports table missing panel_position/panel_side columns")

        port_endpoint_map = _build_panel_positions(source_session)

        table_order = ["sites", "nodes", "racks", "panels", "sub_panels", "devices"]
        fk_map = {
            "nodes": ["site_id"],
            "racks": ["node_id"],
            "panels": ["node_id", "rack_id"],
            "sub_panels": ["panel_id"],
            "devices": ["node_id", "rack_id"],
        }
        dedupe_keys = {
            "sites": ["name"],
            "nodes": ["name", "site_id"],
            "racks": ["name", "node_id"],
            "panels": ["name", "node_id", "rack_id"],
            "sub_panels": ["panel_id", "sub_panel_number"],
            "devices": ["name", "node_id", "rack_id"],
        }

        for table in table_order:
            cols, rows = _fetch_sqlite_table(source_session, table)
            migrated = 0
            skipped = 0
            for row in rows:
                old_id = row[cols.index("id")]
                data = {k: v for k, v in zip(cols, row) if k not in {"id", "created_at", "updated_at"}}
                for fk in fk_map.get(table, []):
                    fk_table = fk[:-3] + "s"
                    data[fk] = id_map[fk_table].get(data[fk], data[fk])

                where = " AND ".join([f"{k} = :{k}" for k in dedupe_keys[table]])
                existing = target_session.execute(
                    text(f"SELECT id FROM {table} WHERE {where}"), {k: data[k] for k in dedupe_keys[table]}
                ).fetchone()
                if existing:
                    id_map[table][old_id] = existing[0]
                    skipped += 1
                    continue

                data["created_at"] = now
                data["updated_at"] = now
                if not args.dry_run:
                    res = target_session.execute(
                        text(
                            f"INSERT INTO {table} ({', '.join(data.keys())}) VALUES ({', '.join(':' + k for k in data.keys())}) RETURNING id"
                        ),
                        data,
                    )
                    id_map[table][old_id] = res.fetchone()[0]
                else:
                    id_map[table][old_id] = -old_id
                migrated += 1

            report["counts"][table] = {"source": len(rows), "migrated": migrated, "skipped": skipped}

        port_cols, port_rows = _fetch_sqlite_table(source_session, "ports")
        migrated = 0
        skipped = 0
        for row in port_rows:
            old_id = row[port_cols.index("id")]
            data = {k: v for k, v in zip(port_cols, row) if k not in {"id", "created_at", "updated_at"}}
            if data.get("panel_id") is not None:
                data["panel_id"] = id_map["panels"].get(data["panel_id"], data["panel_id"])
            if data.get("sub_panel_id") is not None:
                data["sub_panel_id"] = id_map["sub_panels"].get(data["sub_panel_id"], data["sub_panel_id"])
            if data.get("device_id") is not None:
                data["device_id"] = id_map["devices"].get(data["device_id"], data["device_id"])

            endpoint = port_endpoint_map.get(old_id, {"panel_position": None, "panel_side": None})
            data["panel_position"] = endpoint["panel_position"]
            data["panel_side"] = endpoint["panel_side"]

            if data.get("panel_id") is not None:
                existing = target_session.execute(
                    text(
                        "SELECT id FROM ports WHERE panel_id=:panel_id AND panel_position=:panel_position AND panel_side=:panel_side"
                    ),
                    {
                        "panel_id": data["panel_id"],
                        "panel_position": data["panel_position"],
                        "panel_side": data["panel_side"],
                    },
                ).fetchone()
            else:
                existing = target_session.execute(
                    text("SELECT id FROM ports WHERE device_id=:device_id AND name=:name"),
                    {"device_id": data.get("device_id"), "name": data.get("name")},
                ).fetchone()

            if existing:
                id_map["ports"][old_id] = existing[0]
                skipped += 1
                continue

            data["created_at"] = now
            data["updated_at"] = now
            if not args.dry_run:
                res = target_session.execute(
                    text(
                        f"INSERT INTO ports ({', '.join(data.keys())}) VALUES ({', '.join(':' + k for k in data.keys())}) RETURNING id"
                    ),
                    data,
                )
                id_map["ports"][old_id] = res.fetchone()[0]
            else:
                id_map["ports"][old_id] = -old_id
            migrated += 1

        report["counts"]["ports"] = {"source": len(port_rows), "migrated": migrated, "skipped": skipped}

        conn_cols, conn_rows = _fetch_sqlite_table(source_session, "connections")
        migrated = 0
        skipped = 0
        skip_reasons = {"missing_port_mapping": 0, "duplicate_or_conflict": 0, "other": 0}
        seen_pairs = set()
        for row in conn_rows:
            raw = {k: v for k, v in zip(conn_cols, row) if k not in {"id", "created_at", "updated_at"}}
            mapped_a = id_map["ports"].get(raw["port_a_id"])
            mapped_b = id_map["ports"].get(raw["port_b_id"])
            if not mapped_a or not mapped_b:
                skipped += 1
                skip_reasons["missing_port_mapping"] += 1
                continue

            port_a_id = min(mapped_a, mapped_b)
            port_b_id = max(mapped_a, mapped_b)
            pair = (port_a_id, port_b_id)
            if pair in seen_pairs:
                skipped += 1
                skip_reasons["duplicate_or_conflict"] += 1
                continue

            payload = {
                "port_a_id": port_a_id,
                "port_b_id": port_b_id,
                "status": raw.get("status") or "active",
                "notes": raw.get("notes"),
                "created_at": now,
                "updated_at": now,
            }
            try:
                if not args.dry_run:
                    target_session.execute(
                        text(
                            """
                            INSERT INTO connections (port_a_id, port_b_id, status, notes, created_at, updated_at)
                            VALUES (:port_a_id, :port_b_id, :status, :notes, :created_at, :updated_at)
                            """
                        ),
                        payload,
                    )
                seen_pairs.add(pair)
                migrated += 1
            except SQLAlchemyError as exc:
                skipped += 1
                skip_reasons["duplicate_or_conflict"] += 1
                report["errors"].append(str(exc))
                if args.strict:
                    raise

        report["counts"]["connections"] = {"source": len(conn_rows), "migrated": migrated, "skipped": skipped}
        report["skips"]["connections"] = skip_reasons

        if not args.dry_run:
            target_session.commit()

        report["checks"]["panel_ports_missing_endpoint"] = target_session.execute(
            text("SELECT COUNT(*) FROM ports WHERE panel_id IS NOT NULL AND (panel_position IS NULL OR panel_side IS NULL)")
        ).scalar() if not args.dry_run else 0

        report["checks"]["orphan_connections"] = target_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM connections c
                LEFT JOIN ports pa ON pa.id = c.port_a_id
                LEFT JOIN ports pb ON pb.id = c.port_b_id
                WHERE pa.id IS NULL OR pb.id IS NULL
                """
            )
        ).scalar() if not args.dry_run else 0

        report["finished_at"] = _utcnow().isoformat()
        print(json.dumps(report, indent=2))
        if args.report_file:
            with open(args.report_file, "w", encoding="utf-8") as fp:
                json.dump(report, fp, indent=2)
        return 0
    except Exception as exc:
        if not args.dry_run:
            target_session.rollback()
        report["errors"].append(str(exc))
        report["finished_at"] = _utcnow().isoformat()
        print(json.dumps(report, indent=2))
        return 1
    finally:
        source_session.close()
        target_session.close()


if __name__ == "__main__":
    sys.exit(migrate())
