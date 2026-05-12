from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload

from src.db import get_db
from src.models import Node as NodeModel, Rack as RackModel
from src.schemas import Rack, RackCreate, RackUpdate

router = APIRouter()

@router.get("", response_model=List[Rack])
def get_racks(node_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(RackModel).options(
        joinedload(RackModel.node),
        selectinload(RackModel.panels),
        selectinload(RackModel.devices),
    )
    if node_id:
        query = query.filter(RackModel.node_id == node_id)
    return query.all()

@router.post("", response_model=Rack, status_code=status.HTTP_201_CREATED)
def create_rack(rack_in: RackCreate, db: Session = Depends(get_db)):
    node = db.query(NodeModel).filter(NodeModel.id == rack_in.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    rack = RackModel(**rack_in.model_dump())
    db.add(rack)
    db.commit()
    db.refresh(rack)
    return rack

@router.put("/{rack_id}", response_model=Rack)
def update_rack(rack_id: int, rack_in: RackUpdate, db: Session = Depends(get_db)):
    rack = db.query(RackModel).filter(RackModel.id == rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")

    update_data = rack_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rack, key, value)

    db.commit()
    db.refresh(rack)
    return rack

@router.delete("/{rack_id}")
def delete_rack(rack_id: int, db: Session = Depends(get_db)):
    rack = db.query(RackModel).filter(RackModel.id == rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")

    db.delete(rack)
    db.commit()
    return {"message": "Rack deleted successfully"}