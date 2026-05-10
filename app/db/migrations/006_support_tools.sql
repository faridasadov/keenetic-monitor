ALTER TABLE routers ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE routers ADD COLUMN IF NOT EXISTS contact_name VARCHAR(120);
ALTER TABLE routers ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(64);
ALTER TABLE routers ADD COLUMN IF NOT EXISTS support_status VARCHAR(32) NOT NULL DEFAULT 'normal';

CREATE TABLE IF NOT EXISTS diagnostic_runs (
    id UUID PRIMARY KEY,
    router_id UUID NOT NULL REFERENCES routers(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'unknown',
    summary TEXT NOT NULL DEFAULT '',
    result JSONB NOT NULL,
    created_by VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_runs_router_time ON diagnostic_runs(router_id, created_at DESC);
