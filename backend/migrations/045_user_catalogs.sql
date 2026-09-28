-- 045_user_catalogs.sql -- §45, фаза 1d: пользовательские справочники
-- (создаются администратором из UI, без правки кода) + иерархия контрагентов.
--
-- Решение владельца 28.09.2026: реестр типов в БД (catalog_types) + одна
-- generic-таблица записей (nsi_user_items, значения полей в attrs JSONB) —
-- без CREATE TABLE на лету. Служебные справочники (единицы/контрагенты/…)
-- остаются физическими таблицами. Идемпотентно.

-- Реестр пользовательских справочников
CREATE TABLE IF NOT EXISTS catalog_types (
    id            BIGSERIAL PRIMARY KEY,
    key           TEXT NOT NULL UNIQUE,         -- лат. slug, напр. 'vineyards'
    title         TEXT NOT NULL,
    group_name    TEXT NOT NULL DEFAULT 'Мои справочники',
    icon          TEXT NOT NULL DEFAULT '📁',
    hierarchical  BOOLEAN NOT NULL DEFAULT true, -- подразделы внутри справочника
    code_prefix   TEXT NOT NULL DEFAULT 'NSI',
    fields_schema JSONB NOT NULL DEFAULT '[]',  -- [{key,type,label,required,unique,grid,width,options}]
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order    INT NOT NULL DEFAULT 0,
    created_by    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by    TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Записи всех пользовательских справочников (значения полей — в attrs)
CREATE TABLE IF NOT EXISTS nsi_user_items (
    id          BIGSERIAL PRIMARY KEY,
    catalog_id  BIGINT NOT NULL REFERENCES catalog_types(id) ON DELETE RESTRICT,
    code        TEXT NOT NULL,                  -- уникален в пределах справочника
    name        TEXT NOT NULL,
    parent_id   BIGINT REFERENCES nsi_user_items(id) ON DELETE RESTRICT,
    is_group    BOOLEAN NOT NULL DEFAULT false,
    is_system   BOOLEAN NOT NULL DEFAULT false,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order  INT NOT NULL DEFAULT 0,
    attrs       JSONB NOT NULL DEFAULT '{}',
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS nsi_user_items_code_idx ON nsi_user_items (catalog_id, code);
CREATE INDEX IF NOT EXISTS nsi_user_items_parent_idx ON nsi_user_items (parent_id);
CREATE INDEX IF NOT EXISTS nsi_user_items_name_trgm ON nsi_user_items USING gin (name gin_trgm_ops);

-- Контрагенты: подразделы (виноградники/сады/…) — 1С-стиль группы+элементы,
-- как у номенклатуры (043). Бизнес-поля остаются в своей таблице.
ALTER TABLE nsi_contractors ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES nsi_contractors(id) ON DELETE RESTRICT;
ALTER TABLE nsi_contractors ADD COLUMN IF NOT EXISTS is_group BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS nsi_contractors_parent_idx ON nsi_contractors (parent_id);
