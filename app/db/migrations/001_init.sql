CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS routers (
    id UUID PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    site VARCHAR(120),
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL DEFAULT 80,
    username VARCHAR(120) NOT NULL,
    password_encrypted TEXT,
    access_method VARCHAR(32) NOT NULL DEFAULT 'vpn',
    model VARCHAR(120),
    firmware_version VARCHAR(120),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    failure_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS current_clients (
    id UUID PRIMARY KEY,
    router_id UUID NOT NULL REFERENCES routers(id) ON DELETE CASCADE,
    hostname VARCHAR(255),
    mac VARCHAR(32),
    ip VARCHAR(64),
    interface VARCHAR(120),
    connection_type VARCHAR(32) NOT NULL DEFAULT 'unknown',
    rx_bytes BIGINT,
    tx_bytes BIGINT,
    signal DOUBLE PRECISION,
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_current_clients_router_id ON current_clients(router_id);
CREATE INDEX IF NOT EXISTS idx_current_clients_mac ON current_clients(mac);
CREATE INDEX IF NOT EXISTS idx_current_clients_ip ON current_clients(ip);

CREATE TABLE IF NOT EXISTS router_status (
    router_id UUID PRIMARY KEY REFERENCES routers(id) ON DELETE CASCADE,
    online BOOLEAN NOT NULL DEFAULT FALSE,
    wan_status VARCHAR(64),
    wan_ip VARCHAR(64),
    cpu_usage DOUBLE PRECISION,
    ram_usage DOUBLE PRECISION,
    uptime BIGINT,
    rx_bytes_total BIGINT,
    tx_bytes_total BIGINT,
    last_seen TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS router_metrics (
    time TIMESTAMPTZ NOT NULL,
    router_id UUID NOT NULL REFERENCES routers(id) ON DELETE CASCADE,
    cpu_usage DOUBLE PRECISION,
    ram_usage DOUBLE PRECISION,
    uptime BIGINT,
    wan_status VARCHAR(64),
    wan_ip VARCHAR(64),
    rx_bytes_total BIGINT,
    tx_bytes_total BIGINT,
    online BOOLEAN NOT NULL DEFAULT FALSE,
    raw JSONB,
    PRIMARY KEY (time, router_id)
);

SELECT create_hypertable('router_metrics', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS client_metrics (
    time TIMESTAMPTZ NOT NULL,
    router_id UUID NOT NULL REFERENCES routers(id) ON DELETE CASCADE,
    client_key VARCHAR(255) NOT NULL,
    hostname VARCHAR(255),
    mac VARCHAR(32),
    ip VARCHAR(64),
    rx_bytes BIGINT,
    tx_bytes BIGINT,
    signal DOUBLE PRECISION,
    PRIMARY KEY (time, router_id, client_key)
);

CREATE INDEX IF NOT EXISTS idx_client_metrics_router_time ON client_metrics(router_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_client_metrics_mac ON client_metrics(mac);
CREATE INDEX IF NOT EXISTS idx_client_metrics_ip ON client_metrics(ip);

SELECT create_hypertable('client_metrics', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    entity_id UUID,
    action VARCHAR(64) NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
