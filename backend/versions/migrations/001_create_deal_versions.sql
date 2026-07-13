-- AgroPILOT M9 — Deal Versions
-- Migration: 001_create_deal_versions
-- Applies to: backend/versions/models.py → DealVersion

CREATE TABLE IF NOT EXISTS deal_versions (
    id          TEXT        PRIMARY KEY,
    deal_id     TEXT        NOT NULL,
    version_num INTEGER     NOT NULL,
    snapshot    JSONB       NOT NULL,
    comment     TEXT,
    author_id   TEXT        NOT NULL,
    author_name TEXT        NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_deal_version
    ON deal_versions (deal_id, version_num);

CREATE INDEX IF NOT EXISTS idx_deal_versions_deal_id
    ON deal_versions (deal_id);

-- Seed: пустой — версии создаются через POST /v1/deals/:id/versions
