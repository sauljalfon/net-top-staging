from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload

from src.db import get_db
from src.models import Node as NodeModel, Rack as RackModel, Panel as PanelModel
from src.schemas import Panel, PanelCreate, PanelUpdate

router = APIRouter()

@router.get("", response_model=List[Panel])
def get_panels(node_id: Optional[int] = None, rack_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(PanelModel).options(
        joinedload(PanelModel.node),
        joinedload(PanelModel.rack),
        selectinload(PanelModel.ports),
        selectinload(PanelModel.sub_panels),
    )
    if node_id:
        query = query.filter(PanelModel.node_id == node_id)
    if rack_id:
        query = query.filter(PanelModel.rack_id == rack_id)
    return query.all()

@router.get("/{panel_id}", response_model=Panel)
def get_panel(panel_id: int, db: Session = Depends(get_db)):
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    return panel

@router.post("", response_model=Panel, status_code=status.HTTP_201_CREATED)
def create_panel(panel_in: PanelCreate, db: Session = Depends(get_db)):
    physical = (panel_in.physical_type or '').lower()
    connector = (panel_in.connector_type or '').upper()

    if physical == 'ethernet' and connector != 'RJ45':
        raise HTTPException(status_code=400, detail="For ethernet panels connector_type must be 'RJ45'")
    if physical == 'fiber' and connector not in ('LC', 'SC', 'MPO', 'ST', 'FC'):
        raise HTTPException(status_code=400, detail="For fiber panels connector_type must be one of LC/SC/MPO/ST/FC")

    node = db.query(NodeModel).filter(NodeModel.id == panel_in.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if panel_in.rack_id:
        rack = db.query(RackModel).filter(
            RackModel.id == panel_in.rack_id,
            RackModel.node_id == panel_in.node_id
        ).first()
        if not rack:
            raise HTTPException(status_code=404, detail="Rack not found or does not belong to the specified node")

    panel_data = panel_in.model_dump()
    panel_data['physical_type'] = physical
    panel_data['connector_type'] = connector

    panel = PanelModel(**panel_data)
    db.add(panel)
    db.commit()
    db.refresh(panel)
    return panel

@router.put("/{panel_id}", response_model=Panel)
def update_panel(panel_id: int, panel_in: PanelUpdate, db: Session = Depends(get_db)):
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    update_data = panel_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(panel, key, value)

    db.commit()
    db.refresh(panel)
    return panel

@router.delete("/{panel_id}")
def delete_panel(panel_id: int, db: Session = Depends(get_db)):
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    db.delete(panel)
    db.commit()
    return {"message": "Panel deleted successfully"}