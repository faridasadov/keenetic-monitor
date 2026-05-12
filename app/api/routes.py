from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import socket
import subprocess
import telnetlib
import time
from datetime import timedelta, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.collector.keenetic_client import KeeneticClient
from app.collector.parser import parse_ports, parse_traffic_groups, parse_wan_info, parse_wifi_credentials
from app.config import get_settings
from app.models import (
    AppUser,
    AppUserCreate,
    AppUserRead,
    AppUserUpdate,
    AuthTokenRead,
    BlockedClient,
    BlockedClientRead,
    ClientRead,
    ClientAccessUpdate,
    ClientMetric,
    ClientMetricRead,
    CurrentClient,
    DiagnosticRun,
    DiagnosticRunRead,
    DnsCheckRequest,
    InterfacePowerUpdate,
    LoginRequest,
    PingRequest,
    PortRead,
    Router,
    RouterCreate,
    RouterCredentialTest,
    RouterMetric,
    RouterOsUpdateRequest,
    RouterRead,
    RouterStatus,
    RouterUpdate,
    SiteCheckRequest,
    SummaryRead,
    StatusRead,
    WifiPowerUpdate,
    WifiPasswordUpdate,
    WifiSsidUpdate,
    UserRole,
    decrypt_secret,
    encrypt_secret,
    utcnow,
)

router = APIRouter()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return f"pbkdf2_sha256$180000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_value, digest_value = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_value)
    expected = base64.b64decode(digest_value)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(actual, expected)


def _ensure_default_users(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(AppUser)):
        return
    db.add_all(
        [
            AppUser(username="admin", password_hash=_hash_password("admin"), role=UserRole.admin.value, enabled=True),
            AppUser(username="user", password_hash=_hash_password("user"), role=UserRole.user.value, enabled=True),
        ]
    )
    db.commit()


def _make_token(user: AppUser) -> str:
    payload = {
        "sub": user.username,
        "role": user.role,
        "exp": int((utcnow() + timedelta(days=7)).timestamp()),
    }
    return encrypt_secret(json.dumps(payload, separators=(",", ":"))) or ""


def _current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> AppUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    try:
        token = decrypt_secret(authorization.removeprefix("Bearer ").strip())
        data = json.loads(token or "{}")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid login token") from exc
    if int(data.get("exp", 0)) < int(utcnow().timestamp()):
        raise HTTPException(status_code=401, detail="Login expired")
    user = db.scalar(select(AppUser).where(AppUser.username == data.get("sub")))
    if user is None or not user.enabled:
        raise HTTPException(status_code=401, detail="User is disabled")
    return user


def _optional_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> AppUser | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = decrypt_secret(authorization.removeprefix("Bearer ").strip())
        data = json.loads(token or "{}")
    except Exception:
        return None
    if int(data.get("exp", 0)) < int(utcnow().timestamp()):
        return None
    user = db.scalar(select(AppUser).where(AppUser.username == data.get("sub")))
    if user is None or not user.enabled:
        return None
    return user


def _require_admin(current_user: AppUser = Depends(_current_user)) -> AppUser:
    if current_user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _require_first_support(current_user: AppUser = Depends(_current_user)) -> AppUser:
    if current_user.role not in {UserRole.admin.value, UserRole.first_support.value}:
        raise HTTPException(status_code=403, detail="First support access required")
    return current_user


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/login", response_model=AuthTokenRead)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    _ensure_default_users(db)
    user = db.scalar(select(AppUser).where(AppUser.username == payload.username))
    if user is None or not user.enabled or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username or password is wrong")
    return {"token": _make_token(user), "username": user.username, "role": user.role}


@router.get("/auth/me", response_model=AppUserRead)
def auth_me(current_user: AppUser = Depends(_current_user)) -> AppUser:
    return current_user


