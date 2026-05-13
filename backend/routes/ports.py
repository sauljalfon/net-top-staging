from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field

from src.db import get_db
from src.models import Node as NodeModel, Panel as PanelModel, Device as DeviceModel, Port as PortModel, SubPanel as SubPanelModel
from src.schemas import Port, PortCreate, PortUpdate

router = APIRouter()


class PortBulkCreate(BaseModel):
    entity_type: str
    entity_id: int
    start_port: int = Field(..., ge=1)
    end_port: int = Field(..., ge=1)
    port_type: Optional[str] = None
    connector_type: Optional[str] = None
    status: Optional[str] = "available"


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def create_ports_bulk(data: PortBulkCreate, db: Session = Depends(get_db)):
    entity_type = (data.entity_type or "").strip().lower()
    if entity_type not in ("panel", "device"):
        raise HTTPException(status_code=400, detail="entity_type must be panel or device")
    if data.end_port < data.start_port:
        raise HTTPException(status_code=400, detail="end_port must be greater than or equal to start_port")

    panel_id = None
    device_id = None
    if entity_type == "panel":
        panel = db.query(PanelModel).filter(PanelModel.id == data.entity_id).first()
        if not panel:
            raise HTTPException(status_code=404, detail="Panel not found")
        panel_id = panel.id
    else:
        device = db.query(DeviceModel).filter(DeviceModel.id == data.entity_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        device_id = device.id

    existing_query = db.query(PortModel)
    if panel_id:
        existing_query = existing_query.filter(PortModel.panel_id == panel_id)
    else:
        existing_query = existing_query.filter(PortModel.device_id == device_id)

    existing_numbers = {
        int(p.port_number) for p in existing_query.all()
        if p.port_number and str(p.port_number).isdigit()
    }

    created = 0
    skipped = 0
    for idx in range(data.start_port, data.end_port + 1):
        if idx in existing_numbers:
            skipped += 1
            continue
        db.add(PortModel(
            name=str(idx),
            port_number=str(idx),
            panel_id=panel_id,
            device_id=device_id,
            port_type=(data.port_type or ("fiber" if panel_id else "ethernet")).lower(),
            connector_type=(data.connector_type or ("RJ45" if device_id else None)),
            status=data.status or "available",
        ))
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "range": [data.start_port, data.end_port]}

@router.get("", response_model=List[Port])
def get_ports(panel_id: Optional[int] = None, device_id: Optional[int] = None, node_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(PortModel).options(
        joinedload(PortModel.sub_panel),
        joinedload(PortModel.panel),
        joinedload(PortModel.device)
    ).outerjoin(PanelModel).outerjoin(DeviceModel)

    if node_id:
        query = query.filter((PanelModel.node_id == node_id) | (DeviceModel.node_id == node_id))
    if panel_id:
        query = query.filter(PortModel.panel_id == panel_id)
    if device_id:
        query = query.filter(PortModel.device_id == device_id)

    return query.all()

@router.get("/{port_id}", response_model=Port)
def get_port(port_id: int, db: Session = Depends(get_db)):
    port = db.query(PortModel).options(
        joinedload(PortModel.sub_panel),
        joinedload(PortModel.panel),
        joinedload(PortModel.device)
    ).filter(PortModel.id == port_id).first()
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")
    return port

@router.post("", response_model=Port, status_code=status.HTTP_201_CREATED)
def create_port(port_in: PortCreate, db: Session = Depends(get_db)):
    if not port_in.panel_id and not port_in.device_id:
        raise HTTPException(status_code=400, detail="Must specify either panel_id or device_id")
    if port_in.panel_id and port_in.device_id:
        raise HTTPException(status_code=400, detail="Cannot specify both panel_id and device_id")

    port_type = (port_in.port_type or '').lower()
    if port_type and port_type not in ('fiber', 'copper'):
        raise HTTPException(status_code=400, detail="port_type must be 'fiber' or 'copper'")

    connector_type = (port_in.connector_type or '').upper() if port_in.connector_type else None
    if port_type == 'fiber':
        if not connector_type:
            raise HTTPException(status_code=400, detail="connector_type is required for fiber ports")

    if port_in.panel_id:
        panel = db.query(PanelModel).filter(PanelModel.id == port_in.panel_id).first()
        if not panel:
            raise HTTPException(status_code=404, detail="Panel not found")

        if port_in.sub_panel_id:
            sub_panel = db.query(SubPanelModel).filter(SubPanelModel.id == port_in.sub_panel_id).first()
            if not sub_panel:
                raise HTTPException(status_code=404, detail="Sub-panel not found")
            if sub_panel.panel_id != port_in.panel_id:
                raise HTTPException(status_code=400, detail="Sub-panel does not belong to the specified panel")

    if port_in.device_id:
        device = db.query(DeviceModel).filter(DeviceModel.id == port_in.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

    port_data = port_in.model_dump()
    port_data['port_type'] = port_type
    port_data['connector_type'] = connector_type

    port = PortModel(**port_data)
    db.add(port)
    db.commit()
    db.refresh(port)
    return port

@router.put("/{port_id}", response_model=Port)
def update_port(port_id: int, port_in: PortUpdate, db: Session = Depends(get_db)):
    port = db.query(PortModel).filter(PortModel.id == port_id).first()
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")

    update_data = port_in.model_dump(exclude_unset=True)

    if "port_type" in update_data and update_data['port_type']:
        pt = update_data['port_type'].lower()
        if pt not in ('fiber', 'copper'):
            raise HTTPException(status_code=400, detail="port_type must be 'fiber' or 'copper'")
        update_data['port_type'] = pt

    if "connector_type" in update_data and update_data['connector_type']:
        update_data['connector_type'] = update_data['connector_type'].upper()

    for key, value in update_data.items():
        setattr(port, key, value)

    db.commit()
    db.refresh(port)
    return port

@router.delete("/{port_id}")
def delete_port(port_id: int, db: Session = Depends(get_db)):
    port = db.query(PortModel).filter(PortModel.id == port_id).first()
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")

    if port.connections or port.connections_b:
        raise HTTPException(status_code=400, detail="Cannot delete a connected port")

    db.delete(port)
    db.commit()
    return {"message": "Port deleted successfully"}
