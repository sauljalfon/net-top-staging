from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db import get_db
from src.models import SubPanel as SubPanelModel, Panel as PanelModel, Port as PortModel
from src.schemas import SubPanel, SubPanelCreate, SubPanelUpdate

router = APIRouter()

@router.get("", response_model=List[SubPanel])
def get_sub_panels(panel_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(SubPanelModel)
    if panel_id:
        query = query.filter(SubPanelModel.panel_id == panel_id)
    return query.order_by(SubPanelModel.panel_id, SubPanelModel.sub_panel_number).all()

@router.get("/{sub_panel_id}", response_model=SubPanel)
def get_sub_panel(sub_panel_id: int, db: Session = Depends(get_db)):
    sp = db.query(SubPanelModel).filter_by(id=sub_panel_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Sub-panel not found")
    return sp

@router.post("", response_model=SubPanel, status_code=status.HTTP_201_CREATED)
def create_sub_panel(sp_in: SubPanelCreate, db: Session = Depends(get_db)):
    panel = db.query(PanelModel).filter_by(id=sp_in.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail=f"Panel with ID {sp_in.panel_id} not found")

    if sp_in.port_count <= 0:
        raise HTTPException(status_code=400, detail="port_count must be a positive integer")
    if sp_in.sub_panel_number <= 0:
        raise HTTPException(status_code=400, detail="sub_panel_number must be a positive integer")

    existing = db.query(SubPanelModel).filter_by(
        panel_id=sp_in.panel_id,
        sub_panel_number=sp_in.sub_panel_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Sub-panel number {sp_in.sub_panel_number} already exists for this panel")

    sub_panel = SubPanelModel(**sp_in.model_dump())
    db.add(sub_panel)
    db.commit()
    db.refresh(sub_panel)

    return sub_panel

@router.put("/{sub_panel_id}", response_model=SubPanel)
def update_sub_panel(sub_panel_id: int, sp_in: SubPanelUpdate, db: Session = Depends(get_db)):
    sp = db.query(SubPanelModel).filter_by(id=sub_panel_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Sub-panel not found")

    update_data = sp_in.model_dump(exclude_unset=True)

    if 'sub_panel_number' in update_data:
        num = update_data['sub_panel_number']
        if num <= 0:
            raise HTTPException(status_code=400, detail="sub_panel_number must be a positive integer")
        existing = db.query(SubPanelModel).filter(
            SubPanelModel.panel_id == sp.panel_id,
            SubPanelModel.sub_panel_number == num,
            SubPanelModel.id != sub_panel_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Sub-panel number {num} already exists for this panel")

    if 'port_count' in update_data:
        if update_data['port_count'] <= 0:
            raise HTTPException(status_code=400, detail="port_count must be a positive integer")

    for key, value in update_data.items():
        setattr(sp, key, value)

    db.commit()
    db.refresh(sp)
    return sp

@router.delete("/{sub_panel_id}")
def delete_sub_panel(sub_panel_id: int, db: Session = Depends(get_db)):
    sp = db.query(SubPanelModel).filter_by(id=sub_panel_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Sub-panel not found")

    db.query(PortModel).filter(PortModel.sub_panel_id == sub_panel_id).delete()
    db.delete(sp)
    db.commit()
    return {"message": f"Sub-panel {sp.name} and associated ports deleted successfully"}