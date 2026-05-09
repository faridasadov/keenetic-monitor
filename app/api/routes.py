from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import subprocess
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
        "exp": int((utcnow() + timedelta(hours=12)).timestamp()),
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


def _require_admin(current_user: AppUser = Depends(_current_user)) -> AppUser:
    if current_user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Admin access required")
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
        existing.site = payload.site
        existing.username = payload.username
        existing.password_encrypted = encrypt_secret(payload.password)
        existing.access_method = payload.access_method.value
        existing.enabled = payload.enabled
        db.commit()
        db.refresh(existing)
        return existing

    item = Router(
        name=payload.name,
        site=payload.site,
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


@router.get("/routers/{router_id}/summary", response_model=SummaryRead)
def router_summary(router_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    status_row = db.get(RouterStatus, router_id)
    if status_row is None:
        raise HTTPException(status_code=404, detail="Router status not found")
    client_count = db.scalar(select(func.count()).select_from(CurrentClient).where(CurrentClient.router_id == router_id)) or 0
    metrics = list(
        db.scalars(
            select(RouterMetric)
            .where(RouterMetric.router_id == router_id)
            .order_by(RouterMetric.time.desc())
            .limit(8)
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
    wan_provider = None
    for index in range(len(metrics) - 1):
        current, previous = metrics[index], metrics[index + 1]
        seconds = (current.time - previous.time).total_seconds()
        if seconds <= 0:
            continue
        if current.rx_bytes_total is not None and previous.rx_bytes_total is not None:
            delta = current.rx_bytes_total - previous.rx_bytes_total
            wan_rx_bps = (delta * 8) / seconds if delta >= 0 else None
        if current.tx_bytes_total is not None and previous.tx_bytes_total is not None:
            delta = current.tx_bytes_total - previous.tx_bytes_total
            wan_tx_bps = (delta * 8) / seconds if delta >= 0 else None
        current_groups = _metric_traffic_groups(current)
        previous_groups = _metric_traffic_groups(previous)
        total_rx_bps = _traffic_bps(current_groups, previous_groups, "total", "rx_bytes", seconds)
        total_tx_bps = _traffic_bps(current_groups, previous_groups, "total", "tx_bytes", seconds)
        lan_rx_bps = _traffic_bps(current_groups, previous_groups, "lan", "rx_bytes", seconds)
        lan_tx_bps = _traffic_bps(current_groups, previous_groups, "lan", "tx_bytes", seconds)
        wifi_rx_bps = _traffic_bps(current_groups, previous_groups, "wifi", "rx_bytes", seconds)
        wifi_tx_bps = _traffic_bps(current_groups, previous_groups, "wifi", "tx_bytes", seconds)
        if any(value is not None for value in (lan_rx_bps, lan_tx_bps, wifi_rx_bps, wifi_tx_bps)):
            break
    if metrics:
        raw = metrics[0].raw or {}
        if isinstance(raw, dict):
            wan_provider = parse_wan_info(raw.get("interfaces")).get("provider")
    return {
        "router_id": router_id,
        "client_count": client_count,
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
    command = ["ping", "-c", str(payload.count), "-W", "2", payload.host]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(payload.count * 3, 6),
            check=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Server ping command is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(part for part in (exc.stdout, exc.stderr) if part)
        return {
            "host": payload.host,
            "count": payload.count,
            "method": "icmp",
            "ok": False,
            "output": output.strip() or "Ping timeout",
        }
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    avg_ms = _ping_average_ms(output)
    loss_percent = _ping_loss_percent(output)
    return {
        "host": payload.host,
        "count": payload.count,
        "method": "icmp",
        "ok": completed.returncode == 0,
        "avg_ms": avg_ms,
        "loss_percent": loss_percent,
        "warning": avg_ms is not None and avg_ms > 120,
        "output": output,
    }


@router.post("/site-check")
def check_site(payload: SiteCheckRequest, _user: AppUser = Depends(_current_user)) -> dict[str, object]:
    raw_url = payload.url.strip()
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


@router.post("/speedtest")
def speedtest(_user: AppUser = Depends(_current_user)) -> dict[str, object]:
    command = ["speedtest-cli", "--json", "--secure", "--timeout", "20"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="speedtest-cli is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(part for part in (exc.stdout, exc.stderr) if part)
        return {"ok": False, "warning": True, "tool": "speedtest-cli", "errors": [output.strip() or "Speedtest timeout"]}
    if completed.returncode != 0:
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        return {"ok": False, "warning": True, "tool": "speedtest-cli", "errors": [output or "Speedtest failed"]}
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"speedtest-cli returned invalid JSON: {exc}") from exc
    download_mbps = round((float(data.get("download") or 0) / 1_000_000), 2)
    upload_mbps = round((float(data.get("upload") or 0) / 1_000_000), 2)
    ping_ms = round(float(data.get("ping") or 0), 2)
    server = data.get("server") if isinstance(data.get("server"), dict) else {}
    return {
        "ok": True,
        "tool": "speedtest-cli",
        "download_mbps": download_mbps,
        "upload_mbps": upload_mbps,
        "ping_ms": ping_ms,
        "server": {
            "sponsor": server.get("sponsor"),
            "name": server.get("name"),
            "country": server.get("country"),
            "host": server.get("host"),
        },
        "warning": download_mbps < 10 or ping_ms > 120,
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
    _admin: AppUser = Depends(_require_admin),
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
    _admin: AppUser = Depends(_require_admin),
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
    _admin: AppUser = Depends(_require_admin),
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
    _admin: AppUser = Depends(_require_admin),
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
