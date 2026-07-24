-- 012_sources_revision.sql -- Block D (Stage-2): ревизия sources (вариант 1a, CONTRACTS.md §13.1)
-- Таблица на проде пуста (0 строк) -> замена CHECK type без миграции данных.
-- Идемпотентно: ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT IF EXISTS перед ADD. Без DROP TABLE/COLUMN.

-- type: замена набора site/rss/telegram/tender -> news/supplier/competitor/market/tech
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_type_check;
ALTER TABLE sources ADD CONSTRAINT sources_type_check
  CHECK (type IN ('news','supplier','competitor','market','tech'));

-- НОВЫЕ колонки lifecycle / маршрутизация D-5
ALTER TABLE sources ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'active';
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_status_check;
ALTER TABLE sources ADD CONSTRAINT sources_status_check
  CHECK (status IN ('active','proposed','disabled','rejected'));

ALTER TABLE sources ADD COLUMN IF NOT EXISTS linked_strategy_task VARCHAR(64) NULL;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS added_by VARCHAR(16) NULL;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS receiver_user_id VARCHAR(16) NULL;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS routing_reason VARCHAR(16) NULL;
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_routing_reason_check;
ALTER TABLE sources ADD CONSTRAINT sources_routing_reason_check
  CHECK (routing_reason IS NULL OR routing_reason IN ('added_by','competency'));

-- FK только на уровне БД (локальный Base без ORM-FK, протокол 4 дефектов)
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_linked_strategy_task_fkey;
ALTER TABLE sources ADD CONSTRAINT sources_linked_strategy_task_fkey
  FOREIGN KEY (linked_strategy_task) REFERENCES strategy_tasks(id) ON DELETE SET NULL;
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_added_by_fkey;
ALTER TABLE sources ADD CONSTRAINT sources_added_by_fkey
  FOREIGN KEY (added_by) REFERENCES team(id) ON DELETE SET NULL;
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_receiver_user_id_fkey;
ALTER TABLE sources ADD CONSTRAINT sources_receiver_user_id_fkey
  FOREIGN KEY (receiver_user_id) REFERENCES team(id) ON DELETE SET NULL;
