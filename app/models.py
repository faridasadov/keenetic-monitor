from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
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


class UserRole(str, Enum):
    admin = "admin"
    first_support = "first_support"
    call_center = "call_center"
    user = "user"


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default=UserRole.user.value)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Router(Base):
    __tablename__ = "routers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    site: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(Text)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    support_status: Mapped[str] = mapped_column(String(32), default="normal")
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


class BlockedClient(Base):
    __tablename__ = "blocked_clients"

    router_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    mac: Mapped[str] = mapped_column(String(32), primary_key=True)
    hostname: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


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


class ClientMetric(Base):
    __tablename__ = "client_metrics"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, default=utcnow)
    router_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    client_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    hostname: Mapped[str | None] = mapped_column(String(255))
    mac: Mapped[str | None] = mapped_column(String(32), index=True)
    ip: Mapped[str | None] = mapped_column(String(64), index=True)
    rx_bytes: Mapped[int | None] = mapped_column(BigInteger)
    tx_bytes: Mapped[int | None] = mapped_column(BigInteger)
    signal: Mapped[float | None] = mapped_column(Float)


class DiagnosticRun(Base):
    __tablename__ = "diagnostic_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    router_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    summary: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RouterCreate(BaseModel):
    name: str
    description: str | None = None
    site: str | None = None
    address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    support_status: str = "normal"
    host: str
    port: int = 80
    username: str
    password: str | None = None
    access_method: AccessMethod = AccessMethod.vpn
    enabled: bool = True


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthTokenRead(BaseModel):
    token: str
    username: str
    role: UserRole


class AppUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=4, max_length=120)
    role: UserRole = UserRole.user
    enabled: bool = True


class AppUserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=4, max_length=120)
    role: UserRole | None = None
    enabled: bool | None = None


class AppUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RouterCredentialTest(BaseModel):
    host: str
    port: int = 80
    username: str
    password: str


class RouterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    site: str | None = None
    address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    support_status: str | None = None
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
    description: str | None
    site: str | None
    address: str | None
    contact_name: str | None
    contact_phone: str | None
    support_status: str
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


class ClientMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: datetime
    router_id: str
    client_key: str
    hostname: str | None
    mac: str | None
    ip: str | None
    rx_bytes: int | None
    tx_bytes: int | None
    signal: float | None


class BlockedClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    router_id: str
    mac: str
    hostname: str | None
    ip: str | None
    created_at: datetime
    updated_at: datetime


class PortRead(BaseModel):
    id: str
    label: str
    kind: str
    category: str = "access"
    is_wan: bool = False
    link: str | None = None
    state: str | None = None
    connected: bool
    speed_mbps: int | None = None
    duplex: str | None = None
    role: str | None = None
    ssid: str | None = None


class SummaryRead(BaseModel):
    router_id: str
    client_count: int
    wifi_client_count: int = 0
    online: bool
    wan_status: str | None
    wan_ip: str | None
    wan_provider: str | None
    wan_rx_bps: float | None
    wan_tx_bps: float | None
    total_rx_bps: float | None = None
    total_tx_bps: float | None = None
    lan_rx_bps: float | None = None
    lan_tx_bps: float | None = None
    wifi_rx_bps: float | None = None
    wifi_tx_bps: float | None = None
    max_traffic_bps: float | None = None
    max_client_count: int | None = None


class ClientAccessUpdate(BaseModel):
    mac: str
    blocked: bool


class WifiPasswordUpdate(BaseModel):
    password: str = Field(min_length=8, max_length=63)
    access_points: list[str] | None = None
    save: bool = True


class WifiSsidUpdate(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    access_points: list[str] | None = None
    save: bool = True


class PingRequest(BaseModel):
    host: str
    count: int = Field(default=4, ge=1, le=20)


class SiteCheckRequest(BaseModel):
    url: str


class DnsCheckRequest(BaseModel):
    host: str = "google.com"


class DiagnosticRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    router_id: str
    status: str
    summary: str
    result: dict[str, Any]
    created_by: str | None
    created_at: datetime


class RouterOsUpdateRequest(BaseModel):
    channel: str = Field(default="stable", pattern="^(stable|preview|draft)$")


class InterfacePowerUpdate(BaseModel):
    enabled: bool
    save: bool = True


class WifiPowerUpdate(BaseModel):
    enabled: bool
    access_points: list[str] | None = None
    save: bool = True


class StatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    router_id: str
    online: bool
    wan_status: str | None
    wan_ip: str | None
    wan_ip_private: bool | None = None
    firmware_version: str | None = None
    os_available_version: str | None = None
    os_update_available: bool | None = None
    os_check_status: Literal["ok", "unavailable", "error"] | None = None
    os_check_message: str | None = None
    public_ip: str | None = None
    public_ip_source: str | None = None
    public_ip_blacklisted: bool | None = None
    public_ip_blacklist_hits: list[str] = Field(default_factory=list)
    public_ip_blacklist_checked: list[str] = Field(default_factory=list)
    public_ip_checked_at: datetime | None = None
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
