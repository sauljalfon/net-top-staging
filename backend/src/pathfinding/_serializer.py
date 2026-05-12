"""Serialization helpers for pathfinding results."""

from __future__ import annotations

from typing import Optional

from src.models import Connection, Device, Panel, Port, compute_fiber_pair_display

from ._constants import AGG_KEYWORDS, EDGE_KEYWORDS


def is_aggregation_switch(device: Device) -> bool:
    dtype = (device.device_type or "").lower()
    name = (device.name or "").lower()
    return any(kw in dtype or kw in name for kw in AGG_KEYWORDS)


def is_edge_device(device: Device) -> bool:
    dtype = (device.device_type or "").lower()
    return any(kw in dtype for kw in EDGE_KEYWORDS)


def port_display_name(port: Optional[Port], session=None) -> str:
    if not port:
        return "Unknown"
    display = compute_fiber_pair_display(port, session) if session else port.display_name
    display = display or port.name or "Unknown"
    return f"Port {display}" if str(display).isdigit() else display


def _base_hop(hop_number: int, port: Port, conn: Optional[Connection], session=None) -> dict:
    return {
        "hop_number": hop_number,
        "port_id": port.id,
        "port_name": port.name,
        "port_display_name": port_display_name(port, session),
        "connection_id": conn.id if conn else None,
        "connection_status": conn.status if conn else None,
    }


def device_hop(hop_number: int, port: Port, conn: Optional[Connection], session=None) -> dict:
    dev = port.device
    hop = _base_hop(hop_number, port, conn, session)
    hop.update({
        "type": "device",
        "device_id": dev.id if dev else None,
        "device_name": dev.name if dev else None,
        "device_type": dev.device_type if dev else None,
        "node_name": dev.node.name if dev and dev.node else None,
        "rack_name": dev.rack.name if dev and dev.rack else None,
    })
    return hop


def panel_hop(hop_number: int, port: Port, conn: Optional[Connection], session=None) -> dict:
    pan = port.panel
    hop = _base_hop(hop_number, port, conn, session)
    hop.update({
        "type": "panel",
        "panel_id": pan.id if pan else None,
        "panel_name": pan.name if pan else None,
        "panel_type": pan.physical_type if pan else None,
        "node_name": pan.node.name if pan and pan.node else None,
        "rack_name": pan.rack.name if pan and pan.rack else None,
    })
    return hop


def hop_from_port(hop_number: int, port: Port, conn: Optional[Connection], session=None) -> Optional[dict]:
    if port.device_id:
        return device_hop(hop_number, port, conn, session)
    if port.panel_id:
        return panel_hop(hop_number, port, conn, session)
    return None


def entity_info_from_device(device: Device) -> dict:
    return {
        "type": "device",
        "id": device.id,
        "name": device.name,
        "device_type": device.device_type,
        "node": device.node.name if device.node else None,
        "node_id": device.node_id,
        "site": device.node.site.name if device.node and device.node.site else None,
        "rack": device.rack.name if device.rack else None,
        "rack_id": device.rack_id,
    }


def entity_info_from_panel(panel: Panel) -> dict:
    return {
        "type": "panel",
        "id": panel.id,
        "name": panel.name,
        "physical_type": panel.physical_type,
        "node": panel.node.name if panel.node else None,
        "node_id": panel.node_id,
        "site": panel.node.site.name if panel.node and panel.node.site else None,
        "rack": panel.rack.name if panel.rack else None,
        "rack_id": panel.rack_id,
    }


def entity_info_from_port(port: Port) -> dict:
    info: dict = {
        "type": "port",
        "id": port.id,
        "name": port.name,
        "port_type": port.port_type,
        "parent_type": None,
        "parent_name": None,
        "site": None,
        "node": None,
        "rack": None,
    }
    if port.device:
        dev = port.device
        info.update({
            "parent_type": "device",
            "parent_name": dev.name,
            "node": dev.node.name if dev.node else None,
            "site": dev.node.site.name if dev.node and dev.node.site else None,
            "rack": dev.rack.name if dev.rack else None,
        })
    elif port.panel:
        pan = port.panel
        info.update({
            "parent_type": "panel",
            "parent_name": pan.name,
            "node": pan.node.name if pan.node else None,
            "site": pan.node.site.name if pan.node and pan.node.site else None,
            "rack": pan.rack.name if pan.rack else None,
        })
    return info


def graph_node_from_device(device: Device) -> dict:
    return {
        "id": f"device_{device.id}",
        "type": "device",
        "label": device.name,
        "device_type": device.device_type,
        "is_agg": is_aggregation_switch(device),
        "is_edge": is_edge_device(device),
        "node": device.node.name if device.node else None,
        "node_id": device.node_id,
        "site": device.node.site.name if device.node and device.node.site else None,
        "rack": device.rack.name if device.rack else None,
        "rack_id": device.rack_id,
    }


def graph_node_from_panel(panel: Panel, arriving_port: Optional[Port] = None) -> dict:
    sub_panel_name = None
    if arriving_port and arriving_port.sub_panel:
        sub_panel_name = arriving_port.sub_panel.name
    return {
        "id": f"panel_{panel.id}",
        "type": "panel",
        "label": panel.name,
        "physical_type": panel.physical_type,
        "node": panel.node.name if panel.node else None,
        "node_id": panel.node_id,
        "site": panel.node.site.name if panel.node and panel.node.site else None,
        "rack": panel.rack.name if panel.rack else None,
        "rack_id": panel.rack_id,
        "sub_panel_name": sub_panel_name,
    }


def graph_edge_dict(conn_id: int, source_id: str, target_id: str, from_port: Port, to_port: Port, conn_status: str, session=None) -> dict:
    src = port_display_name(from_port, session)
    tgt = port_display_name(to_port, session)
    return {
        "id": f"edge_{conn_id}",
        "source": source_id,
        "target": target_id,
        "label": f"{src} \u2192 {tgt}",
        "data": {
            "source_port": src,
            "source_port_type": from_port.port_type,
            "source_connector": from_port.connector_type,
            "target_port": tgt,
            "target_port_type": to_port.port_type,
            "target_connector": to_port.connector_type,
            "connection_status": conn_status,
            "connection_id": conn_id,
        },
    }


def bfs_hop(from_port: Port, to_port: Port, conn: Connection, session=None) -> dict:
    hop: dict = {
        "from_port": {
            "id": from_port.id,
            "name": from_port.name,
            "display_name": port_display_name(from_port, session),
        },
        "to_port": {
            "id": to_port.id,
            "name": to_port.name,
            "display_name": port_display_name(to_port, session),
        },
        "connection_status": conn.status,
        "connection_id": conn.id,
    }

    if to_port.device_id and to_port.device:
        dev = to_port.device
        hop.update({
            "to_type": "device",
            "to_id": dev.id,
            "to_name": dev.name,
            "name": dev.name,
            "type": "device",
            "device_name": dev.name,
            "device_type": dev.device_type,
            "node_name": dev.node.name if dev.node else None,
            "rack_name": dev.rack.name if dev.rack else None,
        })
    elif to_port.panel_id and to_port.panel:
        pan = to_port.panel
        hop.update({
            "to_type": "panel",
            "to_id": pan.id,
            "to_name": pan.name,
            "name": pan.name,
            "type": "panel",
            "panel_name": pan.name,
            "physical_type": pan.physical_type,
            "node_name": pan.node.name if pan.node else None,
            "rack_name": pan.rack.name if pan.rack else None,
        })
    return hop