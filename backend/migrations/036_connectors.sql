-- 036_connectors.sql -- §39 (О2 ТЗ_ИНТЕГРАЦИЯ_OCTOP): коннекторный слой источников
-- Идемпотентно. Данные не трогаем.
-- 1) Синхронизация CHECK типов sources: объединение множеств кода (миграция 012:
--    news/supplier/competitor/market/tech) и БД (миграция 017: news/telegram/site/rss)
--    -- закрывает дефект, когда API-валидный тип отвергался CHECK на INSERT.
--    «Смысловые» роли (supplier/competitor/...) остаются валидными типами;
--    механика сбора определяется колонкой connector (реестр §39.1) или типом.
-- 2) connector -- ключ реестра коннекторов backend/connectors/registry.py
--    (rss | telegram-web | site | arxiv | cyberleninka | ...), NULL -> выбор
--    коннектора по типу/url (эвристика уровня news/collectors.py).

ALTER TABLE sources ADD COLUMN IF NOT EXISTS connector varchar(48);

DROP INDEX IF EXISTS sources_connector_idx;
CREATE INDEX sources_connector_idx ON sources (connector) WHERE connector IS NOT NULL;

DROP INDEX IF EXISTS sources_type_status_active_idx;
CREATE INDEX sources_type_status_active_idx ON sources (status, active);

DO $$ BEGIN
  ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_type_ck;
  ALTER TABLE sources ADD CONSTRAINT sources_type_ck CHECK (type IN (
    'news', 'telegram', 'site', 'rss',
    'supplier', 'competitor', 'market', 'tech'
  ));
END $$;
