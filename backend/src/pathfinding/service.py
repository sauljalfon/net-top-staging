"""Pathfinding service orchestrators."""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session, selectinload

from src.db import get_db_session
from src.models import Connection, Device, Node, Panel, Port

from ._constants import MAX_DEPTH, MAX_PATHS
from ._serializer import (
    bfs_hop,
    entity_info_from_device,
    entity_info_from_panel,
    entity_info_from_port,
    graph_edge_dict,
    graph_node_from_device,
    graph_node_from_panel,
    hop_from_port,
    is_aggregation_switch,
    is_edge_device,
    port_display_name,
)
from ._traversal import PathStep, all_connections, bfs_direct, dfs_transit, other_end


def _eager_device(session: Session, device_id: int) -> Optional[Device]:
    return (
        session.query(Device)
        .options(
            selectinload(Device.ports).selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.device).selectinload(Device.node),
            selectinload(Device.ports).selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.device).selectinload(Device.rack),
            selectinload(Device.ports).selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.panel).selectinload(Panel.node),
            selectinload(Device.ports).selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.panel).selectinload(Panel.rack),
            selectinload(Device.ports).selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.device).selectinload(Device.node),
            selectinload(Device.ports).selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.device).selectinload(Device.rack),
            selectinload(Device.ports).selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.panel).selectinload(Panel.node),
            selectinload(Device.ports).selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.panel).selectinload(Panel.rack),
            selectinload(Device.ports).selectinload(Port.sub_panel),
            selectinload(Device.node).selectinload(Node.site),
            selectinload(Device.rack),
        )
        .filter_by(id=device_id)
        .first()
    )


def _eager_panel(session: Session, panel_id: int) -> Optional[Panel]:
    return (
        session.query(Panel)
        .options(
            selectinload(Panel.ports).selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.device).selectinload(Device.node),
            selectinload(Panel.ports).selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.panel).selectinload(Panel.node),
            selectinload(Panel.ports).selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.device).selectinload(Device.node),
            selectinload(Panel.ports).selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.panel).selectinload(Panel.node),
            selectinload(Panel.ports).selectinload(Port.sub_panel),
            selectinload(Panel.node).selectinload(Node.site),
            selectinload(Panel.rack),
        )
        .filter_by(id=panel_id)
        .first()
    )


def _eager_port(session: Session, port_id: int) -> Optional[Port]:
    return (
        session.query(Port)
        .options(
            selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.device).selectinload(Device.node),
            selectinload(Port.connections).selectinload(Connection.port_b).selectinload(Port.panel).selectinload(Panel.node),
            selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.device).selectinload(Device.node),
            selectinload(Port.connections_b).selectinload(Connection.port_a).selectinload(Port.panel).selectinload(Panel.node),
            selectinload(Port.sub_panel),
            selectinload(Port.device).selectinload(Device.node).selectinload(Node.site),
            selectinload(Port.device).selectinload(Device.rack),
            selectinload(Port.panel).selectinload(Panel.node).selectinload(Node.site),
            selectinload(Port.panel).selectinload(Panel.rack),
        )
        .filter_by(id=port_id)
        .first()
    )


def _resolve_entity(session: Session, entity_type: str, entity_id: int) -> Tuple[dict, List[Port]]:
    if entity_type == "device":
        device = _eager_device(session, entity_id)
        if not device:
            raise ValueError(f"Device {entity_id} not found")
        return entity_info_from_device(device), list(device.ports)

    if entity_type == "panel":
        panel = _eager_panel(session, entity_id)
        if not panel:
            raise ValueError(f"Panel {entity_id} not found")
        return entity_info_from_panel(panel), list(panel.ports)

    if entity_type == "port":
        port = _eager_port(session, entity_id)
        if not port:
            raise ValueError(f"Port {entity_id} not found")
        return entity_info_from_port(port), [port]

    raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'device', 'panel', or 'port'.")


