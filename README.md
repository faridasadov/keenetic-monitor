# Keenetic Router Monitoring Collector

Self-hosted monitoring collector for multiple Keenetic routers using KeeneticOS HTTP API / RCI.

## Research notes

Keenetic documents the HTTP API as RCI, served under `/rci`. The API maps CLI commands to URL paths, uses JSON request/response bodies, supports GET and POST, and uses Digest authentication for browser/cURL access. Example:

```bash
curl -u login:password --digest http://rci.example.keenetic.pro/rci/show/system
```

Useful initial requests:

```text
GET /rci/show/system
GET /rci/show/interface
GET /rci/show/ip/dhcp/bindings
GET /rci/show/associations
GET /rci/show/running-config
GET /rci/show/log
POST /rci
{"show":{"ip":{"hotspot":{"hosts":{}}}}}
```

Security stance: use WireGuard/VPN to site routers whenever possible. Do not expose router admin or RCI directly to the public internet. If KeenDNS HTTP Proxy is used, grant access only to a dedicated low-privilege user where supported.

Sources:

- Keenetic support: Using API methods through the HTTP Proxy service
- Keenetic CLI documentation
- Keenetic command reference manuals describing REST Core Interface behavior

## Stack

- Python 3.12
- FastAPI
- TimescaleDB, PostgreSQL-compatible, for inventory and metrics
- Grafana
- Docker Compose

## Structure

```text
app/
  main.py
  config.py
  models.py
  collector/
    keenetic_client.py
    parser.py
    scheduler.py
  api/
    routes.py
  db/
    postgres.py
    migrations/
docker-compose.yml
requirements.txt
.env.example
```

## Start

Create `.env`:

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the generated value into `FERNET_KEY`.

Run:

```bash
docker compose up --build
```

Services:

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3000` with `admin` / `admin`

## Router API

Create a router:

```bash
curl -X POST http://localhost:8000/routers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main office",
    "site": "HQ",
    "host": "192.168.10.1",
    "port": 80,
    "username": "monitor",
    "password": "change-me",
    "access_method": "vpn",
    "enabled": true
  }'
```

Test RCI access:

```bash
curl -X POST http://localhost:8000/routers/{router_id}/test
```

List current state:

```bash
curl http://localhost:8000/routers
curl http://localhost:8000/routers/{router_id}/status
curl http://localhost:8000/routers/{router_id}/clients
```

## Polling

- WAN/status: every 60 seconds
- Clients: every 5 minutes
- Traffic: every 5 minutes
- System info: every 15 minutes
- Router is marked offline after 3 failed polls

Raw RCI responses are saved to `raw-responses/` when collector calls succeed.

## MVP status

Implemented:

- Router inventory CRUD
- Encrypted stored router passwords
- RCI client with Digest auth, timeouts, retries and raw response capture
- Parser normalization for router metrics and clients
- Poll scheduler
- TimescaleDB/PostgreSQL schema
- Grafana datasource and starter dashboard
- Offline status marking after repeated failures

Needs validation with a real router:

- Exact payload shape for DHCP bindings, associations, hotspot hosts and interface counters
- Firmware-specific keys for model/version, WAN IP and byte counters
- Read-only user capability and minimum permissions

## Next implementation steps

- Add Telegram alerts table and notifier worker
- Add audit log writes for router CRUD changes
- Add per-interface and per-client metric hypertables
- Add richer Grafana dashboards for all requested panels
- Add configuration backup collector using `show running-config`
