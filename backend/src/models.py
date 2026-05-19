"""Database models for Network Topology Staging - SQLite version."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, Boolean,
    Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


class Site(Base, TimestampMixin):
    __tablename__ = 'sites'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    location = Column(String(200))
    site_type = Column(String(50))
    contact_name = Column(String(100))
    contact_email = Column(String(100))
    contact_phone = Column(String(50))
    image_path = Column(String(500))
    description = Column(Text)

    nodes = relationship('Node', back_populates='site', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Site(id={self.id}, name='{self.name}')>"


class Node(Base, TimestampMixin):
    __tablename__ = 'nodes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(Integer, ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    image_path = Column(String(500))
    description = Column(Text)
    contact_person = Column(String(100))

    site = relationship('Site', back_populates='nodes')
    racks = relationship('Rack', back_populates='node', cascade='all, delete-orphan')
    panels = relationship('Panel', back_populates='node', cascade='all, delete-orphan')
    devices = relationship('Device', back_populates='node', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('site_id', 'location', name='uq_node_site_location'),
        Index('idx_node_site', 'site_id'),
    )

    def __repr__(self):
        return f"<Node(id={self.id}, location='{self.location}', name='{self.name}')>"


class Rack(Base, TimestampMixin):
    __tablename__ = 'racks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    rack_unit_size = Column(Integer, default=42)
    rack_type = Column(String(50), default='standard')
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False, index=True)
    description = Column(Text)

    node = relationship('Node', back_populates='racks')
    panels = relationship('Panel', back_populates='rack', cascade='all, delete-orphan')
    devices = relationship('Device', back_populates='rack', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('rack_unit_size > 0', name='check_rack_unit_size_positive'),
        Index('idx_rack_node_name', 'node_id', 'name'),
    )


class Panel(Base, TimestampMixin):
    __tablename__ = 'panels'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    physical_type = Column(String(50), nullable=False)
    connector_type = Column(String(50), nullable=False)
    port_count = Column(Integer, default=24)
    rack_units = Column(Integer, default=1)
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False, index=True)
    rack_id = Column(Integer, ForeignKey('racks.id', ondelete='CASCADE'), nullable=False)
    rack_position = Column(Integer)
    description = Column(Text)

    node = relationship('Node', back_populates='panels')
    rack = relationship('Rack', back_populates='panels')
    sub_panels = relationship('SubPanel', back_populates='panel', cascade='all, delete-orphan', order_by='SubPanel.sub_panel_number')
    ports = relationship('Port', back_populates='panel', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('port_count > 0', name='check_port_count_positive'),
        CheckConstraint('rack_position > 0', name='check_rack_position_positive'),
        CheckConstraint('rack_units > 0', name='check_panel_rack_units_positive'),
        Index('idx_panel_rack_position', 'rack_id', 'rack_position'),
    )


class SubPanel(Base, TimestampMixin):
    __tablename__ = 'sub_panels'

    id = Column(Integer, primary_key=True, autoincrement=True)
    panel_id = Column(Integer, ForeignKey('panels.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sub_panel_number = Column(Integer, nullable=False)
    port_count = Column(Integer, nullable=False)
    description = Column(Text)

    panel = relationship('Panel', back_populates='sub_panels')
    ports = relationship('Port', back_populates='sub_panel', cascade='all, delete-orphan', order_by='Port.port_number')

    __table_args__ = (
        CheckConstraint('port_count > 0', name='check_sub_panel_port_count_positive'),
        CheckConstraint('sub_panel_number > 0', name='check_sub_panel_number_positive'),
        Index('idx_sub_panel_panel', 'panel_id', 'sub_panel_number'),
        Index('idx_sub_panel_unique', 'panel_id', 'sub_panel_number', unique=True),
    )


class Device(Base, TimestampMixin):
    __tablename__ = 'devices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    device_type = Column(String(50))
    manufacturer = Column(String(100))
    model = Column(String(100))
    serial_number = Column(String(100), unique=True)
    ip_address = Column(String(45))
    location = Column(Text)
    rack_id = Column(Integer, ForeignKey('racks.id', ondelete='CASCADE'), nullable=False)
    rack_position = Column(Integer)
    rack_units = Column(Integer, default=1)
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(20), default='active')
    network = Column(String(100))
    description = Column(Text)

    rack = relationship('Rack', back_populates='devices')
    node = relationship('Node', back_populates='devices')
    ports = relationship('Port', back_populates='device', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('rack_position > 0', name='check_device_rack_position_positive'),
        CheckConstraint('rack_units > 0', name='check_rack_units_positive'),
        CheckConstraint("device_type IN ('edge switch','agg switch','router','ups','other')", name='check_device_type_allowed'),
        Index('idx_device_rack_position', 'rack_id', 'rack_position'),
        Index('idx_device_type', 'device_type'),
        Index('idx_device_status', 'status'),
    )


class Port(Base, TimestampMixin):
    __tablename__ = 'ports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    connector_type = Column(String(50))
    panel_id = Column(Integer, ForeignKey('panels.id', ondelete='CASCADE'), index=True)
    sub_panel_id = Column(Integer, ForeignKey('sub_panels.id', ondelete='SET NULL'), index=True)
    device_id = Column(Integer, ForeignKey('devices.id', ondelete='CASCADE'), index=True)
    port_type = Column(String(50))
    port_number = Column(String(50))
    panel_position = Column(Integer)
    panel_side = Column(String(10))
    status = Column(String(20), default='available')
    speed = Column(String(20))
    description = Column(Text)

    panel = relationship('Panel', back_populates='ports')
    sub_panel = relationship('SubPanel', back_populates='ports')
    device = relationship('Device', back_populates='ports')

    connections = relationship(
        'Connection',
        foreign_keys='Connection.port_a_id',
        back_populates='port_a',
        cascade='all, delete-orphan'
    )
    connections_b = relationship(
        'Connection',
        foreign_keys='Connection.port_b_id',
        back_populates='port_b'
    )

    __table_args__ = (
        CheckConstraint(
            '(panel_id IS NOT NULL AND device_id IS NULL) OR (panel_id IS NULL AND device_id IS NOT NULL)',
            name='check_port_belongs_to_panel_or_device'
        ),
        CheckConstraint(
            "(panel_id IS NOT NULL AND panel_position IS NOT NULL AND panel_side IN ('front','rear')) "
            "OR (panel_id IS NULL AND panel_position IS NULL AND panel_side IS NULL)",
            name='check_panel_side_fields'
        ),
        CheckConstraint('panel_position IS NULL OR panel_position > 0', name='check_panel_position_positive'),
        UniqueConstraint('panel_id', 'panel_position', 'panel_side', name='uq_panel_position_side'),
        Index('idx_port_panel', 'panel_id'),
        Index('idx_port_device', 'device_id'),
        Index('idx_port_status', 'status'),
        Index('idx_port_panel_position_side', 'panel_id', 'panel_position', 'panel_side'),
    )

    @property
    def display_name(self):
        if self.sub_panel:
            position = int(self.port_number) if self.port_number and str(self.port_number).isdigit() else 1
            fiber_start = (position - 1) * 2 + 1
            fiber_end = fiber_start + 1
            return f"{fiber_start},{fiber_end}"
        return str(self.port_number) if self.port_number else self.name


class Connection(Base, TimestampMixin):
    __tablename__ = 'connections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    port_a_id = Column(Integer, ForeignKey('ports.id', ondelete='CASCADE'), nullable=False, index=True)
    port_b_id = Column(Integer, ForeignKey('ports.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(20), default='active')
    notes = Column(Text)

    port_a = relationship('Port', foreign_keys=[port_a_id], back_populates='connections')
    port_b = relationship('Port', foreign_keys=[port_b_id], back_populates='connections_b')

    __table_args__ = (
        CheckConstraint('port_a_id != port_b_id', name='check_different_ports'),
        UniqueConstraint('port_a_id', name='uq_connection_port_a'),
        UniqueConstraint('port_b_id', name='uq_connection_port_b'),
        Index('idx_connection_port_a', 'port_a_id'),
        Index('idx_connection_port_b', 'port_b_id'),
    )


from sqlalchemy import select, func as _sa_func
from sqlalchemy.orm import column_property as _column_property

Panel.actual_port_count = _column_property(
    select(_sa_func.count(Port.id))
    .where(Port.panel_id == Panel.id)
    .correlate(Panel)
    .scalar_subquery()
)

SubPanel.actual_port_count = _column_property(
    select(_sa_func.count(Port.id))
    .where(Port.sub_panel_id == SubPanel.id)
    .correlate(SubPanel)
    .scalar_subquery()
)


def compute_fiber_pair_display(port: 'Port', session) -> str:
    if not port or not port.sub_panel_id or not session:
        return port.display_name if port else "Unknown"

    from sqlalchemy import func, cast, Integer

    my_num = int(port.port_number) if port.port_number and str(port.port_number).isdigit() else 999999
    position = session.query(func.count(Port.id)).filter(
        Port.sub_panel_id == port.sub_panel_id,
        cast(Port.port_number, Integer) < my_num
    ).scalar() + 1

    fiber_start = (position - 1) * 2 + 1
    fiber_end = fiber_start + 1
    return f"{fiber_start},{fiber_end}"