def find_path_from_device_to_agg(device_id: int) -> Dict:
    with get_db_session() as session:
        device = _eager_device(session, device_id)
        if not device:
            return {"path": [], "reached_agg": False, "agg_device": None, "total_hops": 0, "error": "Device not found"}

        if is_aggregation_switch(device):
            first_port = device.ports[0] if device.ports else None
            hop = hop_from_port(1, first_port, None, session) if first_port else {}
            return {
                "path": [hop] if hop else [],
                "reached_agg": True,
                "agg_device": {"id": device.id, "name": device.name, "type": device.device_type},
                "total_hops": 1 if hop else 0,
            }

        def _is_agg_port(port: Port) -> bool:
            return bool(port.device_id and port.device and is_aggregation_switch(port.device))

        best: Optional[Dict] = None
        found_agg = False

        for start_port in device.ports:
            if found_agg:
                break
            for path_steps in dfs_transit(start_port, None, MAX_DEPTH, stop_at=_is_agg_port):
                hops = [
                    hop_from_port(i, port, conn, session)
                    for i, (port, conn) in enumerate(path_steps, start=1)
                ]
                hops = [h for h in hops if h]

                last_port = path_steps[-1][0] if path_steps else None
                reached_agg = bool(
                    last_port
                    and last_port.device_id
                    and last_port.device
                    and is_aggregation_switch(last_port.device)
                )
                agg_device = None
                if reached_agg and last_port and last_port.device:
                    d = last_port.device
                    agg_device = {"id": d.id, "name": d.name, "type": d.device_type}

                candidate = {
                    "path": hops,
                    "reached_agg": reached_agg,
                    "agg_device": agg_device,
                    "total_hops": len(hops),
                }

                if reached_agg:
                    best = candidate
                    found_agg = True
                    break
                if best is None or len(hops) > best["total_hops"]:
                    best = candidate

        return best or {"path": [], "reached_agg": False, "agg_device": None, "total_hops": 0}


def find_all_paths_from_agg(agg_device_id: int, max_paths: int = MAX_PATHS) -> Dict:
    with get_db_session() as session:
        agg_device = _eager_device(session, agg_device_id)
        if not agg_device:
            return {"paths": [], "agg_device": None, "total_paths": 0, "edge_devices_reached": [], "error": "Aggregation device not found"}

        if not is_aggregation_switch(agg_device):
            return {
                "paths": [],
                "agg_device": {"id": agg_device.id, "name": agg_device.name},
                "total_paths": 0,
                "edge_devices_reached": [],
                "error": "Device is not an aggregation switch",
            }

        all_paths: List[Dict] = []
        edge_devices: Set[int] = set()

        for start_port in agg_device.ports:
            if len(all_paths) >= max_paths:
                break
            for path_steps in dfs_transit(start_port, None, MAX_DEPTH):
                if len(all_paths) >= max_paths:
                    break
                hops = [
                    hop_from_port(i, port, conn, session)
                    for i, (port, conn) in enumerate(path_steps, start=1)
                ]
                hops = [h for h in hops if h]

                last_port = path_steps[-1][0] if path_steps else None
                end_device = None
                if last_port and last_port.device_id and last_port.device:
                    d = last_port.device
                    end_device = {"id": d.id, "name": d.name, "type": d.device_type}
                    edge_devices.add(d.id)

                all_paths.append({"path": hops, "end_device": end_device, "total_hops": len(hops)})

        return {
            "paths": all_paths,
            "agg_device": {"id": agg_device.id, "name": agg_device.name, "type": agg_device.device_type},
            "total_paths": len(all_paths),
            "edge_devices_reached": list(edge_devices),
        }


def find_full_bidirectional_paths(agg_device_id: int, max_paths: int = 50) -> Dict:
    result = find_all_paths_from_agg(agg_device_id, max_paths)
    return {
        "agg_device": result["agg_device"],
        "downstream_paths": result["paths"],
        "total_downstream_paths": result["total_paths"],
        "edge_devices_reached": result["edge_devices_reached"],
        "total_edge_devices": len(result["edge_devices_reached"]),
    }


