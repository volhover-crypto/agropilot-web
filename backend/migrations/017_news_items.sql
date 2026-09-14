-- 017_news_items.sql -- §20: медиа-мониторинг A1 — news_items + расширение sources
-- Идемпотентно. Существующие данные sources не трогаем (type 'news' валиден).

-- sources: расширение типов и периодичность сканирования
ALTER TABLE sources ALTER COLUMN type TYPE varchar(32);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS check_period_min int
    NOT NULL DEFAULT 1440 CHECK (check_period_min BETWEEN 30 AND 43200);
DO $$ BEGIN
  ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_type_ck;
  ALTER TABLE sources ADD CONSTRAINT sources_type_ck
    CHECK (type IN ('news', 'telegram', 'site', 'rss'));
END $$;

CREATE TABLE IF NOT EXISTS news_items (
    id              serial PRIMARY KEY,
    source_id       int NOT NULL REFERENCES sources(id),
    title           text NOT NULL,
    summary         text,
    url             varchar(1000),
    published_at    timestamptz,
    fetched_at      timestamptz NOT NULL DEFAULT now(),
    status          varchar(16) NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'selected', 'rejected', 'used')),
    relevance       numeric(4,2) CHECK (relevance IS NULL OR (relevance >= 0 AND relevance <= 1)),
    relevance_reason text,
    agent_run_id    varchar(64)
);

CREATE UNIQUE INDEX IF NOT EXISTS news_items_source_url_uidx
    ON news_items (source_id, url) WHERE url IS NOT NULL;
CREATE INDEX IF NOT EXISTS news_items_status_idx ON news_items (status);
CREATE INDEX IF NOT EXISTS news_items_fetched_idx ON news_items (fetched_at DESC);