@router.get("/users", response_model=list[AppUserRead])
def list_users(
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> list[AppUser]:
    _ensure_default_users(db)
    return list(db.scalars(select(AppUser).order_by(AppUser.created_at.desc())))


@router.post("/users", response_model=AppUserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AppUserCreate,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> AppUser:
    _ensure_default_users(db)
    existing = db.scalar(select(AppUser).where(AppUser.username == payload.username))
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists")
    user = AppUser(
        username=payload.username,
        password_hash=_hash_password(payload.password),
        role=payload.role.value,
        enabled=payload.enabled,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=AppUserRead)
def update_user(
    user_id: str,
    payload: AppUserUpdate,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(_require_admin),
) -> AppUser:
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    values = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and values.get("enabled") is False:
        raise HTTPException(status_code=400, detail="You cannot disable your own admin user")
    if user.id == admin.id and values.get("role") == UserRole.user:
        raise HTTPException(status_code=400, detail="You cannot demote your own admin user")
    if "password" in values and values["password"]:
        user.password_hash = _hash_password(values["password"])
    if "role" in values and values["role"] is not None:
        user.role = values["role"].value
    if "enabled" in values and values["enabled"] is not None:
        user.enabled = values["enabled"]
    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(_require_admin),
) -> None:
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin user")
    db.delete(user)
    db.commit()


@router.get("/routers", response_model=list[RouterRead])
def list_routers(db: Session = Depends(get_db)) -> list[Router]:
    return list(db.scalars(select(Router).order_by(Router.created_at.desc())))


@router.post("/routers", response_model=RouterRead, status_code=status.HTTP_201_CREATED)
def create_router(
    payload: RouterCreate,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> Router:
    existing = db.scalar(select(Router).where(Router.host == payload.host, Router.port == payload.port))
    if existing is not None:
        existing.name = payload.name
        existing.description = payload.description
        existing.site = payload.site
        existing.address = payload.address
        existing.contact_name = payload.contact_name
        existing.contact_phone = payload.contact_phone
        existing.support_status = payload.support_status
        existing.username = payload.username
        existing.password_encrypted = encrypt_secret(payload.password)
        existing.access_method = payload.access_method.value
        existing.enabled = payload.enabled
        db.commit()
        db.refresh(existing)
        return existing

    item = Router(
        name=payload.name,
        description=payload.description,
        site=payload.site,
        address=payload.address,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        support_status=payload.support_status,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password_encrypted=encrypt_secret(payload.password),
        access_method=payload.access_method.value,
        enabled=payload.enabled,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/routers/test-credentials")
def test_router_credentials(
    payload: RouterCredentialTest,
    _admin: AppUser = Depends(_require_admin),
) -> dict[str, object]:
    try:
        with KeeneticClient(payload.host, payload.port, payload.username, payload.password) as client:
            system = client.get_system_info()
            try:
                version = client.get_version_info()
            except Exception:
                version = {}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router RCI test failed: {exc}") from exc
    system_data = system if isinstance(system, dict) else {}
    version_data = version if isinstance(version, dict) else {}
    model = version_data.get("model") or version_data.get("description") or system_data.get("model")
    release = version_data.get("release") or version_data.get("title") or system_data.get("release") or system_data.get("version")
    return {"status": "ok", "model": model, "firmware_version": release}


@router.post("/routers/{router_id}/refresh-identity", response_model=RouterRead)
def refresh_router_identity(
    router_id: str,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> Router:
    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password, timeout=20.0) as client:
            system = client.get_system_info()
            version = client.get_version_info()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router identity refresh failed: {exc}") from exc
    _write_router_identity(item, system, version)
    db.commit()
    db.refresh(item)
    return item


@router.post("/routers/{router_id}/os/check")
def check_router_os(
    router_id: str,
    payload: RouterOsUpdateRequest,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password, timeout=45.0) as client:
            before = client.get_version_info()
            result = client.list_components(payload.channel)
            after = client.get_version_info()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router OS update check failed: {exc}") from exc
    _write_router_identity(item, {}, after)
    db.commit()
    return {
        "status": "ok",
        "channel": payload.channel,
        "current": _version_summary(before),
        "after_check": _version_summary(after),
        "update": _components_summary(result),
    }


@router.post("/routers/{router_id}/os/update")
def update_router_os(
    router_id: str,
    payload: RouterOsUpdateRequest,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password, timeout=60.0) as client:
            before = client.get_version_info()
            list_result = client.list_components(payload.channel)
            commit_result = client.commit_components()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router OS update failed: {exc}") from exc
    return {
        "status": "started",
        "channel": payload.channel,
        "current": _version_summary(before),
        "update": _components_summary(list_result),
        "commit_result": commit_result if isinstance(commit_result, dict) else {"result": str(commit_result)},
        "message": "Update command sent. Router may reboot.",
    }


@router.put("/routers/{router_id}", response_model=RouterRead)
def update_router(
    router_id: str,
    payload: RouterUpdate,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> Router:
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "password":
            item.password_encrypted = encrypt_secret(value)
        elif field == "access_method" and value is not None:
            item.access_method = value.value
        else:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/routers/{router_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_router(
    router_id: str,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> None:
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    db.execute(delete(CurrentClient).where(CurrentClient.router_id == router_id))
    status_row = db.get(RouterStatus, router_id)
    if status_row is not None:
        db.delete(status_row)
    db.delete(item)
    db.commit()


@router.get("/routers/{router_id}/clients", response_model=list[ClientRead])
def router_clients(router_id: str, db: Session = Depends(get_db)) -> list[CurrentClient]:
    return list(db.scalars(select(CurrentClient).where(CurrentClient.router_id == router_id).order_by(CurrentClient.hostname)))


@router.get("/routers/{router_id}/blocked-clients", response_model=list[BlockedClientRead])
def router_blocked_clients(router_id: str, db: Session = Depends(get_db)) -> list[BlockedClient]:
    return list(db.scalars(select(BlockedClient).where(BlockedClient.router_id == router_id).order_by(BlockedClient.updated_at.desc())))


@router.get("/routers/{router_id}/diagnostics", response_model=list[DiagnosticRunRead])
def router_diagnostic_history(
    router_id: str,
    db: Session = Depends(get_db),
) -> list[DiagnosticRun]:
    return list(
        db.scalars(
            select(DiagnosticRun)
            .where(DiagnosticRun.router_id == router_id)
            .order_by(DiagnosticRun.created_at.desc())
            .limit(10)
        )
    )


@router.post("/routers/{router_id}/diagnose", response_model=DiagnosticRunRead)
def diagnose_router(
    router_id: str,
    db: Session = Depends(get_db),
    user: AppUser | None = Depends(_optional_current_user),
) -> DiagnosticRun:
    router_item = db.get(Router, router_id)
    if router_item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    status_row = db.get(RouterStatus, router_id)
    client_count = db.scalar(select(func.count()).select_from(CurrentClient).where(CurrentClient.router_id == router_id)) or 0
    wifi_client_count = (
        db.scalar(
            select(func.count())
            .select_from(CurrentClient)
            .where(CurrentClient.router_id == router_id, CurrentClient.connection_type == "wifi")
        )
        or 0
    )
    router_ping_result = _run_ping(router_item.host, 3)
    dns_result = _run_dns_check("google.com")
    item, password = _router_credentials(router_id, db)
    internet_ping_result = _run_router_cli_ping(item, password, "8.8.8.8", 3)
    site_result = _run_router_cli_ping(item, password, "google.com", 3)
    rci_result: dict[str, object]
    try:
        with _keenetic_client(item, password, timeout=8.0) as client:
            client.login()
        rci_result = {"ok": True, "message": "RCI login OK"}
    except Exception as exc:
        rci_result = {"ok": False, "message": str(exc), "warning": True}

    online = bool(status_row and status_row.online)
    warnings: list[str] = []
    if not router_ping_result.get("ok"):
        warnings.append("Router ping cavab vermir")
    if not rci_result.get("ok"):
        warnings.append("Router RCI giriş alınmadı")
    if not internet_ping_result.get("ok"):
        warnings.append("Routerdən internet ping alınmadı")
    if not dns_result.get("ok"):
        warnings.append("DNS resolve alınmadı")
    if status_row and status_row.cpu_usage is not None and status_row.cpu_usage > 85:
        warnings.append("CPU yüksəkdir")
    if status_row and status_row.ram_usage is not None and status_row.ram_usage > 85:
        warnings.append("RAM yüksəkdir")
    if status_row and status_row.uptime is not None and status_row.uptime < 600:
        warnings.append("Router yaxınlarda restart olub")
    if client_count > 150:
        warnings.append(f"Client sayı yüksəkdir: {client_count}/150")
    if wifi_client_count > 15:
        warnings.append(f"Wi-Fi client sayı yüksəkdir: {wifi_client_count}/15")

    if not router_ping_result.get("ok"):
        verdict = "Router və ya VPN/routing əlçatmazdır"
        state_value = "critical"
    elif not rci_result.get("ok"):
        verdict = "Router şəbəkədədir, amma idarəetmə girişi alınmır"
        state_value = "warning"
    elif not internet_ping_result.get("ok") or not dns_result.get("ok"):
        verdict = "Router işləyir, problem internet/DNS tərəfində ola bilər"
        state_value = "warning"
    elif warnings:
        verdict = "Router işləyir, amma yoxlanmalı xəbərdarlıqlar var"
        state_value = "warning"
    else:
        verdict = "Router və əsas internet testləri normaldır"
        state_value = "ok"

    result = {
        "router": {"id": router_item.id, "name": router_item.name, "host": router_item.host},
        "status": {
            "online": online,
            "wan_status": status_row.wan_status if status_row else None,
            "wan_ip": status_row.wan_ip if status_row else None,
            "cpu_usage": status_row.cpu_usage if status_row else None,
            "ram_usage": status_row.ram_usage if status_row else None,
            "uptime": status_row.uptime if status_row else None,
            "last_seen": status_row.last_seen.isoformat() if status_row and status_row.last_seen else None,
        },
        "client_count": client_count,
        "wifi_client_count": wifi_client_count,
        "tests": {
            "router_ping": router_ping_result,
            "rci": rci_result,
            "internet_ping": internet_ping_result,
            "dns": dns_result,
            "site": {**site_result, "method": "router_cli_icmp"},
        },
        "warnings": warnings,
        "operator_script": _support_script(verdict, warnings),
    }
    row = DiagnosticRun(
        router_id=router_id,
        status=state_value,
        summary=verdict,
        result=result,
        created_by=user.username if user else "system",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/routers/{router_id}/summary", response_model=SummaryRead)
def router_summary(router_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    status_row = db.get(RouterStatus, router_id)
    if status_row is None:
        raise HTTPException(status_code=404, detail="Router status not found")
    client_count = db.scalar(select(func.count()).select_from(CurrentClient).where(CurrentClient.router_id == router_id)) or 0
    wifi_client_count = (
        db.scalar(
            select(func.count())
            .select_from(CurrentClient)
            .where(CurrentClient.router_id == router_id, CurrentClient.connection_type == "wifi")
        )
        or 0
    )
    day_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    metrics = list(
        db.scalars(
            select(RouterMetric)
            .where(RouterMetric.router_id == router_id)
            .order_by(RouterMetric.time.desc())
            .limit(120)
        )
    )
    daily_metrics = list(
        db.scalars(
            select(RouterMetric)
            .where(RouterMetric.router_id == router_id, RouterMetric.time >= day_start)
            .order_by(RouterMetric.time.desc())
        )
    )
    wan_rx_bps = None
    wan_tx_bps = None
    total_rx_bps = None
    total_tx_bps = None
    lan_rx_bps = None
    lan_tx_bps = None
    wifi_rx_bps = None
    wifi_tx_bps = None
    max_traffic_bps = None
    wan_provider = None
    traffic_samples: list[tuple[RouterMetric, dict[str, dict[str, int | None]]]] = []
    for metric in metrics:
        groups = _metric_traffic_groups(metric)
        if any(value is not None for bucket in groups.values() for value in bucket.values()):
            traffic_samples.append((metric, groups))
    for index in range(len(traffic_samples) - 1):
        current, current_groups = traffic_samples[index]
        previous, previous_groups = traffic_samples[index + 1]
        seconds = (current.time - previous.time).total_seconds()
        if seconds <= 0:
            continue
        if current.rx_bytes_total is not None and previous.rx_bytes_total is not None:
            delta = current.rx_bytes_total - previous.rx_bytes_total
            wan_rx_bps = (delta * 8) / seconds if delta >= 0 else None
        if current.tx_bytes_total is not None and previous.tx_bytes_total is not None:
            delta = current.tx_bytes_total - previous.tx_bytes_total
            wan_tx_bps = (delta * 8) / seconds if delta >= 0 else None
        sample_total_rx = _traffic_bps(current_groups, previous_groups, "total", "rx_bytes", seconds)
        sample_total_tx = _traffic_bps(current_groups, previous_groups, "total", "tx_bytes", seconds)
        sample_lan_rx = _traffic_bps(current_groups, previous_groups, "lan", "rx_bytes", seconds)
        sample_lan_tx = _traffic_bps(current_groups, previous_groups, "lan", "tx_bytes", seconds)
        sample_wifi_rx = _traffic_bps(current_groups, previous_groups, "wifi", "rx_bytes", seconds)
        sample_wifi_tx = _traffic_bps(current_groups, previous_groups, "wifi", "tx_bytes", seconds)
        sample_peak = sum(value or 0 for value in (sample_total_rx, sample_total_tx))
        if total_rx_bps is None and total_tx_bps is None and any(
            value is not None
            for value in (sample_total_rx, sample_total_tx, sample_lan_rx, sample_lan_tx, sample_wifi_rx, sample_wifi_tx)
        ):
            total_rx_bps = sample_total_rx
            total_tx_bps = sample_total_tx
            lan_rx_bps = sample_lan_rx
            lan_tx_bps = sample_lan_tx
            wifi_rx_bps = sample_wifi_rx
            wifi_tx_bps = sample_wifi_tx
    max_traffic_bps = _max_total_traffic_bps(daily_metrics)
    max_client_count = db.scalar(
        select(func.count(ClientMetric.client_key))
        .where(ClientMetric.router_id == router_id)
        .group_by(ClientMetric.time)
        .order_by(func.count(ClientMetric.client_key).desc())
        .limit(1)
    )
    if metrics:
        raw = metrics[0].raw or {}
        if isinstance(raw, dict):
            wan_provider = parse_wan_info(raw.get("interfaces")).get("provider")
    return {
        "router_id": router_id,
        "client_count": client_count,
        "wifi_client_count": wifi_client_count,
        "online": status_row.online,
        "wan_status": status_row.wan_status,
        "wan_ip": status_row.wan_ip,
        "wan_provider": wan_provider,
        "wan_rx_bps": wan_rx_bps,
        "wan_tx_bps": wan_tx_bps,
        "total_rx_bps": total_rx_bps,
        "total_tx_bps": total_tx_bps,
        "lan_rx_bps": lan_rx_bps,
        "lan_tx_bps": lan_tx_bps,
        "wifi_rx_bps": wifi_rx_bps,
        "wifi_tx_bps": wifi_tx_bps,
        "max_traffic_bps": max_traffic_bps,
        "max_client_count": max(max_client_count or 0, client_count),
    }


@router.get("/routers/{router_id}/ports", response_model=list[PortRead])
def router_ports(router_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    metric = db.scalar(
        select(RouterMetric)
        .where(RouterMetric.router_id == router_id)
        .order_by(RouterMetric.time.desc())
        .limit(1)
    )
    raw = metric.raw if metric is not None else None
    if isinstance(raw, dict) and raw.get("interfaces"):
        return parse_ports(raw.get("interfaces"))
    if not _router_recently_online(router_id, db):
        return []

    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password) as client:
            interfaces = client.get_interfaces()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router RCI ports failed: {exc}") from exc
    return parse_ports(interfaces)


@router.get("/routers/{router_id}/wifi")
def router_wifi(router_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    if not _router_recently_online(router_id, db):
        return []
    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password) as client:
            interfaces = client.get_interfaces()
            running_config = client.get_running_config()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router Wi-Fi read failed: {exc}") from exc
    return parse_wifi_credentials(interfaces, running_config)


@router.post("/routers/{router_id}/ping")
def router_ping(router_id: str, payload: PingRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    if db.get(Router, router_id) is None:
        raise HTTPException(status_code=404, detail="Router not found")
    return _run_ping(payload.host, payload.count)


@router.post("/routers/{router_id}/cli-ping")
def router_cli_ping(
    router_id: str,
    payload: PingRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    return _run_router_cli_ping(item, password, payload.host, payload.count)


@router.post("/routers/{router_id}/cli-site-check")
def router_cli_site_check(
    router_id: str,
    payload: SiteCheckRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    parsed = urlparse(payload.url if payload.url.startswith(("http://", "https://")) else f"https://{payload.url}")
    host = parsed.hostname or payload.url.strip()
    result = _run_router_cli_ping(item, password, host, 4)
    return {
        **result,
        "url": payload.url,
        "host": host,
        "method": "router_cli_icmp",
        "message": "Router CLI tools ping istifadə edir. Bu router CLI-də HTTP status aləti yoxdur.",
    }


def _run_ping(host: str, count: int = 4) -> dict[str, object]:
    command = ["ping", "-c", str(count), "-W", "2", host]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(count * 3, 6),
            check=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Server ping command is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(part for part in (exc.stdout, exc.stderr) if part)
        return {
            "host": host,
            "count": count,
            "method": "icmp",
            "ok": False,
            "output": output.strip() or "Ping timeout",
        }
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    avg_ms = _ping_average_ms(output)
    loss_percent = _ping_loss_percent(output)
    return {
        "host": host,
        "count": count,
        "method": "icmp",
        "ok": completed.returncode == 0,
        "avg_ms": avg_ms,
        "loss_percent": loss_percent,
        "warning": avg_ms is not None and avg_ms > 120,
        "output": output,
    }


def _run_router_cli_ping(item: Router, password: str, host: str, count: int = 4) -> dict[str, object]:
    started = time.perf_counter()
    target = _validate_cli_ping_target(host)
    command = f"tools ping {target}"
    try:
        output = _run_router_telnet_command(item.host, item.username, password, command, count=count)
    except Exception as exc:
        return {
            "host": target,
            "count": count,
            "method": "router_cli_icmp",
            "ok": False,
            "avg_ms": None,
            "loss_percent": None,
            "warning": True,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "output": str(exc),
        }
    samples = [float(value) for value in re.findall(r"time=([0-9.]+)\s*ms", output)]
    avg_ms = round(sum(samples) / len(samples), 3) if samples else None
    transmitted = max(count, len(re.findall(r"icmp_req=", output)))
    received = len(samples)
    loss_percent = round(max(transmitted - received, 0) * 100 / transmitted, 2) if transmitted else None
    return {
        "host": target,
        "count": count,
        "method": "router_cli_icmp",
        "ok": received > 0,
        "avg_ms": avg_ms,
        "loss_percent": loss_percent,
        "warning": avg_ms is None or avg_ms > 120 or loss_percent not in {0, 0.0},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "output": output,
    }


def _validate_cli_ping_target(host: str) -> str:
    target = host.strip()
    if not target or len(target) > 253:
        raise HTTPException(status_code=422, detail="Ping host is invalid")
    if not re.fullmatch(r"[A-Za-z0-9.:-]+", target):
        raise HTTPException(status_code=422, detail="Ping host can only contain letters, numbers, dots, dashes and colons")
    if target.startswith("-") or ".." in target:
        raise HTTPException(status_code=422, detail="Ping host is invalid")
    return target


def _run_router_telnet_command(host: str, username: str, password: str, command: str, *, count: int = 4) -> str:
    with telnetlib.Telnet(host, 23, timeout=8) as tn:
        tn.read_until(b"Login:", timeout=6)
        tn.write(username.encode() + b"\n")
        tn.read_until(b"Password:", timeout=6)
        tn.write(password.encode() + b"\n")
        welcome = tn.read_until(b"(config)>", timeout=10)
        if b"(config)>" not in welcome:
            raise RuntimeError("Router Telnet login failed")
        tn.write(command.encode() + b"\n")
        chunks = []
        deadline = time.monotonic() + max(count * 1.2, 4)
        while time.monotonic() < deadline:
            chunk = tn.read_very_eager()
            if chunk:
                chunks.append(chunk)
                if len(re.findall(rb"icmp_req=", b"".join(chunks))) >= count:
                    break
            time.sleep(0.25)
        tn.write(b"\x03")
        time.sleep(0.5)
        chunks.append(tn.read_very_eager())
        tn.write(b"exit\n")
    return _clean_cli_output(b"".join(chunks).decode(errors="ignore"))


def _clean_cli_output(value: str) -> str:
    value = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", value)
    value = value.replace("\r", "")
    value = value.replace("\x00", "")
    lines = []
    for line in value.splitlines():
        cleaned = line.replace("\x08", "").strip()
        if not cleaned or cleaned == "Core::Configurator: Done.":
            continue
        if re.fullmatch(r"(?:\(config\)>\s*)+", cleaned):
            continue
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


@router.post("/dns-check")
def dns_check(payload: DnsCheckRequest, _user: AppUser = Depends(_current_user)) -> dict[str, object]:
    return _run_dns_check(payload.host)


def _run_dns_check(host: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        rows = socket.getaddrinfo(host.strip(), None, proto=socket.IPPROTO_TCP)
        addresses = sorted({row[4][0] for row in rows})
    except Exception as exc:
        return {
            "host": host,
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "addresses": [],
            "message": str(exc),
            "warning": True,
        }
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "host": host,
        "ok": bool(addresses),
        "elapsed_ms": elapsed_ms,
        "addresses": addresses[:8],
        "message": "OK" if addresses else "No DNS records",
        "warning": not addresses or elapsed_ms > 800,
    }


@router.post("/site-check")
def check_site(payload: SiteCheckRequest, _user: AppUser = Depends(_current_user)) -> dict[str, object]:
    return _check_site_url(payload.url)


def _check_site_url(raw_url: str) -> dict[str, object]:
    raw_url = raw_url.strip()
    candidates = [raw_url] if raw_url.startswith(("http://", "https://")) else [f"https://{raw_url}", f"http://{raw_url}"]
    parsed = urlparse(candidates[0])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid site URL")
    started = time.perf_counter()
    last_error = ""
    url = candidates[0]
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = None
            for url in candidates:
                try:
                    response = client.head(url)
                    if response.status_code in {405, 403}:
                        response = client.get(url)
                    break
                except Exception as exc:
                    last_error = str(exc)
            if response is None:
                raise RuntimeError(last_error or "Site check failed")
    except Exception as exc:
        return {
            "url": url,
            "ok": False,
            "status_code": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "warning": True,
            "message": str(exc),
        }
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    ok = response.status_code < 500
    return {
        "url": str(response.url),
        "ok": ok,
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
        "warning": not ok or elapsed_ms > 1200,
        "message": response.reason_phrase,
    }


@router.get("/routers/{router_id}/client-metrics", response_model=list[ClientMetricRead])
def router_client_metrics(
    router_id: str,
    limit: int = Query(default=300, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[ClientMetric]:
    rows = list(
        db.scalars(
            select(ClientMetric)
            .where(ClientMetric.router_id == router_id)
            .order_by(ClientMetric.time.desc())
            .limit(limit)
        )
    )
    return list(reversed(rows))


@router.get("/routers/{router_id}/status", response_model=StatusRead)
def router_status(router_id: str, db: Session = Depends(get_db)) -> RouterStatus:
    item = db.get(RouterStatus, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router status not found")
    return item


@router.post("/routers/{router_id}/clients/access")
def set_client_access(
    router_id: str,
    payload: ClientAccessUpdate,
    db: Session = Depends(get_db),
    _support: AppUser = Depends(_require_first_support),
) -> dict[str, str]:
    item, password = _router_credentials(router_id, db)
    access = "deny" if payload.blocked else "permit"
    try:
        with _keenetic_client(item, password) as client:
            client.set_hotspot_host_access(payload.mac, access)
            client.save_configuration()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router client access update failed: {exc}") from exc
    _sync_blocked_client(router_id, payload.mac, payload.blocked, db)
    db.commit()
    return {"status": "ok", "mac": payload.mac, "access": access}


@router.post("/routers/{router_id}/wifi/password")
def set_wifi_password(
    router_id: str,
    payload: WifiPasswordUpdate,
    db: Session = Depends(get_db),
    _support: AppUser = Depends(_require_first_support),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    access_points = payload.access_points or ["WifiMaster0/AccessPoint0", "WifiMaster1/AccessPoint0"]
    try:
        with _keenetic_client(item, password) as client:
            for access_point in access_points:
                client.set_wifi_password(access_point, payload.password)
            if payload.save:
                client.save_configuration()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router Wi-Fi password update failed: {exc}") from exc
    return {"status": "ok", "access_points": access_points}


@router.post("/routers/{router_id}/wifi/ssid")
def set_wifi_ssid(
    router_id: str,
    payload: WifiSsidUpdate,
    db: Session = Depends(get_db),
    _support: AppUser = Depends(_require_first_support),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    access_points = payload.access_points or ["WifiMaster0/AccessPoint0", "WifiMaster1/AccessPoint0"]
    try:
        with _keenetic_client(item, password) as client:
            for access_point in access_points:
                client.set_wifi_ssid(access_point, payload.ssid)
            if payload.save:
                client.save_configuration()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router Wi-Fi name update failed: {exc}") from exc
    return {"status": "ok", "ssid": payload.ssid, "access_points": access_points}


@router.post("/routers/{router_id}/wifi/power")
def set_wifi_power(
    router_id: str,
    payload: WifiPowerUpdate,
    db: Session = Depends(get_db),
    _support: AppUser = Depends(_require_first_support),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    access_points = payload.access_points or ["WifiMaster0/AccessPoint0", "WifiMaster1/AccessPoint0"]
    try:
        with _keenetic_client(item, password) as client:
            for access_point in access_points:
                client.set_interface_enabled(access_point, payload.enabled)
            if payload.save:
                client.save_configuration()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router Wi-Fi power update failed: {exc}") from exc
    return {"status": "ok", "enabled": payload.enabled, "access_points": access_points}


@router.post("/routers/{router_id}/interfaces/{interface_id:path}/power")
def set_interface_power(
    router_id: str,
    interface_id: str,
    payload: InterfacePowerUpdate,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> dict[str, object]:
    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password) as client:
            client.set_interface_enabled(interface_id, payload.enabled)
            if payload.save:
                client.save_configuration()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router interface power update failed: {exc}") from exc
    return {"status": "ok", "interface_id": interface_id, "enabled": payload.enabled}


@router.post("/routers/{router_id}/restart")
def restart_router(
    router_id: str,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> dict[str, str]:
    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password) as client:
            client.reboot()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router restart failed: {exc}") from exc
    return {"status": "ok"}


@router.post("/routers/{router_id}/test")
def test_router(
    router_id: str,
    db: Session = Depends(get_db),
    _admin: AppUser = Depends(_require_admin),
) -> dict[str, str]:
    item, password = _router_credentials(router_id, db)
    try:
        with _keenetic_client(item, password) as client:
            client.login()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Router RCI test failed: {exc}") from exc
    return {"status": "ok"}


def _router_credentials(router_id: str, db: Session) -> tuple[Router, str]:
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    password = decrypt_secret(item.password_encrypted)
    if password is None:
        raise HTTPException(status_code=400, detail="Router password is not configured")
    return item, password


def _keenetic_client(item: Router, password: str, *, timeout: float = 10.0) -> KeeneticClient:
    return KeeneticClient(
        item.host,
        item.port,
        item.username,
        password,
        timeout=timeout,
        raw_response_dir=get_settings().raw_response_dir,
        router_id=item.id,
    )


def _router_recently_online(router_id: str, db: Session, *, max_age_seconds: int = 60) -> bool:
    status_row = db.get(RouterStatus, router_id)
    if status_row is None or not status_row.online or status_row.last_seen is None:
        return False
    last_seen = status_row.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (utcnow() - last_seen).total_seconds() <= max_age_seconds


def _write_router_identity(router_item: Router, system, version) -> None:
    system_data = system if isinstance(system, dict) else {}
    version_data = version if isinstance(version, dict) else {}
    router_item.model = version_data.get("model") or version_data.get("description") or system_data.get("model") or router_item.model
    router_item.firmware_version = (
        version_data.get("release")
        or version_data.get("title")
        or system_data.get("release")
        or system_data.get("version")
        or router_item.firmware_version
    )


def _version_summary(data) -> dict[str, object | None]:
    version = data if isinstance(data, dict) else {}
    return {
        "release": version.get("release"),
        "title": version.get("title"),
        "model": version.get("model") or version.get("description"),
        "channel": version.get("sandbox"),
        "device": version.get("device"),
    }


def _components_summary(data) -> dict[str, object | None]:
    components = data.get("component") if isinstance(data, dict) else {}
    queued = [
        name
        for name, item in components.items()
        if isinstance(item, dict) and item.get("queued")
    ] if isinstance(components, dict) else []
    firmware = data.get("firmware") if isinstance(data, dict) else {}
    local = data.get("local") if isinstance(data, dict) else {}
    available = firmware.get("version") if isinstance(firmware, dict) else None
    current = local.get("version") if isinstance(local, dict) else None
    return {
        "current_version": current,
        "available_version": available,
        "available_title": firmware.get("title") if isinstance(firmware, dict) else None,
        "channel": data.get("sandbox") if isinstance(data, dict) else None,
        "update_available": bool(available and current and available != current),
        "queued_count": len(queued),
        "queued_components": queued[:12],
    }


def _support_script(verdict: str, warnings: list[str]) -> str:
    lines = [
        f"Nəticə: {verdict}.",
        "Abunəçiyə/müəssisəyə bildirin: hazırda əsas şəbəkə testləri yoxlanıldı.",
    ]
    if warnings:
        lines.append("Yoxlanmalı məqamlar: " + "; ".join(warnings) + ".")
    else:
        lines.append("Router, internet ping, DNS və sayt yoxlaması normal görünür.")
    lines.extend(
        [
            "Növbəti addım: problem bir cihazdadırsa, həmin cihazın Wi-Fi/LAN bağlantısını və IP alıb-almadığını yoxlayın.",
            "Problem bütün cihazlardadırsa, son diaqnostika nəticəsini first support qrupuna ötürün.",
        ]
    )
    return "\n".join(lines)


def _ping_average_ms(output: str) -> float | None:
    match = re.search(r"=\s*([\d.]+)/([\d.]+)/([\d.]+)/", output)
    if not match:
        return None
    return float(match.group(2))


def _ping_loss_percent(output: str) -> float | None:
    match = re.search(r"([\d.]+)%\s*packet loss", output)
    if not match:
        return None
    return float(match.group(1))


def _sync_blocked_client(router_id: str, mac: str, blocked: bool, db: Session) -> None:
    normalized_mac = mac.lower()
    existing = db.get(BlockedClient, {"router_id": router_id, "mac": normalized_mac})
    if not blocked:
        if existing is not None:
            db.delete(existing)
        return

    client = db.scalar(
        select(CurrentClient).where(CurrentClient.router_id == router_id, func.lower(CurrentClient.mac) == normalized_mac)
    )
    if existing is None:
        existing = BlockedClient(router_id=router_id, mac=normalized_mac)
        db.add(existing)
    existing.hostname = client.hostname if client is not None else existing.hostname
    existing.ip = client.ip if client is not None else existing.ip


def _metric_traffic_groups(metric: RouterMetric) -> dict[str, dict[str, int | None]]:
    raw = metric.raw or {}
    interfaces = raw.get("interfaces") if isinstance(raw, dict) else None
    interface_stats = raw.get("interface_stats") if isinstance(raw, dict) else None
    return parse_traffic_groups(interfaces, interface_stats=interface_stats if isinstance(interface_stats, dict) else None)


def _traffic_bps(
    current: dict[str, dict[str, int | None]],
    previous: dict[str, dict[str, int | None]],
    group: str,
    field: str,
    seconds: float,
) -> float | None:
    current_value = current.get(group, {}).get(field)
    previous_value = previous.get(group, {}).get(field)
    if current_value is None or previous_value is None:
        return None
    delta = current_value - previous_value
    return (delta * 8) / seconds if delta >= 0 else None


def _max_total_traffic_bps(metrics: list[RouterMetric]) -> float | None:
    samples: list[tuple[RouterMetric, dict[str, dict[str, int | None]]]] = []
    for metric in metrics:
        groups = _metric_traffic_groups(metric)
        if any(value is not None for bucket in groups.values() for value in bucket.values()):
            samples.append((metric, groups))
    peak = None
    for index in range(len(samples) - 1):
        current, current_groups = samples[index]
        previous, previous_groups = samples[index + 1]
        seconds = (current.time - previous.time).total_seconds()
        if seconds <= 0:
            continue
        rx_bps = _traffic_bps(current_groups, previous_groups, "total", "rx_bytes", seconds)
        tx_bps = _traffic_bps(current_groups, previous_groups, "total", "tx_bytes", seconds)
        total = sum(value or 0 for value in (rx_bps, tx_bps))
        if total > 0:
            peak = max(peak or 0, total)
    return peak
