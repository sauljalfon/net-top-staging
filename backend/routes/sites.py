from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from src.db import get_db
from src.models import Site as SiteModel
from src.schemas import Site, SiteCreate, SiteUpdate

router = APIRouter()

@router.get("", response_model=List[Site])
def get_sites(name: str = None, db: Session = Depends(get_db)):
    query = db.query(SiteModel)
    if name:
        query = query.filter(SiteModel.name.ilike(f"%{name}%"))
    sites = query.options(selectinload(SiteModel.nodes)).all()
    return sites

@router.get("/{site_id}", response_model=Site)
def get_site(site_id: int, db: Session = Depends(get_db)):
    site = db.query(SiteModel).filter(SiteModel.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site

@router.post("", response_model=Site, status_code=status.HTTP_201_CREATED)
def create_site(site_in: SiteCreate, db: Session = Depends(get_db)):
    if db.query(SiteModel).filter(SiteModel.name == site_in.name).first():
        raise HTTPException(status_code=409, detail="Site with this name already exists")

    site = SiteModel(**site_in.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site

@router.put("/{site_id}", response_model=Site)
def update_site(site_id: int, site_in: SiteUpdate, db: Session = Depends(get_db)):
    site = db.query(SiteModel).filter(SiteModel.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    update_data = site_in.model_dump(exclude_unset=True)
    if "name" in update_data:
        existing = db.query(SiteModel).filter(SiteModel.name == update_data["name"]).first()
        if existing and existing.id != site_id:
            raise HTTPException(status_code=409, detail="Site with this name already exists")

    for key, value in update_data.items():
        setattr(site, key, value)

    db.commit()
    db.refresh(site)
    return site

@router.delete("/{site_id}")
def delete_site(site_id: int, db: Session = Depends(get_db)):
    site = db.query(SiteModel).filter(SiteModel.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    db.delete(site)
    db.commit()
    return {"message": f"Site {site_id} deleted successfully"}