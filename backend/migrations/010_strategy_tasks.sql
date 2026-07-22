-- 010_strategy_tasks.sql -- Block C (Stage-2): strategic tasks / monitoring focuses
-- CONTRACTS.md 12.1. Standalone entity, does not replace operational `tasks`.
CREATE TABLE IF NOT EXISTS strategy_tasks (
    id               VARCHAR(64)  PRIMARY KEY,
    title            TEXT         NOT NULL,
    description      TEXT,
    priority         VARCHAR(16)  NOT NULL DEFAULT 'medium'
                     CHECK (priority IN ('low','medium','high')),
    status           VARCHAR(16)  NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','inactive')),
    monitoring_focus JSONB        NOT NULL DEFAULT '[]',
    owner_id         VARCHAR(16)  NOT NULL REFERENCES team(id),
    added_by         VARCHAR(16)  NOT NULL REFERENCES team(id),
    linked_scenario  VARCHAR(64),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
