from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AccessMethod(str, Enum):
    vpn = "vpn"
    keendns = "keendns"
    http_proxy = "http_proxy"


class Router(Base):
    __tablename__ = "routers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    site: Mapped[str | None] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=80)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    access_method: Mapped[str] = mapped_column(String(32), default=AccessMethod.vpn.value)
    model: Mapped[str | None] = mapped_column(String(120))
    firmware_version: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CurrentClient(Base):
    __tablename__ = "current_clients"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    router_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255))
    mac: Mapped[str | None] = mapped_column(String(32), index=True)
    ip: Mapped[str | None] = mapped_column(String(64), index=True)
    interface: Mapped[str | None] = mapped_column(String(120))
    connection_type: Mapped[str] = mapped_column(String(32), default="unknown")
    rx_bytes: Mapped[int | None] = mapped_column(BigInteger)
    tx_bytes: Mapped[int | None] = mapped_column(BigInteger)
    signal: Mapped[float | None] = mapped_column(Float)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RouterStatus(Base):
    __tablename__ = "router_status"

    router_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    wan_status: Mapped[str | None] = mapped_column(String(64))
    wan_ip: Mapped[str | None] = mapped_column(String(64))
    cpu_usage: Mapped[float | None] = mapped_column(Float)
    ram_usage: Mapped[float | None] = mapped_column(Float)
    uptime: Mapped[int | None] = mapped_column(BigInteger)
    rx_bytes_total: Mapped[int | None] = mapped_column(BigInteger)
    tx_bytes_total: Mapped[int | None] = mapped_column(BigInteger)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RouterMetric(Base):
    __tablename__ = "router_metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, default=utcnow)
    router_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    cpu_usage: Mapped[float | None] = mapped_column(Float)
    ram_usage: Mapped[float | None] = mapped_column(Float)
    uptime: Mapped[int | None] = mapped_column(BigInteger)
    wan_status: Mapped[str | None] = mapped_column(String(64))
    wan_ip: Mapped[str | None] = mapped_column(String(64))
    rx_bytes_total: Mapped[int | None] = mapped_column(BigInteger)
    tx_bytes_total: Mapped[int | None] = mapped_column(BigInteger)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class RouterCreate(BaseModel):
    name: str
    site: str | None = None
    host: str
    port: int = 80
    username: str
    password: str | None = None
    access_method: AccessMethod = AccessMethod.vpn
    enabled: bool = True


class RouterUpdate(BaseModel):
    name: str | None = None
    site: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    access_method: AccessMethod | None = None
    enabled: bool | None = None


class RouterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    site: str | None
    host: str
    port: int
    username: str
    access_method: str
    model: str | None
    firmware_version: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    router_id: str
    hostname: str | None
    mac: str | None
    ip: str | None
    interface: str | None
    connection_type: str
    rx_bytes: int | None
    tx_bytes: int | None
    signal: float | None
    last_seen: datetime


class StatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    router_id: str
    online: bool
    wan_status: str | None
    wan_ip: str | None
    cpu_usage: float | None
    ram_usage: float | None
    uptime: int | None
    rx_bytes_total: int | None
    tx_bytes_total: int | None
    last_seen: datetime | None
    updated_at: datetime


class RouterMetricData(BaseModel):
    router_id: str
    cpu_usage: float | None = None
    ram_usage: float | None = None
    uptime: int | None = None
    wan_status: str | None = None
    wan_ip: str | None = None
    rx_bytes_total: int | None = None
    tx_bytes_total: int | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    online: bool = True
    raw: dict[str, Any] | None = None


def _fernet() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise RuntimeError("FERNET_KEY is required to encrypt router credentials")
    return Fernet(key.encode())


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Stored router credential cannot be decrypted") from exc
