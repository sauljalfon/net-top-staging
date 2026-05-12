from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.db import get_db
from src.models import Node as NodeModel, Panel as PanelModel, Device as DeviceModel, Port as PortModel, SubPanel as SubPanelModel
from src.schemas import Port, PortCreate, PortUpdate

router = APIRouter()

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

    db.delete(port)
    db.commit()
    return {"message": "Port deleted successfully"}