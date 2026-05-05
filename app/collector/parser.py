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
    online: bool = True,
    timestamp: datetime | None = None,
) -> RouterMetricData:
    system = system or {}
    rx_total, tx_total = parse_total_traffic(interfaces)
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
        raw={"system": system, "interfaces": interfaces},
    )


def parse_total_traffic(interfaces: Any) -> tuple[int | None, int | None]:
    rows = interfaces if isinstance(interfaces, list) else interfaces.get("interface", []) if isinstance(interfaces, dict) else []
    rx_total = 0
    tx_total = 0
    found = False
    for row in rows if isinstance(rows, list) else []:
        counters = row.get("counters", row) if isinstance(row, dict) else {}
        rx = _as_int(counters.get("rxbytes") or counters.get("rx-bytes") or counters.get("ibytes"))
        tx = _as_int(counters.get("txbytes") or counters.get("tx-bytes") or counters.get("obytes"))
        if rx is not None or tx is not None:
            rx_total += rx or 0
            tx_total += tx or 0
            found = True
    return (rx_total, tx_total) if found else (None, None)


def parse_wan_status(interfaces: Any) -> tuple[str | None, str | None]:
    rows = interfaces if isinstance(interfaces, list) else interfaces.get("interface", []) if isinstance(interfaces, dict) else []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("id") or row.get("name") or row.get("interface") or "")
        role = str(row.get("role") or row.get("description") or "")
        if "wan" not in f"{name} {role}".lower() and "internet" not in f"{name} {role}".lower():
            continue
        status = str(row.get("state") or row.get("status") or row.get("link") or "unknown")
        address = row.get("address") or row.get("ip") or row.get("global")
        if isinstance(address, list) and address:
            address = address[0]
        return status, str(address) if address else None
    return None, None


def parse_clients(
    router_id: str,
    *,
    leases: Any = None,
    wifi_clients: Any = None,
    connected_clients: Any = None,
    timestamp: datetime | None = None,
) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    ts = timestamp or utcnow()

    for row in _rows(leases):
        mac = _norm_mac(row.get("mac") or row.get("mac-address") or row.get("hardware"))
        key = mac or str(row.get("ip") or row.get("address") or "")
        if not key:
            continue
        seen[key] = {
            "router_id": router_id,
            "hostname": row.get("hostname") or row.get("name"),
            "mac": mac,
            "ip": row.get("ip") or row.get("address"),
            "interface": row.get("interface"),
            "connection_type": "unknown",
            "rx_bytes": None,
            "tx_bytes": None,
            "signal": None,
            "last_seen": ts,
        }

    for row in _rows(wifi_clients):
        mac = _norm_mac(row.get("mac") or row.get("mac-address") or row.get("sta"))
        key = mac or str(row.get("ip") or "")
        if not key:
            continue
        client = seen.setdefault(key, {"router_id": router_id, "mac": mac, "last_seen": ts})
        client.update(
            {
                "hostname": client.get("hostname") or row.get("hostname") or row.get("name"),
                "ip": client.get("ip") or row.get("ip"),
                "interface": row.get("interface") or row.get("ap") or client.get("interface"),
                "connection_type": "wifi",
                "rx_bytes": _as_int(row.get("rxbytes") or row.get("rx-bytes")),
                "tx_bytes": _as_int(row.get("txbytes") or row.get("tx-bytes")),
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
                "rx_bytes": _as_int(row.get("rxbytes") or row.get("rx-bytes")) or client.get("rx_bytes"),
                "tx_bytes": _as_int(row.get("txbytes") or row.get("tx-bytes")) or client.get("tx_bytes"),
                "signal": client.get("signal"),
                "last_seen": ts,
            }
        )

    return list(seen.values())


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _norm_mac(value: Any) -> str | None:
    if not value:
        return None
    return str(value).lower().replace("-", ":")
