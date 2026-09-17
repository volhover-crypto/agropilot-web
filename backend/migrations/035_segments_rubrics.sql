-- 035_segments_rubrics.sql -- §37: сегменты аудитории и рубрикатор для A2
--
-- Сегмент = профиль аудитории (язык/CTA/география) — промт-аддон к A2.
-- Привязка: источник (news наследует) -> пост; канал тоже может иметь сегмент.
-- Рубрикатор — тематические углы постов (концепт apilot92, 9 рубрик).
-- Оба справочника управляются контент-мейкером (content:edit/approve).

CREATE TABLE IF NOT EXISTS audience_segments (
    id          serial PRIMARY KEY,
    code        text NOT NULL UNIQUE,          -- vine / grain / greenhouse
    name        text NOT NULL,
    description text,                          -- для людей: кто аудитория
    prompt_addon text,                         -- инструкция для A2 (язык/CTA)
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rubrics (
    id          serial PRIMARY KEY,
    code        text NOT NULL UNIQUE,
    title       text NOT NULL,
    description text,                          -- угол/тема поста
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE sources    ADD COLUMN IF NOT EXISTS segment_code text;
ALTER TABLE channels   ADD COLUMN IF NOT EXISTS segment_code text;
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS segment_code text;
ALTER TABLE content    ADD COLUMN IF NOT EXISTS segment_code text;
ALTER TABLE content    ADD COLUMN IF NOT EXISTS rubric_code  text;

-- Сиды: сегменты (язык/CTA по концепту apilot92)
INSERT INTO audience_segments (code, name, description, prompt_addon) VALUES
('vine', 'Виноградники',
 'Крым, Севастополь, Анапа — агрономы и владельцы виноградников',
 'Аудитория — виноградари (Крым/Севастополь/Анапа). Стиль: сигнал + что делать сегодня, язык практикующего агронома. Пиши предметно по фазе лозы (заморозки, фазы, болезни, микрозоны). CTA — конкретное действие в ближайшие часы/день (обработать, проверить, записаться на осмотр). Без канцелярита.'),
('grain', 'Зерновые',
 'Краснодарский край, Кубань — руководители и агрономы полевых культур',
 'Аудитория — зерновые хозяйства (Краснодарский край, Кубань). Стиль: «окно на 72 часа» — упор на погодные окна 48–72 ч, экономику решений, фунгицидные обработки. CTA прагматичный: посчитать/успеть в окно/оставить заявку на расчёт.'),
('greenhouse', 'Тепличные комплексы',
 'Крым и Краснодарский край — технологи и руководители теплиц',
 'Аудитория — тепличные комплексы (Крым/Краснодарский край). Стиль: связь внешней погоды с внутренним контуром (обогрев, проветривание, влажность). Акцент на управляемость и предсказуемость. CTA — проверить контур/запросить рекомендации по режиму.')
ON CONFLICT (code) DO NOTHING;

-- Сиды: 9 рубрик (рубрикатор концепта apilot92)
INSERT INTO rubrics (code, title, description) VALUES
('signal_week',   'Сигнал недели',        'Главный агросигнал недели и что с ним делать'),
('weather_todo',  'Что делать по погоде', 'Конкретные операции под прогноз на горизонте 24–72 ч'),
('disease_risk',  'Риски болезней',       'Профилактика/обработки по рискам инфекций'),
('harvest_prep',  'Подготовка к уборке',  'Технологическая готовность к уборочной'),
('case_week',     'Кейс недели',          'Практический кейс (внутренние proof-points, без цифр без согласования)'),
('partner_news',  'Партнёрская новость',  'Новость партнёров (только согласованные упоминания)'),
('demo_announce', 'Анонс демо-дня',       'Анонс мероприятия/демонстрации'),
('subsidies',     'Субсидии и господдержка', 'Материалы по господдержке (публикация только после согласования)'),
('irrigation_windows', 'Полив и окна операций', 'Режимы полива и агротехнические окна')
ON CONFLICT (code) DO NOTHING;
