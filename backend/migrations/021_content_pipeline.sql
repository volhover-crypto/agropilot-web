-- 021_content_pipeline.sql -- §21: конвейер контента A2/A3
-- Статус-цепочка draft → in_review → approved → scheduled → published (+rejected/archived),
-- привязка к NewsItem, версии текста.

ALTER TABLE content DROP CONSTRAINT IF EXISTS content_status_check;
ALTER TABLE content ADD CONSTRAINT content_status_check
  CHECK (status IN ('draft','in_review','approved','scheduled','published','rejected','archived'));

ALTER TABLE content ADD COLUMN IF NOT EXISTS news_item_id int REFERENCES news_items(id) ON DELETE SET NULL;
ALTER TABLE content ADD COLUMN IF NOT EXISTS editor_id   varchar(16) REFERENCES team(id) ON DELETE SET NULL;
ALTER TABLE content ADD COLUMN IF NOT EXISTS scheduled_at timestamptz;
ALTER TABLE content ADD COLUMN IF NOT EXISTS tags        jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE content ADD COLUMN IF NOT EXISTS channel_ids jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE content ADD COLUMN IF NOT EXISTS updated_at  timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS content_status_idx ON content (status);

CREATE TABLE IF NOT EXISTS content_versions (
    id         serial PRIMARY KEY,
    content_id int NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    title      varchar(300) NOT NULL,
    body       text NOT NULL,
    author_id  varchar(16) REFERENCES team(id) ON DELETE SET NULL,
    comment    text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS content_versions_content_idx ON content_versions (content_id, created_at DESC);
