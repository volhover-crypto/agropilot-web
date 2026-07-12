-- migrations/001_create_strategy.sql -- AgroPILOT M4 Strategy schema
CREATE TABLE IF NOT EXISTS strategy (
    id         VARCHAR(64) PRIMARY KEY,
    scenarios  JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by VARCHAR(64)
);

-- Seed the single strategy row
INSERT INTO strategy (id, scenarios)
VALUES ('strategy_main', '[]'::jsonb)
ON CONFLICT (id) DO NOTHING;
