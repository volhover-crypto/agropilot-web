-- 008_artifacts.sql — M10-5: артефакты (КП/договоры/схемы)
CREATE TABLE IF NOT EXISTS artifacts (
    id          SERIAL PRIMARY KEY,
    kind        VARCHAR(32)  NOT NULL CHECK (kind IN ('kp','contract','schema','other')),
    title       VARCHAR(300) NOT NULL,
    url         TEXT,
    deal_id     VARCHAR(16)  REFERENCES deals(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
