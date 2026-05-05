import json
import logging
from hashlib import md5, sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class KeeneticClientError(RuntimeError):
    pass


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {404, 405}:
        return False
    return isinstance(exc, (httpx.HTTPError, KeeneticClientError))


class KeeneticClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        *,
        use_https: bool = False,
        timeout: float = 10.0,
        raw_response_dir: Path | None = None,
        router_id: str | None = None,
    ) -> None:
        scheme = "https" if use_https else "http"
        self.base_url = f"{scheme}://{host}:{port}/rci"
        self.username = username
        self._password = password
        self.timeout = timeout
        self.raw_response_dir = raw_response_dir
        self.router_id = router_id or host
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
        )
        self._digest_client = httpx.Client(
            auth=httpx.DigestAuth(username, password),
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
        )
        self._authenticated = False

    def close(self) -> None:
        self._client.close()
        self._digest_client.close()

    def __enter__(self) -> "KeeneticClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def login(self) -> bool:
        auth_url = self.base_url.rsplit("/rci", 1)[0] + "/auth"
        challenge_response = self._client.get(auth_url)
        if challenge_response.status_code == 200:
            self._authenticated = True
            return True
        if challenge_response.status_code != 401:
            raise KeeneticClientError(f"Keenetic auth challenge failed: HTTP {challenge_response.status_code}")

        realm = challenge_response.headers.get("X-NDM-Realm")
        challenge = challenge_response.headers.get("X-NDM-Challenge")
        if not realm or not challenge:
            self.get_system_info()
            self._authenticated = True
            return True

        password_hash = md5(f"{self.username}:{realm}:{self._password}".encode()).hexdigest()
        challenge_hash = sha256(f"{challenge}{password_hash}".encode()).hexdigest()
        response = self._client.post(auth_url, json={"login": self.username, "password": challenge_hash})
        if response.status_code == 401:
            raise KeeneticClientError("Keenetic interactive authentication failed")
        response.raise_for_status()
        self._authenticated = True
        return True

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def rci(self, command_payload: str | dict[str, Any], method: str = "GET") -> Any:
        method = method.upper()
        logger.debug("RCI request", extra={"base_url": self.base_url, "method": method})

        response = self._request(command_payload, method)

        if response.status_code == 401:
            www_auth = response.headers.get("WWW-Authenticate", "")
            if "x-ndw2-interactive" in www_auth:
                self.login()
                response = self._request(command_payload, method)
            else:
                response = self._digest_request(command_payload, method)
        if response.status_code == 401:
            raise KeeneticClientError("Keenetic RCI authentication failed")
        response.raise_for_status()
        data = response.json()
        self._save_raw_response(command_payload, data)
        return data

    def get_system_info(self) -> Any:
        return self.rci("show system")

    def get_interfaces(self) -> Any:
        return self.rci("show interface")

    def get_dhcp_leases(self) -> Any:
        return self.rci("show ip dhcp bindings")

    def get_connected_clients(self) -> Any:
        try:
            return self.rci("show ip hotspot hosts")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {404, 405}:
                return []
            raise

    def get_wifi_clients(self) -> Any:
        return self.rci("show associations")

    def get_traffic_counters(self) -> Any:
        return self.rci("show interface")

    def get_uptime(self) -> int | None:
        data = self.get_system_info()
        uptime = data.get("uptime") if isinstance(data, dict) else None
        return int(uptime) if uptime is not None else None

    def get_event_log(self) -> Any:
        return self.rci("show log")

    def _save_raw_response(self, command_payload: str | dict[str, Any], data: Any) -> None:
        if self.raw_response_dir is None:
            return
        self.raw_response_dir.mkdir(parents=True, exist_ok=True)
        command_name = command_payload if isinstance(command_payload, str) else "post-rci"
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in command_name).strip("-")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.raw_response_dir / f"{self.router_id}-{safe_name}-{ts}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _request(self, command_payload: str | dict[str, Any], method: str) -> httpx.Response:
        if isinstance(command_payload, str):
            path = "/".join(part.strip("/") for part in command_payload.split() if part)
            return self._client.request(method, f"{self.base_url}/{path}")
        return self._client.post(self.base_url, json=command_payload)

    def _digest_request(self, command_payload: str | dict[str, Any], method: str) -> httpx.Response:
        if isinstance(command_payload, str):
            path = "/".join(part.strip("/") for part in command_payload.split() if part)
            return self._digest_client.request(method, f"{self.base_url}/{path}")
        return self._digest_client.post(self.base_url, json=command_payload)
