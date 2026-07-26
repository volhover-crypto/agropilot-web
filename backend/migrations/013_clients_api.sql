-- 013_clients_api.sql -- A-6 clients API over existing table (idempotent, ADD-only)
-- ПРИМЕНЕНИЕ = ШАГ 3. CREATE TABLE / DROP / изменение типов и FK ЗАПРЕЩЕНЫ.

ALTER TABLE clients ADD COLUMN IF NOT EXISTS source     varchar(32);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS status     varchar(16) DEFAULT 'active';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

UPDATE clients SET status='active'  WHERE status IS NULL;
UPDATE clients SET source='manual'  WHERE source IS NULL;
UPDATE clients SET health='green'   WHERE health IS NULL;
-- deals_count НЕ трогаем: колонка остаётся (её пишет seed), но API её НЕ читает.
