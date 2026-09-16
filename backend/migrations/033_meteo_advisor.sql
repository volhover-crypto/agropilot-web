-- 033_meteo_advisor.sql -- §34: MIA-погодный агро-консультант (замена §17 field_alerts)
-- Прогноз Open-Meteo по гео-пункту + правила культуры/фенофазы -> резюме
-- «плюсы/минусы/рекомендации» (LLM) -> Telegram. Горизонты 24/72/120 ч.

-- Справочник культур (оператор добавляет сам)
CREATE TABLE IF NOT EXISTS crops (
    id          serial PRIMARY KEY,
    code        text NOT NULL UNIQUE,           -- vine, grain, greenhouse...
    name        text NOT NULL,                  -- «Виноград»
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Справочник гео-пунктов (регионов наблюдения)
CREATE TABLE IF NOT EXISTS geo_points (
    id          serial PRIMARY KEY,
    name        text NOT NULL,                  -- «ЮБК — Ялта»
    lat         numeric(8,5) NOT NULL,
    lon         numeric(8,5) NOT NULL,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Календарь фенофаз: одна запись на месяц культуры (MVP; правится оператором)
CREATE TABLE IF NOT EXISTS crop_phases (
    id          serial PRIMARY KEY,
    crop_code   text NOT NULL,
    month       int NOT NULL CHECK (month BETWEEN 1 AND 12),
    phase       text NOT NULL,                  -- «Цветение»
    note        text,
    UNIQUE (crop_code, month)
);

-- Детерминированные правила: risk (минус/угроза) и window (благоприятное окно)
CREATE TABLE IF NOT EXISTS crop_rules (
    id            serial PRIMARY KEY,
    crop_code     text NOT NULL,
    phase         text,                          -- NULL = любая фаза
    kind          text NOT NULL DEFAULT 'risk' CHECK (kind IN ('risk', 'window')),
    metric        text NOT NULL,                 -- temp_min/temp_max/precip_sum/humidity_avg/wind_max
    op            text NOT NULL CHECK (op IN ('<', '>', '<=', '>=', '=')),
    threshold     numeric NOT NULL,
    severity      text NOT NULL DEFAULT 'info' CHECK (severity IN ('info', 'warn', 'critical')),
    recommendation text NOT NULL,
    active        boolean NOT NULL DEFAULT true
);

-- Подписки: для какой точки какую культуру и с какими горизонтами считать
CREATE TABLE IF NOT EXISTS meteo_subscriptions (
    id          serial PRIMARY KEY,
    point_id    int NOT NULL REFERENCES geo_points(id) ON DELETE CASCADE,
    crop_code   text NOT NULL,
    horizons    int[] NOT NULL DEFAULT '{24}',  -- {24} / {24,72} / {24,72,120}
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (point_id, crop_code)
);

-- Прогоны: агрегаты погоды, рассчитанные риски/окна, LLM-резюме
CREATE TABLE IF NOT EXISTS weather_runs (
    id            serial PRIMARY KEY,
    point_id      int NOT NULL REFERENCES geo_points(id) ON DELETE CASCADE,
    crop_code     text NOT NULL,
    horizon_h     int NOT NULL,                  -- 24/72/120
    ran_at        timestamptz NOT NULL DEFAULT now(),
    metrics       jsonb NOT NULL DEFAULT '{}',   -- {temp_min, temp_max, precip_sum, humidity_avg, wind_max, phase}
    risks         jsonb NOT NULL DEFAULT '[]',   -- [{metric, value, threshold, op, severity, text}]
    windows       jsonb NOT NULL DEFAULT '[]',
    summary       text,                          -- LLM: плюсы/минусы/рекомендации
    telegram_sent boolean NOT NULL DEFAULT false,
    critical      boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_weather_runs_point ON weather_runs (point_id, crop_code, ran_at DESC);

-- Карточка агента MIA-метео (реестр §29; дашборд §33 подхватит автоматически)
INSERT INTO agent_cards (code, name, role, model, limits, active, updated_at)
VALUES ('a-mia', 'MIA Погодный агро-консультант',
        'Прогноз Open-Meteo по региону -> правила культуры/фазы -> резюме и рекомендации',
        'openai/gpt-4o-mini', '{}', true, now())
ON CONFLICT (code) DO NOTHING;

INSERT INTO prompts (agent_code, version, text, note, author_id, created_at)
VALUES ('a-mia', 1,
'Ты — агроконсультант MIA системы AgroPILOT. На входе: регион, культура, фенофаза, горизонт прогноза (ч), агрегаты погоды за горизонт и рассчитанные правилами риски (минусы) и окна (плюсы). Задача: краткое резюме для агронома в 3 блока: «Плюсы» (благоприятные условия/окна), «Минусы и риски» (угрозы культуры), «Рекомендации на горизонт» (зелёные операции, обработки СЗР, полив, укрытия — только следующие из рисков и окон). Только факты из данных, значения не выдумывать. Телеграфно: 2-4 пункта на блок.',
        'сид v1', 'U6', now())
ON CONFLICT DO NOTHING;

-- Сиды: культуры
INSERT INTO crops (code, name) VALUES
    ('vine', 'Виноград'),
    ('grain', 'Зерновые (колосовые)'),
    ('greenhouse', 'Тепличные культуры')
ON CONFLICT (code) DO NOTHING;

-- Сиды: фенофазы винограда (Крым, усреднённо; правится оператором)
INSERT INTO crop_phases (crop_code, month, phase) VALUES
    ('vine', 1, 'Вынужденный покой'),
    ('vine', 2, 'Покой / сокодвижение к концу месяца'),
    ('vine', 3, 'Открытие почек, начало роста побегов'),
    ('vine', 4, 'Рост побегов'),
    ('vine', 5, 'Цветение'),
    ('vine', 6, 'Рост ягод (завязь)'),
    ('vine', 7, 'Налив и созревание ягод'),
    ('vine', 8, 'Созревание, начало уборки'),
    ('vine', 9, 'Уборка'),
    ('vine', 10, 'Уборка, листопад'),
    ('vine', 11, 'Листопад, закалка лозы'),
    ('vine', 12, 'Закалка, покой')
ON CONFLICT (crop_code, month) DO NOTHING;

-- Сиды: правила винограда (образец; оператор дополняет в UI)
INSERT INTO crop_rules (crop_code, phase, kind, metric, op, threshold, severity, recommendation) VALUES
    ('vine', NULL, 'risk', 'temp_min', '<', -1, 'critical',
     'Риск заморозка: подготовить укрытие/дымление, отложить зелёные операции и обработки.'),
    ('vine', NULL, 'risk', 'temp_max', '>', 35, 'warn',
     'Тепловой стресс: риск ожогов ягод и солнечного удара куста — проверить полив.'),
    ('vine', NULL, 'risk', 'precip_sum', '>', 5, 'warn',
     'Осадки: повышен риск милдью/оидиума — контроль листьев, обработку в ближайшее сухое окно.'),
    ('vine', NULL, 'risk', 'humidity_avg', '>', 75, 'warn',
     'Высокая влажность воздуха: благоприятные условия развития инфекций (милдью, оидиум).'),
    ('vine', NULL, 'window', 'wind_max', '<', 4, 'info',
     'Ветер слабый — условия для качественного опрыскивания.'),
    ('vine', NULL, 'window', 'precip_sum', '=', 0, 'info',
     'Без осадков — окно для обработок СЗР и зелёных операций.'),
    ('greenhouse', NULL, 'risk', 'temp_min', '<', -5, 'critical',
     'Сильный мороз снаружи: проверить обогрев/утепление теплицы, риск промораживания.'),
    ('greenhouse', NULL, 'risk', 'temp_max', '>', 32, 'warn',
     'Жара снаружи: усилить проветривание и затенение, контроль перегрева контура.')
;

-- Сид: гео-пункт ЮБК (Ялта) + подписка виноград со всеми горизонтами
INSERT INTO geo_points (name, lat, lon) VALUES ('ЮБК — Ялта', 44.49523, 34.16628);
INSERT INTO meteo_subscriptions (point_id, crop_code, horizons)
SELECT id, 'vine', '{24,72,120}' FROM geo_points WHERE name = 'ЮБК — Ялта';
