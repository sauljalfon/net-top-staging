from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from src.db import get_db
from src.models import Node as NodeModel, Rack as RackModel, Panel as PanelModel, Device as DeviceModel, Port as PortModel, SubPanel as SubPanelModel
from src.schemas import Node, NodeCreate, NodeUpdate

router = APIRouter()

@router.get("", response_model=List[Node])
def get_nodes(site_id: Optional[int] = None, name: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(NodeModel)
    if site_id:
        query = query.filter(NodeModel.site_id == site_id)
    if name:
        query = query.filter(NodeModel.name.ilike(f"%{name}%"))

    return query.options(
        selectinload(NodeModel.site),
        selectinload(NodeModel.racks),
        selectinload(NodeModel.panels),
        selectinload(NodeModel.devices)
    ).all()

@router.get("/{node_id}", response_model=Node)
def get_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node

@router.post("", response_model=Node, status_code=status.HTTP_201_CREATED)
def create_node(node_in: NodeCreate, db: Session = Depends(get_db)):
    node = NodeModel(**node_in.model_dump())
    try:
        db.add(node)
        db.commit()
        db.refresh(node)
    except Exception as e:
        db.rollback()
        raise e
    return node

@router.put("/{node_id}", response_model=Node)
def update_node(node_id: int, node_in: NodeUpdate, db: Session = Depends(get_db)):
    node = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    update_data = node_in.model_dump(exclude_unset=True)

    if "location" in update_data:
        existing = db.query(NodeModel).filter(
            NodeModel.site_id == node.site_id,
            NodeModel.location == update_data["location"],
            NodeModel.id != node_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="A node with this location already exists in this site")

    for key, value in update_data.items():
        setattr(node, key, value)

    db.commit()
    db.refresh(node)
    return node

@router.delete("/{node_id}")
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    db.delete(node)
    db.commit()
    return {"message": "Node deleted successfully"}