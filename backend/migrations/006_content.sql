-- 006_content.sql — M10-3: архив контента/постов SMM
CREATE TABLE IF NOT EXISTS content (
    id           SERIAL PRIMARY KEY,
    title        VARCHAR(300) NOT NULL,
    body         TEXT         NOT NULL,
    platform     VARCHAR(32)  NOT NULL CHECK (platform IN ('telegram','instagram','vk','linkedin','other')),
    status       VARCHAR(16)  NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft','published','archived')),
    author_id    VARCHAR(16)  REFERENCES team(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
