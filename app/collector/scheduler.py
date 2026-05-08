from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.collector.keenetic_client import KeeneticClient
from app.collector.parser import parse_clients, parse_router_metric, traffic_stat_targets
from app.config import get_settings
from app.db.postgres import SessionLocal
from app.models import ClientMetric, CurrentClient, Router, RouterMetric, RouterStatus, decrypt_secret

logger = logging.getLogger(__name__)


class PollScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._stop = asyncio.Event()
        self._realtime_clients: dict[str, tuple[str, KeeneticClient]] = {}

    async def run(self) -> None:
        interval = max(
            min(
                self.settings.router_poll_wan_seconds,
                self.settings.router_poll_clients_seconds,
                self.settings.router_poll_traffic_seconds,
                self.settings.router_poll_system_seconds,
            ),
            1,
        )
        tasks = [asyncio.create_task(self._loop("realtime", interval, self.poll_all))]
        await self._stop.wait()
        for task in tasks:
            task.cancel()

    def stop(self) -> None:
        self._stop.set()
        for _signature, client in self._realtime_clients.values():
            client.close()
        self._realtime_clients.clear()

    async def _loop(self, name: str, interval: int, func) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(func)
            except Exception:
                logger.exception("Collector loop failed", extra={"loop": name})
            await asyncio.sleep(interval)

    def poll_wan(self) -> None:
        self._poll_metrics(include_system=False, include_interfaces=True)

    def poll_traffic(self) -> None:
        self._poll_metrics(include_system=False, include_interfaces=True)

    def poll_system(self) -> None:
        self._poll_metrics(include_system=True, include_interfaces=True)

    def poll_clients(self) -> None:
        with SessionLocal() as db:
            for router in self._enabled_routers(db):
                password = decrypt_secret(router.password_encrypted)
                if not password:
                    logger.warning("Skipping router without password", extra={"router_id": router.id})
                    continue
                try:
                    with self._client(router, password) as client:
                        leases = client.get_dhcp_leases()
                        arp = client.get_arp_table()
                        wifi = client.get_wifi_clients()
                        connected = client.get_connected_clients()
                    rows = parse_clients(router.id, leases=leases, wifi_clients=wifi, connected_clients=connected, arp_table=arp)
                    db.execute(delete(CurrentClient).where(CurrentClient.router_id == router.id))
                    db.add_all(CurrentClient(**row) for row in rows)
                    self._mark_success(db, router.id)
                    db.commit()
                except Exception:
                    logger.exception("Client poll failed", extra={"router_id": router.id, "host": router.host})
                    self._mark_failure(db, router)
                    db.commit()

    def poll_all(self) -> None:
        with SessionLocal() as db:
            for router in self._enabled_routers(db):
                password = decrypt_secret(router.password_encrypted)
                if not password:
                    logger.warning("Skipping router without password", extra={"router_id": router.id})
                    continue
                try:
                    client = self._realtime_client(router, password)
                    system = client.get_system_info()
                    version = self._version_info(client)
                    interfaces = client.get_interfaces()
                    interface_stats = self._interface_stats(client, interfaces)
                    leases = client.get_dhcp_leases()
                    arp = client.get_arp_table()
                    wifi = client.get_wifi_clients()
                    connected = client.get_connected_clients()

                    metric = parse_router_metric(router.id, system=system, interfaces=interfaces, interface_stats=interface_stats)
                    clients = parse_clients(router.id, leases=leases, wifi_clients=wifi, connected_clients=connected, arp_table=arp)
                    self._write_metric(db, metric)
                    self._write_clients(db, router.id, clients)
                    self._write_client_metrics(db, clients, metric.timestamp)
                    self._mark_success(db, router.id)
                    self._write_router_identity(router, system, version)
                    db.commit()
                except Exception:
                    logger.exception("Realtime poll failed", extra={"router_id": router.id, "host": router.host})
                    self._mark_failure(db, router)
                    db.commit()

    def _poll_metrics(self, *, include_system: bool, include_interfaces: bool) -> None:
        with SessionLocal() as db:
            for router in self._enabled_routers(db):
                password = decrypt_secret(router.password_encrypted)
                if not password:
                    logger.warning("Skipping router without password", extra={"router_id": router.id})
                    continue
                try:
                    system = None
                    version = None
                    interfaces = None
                    interface_stats = None
                    with self._client(router, password) as client:
                        if include_system:
                            system = client.get_system_info()
                            version = self._version_info(client)
                        if include_interfaces:
                            interfaces = client.get_interfaces()
                        interface_stats = self._interface_stats(client, interfaces) if interfaces is not None else None
                    metric = parse_router_metric(router.id, system=system, interfaces=interfaces, interface_stats=interface_stats)
                    self._write_metric(db, metric)
                    self._mark_success(db, router.id)
                    self._write_router_identity(router, system, version)
                    db.commit()
                except Exception:
                    logger.exception("Metric poll failed", extra={"router_id": router.id, "host": router.host})
                    self._mark_failure(db, router)
                    db.commit()

    def _client(self, router: Router, password: str) -> KeeneticClient:
        return KeeneticClient(
            router.host,
            router.port,
            router.username,
            password,
            raw_response_dir=self.settings.raw_response_dir,
            save_raw_responses=self.settings.save_raw_responses,
            router_id=router.id,
        )

    def _realtime_client(self, router: Router, password: str) -> KeeneticClient:
        signature = f"{router.host}:{router.port}:{router.username}:{password}"
        cached = self._realtime_clients.get(router.id)
        if cached and cached[0] == signature:
            return cached[1]
        if cached:
            cached[1].close()
        client = self._client(router, password)
        self._realtime_clients[router.id] = (signature, client)
        return client

    @staticmethod
    def _interface_stats(client: KeeneticClient, interfaces) -> dict[str, object]:
        stats: dict[str, object] = {}
        for target in traffic_stat_targets(interfaces):
            try:
                stats[target] = client.get_interface_stat(target)
            except Exception:
                logger.debug("Interface stat poll failed", exc_info=True, extra={"interface": target})
        return stats

    @staticmethod
    def _version_info(client: KeeneticClient) -> dict[str, object] | None:
        try:
            data = client.get_version_info()
        except Exception:
            logger.debug("Version poll failed", exc_info=True)
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _write_router_identity(router: Router, system, version) -> None:
        system_data = system if isinstance(system, dict) else {}
        version_data = version if isinstance(version, dict) else {}
        router.model = version_data.get("model") or version_data.get("description") or system_data.get("model") or router.model
        router.firmware_version = (
            version_data.get("release")
            or version_data.get("title")
            or system_data.get("release")
            or system_data.get("version")
            or router.firmware_version
        )

    @staticmethod
    def _enabled_routers(db: Session) -> list[Router]:
        return list(db.scalars(select(Router).where(Router.enabled.is_(True))))

    @staticmethod
    def _write_metric(db: Session, metric) -> None:
        db.add(
            RouterMetric(
                time=metric.timestamp,
                router_id=metric.router_id,
                cpu_usage=metric.cpu_usage,
                ram_usage=metric.ram_usage,
                uptime=metric.uptime,
                wan_status=metric.wan_status,
                wan_ip=metric.wan_ip,
                rx_bytes_total=metric.rx_bytes_total,
                tx_bytes_total=metric.tx_bytes_total,
                online=metric.online,
                raw=metric.raw,
            )
        )
        stmt = insert(RouterStatus).values(
            router_id=metric.router_id,
            online=True,
            wan_status=metric.wan_status,
            wan_ip=metric.wan_ip,
            cpu_usage=metric.cpu_usage,
            ram_usage=metric.ram_usage,
            uptime=metric.uptime,
            rx_bytes_total=metric.rx_bytes_total,
            tx_bytes_total=metric.tx_bytes_total,
            last_seen=metric.timestamp,
            updated_at=metric.timestamp,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RouterStatus.router_id],
            set_={
                "online": True,
                "wan_status": func.coalesce(stmt.excluded.wan_status, RouterStatus.wan_status),
                "wan_ip": func.coalesce(stmt.excluded.wan_ip, RouterStatus.wan_ip),
                "cpu_usage": func.coalesce(stmt.excluded.cpu_usage, RouterStatus.cpu_usage),
                "ram_usage": func.coalesce(stmt.excluded.ram_usage, RouterStatus.ram_usage),
                "uptime": func.coalesce(stmt.excluded.uptime, RouterStatus.uptime),
                "rx_bytes_total": func.coalesce(stmt.excluded.rx_bytes_total, RouterStatus.rx_bytes_total),
                "tx_bytes_total": func.coalesce(stmt.excluded.tx_bytes_total, RouterStatus.tx_bytes_total),
                "last_seen": stmt.excluded.last_seen,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)

    @staticmethod
    def _write_clients(db: Session, router_id: str, rows) -> None:
        db.execute(delete(CurrentClient).where(CurrentClient.router_id == router_id))
        db.add_all(CurrentClient(**row) for row in rows)

    @staticmethod
    def _write_client_metrics(db: Session, rows, timestamp: datetime) -> None:
        metrics = []
        for row in rows:
            client_key = row.get("mac") or row.get("ip") or row.get("hostname")
            if not client_key:
                continue
            metrics.append(
                ClientMetric(
                    time=timestamp,
                    router_id=row["router_id"],
                    client_key=client_key,
                    hostname=row.get("hostname"),
                    mac=row.get("mac"),
                    ip=row.get("ip"),
                    rx_bytes=row.get("rx_bytes"),
                    tx_bytes=row.get("tx_bytes"),
                    signal=row.get("signal"),
                )
            )
        db.add_all(metrics)

    @staticmethod
    def _mark_success(db: Session, router_id: str) -> None:
        router = db.get(Router, router_id)
        if router is not None:
            router.failure_count = 0

    def _mark_failure(self, db: Session, router: Router) -> None:
        router.failure_count += 1
        if router.failure_count < self.settings.router_offline_after_failures:
            return
        now = datetime.now(timezone.utc)
        status = db.get(RouterStatus, router.id)
        if status and status.last_seen:
            last_seen = status.last_seen
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            if (now - last_seen).total_seconds() < self.settings.router_offline_grace_seconds:
                return
        stmt = insert(RouterStatus).values(
            router_id=router.id,
            online=False,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RouterStatus.router_id],
            set_={"online": False, "updated_at": now},
        )
        db.execute(stmt)