def find_all_paths_from_entity(entity_type: str, entity_id: int, max_paths: int = MAX_PATHS, max_depth: int = MAX_DEPTH) -> Dict:
    with get_db_session() as session:
        entity_info, starting_ports = _resolve_entity(session, entity_type, entity_id)

        root_id = f"{entity_type}_{entity_id}"
        graph_nodes: Dict[str, dict] = {
            root_id: {
                "id": root_id,
                "type": entity_type,
                "label": entity_info.get("name", ""),
                "site": entity_info.get("site"),
                "node": entity_info.get("node"),
                "rack": entity_info.get("rack"),
                "data": entity_info,
            }
        }
        graph_edges: List[dict] = []
        all_paths: List[List[dict]] = []
        connected_devices: Set[int] = set()
        connected_panels: Set[int] = set()
        agg_switches: Set[int] = set()
        edge_devices_set: Set[int] = set()

        for port, conn, _depth in bfs_direct(starting_ports, max_depth):
            if len(all_paths) >= max_paths:
                break
            if conn is None:
                continue

            other = other_end(conn, port)
            if not other:
                continue

            hop: dict = {
                "from_port": {
                    "id": port.id,
                    "name": port.name,
                    "display_name": port_display_name(port, session),
                    "sub_panel_name": port.sub_panel.name if port.sub_panel else None,
                },
                "to_port": {
                    "id": other.id,
                    "name": other.name,
                    "display_name": port_display_name(other, session),
                    "sub_panel_name": other.sub_panel.name if other.sub_panel else None,
                },
                "connection_status": conn.status,
                "connection_id": conn.id,
            }

            source_id = _graph_id_for_port(port, root_id)

            if source_id not in graph_nodes:
                if port.panel_id and port.panel:
                    graph_nodes[source_id] = graph_node_from_panel(port.panel, port)
                    connected_panels.add(port.panel_id)
                elif port.device_id and port.device:
                    graph_nodes[source_id] = graph_node_from_device(port.device)
                    connected_devices.add(port.device_id)

            if other.device_id and other.device:
                dev = other.device
                node_id = f"device_{dev.id}"
                connected_devices.add(dev.id)
                if node_id not in graph_nodes:
                    graph_nodes[node_id] = graph_node_from_device(dev)
                if is_aggregation_switch(dev):
                    agg_switches.add(dev.id)
                if is_edge_device(dev):
                    edge_devices_set.add(dev.id)
                hop.update({"to_type": "device", "to_id": dev.id, "to_name": dev.name, "device_type": dev.device_type})
                graph_edges.append(graph_edge_dict(conn.id, source_id, node_id, port, other, conn.status, session))

            elif other.panel_id and other.panel:
                pan = other.panel
                node_id = f"panel_{pan.id}"
                connected_panels.add(pan.id)
                if node_id not in graph_nodes:
                    graph_nodes[node_id] = graph_node_from_panel(pan, other)
                hop.update({"to_type": "panel", "to_id": pan.id, "to_name": pan.name, "physical_type": pan.physical_type})
                graph_edges.append(graph_edge_dict(conn.id, source_id, node_id, port, other, conn.status, session))

            all_paths.append([hop])

        all_paths.sort(key=len, reverse=True)

        return {
            "entity_info": entity_info,
            "all_paths": all_paths[:max_paths],
            "connected_devices": list(connected_devices),
            "connected_panels": list(connected_panels),
            "agg_switches": list(agg_switches),
            "edge_devices": list(edge_devices_set),
            "total_paths": len(all_paths),
            "graph_data": {"nodes": list(graph_nodes.values()), "edges": graph_edges},
        }


def _graph_id_for_port(port: Port, root_id: str) -> str:
    if port.device_id:
        return f"device_{port.device_id}"
    if port.panel_id:
        return f"panel_{port.panel_id}"
    return root_id


def find_path_between_ports(from_port_id: int, to_port_id: int, max_depth: int = MAX_DEPTH) -> Dict:
    with get_db_session() as session:
        from_port = _eager_port(session, from_port_id)
        if not from_port:
            raise ValueError(f"Source port {from_port_id} not found")

        to_port = _eager_port(session, to_port_id)
        if not to_port:
            raise ValueError(f"Destination port {to_port_id} not found")

        if from_port_id == to_port_id:
            raise ValueError("Cannot connect a port to itself")

        source_info = entity_info_from_port(from_port)
        dest_info = entity_info_from_port(to_port)

        queue: deque = deque([(from_port, [])])
        visited: Set[int] = {from_port_id}
        found_path: Optional[List[dict]] = None

        while queue and not found_path:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for conn in all_connections(current):
                other = other_end(conn, current)
                if not other or other.id in visited:
                    continue
                hop = bfs_hop(current, other, conn, session)
                new_path = path + [hop]
                if other.id == to_port_id:
                    found_path = new_path
                    break
                visited.add(other.id)
                queue.append((other, new_path))

        panels_crossed = sum(1 for h in (found_path or []) if h.get("to_type") == "panel")
        devices_crossed = sum(1 for h in (found_path or []) if h.get("to_type") == "device")

        return {
            "source": source_info,
            "destination": dest_info,
            "path_found": found_path is not None,
            "path": found_path or [],
            "hops": found_path or [],
            "summary": {
                "total_hops": len(found_path) if found_path else 0,
                "panels_crossed": panels_crossed,
                "devices_crossed": devices_crossed,
                "direct_connection": found_path is None,
            },
        }