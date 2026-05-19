from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.db import get_db
from src.models import Port as PortModel, Connection as ConnectionModel, Panel as PanelModel, Device as DeviceModel
from src.schemas import ConnectionCreate, ConnectionUpdate

router = APIRouter()


def _get_port_node_info(port):
    if port.panel:
        return port.panel.node_id, port.panel.node.name if port.panel.node else None
    if port.device:
        return port.device.node_id, port.device.node.name if port.device.node else None
    return None, None


def _serialize_connection(conn, port_a, port_b):
    port_a_node_id, port_a_node_name = _get_port_node_info(port_a)
    port_b_node_id, port_b_node_name = _get_port_node_info(port_b)

    def _display_name(port):
        if port and port.sub_panel:
            return f"[{port.sub_panel.name}] {port.name}"
        return port.name if port else None

    return {
        'id': conn.id,
        'port_a_id': conn.port_a_id,
        'port_a_name': port_a.name,
        'port_a_display_name': _display_name(port_a),
        'port_a_number': port_a.port_number,
        'port_a_type': port_a.port_type,
        'port_a_node_id': port_a_node_id,
        'port_a_node_name': port_a_node_name,
        'port_a_panel_id': port_a.panel_id,
        'port_a_panel_name': port_a.panel.name if port_a.panel else None,
        'port_a_device_id': port_a.device_id,
        'port_a_device_name': port_a.device.name if port_a.device else None,
        'port_b_id': conn.port_b_id,
        'port_b_name': port_b.name,
        'port_b_display_name': _display_name(port_b),
        'port_b_number': port_b.port_number if port_b else None,
        'port_b_type': port_b.port_type if port_b else None,
        'port_b_node_id': port_b_node_id,
        'port_b_node_name': port_b_node_name,
        'port_b_panel_id': port_b.panel_id if port_b else None,
        'port_b_panel_name': port_b.panel.name if port_b and port_b.panel else None,
        'port_b_device_id': port_b.device_id if port_b else None,
        'port_b_device_name': port_b.device.name if port_b and port_b.device else None,
        'status': conn.status,
        'notes': conn.notes,
        'created_at': conn.created_at.isoformat() if conn.created_at else None
    }


