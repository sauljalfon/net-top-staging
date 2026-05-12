from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload
import ipaddress

from src.db import get_db
from src.models import Node as NodeModel, Rack as RackModel, Device as DeviceModel
from src.schemas import Device, DeviceCreate, DeviceUpdate

router = APIRouter()

NETWORK_CHOICES = ['Clicknet', 'Ezrahi Tahor', 'Clickfree', 'Shahor Zahav', 'Tzavar', 'Katom', 'Other']
NETWORK_LOOKUP = {choice.lower(): choice for choice in NETWORK_CHOICES}
ALLOWED_TYPES = ['edge switch', 'agg switch', 'router', 'ups', 'other']

@router.get("", response_model=List[Device])
def get_devices(node_id: Optional[int] = None, rack_id: Optional[int] = None, name: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DeviceModel).options(
        joinedload(DeviceModel.node),
        joinedload(DeviceModel.rack),
        selectinload(DeviceModel.ports),
    )
    if node_id:
        query = query.filter(DeviceModel.node_id == node_id)
    if rack_id:
        query = query.filter(DeviceModel.rack_id == rack_id)
    if name:
        query = query.filter(DeviceModel.name.ilike(f"%{name}%"))
    return query.all()

@router.get("/{device_id}", response_model=Device)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.post("", response_model=Device, status_code=status.HTTP_201_CREATED)
def create_device(device_in: DeviceCreate, db: Session = Depends(get_db)):
    if device_in.device_type and device_in.device_type.lower() not in [t.lower() for t in ALLOWED_TYPES]:
        raise HTTPException(status_code=400, detail=f"Invalid device_type. Allowed: {', '.join(ALLOWED_TYPES)}")

    normalized_network = None
    if device_in.network:
        normalized_network = NETWORK_LOOKUP.get(str(device_in.network).strip().lower())
        if not normalized_network:
            raise HTTPException(status_code=400, detail=f"Invalid network. Allowed: {', '.join(NETWORK_CHOICES)}")

    node = db.query(NodeModel).filter(NodeModel.id == device_in.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if device_in.rack_id:
        rack = db.query(RackModel).filter(
            RackModel.id == device_in.rack_id,
            RackModel.node_id == device_in.node_id
        ).first()
        if not rack:
            raise HTTPException(status_code=404, detail="Rack not found or does not belong to the specified node")

    if device_in.rack_position is not None and device_in.rack_position <= 0:
        raise HTTPException(status_code=400, detail="rack_position must be a positive integer")

    if device_in.ip_address:
        try:
            ipaddress.ip_address(device_in.ip_address)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid ip_address")

    normalized_type = None
    if device_in.device_type:
        for t in ALLOWED_TYPES:
            if device_in.device_type.lower() == t.lower():
                normalized_type = t
                break

    device_data = device_in.model_dump()
    device_data['device_type'] = normalized_type or device_in.device_type
    device_data['network'] = normalized_network

    device = DeviceModel(**device_data)
    try:
        db.add(device)
        db.commit()
        db.refresh(device)
    except Exception as e:
        db.rollback()
        raise e

    return device

@router.put("/{device_id}", response_model=Device)
def update_device(device_id: int, device_in: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    update_data = device_in.model_dump(exclude_unset=True)

    if "device_type" in update_data and update_data["device_type"]:
        if update_data["device_type"].lower() not in [t.lower() for t in ALLOWED_TYPES]:
            raise HTTPException(status_code=400, detail=f"Invalid device_type. Allowed: {', '.join(ALLOWED_TYPES)}")
        for t in ALLOWED_TYPES:
            if update_data['device_type'].lower() == t.lower():
                update_data['device_type'] = t
                break

    if "network" in update_data and update_data["network"]:
        normalized_network = NETWORK_LOOKUP.get(str(update_data['network']).strip().lower())
        if not normalized_network:
            raise HTTPException(status_code=400, detail=f"Invalid network. Allowed: {', '.join(NETWORK_CHOICES)}")
        update_data['network'] = normalized_network

    if "ip_address" in update_data and update_data["ip_address"]:
        try:
            ipaddress.ip_address(update_data['ip_address'])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid ip_address")

    for key, value in update_data.items():
        setattr(device, key, value)

    db.commit()
    db.refresh(device)
    return device

@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    db.delete(device)
    db.commit()
    return {"message": "Device deleted successfully"}