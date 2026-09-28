-- 043_nomenclature.sql -- §45, фаза 1b: номенклатура (товары/услуги),
-- 1С-стиль «группы + элементы» в одной таблице (is_group). Единицы и валюты --
-- ссылки на nsi_units / nsi_currencies (RESTRICT/SET NULL). Идемпотентно.

CREATE TABLE IF NOT EXISTS nsi_nomenclature (
    id           BIGSERIAL PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    parent_id    BIGINT REFERENCES nsi_nomenclature(id) ON DELETE RESTRICT,
    is_group     BOOLEAN NOT NULL DEFAULT false,
    article      TEXT NOT NULL DEFAULT '',
    kind         TEXT NOT NULL DEFAULT 'goods' CHECK (kind IN ('goods','service')),
    unit_id      BIGINT REFERENCES nsi_units(id) ON DELETE RESTRICT,
    vat_rate     NUMERIC(5,2),                        -- проценты, NULL = без НДС
    price_base   NUMERIC(14,2),                       -- базовая цена (прайс-листы — фаза 2)
    currency_id  BIGINT REFERENCES nsi_currencies(id) ON DELETE SET NULL,
    is_system    BOOLEAN NOT NULL DEFAULT false,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order   INT NOT NULL DEFAULT 0,
    attrs        JSONB NOT NULL DEFAULT '{}',
    created_by   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   TEXT,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS nsi_nomenclature_parent_idx ON nsi_nomenclature (parent_id);
CREATE INDEX IF NOT EXISTS nsi_nomenclature_name_trgm ON nsi_nomenclature USING gin (name gin_trgm_ops);
