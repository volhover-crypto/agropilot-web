-- 042_contractors.sql -- §45, фаза 1b: справочник контрагентов.
-- Расширенные реквизиты юрлиц/ИП/физлиц (сейчас частично размазаны по
-- clients.requisites JSONB — перенос данных фазой 2 через импорт-мастер).
-- Идемпотентно.

CREATE TABLE IF NOT EXISTS nsi_contractors (
    id            BIGSERIAL PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,                      -- краткое наименование
    name_full     TEXT NOT NULL DEFAULT '',           -- полное по ЕГРЮЛ/ЕГРИП
    kind          TEXT NOT NULL DEFAULT 'jur' CHECK (kind IN ('jur','ip','person')),
    bin_iin       TEXT NOT NULL DEFAULT '',
    bank_name     TEXT NOT NULL DEFAULT '',
    bic_iban      TEXT NOT NULL DEFAULT '',
    account       TEXT NOT NULL DEFAULT '',
    legal_address TEXT NOT NULL DEFAULT '',
    region_id     BIGINT REFERENCES nsi_regions(id) ON DELETE SET NULL,
    phone         TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    website       TEXT NOT NULL DEFAULT '',
    comment       TEXT NOT NULL DEFAULT '',
    is_system     BOOLEAN NOT NULL DEFAULT false,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order    INT NOT NULL DEFAULT 0,
    attrs         JSONB NOT NULL DEFAULT '{}',
    created_by    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by    TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS nsi_contractors_region_idx ON nsi_contractors (region_id);
-- name НЕ unique (дубли ловит дедуп+merge), bin_iin тоже (данные бывают грязные)
CREATE INDEX IF NOT EXISTS nsi_contractors_name_trgm ON nsi_contractors USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS nsi_contractors_bin_trgm  ON nsi_contractors USING gin (bin_iin gin_trgm_ops);
