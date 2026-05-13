from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import RouterMetricData, utcnow


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _memory_usage(system: dict[str, Any]) -> float | None:
    total = _as_int(system.get("memtotal"))
    free = _as_int(system.get("memfree"))
    buffers = _as_int(system.get("membuffers")) or 0
    cache = _as_int(system.get("memcache")) or 0
    if not total:
        return None
    used = max(total - (free or 0) - buffers - cache, 0)
    return round((used / total) * 100, 2)


def parse_router_metric(
    router_id: str,
    *,
    system: dict[str, Any] | None = None,
    interfaces: Any = None,
    interface_stats: dict[str, Any] | None = None,
    online: bool = True,
    timestamp: datetime | None = None,
) -> RouterMetricData:
    system = system or {}
    rx_total, tx_total = parse_total_traffic(interfaces, interface_stats=interface_stats)
    wan_status, wan_ip = parse_wan_status(interfaces)

    return RouterMetricData(
        router_id=router_id,
        cpu_usage=_as_int(system.get("cpuload")),
        ram_usage=_memory_usage(system),
        uptime=_as_int(system.get("uptime")),
        wan_status=wan_status,
        wan_ip=wan_ip,
        rx_bytes_total=rx_total,
        tx_bytes_total=tx_total,
        timestamp=timestamp or utcnow(),
        online=online,
        raw={"system": system, "interfaces": interfaces, "interface_stats": interface_stats or {}},
    )


def parse_total_traffic(interfaces: Any, *, interface_stats: dict[str, Any] | None = None) -> tuple[int | None, int | None]:
    groups = parse_traffic_groups(interfaces, interface_stats=interface_stats)
    total = groups["total"]
    rx_total = total.get("rx_bytes")
    tx_total = total.get("tx_bytes")
    found = rx_total is not None or tx_total is not None
    return (rx_total, tx_total) if found else (None, None)


def parse_traffic_groups(interfaces: Any, *, interface_stats: dict[str, Any] | None = None) -> dict[str, dict[str, int | None]]:
    groups: dict[str, dict[str, int | None]] = {
        "total": {"rx_bytes": None, "tx_bytes": None},
        "lan": {"rx_bytes": None, "tx_bytes": None},
        "wifi": {"rx_bytes": None, "tx_bytes": None},
    }
    rows = _interface_rows(interfaces)
    by_name = _interface_index(rows)

    if interface_stats:
        for name, stats in interface_stats.items():
            if not isinstance(stats, dict):
                continue
            rx = _as_int(stats.get("rxbytes") or stats.get("rx-bytes") or stats.get("ibytes"))
            tx = _as_int(stats.get("txbytes") or stats.get("tx-bytes") or stats.get("obytes"))
            if rx is None and tx is None:
                continue
            row = by_name.get(name) or {"id": name, "interface-name": name}
            group = _traffic_group(row)
            if group == "wan":
                _add_traffic(groups["total"], rx, tx)
            elif group in {"lan", "wifi"}:
                _add_traffic(groups[group], rx, tx)
        return groups

    for row in rows:
        if not isinstance(row, dict):
            continue
        counters = row.get("counters", row)
        if not isinstance(counters, dict):
            counters = {}
        rx = _as_int(counters.get("rxbytes") or counters.get("rx-bytes") or counters.get("ibytes"))
        tx = _as_int(counters.get("txbytes") or counters.get("tx-bytes") or counters.get("obytes"))
        if rx is None and tx is None:
            continue

        _add_traffic(groups["total"], rx, tx)
        group = _traffic_group(row)
        if group in {"lan", "wifi"}:
            _add_traffic(groups[group], rx, tx)

    return groups


def _add_traffic(group: dict[str, int | None], rx: int | None, tx: int | None) -> None:
    if rx is not None:
        group["rx_bytes"] = (group["rx_bytes"] or 0) + rx
    if tx is not None:
        group["tx_bytes"] = (group["tx_bytes"] or 0) + tx


