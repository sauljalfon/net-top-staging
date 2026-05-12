#!/usr/bin/env python3
"""Seed test data into the SQLite staging database."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import init_db, seed_ramla_site, get_db_session
from src.models import Node, Rack, Panel, SubPanel, Device, Port

def seed_data():
    init_db()
    seed_ramla_site()

    with get_db_session() as db:
        ramla = db.query(Node).filter_by(location='Ramla Data Center').first()
        if not ramla:
            ramla = Node(site_id=1, location='Ramla Data Center', name='Main Data Center', description='Primary IDF')
            db.add(ramla)
            db.commit()
            db.refresh(ramla)
            print(f"Created node: {ramla.name}")
        else:
            print(f"Node already exists: {ramla.name}")

        rack1 = Rack(node_id=ramla.id, name='Rack-A1', location='Row 1, Position 1', rack_unit_size=42, rack_type='standard')
        rack2 = Rack(node_id=ramla.id, name='Rack-A2', location='Row 1, Position 2', rack_unit_size=42, rack_type='standard')
        rack3 = Rack(node_id=ramla.id, name='Rack-B1', location='Row 2, Position 1', rack_unit_size=42, rack_type='standard')
        db.add_all([rack1, rack2, rack3])
        db.commit()
        print(f"Created 3 racks")

        panel1 = Panel(node_id=ramla.id, rack_id=rack1.id, name='PAN-A1-01', physical_type='fiber', connector_type='LC', port_count=24, rack_position=1, rack_units=1)
        panel2 = Panel(node_id=ramla.id, rack_id=rack1.id, name='PAN-A1-02', physical_type='fiber', connector_type='LC', port_count=24, rack_position=2, rack_units=1)
        panel3 = Panel(node_id=ramla.id, rack_id=rack2.id, name='PAN-A2-01', physical_type='copper', connector_type='RJ45', port_count=48, rack_position=1, rack_units=2)
        db.add_all([panel1, panel2, panel3])
        db.commit()
        print(f"Created 3 panels")

        sp1 = SubPanel(panel_id=panel1.id, name='1-A', sub_panel_number=1, port_count=6, description='Row 1, Column A')
        sp2 = SubPanel(panel_id=panel1.id, name='1-B', sub_panel_number=2, port_count=6, description='Row 1, Column B')
        sp3 = SubPanel(panel_id=panel1.id, name='1-C', sub_panel_number=3, port_count=6, description='Row 1, Column C')
        sp4 = SubPanel(panel_id=panel1.id, name='1-D', sub_panel_number=4, port_count=6, description='Row 1, Column D')
        db.add_all([sp1, sp2, sp3, sp4])
        db.commit()
        print(f"Created 4 sub-panels")

        ports = []
        for subp in [sp1, sp2, sp3, sp4]:
            for i in range(1, 7):
                p = Port(
                    panel_id=panel1.id,
                    sub_panel_id=subp.id,
                    name=str(i),
                    port_number=len(ports) + 1,
                    port_type='fiber',
                    connector_type='LC',
                    status='available'
                )
                ports.append(p)
        db.add_all(ports)
        db.commit()
        print(f"Created {len(ports)} ports for panel1")

        agg1 = Device(node_id=ramla.id, rack_id=rack1.id, name='AGG-01', device_type='agg switch', manufacturer='Cisco', model='Catalyst 9300', status='active', rack_position=20, rack_units=1)
        agg2 = Device(node_id=ramla.id, rack_id=rack2.id, name='AGG-02', device_type='agg switch', manufacturer='Juniper', model='EX4300', status='active', rack_position=20, rack_units=1)
        edge1 = Device(node_id=ramla.id, rack_id=rack1.id, name='SW-01', device_type='edge switch', manufacturer='Cisco', model='Catalyst 2960', status='active', rack_position=21, rack_units=1)
        edge2 = Device(node_id=ramla.id, rack_id=rack1.id, name='SW-02', device_type='edge switch', manufacturer='Cisco', model='Catalyst 2960', status='active', rack_position=22, rack_units=1)
        ups1 = Device(node_id=ramla.id, rack_id=rack3.id, name='UPS-01', device_type='ups', manufacturer='APC', model='Smart-UPS 3000', status='active', rack_position=1, rack_units=2)
        db.add_all([agg1, agg2, edge1, edge2, ups1])
        db.commit()
        print(f"Created 5 devices")

        for dev in [agg1, agg2, edge1, edge2]:
            dev_ports = []
            for i in range(1, 25):
                p = Port(device_id=dev.id, name=f'Gi0/{i}', port_number=i, port_type='copper', connector_type='RJ45', status='available')
                dev_ports.append(p)
            db.add_all(dev_ports)
        db.commit()
        print(f"Created ports for all switches")

        print("\nSeed data complete!")
        print(f"  Node: {ramla.name} (id={ramla.id})")
        print(f"  Racks: {rack1.name}, {rack2.name}, {rack3.name}")
        print(f"  Panels: {panel1.name}, {panel2.name}, {panel3.name}")
        print(f"  SubPanels: 4")
        print(f"  Ports: {len(ports)} (panel) + 96 (devices)")
        print(f"  Devices: AGG-01, AGG-02, SW-01, SW-02, UPS-01")

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/backend')
    seed_data()