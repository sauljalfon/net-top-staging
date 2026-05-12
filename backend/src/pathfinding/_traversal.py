"""Graph traversal algorithms for the pathfinding service."""

from __future__ import annotations

from collections import deque
from typing import Iterator, List, Optional, Set, Tuple

from src.models import Connection, Port

PathStep = Tuple[Port, Optional[Connection]]


def all_connections(port: Port) -> List[Connection]:
    return list(port.connections) + list(port.connections_b)


def other_end(conn: Connection, port: Port) -> Optional[Port]:
    return conn.port_b if conn.port_a_id == port.id else conn.port_a


def sibling_ports(port: Port) -> List[Port]:
    if port.device:
        return [p for p in port.device.ports if p.id != port.id]
    if port.panel:
        return [p for p in port.panel.ports if p.id != port.id]
    return []


def bfs_direct(
    start_ports: List[Port],
    max_depth: int,
) -> Iterator[Tuple[Port, Optional[Connection], int]]:
    visited: Set[int] = set()
    queue: deque = deque()

    for p in start_ports:
        if p.id not in visited:
            visited.add(p.id)
            queue.append((p, None, 0))

    while queue:
        port, conn, depth = queue.popleft()
        yield port, conn, depth

        if depth >= max_depth:
            continue

        for c in all_connections(port):
            other = other_end(c, port)
            if other and other.id not in visited:
                visited.add(other.id)
                queue.append((other, c, depth + 1))


def dfs_transit(
    start_port: Port,
    start_conn: Optional[Connection],
    max_depth: int,
    stop_at=None,
) -> Iterator[List[PathStep]]:
    visited: Set[int] = {start_port.id}
    path: List[PathStep] = [(start_port, start_conn)]

    def _recurse(port: Port, conn: Optional[Connection], depth: int) -> Iterator[List[PathStep]]:
        if stop_at is not None and stop_at(port):
            yield list(path)
            return

        found_next = False

        if depth < max_depth:
            for next_port, next_conn in _transit_neighbors(port, conn):
                if next_port.id in visited:
                    continue
                found_next = True
                visited.add(next_port.id)
                path.append((next_port, next_conn))
                yield from _recurse(next_port, next_conn, depth + 1)
                path.pop()
                visited.discard(next_port.id)

        if not found_next:
            yield list(path)

    def _transit_neighbors(
        port: Port,
        prev_conn: Optional[Connection],
    ) -> Iterator[PathStep]:
        for sibling in sibling_ports(port):
            for conn in all_connections(sibling):
                if prev_conn and conn.id == prev_conn.id:
                    continue
                other = other_end(conn, sibling)
                if other:
                    yield other, conn

    yield from _recurse(start_port, start_conn, 0)