def _traffic_group(row: dict[str, Any]) -> str | None:
    kind = str(row.get("type") or "")
    name = str(row.get("id") or row.get("name") or row.get("interface") or row.get("interface-name") or "")
    label = str(row.get("label") or row.get("description") or "")
    role = row.get("role")
    role_text = ""
    if isinstance(role, list):
        role_text = " ".join(
            f"{item.get('role') or ''} {item.get('for') or ''}" for item in role if isinstance(item, dict)
        )
    elif role is not None:
        role_text = str(role)
    search = f"{kind} {name} {label} {role_text}".lower()

    if row.get("defaultgw") is True or row.get("public") is True or row.get("security-level") == "public":
        return "wan"
    if kind in {"AccessPoint", "WifiMaster"} or "wifi" in search or "accesspoint" in search:
        return "wifi"
    if kind == "Bridge" or "bridge" in search or "lan" in search or "home" in search or "guest" in search:
        if "inet" not in search and "wan" not in search and "internet" not in search:
            return "lan"
    return None


def traffic_stat_targets(interfaces: Any) -> list[str]:
    targets: list[str] = []
    for row in _interface_rows(interfaces):
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "")
        group = _traffic_group(row)
        if group == "wan" and row.get("defaultgw") is True:
            _append_target(targets, row)
        elif group == "lan" and kind == "Bridge" and row.get("state") in {"up", None}:
            _append_target(targets, row)
        elif group == "wifi" and kind == "AccessPoint" and row.get("state") == "up":
            _append_target(targets, row)
    return targets


def _append_target(targets: list[str], row: dict[str, Any]) -> None:
    name = str(row.get("interface-name") or row.get("id") or "")
    if name and name not in targets:
        targets.append(name)


def parse_wan_status(interfaces: Any) -> tuple[str | None, str | None]:
    info = parse_wan_info(interfaces)
    return info.get("status"), info.get("ip")


def parse_wan_info(interfaces: Any) -> dict[str, Any]:
    rows = _interface_rows(interfaces)
    by_id = {str(row.get("id") or ""): row for row in rows if isinstance(row, dict)}
    fallback: dict[str, Any] | None = None

    for row in rows:
        if isinstance(row, dict) and row.get("defaultgw") is True:
            return _wan_info_from_row(row)

    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("id") or row.get("name") or row.get("interface") or "")
        label = str(row.get("interface-name") or row.get("label") or "")
        role = str(row.get("role") or "")
        description = str(row.get("description") or "")
        search = f"{name} {label} {role} {description}".lower()
        role_items = row.get("role", [])
        if not isinstance(role_items, list):
            role_items = []
        role_target = next(
            (str(item.get("for")) for item in role_items if isinstance(item, dict) and item.get("role") == "inet" and item.get("for")),
            None,
        )
        if role_target and role_target in by_id:
            return _wan_info_from_row(by_id[role_target])
        is_wan = "wan" in search or "internet" in search or role_target is not None
        if not is_wan:
            continue
        fallback = fallback or _wan_info_from_row(row)
    return fallback or {"status": None, "ip": None, "provider": None, "speed_mbps": None}


def _wan_info_from_row(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("state") or row.get("status") or row.get("link") or "unknown")
    address = row.get("address") or row.get("ip")
    if isinstance(address, list) and address:
        address = address[0]
    provider = row.get("description") or row.get("interface-name") or row.get("label") or row.get("id")
    return {
        "status": status,
        "ip": str(address) if address else None,
        "provider": str(provider) if provider else None,
        "speed_mbps": _as_int(row.get("speed")),
    }


def _interface_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("id", "interface-name", "label"):
            value = row.get(key)
            if value:
                index[str(value)] = row
    return index


