-- 032_agent_run_logs.sql -- §32: журнал запусков агентов (дашборд)
CREATE TABLE IF NOT EXISTS run_logs (
    id                serial PRIMARY KEY,
    agent_code        varchar(16) NOT NULL REFERENCES agent_cards(code) ON DELETE CASCADE,
    started_at        timestamptz NOT NULL DEFAULT now(),
    finished_at       timestamptz,
    status            varchar(8) NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','error')),
    error             text,
    model             varchar(64),
    prompt_tokens     int NOT NULL DEFAULT 0,
    completion_tokens int NOT NULL DEFAULT 0,
    total_tokens      int NOT NULL DEFAULT 0,
    cost_usd          numeric(10,4) NOT NULL DEFAULT 0,
    items             int NOT NULL DEFAULT 0,
    meta              jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS run_logs_agent_idx ON run_logs (agent_code, started_at DESC);
CREATE INDEX IF NOT EXISTS run_logs_started_idx ON run_logs (started_at DESC);
