-- 019_inbound.sql -- §22: входящие обращения (A4, Этап 3)

CREATE TABLE IF NOT EXISTS inbounds (
    id            serial PRIMARY KEY,
    channel       varchar(16) NOT NULL
                  CHECK (channel IN ('telegram', 'email', 'site', 'social', 'call')),
    contact       varchar(200),
    subject       varchar(500),
    body          text,
    received_at   timestamptz NOT NULL DEFAULT now(),
    status        varchar(16) NOT NULL DEFAULT 'new'
                  CHECK (status IN ('new', 'in_progress', 'converted', 'spam')),
    assigned_to   varchar(16) REFERENCES team(id),
    client_id     int,
    lead_id       int,
    dedup_key     varchar(200),
    a4_class      jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS inbounds_dedup_uidx
    ON inbounds (dedup_key) WHERE dedup_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS inbounds_status_idx ON inbounds (status);
CREATE INDEX IF NOT EXISTS inbounds_received_idx ON inbounds (received_at DESC);

-- FK на clients/leads добавляются в Этапе 3 вместе с роутером
-- (inbounds.client_id/lead_id сейчас информационные ссылки).