def parse_ports(interfaces: Any) -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    seen: set[str] = set()
    wan_port_prefixes = _wan_port_prefixes(interfaces)
    for row in _interface_rows(interfaces):
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "")
        if kind not in {"Port", "AccessPoint", "WifiMaster"}:
            continue
        port_id = str(row.get("id") or row.get("interface-name") or "")
        if not port_id or port_id in seen:
            continue
        seen.add(port_id)
        link = row.get("link")
        state = row.get("state")
        connected = link == "up" and (state in {None, "up"} or kind == "Port")
        role = row.get("role")
        if isinstance(role, list):
            role = ", ".join(str(item.get("role") or item.get("for") or "") for item in role if isinstance(item, dict))
        is_wan = _is_wan_port(row, wan_port_prefixes)
        category = "wan" if is_wan else _port_category(row)
        ports.append(
            {
                "id": str(row.get("id") or row.get("interface-name") or ""),
                "label": str(row.get("label") or row.get("interface-name") or row.get("id") or ""),
                "kind": kind,
                "category": category,
                "is_wan": is_wan,
                "link": str(link) if link is not None else None,
                "state": str(state) if state is not None else None,
                "connected": bool(connected),
                "speed_mbps": _as_int(row.get("speed")),
                "duplex": row.get("duplex"),
                "role": str(role) if role else None,
                "ssid": row.get("ssid"),
            }
        )
    return ports


def parse_wifi_credentials(interfaces: Any, running_config: Any = None) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in _interface_rows(interfaces):
        if not isinstance(row, dict) or str(row.get("type") or "") != "AccessPoint":
            continue
        ap_id = str(row.get("id") or row.get("interface-name") or "")
        if not ap_id:
            continue
        by_id[ap_id] = {
            "id": ap_id,
            "name": str(row.get("interface-name") or ap_id),
            "ssid": row.get("ssid"),
            "state": row.get("state"),
            "security": None,
        }

    current: dict[str, Any] | None = None
    for line in _config_lines(running_config):
        stripped = line.strip()
        if line.startswith("interface "):
            current_id = line.split(" ", 1)[1].strip()
            current = by_id.get(current_id)
            continue
        if current is None:
            continue
        if stripped.startswith("ssid "):
            current["ssid"] = stripped.split(" ", 1)[1].strip().strip('"')
        elif stripped.startswith("encryption "):
            current["security"] = stripped

    return [item for item in by_id.values() if item.get("ssid") or item.get("state") == "up"]


