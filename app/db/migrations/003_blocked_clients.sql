CREATE TABLE IF NOT EXISTS blocked_clients (
    router_id UUID NOT NULL,
    mac VARCHAR(32) NOT NULL,
    hostname VARCHAR(255),
    ip VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (router_id, mac)
);

