import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.collector.keenetic_client import KeeneticClient
from app.collector.parser import parse_clients, parse_router_metric
from app.config import get_settings
from app.db.postgres import SessionLocal
from app.models import CurrentClient, Router, RouterMetric, RouterStatus, decrypt_secret

logger = logging.getLogger(__name__)


class PollScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._stop = asyncio.Event()

    async def run(self) -> None:
        tasks = [
            asyncio.create_task(self._loop("wan", self.settings.router_poll_wan_seconds, self.poll_wan)),
            asyncio.create_task(self._loop("clients", self.settings.router_poll_clients_seconds, self.poll_clients)),
            asyncio.create_task(self._loop("traffic", self.settings.router_poll_traffic_seconds, self.poll_traffic)),
            asyncio.create_task(self._loop("system", self.settings.router_poll_system_seconds, self.poll_system)),
        ]
        await self._stop.wait()
        for task in tasks:
            task.cancel()

    def stop(self) -> None:
        self._stop.set()

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
                        wifi = client.get_wifi_clients()
                        connected = client.get_connected_clients()
                    rows = parse_clients(router.id, leases=leases, wifi_clients=wifi, connected_clients=connected)
                    db.execute(delete(CurrentClient).where(CurrentClient.router_id == router.id))
                    db.add_all(CurrentClient(**row) for row in rows)
                    self._mark_success(db, router.id)
                    db.commit()
                except Exception:
                    logger.exception("Client poll failed", extra={"router_id": router.id, "host": router.host})
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
                    interfaces = None
                    with self._client(router, password) as client:
                        if include_system:
                            system = client.get_system_info()
                        if include_interfaces:
                            interfaces = client.get_interfaces()
                    metric = parse_router_metric(router.id, system=system, interfaces=interfaces)
                    self._write_metric(db, metric)
                    self._mark_success(db, router.id)
                    if system:
                        router.model = system.get("model") or router.model if isinstance(system, dict) else router.model
                        router.firmware_version = system.get("release") or system.get("version") or router.firmware_version if isinstance(system, dict) else router.firmware_version
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
            router_id=router.id,
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
    def _mark_success(db: Session, router_id: str) -> None:
        router = db.get(Router, router_id)
        if router is not None:
            router.failure_count = 0

    def _mark_failure(self, db: Session, router: Router) -> None:
        router.failure_count += 1
        if router.failure_count < self.settings.router_offline_after_failures:
            return
        now = datetime.now(timezone.utc)
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