def _config_lines(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        lines = payload.get("message")
        if isinstance(lines, list):
            return [str(line) for line in lines]
    if isinstance(payload, list):
        return [str(line) for line in payload]
    return []


def _wan_port_prefixes(interfaces: Any) -> set[str]:
    prefixes: set[str] = set()
    for row in _interface_rows(interfaces):
        if not isinstance(row, dict) or row.get("defaultgw") is not True:
            continue
        interface_id = str(row.get("id") or row.get("interface-name") or "")
        if "/" in interface_id:
            prefixes.add(interface_id.split("/", 1)[0])
        elif interface_id:
            prefixes.add(interface_id)
    return prefixes


def _is_wan_port(row: dict[str, Any], wan_port_prefixes: set[str]) -> bool:
    port_id = str(row.get("id") or row.get("interface-name") or "")
    if port_id in wan_port_prefixes:
        return True
    return any(port_id.startswith(f"{prefix}/") for prefix in wan_port_prefixes)


def _port_category(row: dict[str, Any]) -> str:
    kind = str(row.get("type") or "")
    port_id = str(row.get("id") or "")
    if kind in {"AccessPoint", "WifiMaster"}:
        return "wifi"
    if kind == "Port" and port_id.startswith("GigabitEthernet0/"):
        return "access"
    if kind == "Port":
        return "uplink"
    return "other"


def parse_clients(
    router_id: str,
    *,
    leases: Any = None,
    wifi_clients: Any = None,
    connected_clients: Any = None,
    arp_table: Any = None,
    timestamp: datetime | None = None,
) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    ts = timestamp or utcnow()
    lease_index: dict[str, dict[str, Any]] = {}

    for row in _rows(leases):
        mac = _norm_mac(row.get("mac") or row.get("mac-address") or row.get("hardware"))
        ip = str(row.get("ip") or row.get("address") or "")
        if mac:
            lease_index[mac] = row
        if ip:
            lease_index[ip] = row

    for row in _rows(arp_table):
        mac = _norm_mac(row.get("mac") or row.get("mac-address") or row.get("hardware"))
        ip = str(row.get("ip") or row.get("address") or "")
        interface = str(row.get("interface") or "")
        state = str(row.get("state") or "").lower()
        if not mac and not ip:
            continue
        if interface and not interface.lower().startswith("bridge"):
            continue
        if state in {"failed", "incomplete", "stale"}:
            continue
        lease = lease_index.get(mac or "") or lease_index.get(ip) or {}
        key = mac or ip
        seen[key] = {
            "router_id": router_id,
            "hostname": lease.get("hostname") or lease.get("name"),
            "mac": mac,
            "ip": ip or lease.get("ip") or lease.get("address"),
            "interface": interface or lease.get("interface"),
            "connection_type": "lan",
            "rx_bytes": _client_rx_bytes(row) or _client_rx_bytes(lease),
            "tx_bytes": _client_tx_bytes(row) or _client_tx_bytes(lease),
            "signal": None,
            "last_seen": ts,
        }

    for row in _rows(leases):
        mac = _norm_mac(row.get("mac") or row.get("mac-address") or row.get("hardware"))
        key = mac or str(row.get("ip") or row.get("address") or "")
        if not key or key not in seen:
            continue
        seen[key]["hostname"] = seen[key].get("hostname") or row.get("hostname") or row.get("name")
        seen[key]["ip"] = seen[key].get("ip") or row.get("ip") or row.get("address")

    for row in _rows(wifi_clients):
        mac = _norm_mac(row.get("mac") or row.get("mac-address") or row.get("sta"))
        key = mac or str(row.get("ip") or "")
        if not key:
            continue
        lease = lease_index.get(mac or "") or lease_index.get(str(row.get("ip") or "")) or {}
        client = seen.setdefault(key, {"router_id": router_id, "mac": mac, "last_seen": ts})
        client.update(
            {
                "hostname": client.get("hostname") or row.get("hostname") or row.get("name") or lease.get("hostname") or lease.get("name"),
                "ip": client.get("ip") or row.get("ip") or lease.get("ip") or lease.get("address"),
                "interface": row.get("interface") or row.get("ap") or client.get("interface"),
                "connection_type": "wifi",
                "rx_bytes": _client_rx_bytes(row) or client.get("rx_bytes"),
                "tx_bytes": _client_tx_bytes(row) or client.get("tx_bytes"),
                "signal": _as_int(row.get("rssi") or row.get("signal")),
                "last_seen": ts,
            }
        )

    for row in _rows(connected_clients):
        mac = _norm_mac(row.get("mac") or row.get("mac-address"))
        key = mac or str(row.get("ip") or row.get("address") or "")
        if not key:
            continue
        client = seen.setdefault(key, {"router_id": router_id, "mac": mac, "last_seen": ts})
        client.update(
            {
                "hostname": client.get("hostname") or row.get("hostname") or row.get("name"),
                "ip": client.get("ip") or row.get("address") or client.get("ip"),
                "interface": row.get("interface") or client.get("interface"),
                "connection_type": client.get("connection_type") or "unknown",
                "rx_bytes": _client_rx_bytes(row) or client.get("rx_bytes"),
                "tx_bytes": _client_tx_bytes(row) or client.get("tx_bytes"),
                "signal": client.get("signal"),
                "last_seen": ts,
            }
        )

    return list(seen.values())


def _client_rx_bytes(row: dict[str, Any] | None) -> int | None:
    if not isinstance(row, dict):
        return None
    return _as_int(
        row.get("rxbytes")
        or row.get("rx-bytes")
        or row.get("ibytes")
        or row.get("in-bytes")
        or row.get("bytes-in")
        or row.get("received")
        or row.get("rx")
    )


def _client_tx_bytes(row: dict[str, Any] | None) -> int | None:
    if not isinstance(row, dict):
        return None
    return _as_int(
        row.get("txbytes")
        or row.get("tx-bytes")
        or row.get("obytes")
        or row.get("out-bytes")
        or row.get("bytes-out")
        or row.get("sent")
        or row.get("tx")
    )


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _interface_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    rows: list[dict[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            rows.append(value)
            nested_ports = value.get("port")
            if isinstance(nested_ports, dict):
                rows.extend(port for port in nested_ports.values() if isinstance(port, dict))
            continue
        if key == "interface" and isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    return rows


def _norm_mac(value: Any) -> str | None:
    if not value:
        return None
    return str(value).lower().replace("-", ":")