@router.get("", response_model=List[dict])
def get_connections(node_id: Optional[int] = None, panel_id: Optional[int] = None, device_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(ConnectionModel).options(
        joinedload(ConnectionModel.port_a).joinedload(PortModel.sub_panel),
        joinedload(ConnectionModel.port_a).joinedload(PortModel.panel).joinedload(PanelModel.node),
        joinedload(ConnectionModel.port_a).joinedload(PortModel.device).joinedload(DeviceModel.node),
        joinedload(ConnectionModel.port_b).joinedload(PortModel.sub_panel),
        joinedload(ConnectionModel.port_b).joinedload(PortModel.panel).joinedload(PanelModel.node),
        joinedload(ConnectionModel.port_b).joinedload(PortModel.device).joinedload(DeviceModel.node),
    )

    if panel_id:
        from sqlalchemy import or_
        port_a_alias = db.query(PortModel.id).filter(PortModel.panel_id == panel_id).subquery()
        port_b_alias = db.query(PortModel.id).filter(PortModel.panel_id == panel_id).subquery()
        query = query.filter(
            or_(ConnectionModel.port_a_id.in_(port_a_alias), ConnectionModel.port_b_id.in_(port_b_alias))
        )
    elif device_id:
        from sqlalchemy import or_
        port_a_alias = db.query(PortModel.id).filter(PortModel.device_id == device_id).subquery()
        port_b_alias = db.query(PortModel.id).filter(PortModel.device_id == device_id).subquery()
        query = query.filter(
            or_(ConnectionModel.port_a_id.in_(port_a_alias), ConnectionModel.port_b_id.in_(port_b_alias))
        )
    elif node_id:
        query = (query
            .join(PortModel, ConnectionModel.port_a_id == PortModel.id)
            .outerjoin(PanelModel, PortModel.panel_id == PanelModel.id)
            .outerjoin(DeviceModel, PortModel.device_id == DeviceModel.id)
            .filter((PanelModel.node_id == node_id) | (DeviceModel.node_id == node_id)))

    connections = query.all()
    return [_serialize_connection(conn, conn.port_a, conn.port_b) for conn in connections]


@router.get("/{connection_id}", response_model=dict)
def get_connection(connection_id: int, db: Session = Depends(get_db)):
    conn = db.query(ConnectionModel).filter(ConnectionModel.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _serialize_connection(conn, conn.port_a, conn.port_b)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_connection(conn_in: ConnectionCreate, db: Session = Depends(get_db)):
    if conn_in.port_a_id == conn_in.port_b_id:
        raise HTTPException(status_code=400, detail="Cannot connect a port to itself")

    port_a = db.query(PortModel).filter(PortModel.id == conn_in.port_a_id).first()
    if not port_a:
        raise HTTPException(status_code=404, detail="Port A not found")

    port_b = db.query(PortModel).filter(PortModel.id == conn_in.port_b_id).first()
    if not port_b:
        raise HTTPException(status_code=404, detail="Port B not found")

    normalized_port_a_id = min(conn_in.port_a_id, conn_in.port_b_id)
    normalized_port_b_id = max(conn_in.port_a_id, conn_in.port_b_id)

    existing = db.query(ConnectionModel).filter(
        ((ConnectionModel.port_a_id == normalized_port_a_id) & (ConnectionModel.port_b_id == normalized_port_b_id)) |
        ((ConnectionModel.port_a_id == normalized_port_b_id) & (ConnectionModel.port_b_id == normalized_port_a_id))
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="These ports are already connected")

    port_a_connections = db.query(ConnectionModel).filter(
        (ConnectionModel.port_a_id == conn_in.port_a_id) | (ConnectionModel.port_b_id == conn_in.port_a_id)
    ).first()

    if port_a_connections:
        raise HTTPException(status_code=409, detail=f"Port '{port_a.name}' is already connected to another port")

    port_b_connections = db.query(ConnectionModel).filter(
        (ConnectionModel.port_a_id == conn_in.port_b_id) | (ConnectionModel.port_b_id == conn_in.port_b_id)
    ).first()

    if port_b_connections:
        raise HTTPException(status_code=409, detail=f"Port '{port_b.name}' is already connected to another port")

    connection = ConnectionModel(
        port_a_id=normalized_port_a_id,
        port_b_id=normalized_port_b_id,
        status=conn_in.status or 'active',
        notes=conn_in.notes
    )
    db.add(connection)

    port_a.status = 'in_use'
    port_b.status = 'in_use'

    db.commit()
    db.refresh(connection)

    return get_connection(connection.id, db)


@router.put("/{connection_id}", response_model=dict)
def update_connection(connection_id: int, conn_in: ConnectionUpdate, db: Session = Depends(get_db)):
    connection = db.query(ConnectionModel).filter(ConnectionModel.id == connection_id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    for key, value in conn_in.model_dump(exclude_unset=True).items():
        setattr(connection, key, value)

    db.commit()
    return get_connection(connection.id, db)


@router.delete("/{connection_id}")
def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    connection = db.query(ConnectionModel).filter(ConnectionModel.id == connection_id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    port_a_id = connection.port_a_id
    port_b_id = connection.port_b_id

    db.delete(connection)
    db.flush()

    port_a = db.query(PortModel).filter(PortModel.id == port_a_id).first()
    port_b = db.query(PortModel).filter(PortModel.id == port_b_id).first()

    if port_a:
        port_a.status = 'available'
    if port_b:
        port_b.status = 'available'

    db.commit()
    return {"message": "Connection deleted successfully"}
