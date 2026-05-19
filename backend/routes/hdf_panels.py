from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db import get_db
from src.models import (
    Panel as PanelModel, Port as PortModel, SubPanel as SubPanelModel,
    Node as NodeModel, Rack as RackModel,
)
from src.schemas import HDFPanelCreate, HDFPanelResponse

router = APIRouter()

HDF_COLUMNS = ["A", "B", "C", "D"]
HDF_PORTS_PER_SUBPANEL = 6


def generate_hdf_port_name(row: int, column: str) -> str:
    return f"{row}-{column}"


@router.post("/hdf", response_model=HDFPanelResponse, status_code=201)
def create_hdf_panel(data: HDFPanelCreate, db: Session = Depends(get_db)):
    node = db.query(NodeModel).filter(NodeModel.id == data.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if data.rack_id:
        rack = db.query(RackModel).filter(
            RackModel.id == data.rack_id,
            RackModel.node_id == data.node_id
        ).first()
        if not rack:
            raise HTTPException(status_code=404, detail="Rack not found or doesn't belong to node")

    total_subpanels = data.rows * len(HDF_COLUMNS)
    total_ports = total_subpanels * HDF_PORTS_PER_SUBPANEL

    panel = PanelModel(
        name=data.name,
        node_id=data.node_id,
        rack_id=data.rack_id,
        rack_position=data.rack_position,
        physical_type="hdf",
        connector_type="HDF",
        port_count=total_ports,
        rack_units=max(1, (data.rows + 3) // 4),
        description=data.description or f"HDF Panel with {data.rows} rows x 4 columns",
    )
    db.add(panel)
    db.flush()

    sub_panels = {}
    sub_panel_number = 1

    for row in range(1, data.rows + 1):
        for col in HDF_COLUMNS:
            sub_panel_name = generate_hdf_port_name(row, col)
            sub_panel = SubPanelModel(
                panel_id=panel.id,
                name=sub_panel_name,
                sub_panel_number=sub_panel_number,
                port_count=HDF_PORTS_PER_SUBPANEL,
                description=f"HDF Sub-panel {sub_panel_name} with {HDF_PORTS_PER_SUBPANEL} ports",
            )
            db.add(sub_panel)
            db.flush()
            sub_panels[(row, col)] = sub_panel
            sub_panel_number += 1

    created_ports = []
    global_port_number = 1

    for row in range(1, data.rows + 1):
        for col in HDF_COLUMNS:
            sub_panel = sub_panels[(row, col)]
            sub_panel_name = generate_hdf_port_name(row, col)

            for port_idx in range(1, HDF_PORTS_PER_SUBPANEL + 1):
                port_name = str(port_idx)
                port = PortModel(
                    name=port_name,
                    port_number=global_port_number,
                    panel_id=panel.id,
                    sub_panel_id=sub_panel.id,
                    panel_position=global_port_number,
                    panel_side='front',
                    port_type="fiber",
                    connector_type="HDF",
                    status="available",
                )
                db.add(port)
                created_ports.append({
                    "port_number": global_port_number,
                    "name": port_name,
                    "display_name": f"[{sub_panel_name}] {port_name}",
                    "row": row,
                    "column": col,
                    "sub_panel": sub_panel_name,
                    "port_in_subpanel": port_idx,
                })
                global_port_number += 1

    db.commit()
    db.refresh(panel)

    return HDFPanelResponse(
        panel_id=panel.id,
        name=panel.name,
        rows=data.rows,
        columns=HDF_COLUMNS,
        total_ports=total_ports,
        ports=created_ports,
    )


@router.get("/hdf/preview")
def preview_hdf_ports(rows: int = 1):
    if rows < 1 or rows > 100:
        raise HTTPException(status_code=400, detail="Rows must be between 1 and 100")

    sub_panels = []
    ports = []
    global_port_number = 1
    sub_panel_number = 1

    for row in range(1, rows + 1):
        for col in HDF_COLUMNS:
            sub_panel_name = generate_hdf_port_name(row, col)
            sub_panel_ports = []

            for port_idx in range(1, HDF_PORTS_PER_SUBPANEL + 1):
                port_name = str(port_idx)
                port_info = {
                    "port_number": global_port_number,
                    "name": port_name,
                    "display_name": f"[{sub_panel_name}] {port_name}",
                    "row": row,
                    "column": col,
                    "sub_panel": sub_panel_name,
                    "port_in_subpanel": port_idx,
                }
                ports.append(port_info)
                sub_panel_ports.append(port_info)
                global_port_number += 1

            sub_panels.append({
                "sub_panel_number": sub_panel_number,
                "name": sub_panel_name,
                "row": row,
                "column": col,
                "port_count": HDF_PORTS_PER_SUBPANEL,
                "ports": sub_panel_ports,
            })
            sub_panel_number += 1

    total_subpanels = rows * len(HDF_COLUMNS)
    total_ports = total_subpanels * HDF_PORTS_PER_SUBPANEL

    return {
        "rows": rows,
        "columns": HDF_COLUMNS,
        "ports_per_subpanel": HDF_PORTS_PER_SUBPANEL,
        "total_subpanels": total_subpanels,
        "total_ports": total_ports,
        "sub_panels": sub_panels,
        "ports": ports,
    }
