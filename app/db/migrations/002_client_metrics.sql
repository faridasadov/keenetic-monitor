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
