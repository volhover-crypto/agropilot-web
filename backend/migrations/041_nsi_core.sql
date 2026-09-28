-- 041_nsi_core.sql -- §45: раздел «Справочники» (НСИ), фаза 1a:
-- журнал аудита + базовые справочники (единицы, валюты, регионы, теги)
-- + предопределённые сиды (единицы/валюты/регионы РФ) + pg_trgm для дедупа.
-- Идемпотентно (IF NOT EXISTS / ON CONFLICT DO NOTHING).

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Журнал изменений НСИ: append-only, общий для всех справочников (§45.4).
CREATE TABLE IF NOT EXISTS catalog_audit (
    id         BIGSERIAL PRIMARY KEY,
    entity     TEXT NOT NULL,             -- 'units' | 'currencies' | 'regions' | 'tags' | ...
    entity_id  BIGINT NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('create','update','archive','restore','delete','merge')),
    diff       JSONB NOT NULL DEFAULT '{}',  -- {поле: {old, new}}
    user_id    TEXT,                       -- team.id (String(16))
    user_name  TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS catalog_audit_entity_idx ON catalog_audit (entity, entity_id, id DESC);

-- Единицы измерения
CREATE TABLE IF NOT EXISTS nsi_units (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL UNIQUE,
    symbol      TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL DEFAULT 'шт',
    intl_code   TEXT NOT NULL DEFAULT '',
    is_system   BOOLEAN NOT NULL DEFAULT false,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order  INT NOT NULL DEFAULT 0,
    attrs       JSONB NOT NULL DEFAULT '{}',
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Валюты
CREATE TABLE IF NOT EXISTS nsi_currencies (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,      -- ISO 4217
    name        TEXT NOT NULL UNIQUE,
    symbol      TEXT NOT NULL DEFAULT '',
    minor_unit  INT NOT NULL DEFAULT 2,    -- кратность минорных (копейки = 2)
    is_system   BOOLEAN NOT NULL DEFAULT false,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order  INT NOT NULL DEFAULT 0,
    attrs       JSONB NOT NULL DEFAULT '{}',
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Регионы/гео: страна -> субъект/регион -> город (иерархия, self-FK RESTRICT)
CREATE TABLE IF NOT EXISTS nsi_regions (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    level       TEXT NOT NULL DEFAULT 'region' CHECK (level IN ('country','region','city')),
    parent_id   BIGINT REFERENCES nsi_regions(id) ON DELETE RESTRICT,
    is_system   BOOLEAN NOT NULL DEFAULT false,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order  INT NOT NULL DEFAULT 0,
    attrs       JSONB NOT NULL DEFAULT '{}',
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS nsi_regions_parent_idx ON nsi_regions (parent_id);

-- Теги
CREATE TABLE IF NOT EXISTS nsi_tags (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL UNIQUE,
    color       TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_system   BOOLEAN NOT NULL DEFAULT false,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    sort_order  INT NOT NULL DEFAULT 0,
    attrs       JSONB NOT NULL DEFAULT '{}',
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Тригграммные индексы для fuzzy-дедупа (§45.5)
CREATE INDEX IF NOT EXISTS nsi_units_name_trgm      ON nsi_units      USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS nsi_currencies_name_trgm ON nsi_currencies USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS nsi_regions_name_trgm    ON nsi_regions    USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS nsi_tags_name_trgm       ON nsi_tags       USING gin (name gin_trgm_ops);

-- Сиды: единицы измерения (ОКЕИ)
INSERT INTO nsi_units (code, name, symbol, kind, intl_code, is_system, sort_order) VALUES
    ('ED-0001', 'Штука',              'шт',      'шт',    '796', true, 1),
    ('ED-0002', 'Килограмм',          'кг',      'вес',   '166', true, 2),
    ('ED-0003', 'Тонна',              'т',       'вес',   '168', true, 3),
    ('ED-0004', 'Грамм',              'г',       'вес',   '163', true, 4),
    ('ED-0005', 'Литр',               'л',       'объём', '112', true, 5),
    ('ED-0006', 'Метр',               'м',       'длина', '006', true, 6),
    ('ED-0007', 'Квадратный метр',    'м²',      'площадь', '055', true, 7),
    ('ED-0008', 'Час',                'ч',       'время', '356', true, 8),
    ('ED-0009', 'Условная единица',   'усл.ед',  'усл',   '876', true, 9)
ON CONFLICT (code) DO NOTHING;

-- Сиды: валюты
INSERT INTO nsi_currencies (code, name, symbol, minor_unit, is_system, sort_order) VALUES
    ('RUB', 'Российский рубль', '₽', 2, true, 1),
    ('USD', 'Доллар США',       '$', 2, true, 2),
    ('EUR', 'Евро',             '€', 2, true, 3),
    ('KZT', 'Тенге',            '₸', 2, true, 4)
ON CONFLICT (code) DO NOTHING;

-- Сиды: гео — Российская Федерация + 85 субъектов (города добавляются вручную;
-- decision 2026-09-28: сиды = РФ). Коды субъектов: RU-01…RU-85 по алфавиту.
INSERT INTO nsi_regions (code, name, level, is_system, sort_order)
VALUES ('RU', 'Российская Федерация', 'country', true, 0)
ON CONFLICT (code) DO NOTHING;

INSERT INTO nsi_regions (code, name, level, parent_id, is_system, sort_order)
SELECT v.code, v.name, 'region', p.id, true, v.sort_order
FROM (VALUES
    ('RU-01', 'Республика Адыгея (Адыгея)', 1),
    ('RU-02', 'Республика Алтай', 2),
    ('RU-03', 'Республика Башкортостан', 3),
    ('RU-04', 'Республика Бурятия', 4),
    ('RU-05', 'Республика Дагестан', 5),
    ('RU-06', 'Республика Ингушетия', 6),
    ('RU-07', 'Кабардино-Балкарская Республика', 7),
    ('RU-08', 'Республика Калмыкия', 8),
    ('RU-09', 'Карачаево-Черкесская Республика', 9),
    ('RU-10', 'Республика Карелия', 10),
    ('RU-11', 'Республика Коми', 11),
    ('RU-12', 'Республика Крым', 12),
    ('RU-13', 'Республика Марий Эл', 13),
    ('RU-14', 'Республика Мордовия', 14),
    ('RU-15', 'Республика Саха (Якутия)', 15),
    ('RU-16', 'Республика Северная Осетия — Алания', 16),
    ('RU-17', 'Республика Татарстан (Татарстан)', 17),
    ('RU-18', 'Республика Тыва', 18),
    ('RU-19', 'Удмуртская Республика', 19),
    ('RU-20', 'Республика Хакасия', 20),
    ('RU-21', 'Чеченская Республика', 21),
    ('RU-22', 'Чувашская Республика — Чувашия', 22),
    ('RU-23', 'Алтайский край', 23),
    ('RU-24', 'Забайкальский край', 24),
    ('RU-25', 'Камчатский край', 25),
    ('RU-26', 'Краснодарский край', 26),
    ('RU-27', 'Красноярский край', 27),
    ('RU-28', 'Пермский край', 28),
    ('RU-29', 'Приморский край', 29),
    ('RU-30', 'Ставропольский край', 30),
    ('RU-31', 'Хабаровский край', 31),
    ('RU-32', 'Амурская область', 32),
    ('RU-33', 'Архангельская область', 33),
    ('RU-34', 'Астраханская область', 34),
    ('RU-35', 'Белгородская область', 35),
    ('RU-36', 'Брянская область', 36),
    ('RU-37', 'Владимирская область', 37),
    ('RU-38', 'Волгоградская область', 38),
    ('RU-39', 'Вологодская область', 39),
    ('RU-40', 'Воронежская область', 40),
    ('RU-41', 'Ивановская область', 41),
    ('RU-42', 'Иркутская область', 42),
    ('RU-43', 'Калининградская область', 43),
    ('RU-44', 'Калужская область', 44),
    ('RU-45', 'Кемеровская область — Кузбасс', 45),
    ('RU-46', 'Кировская область', 46),
    ('RU-47', 'Костромская область', 47),
    ('RU-48', 'Курганская область', 48),
    ('RU-49', 'Курская область', 49),
    ('RU-50', 'Ленинградская область', 50),
    ('RU-51', 'Липецкая область', 51),
    ('RU-52', 'Магаданская область', 52),
    ('RU-53', 'Московская область', 53),
    ('RU-54', 'Мурманская область', 54),
    ('RU-55', 'Нижегородская область', 55),
    ('RU-56', 'Новгородская область', 56),
    ('RU-57', 'Новосибирская область', 57),
    ('RU-58', 'Омская область', 58),
    ('RU-59', 'Оренбургская область', 59),
    ('RU-60', 'Орловская область', 60),
    ('RU-61', 'Пензенская область', 61),
    ('RU-62', 'Псковская область', 62),
    ('RU-63', 'Ростовская область', 63),
    ('RU-64', 'Рязанская область', 64),
    ('RU-65', 'Самарская область', 65),
    ('RU-66', 'Саратовская область', 66),
    ('RU-67', 'Сахалинская область', 67),
    ('RU-68', 'Свердловская область', 68),
    ('RU-69', 'Смоленская область', 69),
    ('RU-70', 'Тамбовская область', 70),
    ('RU-71', 'Тверская область', 71),
    ('RU-72', 'Томская область', 72),
    ('RU-73', 'Тульская область', 73),
    ('RU-74', 'Тюменская область', 74),
    ('RU-75', 'Ульяновская область', 75),
    ('RU-76', 'Челябинская область', 76),
    ('RU-77', 'Ярославская область', 77),
    ('RU-78', 'Москва', 78),
    ('RU-79', 'Санкт-Петербург', 79),
    ('RU-80', 'Севастополь', 80),
    ('RU-81', 'Еврейская автономная область', 81),
    ('RU-82', 'Ненецкий автономный округ', 82),
    ('RU-83', 'Ханты-Мансийский автономный округ — Югра', 83),
    ('RU-84', 'Чукотский автономный округ', 84),
    ('RU-85', 'Ямало-Ненецкий автономный округ', 85)
) AS v(code, name, sort_order)
JOIN nsi_regions p ON p.code = 'RU'
ON CONFLICT (code) DO NOTHING;
