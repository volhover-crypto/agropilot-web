-- 005_sources.sql — M10-2: реестр источников мониторинга
CREATE TABLE IF NOT EXISTS sources (
    id         SERIAL PRIMARY KEY,
    type       VARCHAR(16)  NOT NULL CHECK (type IN ('site','rss','telegram','tender')),
    url        VARCHAR(500) NOT NULL,
    handle     VARCHAR(200),
    keywords   JSONB        NOT NULL DEFAULT '[]',
    active     BOOLEAN      NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);
