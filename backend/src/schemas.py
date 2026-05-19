from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

class TimestampSchema(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class SiteBase(BaseModel):
    name: str
    location: Optional[str] = None
    site_type: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    image_path: Optional[str] = None
    description: Optional[str] = None

class SiteCreate(SiteBase):
    pass

class SiteUpdate(SiteBase):
    name: Optional[str] = None

class Site(SiteBase, TimestampSchema):
    id: int
    node_count: Optional[int] = 0

class NodeBase(BaseModel):
    location: str
    name: str
    description: Optional[str] = None
    contact_person: Optional[str] = None
    image_path: Optional[str] = None

class NodeCreate(NodeBase):
    site_id: int

class NodeUpdate(NodeBase):
    location: Optional[str] = None
    name: Optional[str] = None

class Node(NodeBase, TimestampSchema):
    id: int
    site_id: int
    site_name: Optional[str] = None
    rack_count: Optional[int] = 0
    panel_count: Optional[int] = 0
    device_count: Optional[int] = 0

class RackBase(BaseModel):
    name: str
    location: Optional[str] = None
    rack_unit_size: Optional[int] = 42
    rack_type: Optional[str] = 'standard'
    description: Optional[str] = None

class RackCreate(RackBase):
    node_id: int

class RackUpdate(RackBase):
    name: Optional[str] = None

class Rack(RackBase, TimestampSchema):
    id: int
    node_id: int

class PanelBase(BaseModel):
    name: str
    physical_type: str
    connector_type: str
    port_count: Optional[int] = 24
    rack_units: Optional[int] = 1
    rack_position: Optional[int] = None
    description: Optional[str] = None

class PanelCreate(PanelBase):
    node_id: int
    rack_id: int

class PanelUpdate(PanelBase):
    name: Optional[str] = None
    physical_type: Optional[str] = None
    connector_type: Optional[str] = None

class Panel(PanelBase, TimestampSchema):
    id: int
    node_id: int
    rack_id: int
    actual_port_count: Optional[int] = None

class DeviceBase(BaseModel):
    name: str
    device_type: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    rack_position: Optional[int] = None
    rack_units: Optional[int] = 1
    status: Optional[str] = 'active'
    network: Optional[str] = None
    description: Optional[str] = None
    port_count: Optional[int] = Field(default=None, ge=1)

class DeviceCreate(DeviceBase):
    node_id: int
    rack_id: int

class DeviceUpdate(DeviceBase):
    name: Optional[str] = None

class Device(DeviceBase, TimestampSchema):
    id: int
    node_id: int
    rack_id: int

class PortBase(BaseModel):
    name: str
    connector_type: Optional[str] = None
    port_type: Optional[str] = None
    port_number: Optional[str] = None
    status: Optional[str] = 'available'
    speed: Optional[str] = None
    description: Optional[str] = None

class PortCreate(PortBase):
    panel_id: Optional[int] = None
    sub_panel_id: Optional[int] = None
    device_id: Optional[int] = None
    panel_position: Optional[int] = None
    panel_side: Optional[str] = None

class PortUpdate(PortBase):
    name: Optional[str] = None

class Port(PortBase, TimestampSchema):
    id: int
    panel_id: Optional[int] = None
    sub_panel_id: Optional[int] = None
    device_id: Optional[int] = None
    owner_name: Optional[str] = None
    node_name: Optional[str] = None
    rack_name: Optional[str] = None
    panel_name: Optional[str] = None
    sub_panel_name: Optional[str] = None
    device_name: Optional[str] = None
    display_name: Optional[str] = None
    panel_position: Optional[int] = None
    panel_side: Optional[str] = None

class ConnectionBase(BaseModel):
    status: Optional[str] = 'active'
    notes: Optional[str] = None

class ConnectionCreate(ConnectionBase):
    port_a_id: int
    port_b_id: int

class ConnectionUpdate(ConnectionBase):
    pass

class Connection(ConnectionBase, TimestampSchema):
    id: int
    port_a_id: int
    port_b_id: int

class SubPanelBase(BaseModel):
    name: str
    sub_panel_number: int
    port_count: int
    description: Optional[str] = None

class SubPanelCreate(SubPanelBase):
    panel_id: int

class SubPanelUpdate(SubPanelBase):
    name: Optional[str] = None
    sub_panel_number: Optional[int] = None
    port_count: Optional[int] = None

class SubPanel(SubPanelBase, TimestampSchema):
    id: int
    panel_id: int
    actual_port_count: Optional[int] = None
    port_count_actual: Optional[int] = None

    @model_validator(mode='after')
    def _sync_port_count_actual(self) -> 'SubPanel':
        if self.port_count_actual is None:
            self.port_count_actual = self.actual_port_count
        return self

class HDFPanelCreate(BaseModel):
    name: str
    node_id: int
    rack_id: Optional[int] = None
    rack_position: Optional[int] = None
    rows: int = Field(..., ge=1, le=100)
    description: Optional[str] = None

class HDFPanelResponse(BaseModel):
    panel_id: int
    name: str
    rows: int
    columns: list[str]
    total_ports: int
    ports: list[dict]
