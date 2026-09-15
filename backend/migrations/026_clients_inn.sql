-- 026_clients_inn.sql -- ТЗ v1.1 п. 8.4: ИНН + реквизиты (ЕГРЮЛ)
ALTER TABLE clients ADD COLUMN IF NOT EXISTS inn         varchar(12);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS requisites  jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS clients_inn_idx ON clients (inn) WHERE inn IS NOT NULL;
