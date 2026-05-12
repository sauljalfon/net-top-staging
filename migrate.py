#!/usr/bin/env python3
"""
Migration script: Net-Top-Staging (SQLite) -> Net-Top-1 (PostgreSQL)

Usage:
    1. Set PRODUCTION_DATABASE_URL env var or edit line below
    2. Run: python migrate.py

Data is deduplicated by name + parent (e.g., same name + same site = duplicate).
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))


def _utcnow():
    return datetime.now(timezone.utc)


STAGING_URL = os.environ.get('DATABASE_URL')
if not STAGING_URL:
    staging_db_path = os.path.join(os.path.dirname(__file__), 'backend', 'net_top_staging.db')
    STAGING_URL = f'sqlite:///{staging_db_path}'

PRODUCTION_URL = os.environ.get('PRODUCTION_DATABASE_URL', 'postgresql://user:password@localhost:5432/nettop')

STAGING_ENGINE = create_engine(STAGING_URL, echo=False)
PRODUCTION_ENGINE = create_engine(PRODUCTION_URL, echo=False)

StagingSession = sessionmaker(bind=STAGING_ENGINE)
ProdSession = sessionmaker(bind=PRODUCTION_ENGINE)

EXCLUDE_COLS = {'id', 'created_at', 'updated_at'}


def find_existing(prod_session, table, conditions, params):
    """Return ID if record exists matching conditions, else None."""
    query = f"SELECT id FROM {table} WHERE " + " AND ".join([f"{k} = :{k}" for k in conditions])
    result = prod_session.execute(text(query), params).fetchone()
    return result[0] if result else None


def migrate():
    print("Starting migration from SQLite -> PostgreSQL")
    print("=" * 50)

    prod_session = ProdSession()
    staging_session = StagingSession()

    try:
        existing_site_names = {s[0] for s in prod_session.execute(text("SELECT name FROM sites")).fetchall()}
        print(f"Found {len(existing_site_names)} existing sites in production: {existing_site_names}")
    finally:
        prod_session.close()

    id_map = {
        'sites': {}, 'nodes': {}, 'racks': {}, 'panels': {},
        'sub_panels': {}, 'devices': {}, 'ports': {},
    }

    try:
        now = _utcnow()

        print("\n[1/8] Migrating sites...")
        sites = staging_session.execute(text("SELECT * FROM sites")).fetchall()
        site_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(sites)")).fetchall()]

        for site in sites:
            data = {k: v for k, v in zip(site_cols, site) if k not in EXCLUDE_COLS}
            name = data.pop('name')

            existing_id = find_existing(prod_session, 'sites', ['name'], {'name': name})
            if existing_id:
                id_map['sites'][site.id] = existing_id
                print(f"  Skipped '{name}' (already exists, id={existing_id})")
                continue

            data['name'] = name
            data['created_at'] = now
            data['updated_at'] = now

            result = prod_session.execute(
                text(f"INSERT INTO sites ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])}) RETURNING id"),
                data
            )
            new_id = result.fetchone()[0]
            id_map['sites'][site.id] = new_id
            prod_session.commit()
            print(f"  Migrated '{name}' (new id: {new_id})")

        print("\n[2/8] Migrating nodes...")
        nodes = staging_session.execute(text("SELECT * FROM nodes")).fetchall()
        node_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(nodes)")).fetchall()]

        for node in nodes:
            data = {k: v for k, v in zip(node_cols, node) if k not in EXCLUDE_COLS}
            old_id = node.id
            data['site_id'] = id_map['sites'].get(data['site_id'], data['site_id'])

            existing_id = find_existing(prod_session, 'nodes', ['name', 'site_id'], {'name': data['name'], 'site_id': data['site_id']})
            if existing_id:
                id_map['nodes'][old_id] = existing_id
                print(f"  Skipped '{data['name']}' (already exists, id={existing_id})")
                continue

            data['created_at'] = now
            data['updated_at'] = now

            result = prod_session.execute(
                text(f"INSERT INTO nodes ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])}) RETURNING id"),
                data
            )
            new_id = result.fetchone()[0]
            id_map['nodes'][old_id] = new_id
            prod_session.commit()
            print(f"  Migrated node '{data['name']}' (id {old_id} -> {new_id})")

        print("\n[3/8] Migrating racks...")
        racks = staging_session.execute(text("SELECT * FROM racks")).fetchall()
        rack_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(racks)")).fetchall()]

        for rack in racks:
            data = {k: v for k, v in zip(rack_cols, rack) if k not in EXCLUDE_COLS}
            old_id = rack.id
            data['node_id'] = id_map['nodes'].get(data['node_id'], data['node_id'])

            existing_id = find_existing(prod_session, 'racks', ['name', 'node_id'], {'name': data['name'], 'node_id': data['node_id']})
            if existing_id:
                id_map['racks'][old_id] = existing_id
                print(f"  Skipped '{data['name']}' (already exists, id={existing_id})")
                continue

            data['created_at'] = now
            data['updated_at'] = now

            result = prod_session.execute(
                text(f"INSERT INTO racks ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])}) RETURNING id"),
                data
            )
            new_id = result.fetchone()[0]
            id_map['racks'][old_id] = new_id
            prod_session.commit()
            print(f"  Migrated rack '{data['name']}' (id {old_id} -> {new_id})")

        print("\n[4/8] Migrating panels...")
        panels = staging_session.execute(text("SELECT * FROM panels")).fetchall()
        panel_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(panels)")).fetchall()]

        for panel in panels:
            data = {k: v for k, v in zip(panel_cols, panel) if k not in EXCLUDE_COLS}
            old_id = panel.id
            data['node_id'] = id_map['nodes'].get(data['node_id'], data['node_id'])
            data['rack_id'] = id_map['racks'].get(data['rack_id'], data['rack_id'])

            existing_id = find_existing(prod_session, 'panels', ['name', 'node_id', 'rack_id'],
                                        {'name': data['name'], 'node_id': data['node_id'], 'rack_id': data['rack_id']})
            if existing_id:
                id_map['panels'][old_id] = existing_id
                print(f"  Skipped '{data['name']}' (already exists, id={existing_id})")
                continue

            data['created_at'] = now
            data['updated_at'] = now

            result = prod_session.execute(
                text(f"INSERT INTO panels ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])}) RETURNING id"),
                data
            )
            new_id = result.fetchone()[0]
            id_map['panels'][old_id] = new_id
            prod_session.commit()
            print(f"  Migrated panel '{data['name']}' (id {old_id} -> {new_id})")

        print("\n[5/8] Migrating sub_panels...")
        sub_panels = staging_session.execute(text("SELECT * FROM sub_panels")).fetchall()
        sub_panel_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(sub_panels)")).fetchall()]

        for sp in sub_panels:
            data = {k: v for k, v in zip(sub_panel_cols, sp) if k not in EXCLUDE_COLS}
            old_id = sp.id
            data['panel_id'] = id_map['panels'].get(data['panel_id'], data['panel_id'])

            existing_id = find_existing(prod_session, 'sub_panels', ['name', 'panel_id'],
                                        {'name': data['name'], 'panel_id': data['panel_id']})
            if existing_id:
                id_map['sub_panels'][old_id] = existing_id
                print(f"  Skipped '{data['name']}' (already exists, id={existing_id})")
                continue

            data['created_at'] = now
            data['updated_at'] = now

            result = prod_session.execute(
                text(f"INSERT INTO sub_panels ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])}) RETURNING id"),
                data
            )
            new_id = result.fetchone()[0]
            id_map['sub_panels'][old_id] = new_id
            prod_session.commit()
            print(f"  Migrated sub_panel '{data['name']}' (id {old_id} -> {new_id})")

        print("\n[6/8] Migrating devices...")
        devices = staging_session.execute(text("SELECT * FROM devices")).fetchall()
        device_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(devices)")).fetchall()]

        for device in devices:
            data = {k: v for k, v in zip(device_cols, device) if k not in EXCLUDE_COLS}
            old_id = device.id
            data['node_id'] = id_map['nodes'].get(data['node_id'], data['node_id'])
            data['rack_id'] = id_map['racks'].get(data['rack_id'], data['rack_id'])

            existing_id = find_existing(prod_session, 'devices', ['name', 'node_id', 'rack_id'],
                                        {'name': data['name'], 'node_id': data['node_id'], 'rack_id': data['rack_id']})
            if existing_id:
                id_map['devices'][old_id] = existing_id
                print(f"  Skipped '{data['name']}' (already exists, id={existing_id})")
                continue

            data['created_at'] = now
            data['updated_at'] = now

            result = prod_session.execute(
                text(f"INSERT INTO devices ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])}) RETURNING id"),
                data
            )
            new_id = result.fetchone()[0]
            id_map['devices'][old_id] = new_id
            prod_session.commit()
            print(f"  Migrated device '{data['name']}' (id {old_id} -> {new_id})")

        print("\n[7/8] Migrating ports...")
        ports = staging_session.execute(text("SELECT * FROM ports")).fetchall()
        port_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(ports)")).fetchall()]

        migrated_ports = 0
        skipped_ports = 0
        for port in ports:
            data = {k: v for k, v in zip(port_cols, port) if k not in EXCLUDE_COLS}
            old_id = port.id

            panel_id = data.get('panel_id')
            sub_panel_id = data.get('sub_panel_id')
            device_id = data.get('device_id')

            if panel_id:
                data['panel_id'] = id_map['panels'].get(panel_id, panel_id)
            if sub_panel_id:
                data['sub_panel_id'] = id_map['sub_panels'].get(sub_panel_id, sub_panel_id)
            if device_id:
                data['device_id'] = id_map['devices'].get(device_id, device_id)

            if panel_id and sub_panel_id:
                existing_id = find_existing(prod_session, 'ports', ['panel_id', 'sub_panel_id', 'name'],
                                            {'panel_id': data['panel_id'], 'sub_panel_id': data['sub_panel_id'], 'name': data['name']})
            elif device_id:
                existing_id = find_existing(prod_session, 'ports', ['device_id', 'name'],
                                            {'device_id': data['device_id'], 'name': data['name']})
            else:
                existing_id = None

            if existing_id:
                id_map['ports'][old_id] = existing_id
                skipped_ports += 1
                continue

            data['created_at'] = now
            data['updated_at'] = now

            result = prod_session.execute(
                text(f"INSERT INTO ports ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])}) RETURNING id"),
                data
            )
            new_id = result.fetchone()[0]
            id_map['ports'][old_id] = new_id
            prod_session.commit()
            migrated_ports += 1

        print(f"  Migrated {migrated_ports} ports, skipped {skipped_ports} duplicates")

        print("\n[8/8] Migrating connections...")
        connections = staging_session.execute(text("SELECT * FROM connections")).fetchall()
        conn_cols = [c[1] for c in staging_session.execute(text("PRAGMA table_info(connections)")).fetchall()]

        migrated_count = 0
        skipped_count = 0
        for conn in connections:
            data = {k: v for k, v in zip(conn_cols, conn) if k not in EXCLUDE_COLS}
            data.pop('id', None)
            data['port_a_id'] = id_map['ports'].get(data['port_a_id'], data['port_a_id'])
            data['port_b_id'] = id_map['ports'].get(data['port_b_id'], data['port_b_id'])
            data['created_at'] = now
            data['updated_at'] = now

            try:
                prod_session.execute(
                    text(f"INSERT INTO connections ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])})"),
                    data
                )
                prod_session.commit()
                migrated_count += 1
            except Exception:
                prod_session.rollback()
                skipped_count += 1

        print(f"  Migrated {migrated_count} connections, skipped {skipped_count} duplicates")

        print("\n" + "=" * 50)
        print("Migration complete!")
        print(f"  Sites: {len(id_map['sites'])}")
        print(f"  Nodes: {len(id_map['nodes'])}")
        print(f"  Racks: {len(id_map['racks'])}")
        print(f"  Panels: {len(id_map['panels'])}")
        print(f"  SubPanels: {len(id_map['sub_panels'])}")
        print(f"  Devices: {len(id_map['devices'])}")
        print(f"  Ports: {len(id_map['ports'])}")

    finally:
        staging_session.close()
        prod_session.close()


if __name__ == '__main__':
    migrate()