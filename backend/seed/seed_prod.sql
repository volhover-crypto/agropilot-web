-- =============================================================
-- AgroPILOT — PROD SEED (idемпотентный)
-- Источник: js/mock.objects.js (main)
-- Сгенерирован: 2026-07-13
-- Запуск: psql -U postgres -d agropilot -f /opt/agropilot-web/backend/seed/seed_prod.sql
-- Даты календаря (EV*) — относительные: CURRENT_DATE (не хардкод)
-- =============================================================

BEGIN;

-- ---------------------------------------------------
-- 1. CALENDAR EVENTS (EV1–EV5)
-- ---------------------------------------------------
INSERT INTO calendar_events
  (id, title, description, start_at, end_at, all_day, deal_id, owner_id, owner_name, kind, created_at, updated_at)
VALUES
  ('EV1',
   'Встреча: Теплица 1 га (2-я очередь)',
   'Обсуждение ТЗ по расширению',
   CURRENT_DATE + TIME '10:00:00',
   CURRENT_DATE + TIME '11:00:00',
   false, 'D6', 'U3', 'Дмитрий', 'meeting',
   NOW(), NOW()),

  ('EV2',
   'Звонок: логистика зерна',
   '',
   CURRENT_DATE + TIME '14:30:00',
   NULL,
   false, 'D7', 'U5', 'Сергей', 'call',
   NOW(), NOW()),

  ('EV3',
   'Дедлайн КП: доукомплектация',
   'Отправить коммерческое предложение',
   CURRENT_DATE + TIME '09:00:00',
   NULL,
   true, 'D8', 'U4', 'Марина', 'deadline',
   NOW(), NOW()),

  ('EV4',
   'Демо системы капельного орошения',
   'Выезд на объект',
   CURRENT_DATE + TIME '16:00:00',
   CURRENT_DATE + TIME '17:00:00',
   false, 'D1', 'U1', 'Екатерина', 'meeting',
   NOW(), NOW()),

  ('EV5',
   'Планёрка команды',
   '',
   CURRENT_DATE + TIME '08:30:00',
   CURRENT_DATE + TIME '09:00:00',
   false, '', 'U2', 'Оксана', 'other',
   NOW(), NOW())

ON CONFLICT (id) DO UPDATE SET
  title       = EXCLUDED.title,
  description = EXCLUDED.description,
  start_at    = EXCLUDED.start_at,
  end_at      = EXCLUDED.end_at,
  all_day     = EXCLUDED.all_day,
  deal_id     = EXCLUDED.deal_id,
  owner_id    = EXCLUDED.owner_id,
  owner_name  = EXCLUDED.owner_name,
  kind        = EXCLUDED.kind,
  updated_at  = NOW();

-- ---------------------------------------------------
-- 2. TEAM SKILLS (7 записей, UNIQUE user_id+skill)
-- ---------------------------------------------------
INSERT INTO team_skills
  (id, user_id, user_name, skill, level, note, updated_at)
VALUES
  ('SK1', 'U1', 'Екатерина', 'Переговоры',             5, 'Крупные сделки, закрытие', '2026-06-20'),
  ('SK2', 'U1', 'Екатерина', 'Орошение',                4, '',                             '2026-06-18'),
  ('SK3', 'U2', 'Оксана',    'Управление проектами',   5, 'Монтаж под ключ',            '2026-06-22'),
  ('SK4', 'U3', 'Дмитрий',  'Проектирование',          5, 'Теплицы, поливные узлы',   '2026-06-19'),
  ('SK5', 'U3', 'Дмитрий',  'Автоматизация',             3, 'Контроллеры',                 '2026-06-15'),
  ('SK6', 'U4', 'Марина',   'Контент / SMM',             4, 'Telegram + VK',               '2026-06-21'),
  ('SK7', 'U5', 'Сергей',   'Мониторинг / аналитика', 4, 'Источники, тендеры',         '2026-06-23')

ON CONFLICT (user_id, skill) DO UPDATE SET
  user_name  = EXCLUDED.user_name,
  level      = EXCLUDED.level,
  note       = EXCLUDED.note,
  updated_at = EXCLUDED.updated_at;

-- ---------------------------------------------------
-- 3. STRATEGY (SC1–SC3, upsert strategy_main)
-- ---------------------------------------------------
INSERT INTO strategy (id, title, horizon, scenarios, updated_at, updated_by)
VALUES (
  'strategy_main',
  'Стратегия 2026: рост в орошении и продвижение продукта',
  '2026',
  '[
    {
      "id": "SC1",
      "title": "Орошение и автоматизация",
      "description": "Капельное орошение, фертигация, контроллеры — приоритетная ниша года",
      "indicators": [
        {"id": "IND1", "text": "Воронка орошения > 15 млн ₽",       "status": "green"},
        {"id": "IND2", "text": "Конверсия Оценка→Договор > 40%",    "status": "yellow"},
        {"id": "IND3", "text": "Срок сделки < 60 дней (медиана)",      "status": "green"}
      ],
      "action_lines": [
        {"id": "AL1", "text": "Дожать 3 сделки в стадии Оценка до Договора (Q3)"},
        {"id": "AL2", "text": "Запустить пакет «Автополив Умный» в активное продвижение"}
      ]
    },
    {
      "id": "SC2",
      "title": "Хранение и логистика",
      "description": "Холодное хранение, складская логистика — выход в новый сегмент",
      "indicators": [
        {"id": "IND4", "text": "Воронка хранения > 9 млн ₽",          "status": "yellow"},
        {"id": "IND5", "text": "Хотя бы 1 сделка закрыта в сегменте",  "status": "red"},
        {"id": "IND6", "text": "КФХ «Степь-Зерно» реанимирован",       "status": "red"}
      ],
      "action_lines": [
        {"id": "AL3", "text": "Реанимировать D5 (Зерновая логистика): назначить созвон на этой неделе"},
        {"id": "AL4", "text": "Подготовить шаблон КП для сегмента хранения (на базе P3)"}
      ]
    },
    {
      "id": "SC3",
      "title": "Продуктовое продвижение",
      "description": "Три упаковки в статусе «в продвижении» к концу H2 2026",
      "indicators": [
        {"id": "IND7", "text": "Упаковок «в продвижении» ≥ 3",        "status": "yellow"},
        {"id": "IND8", "text": "Охват публикаций > 500 контактов/мес",  "status": "green"}
      ],
      "action_lines": [
        {"id": "AL5", "text": "Перевести P2 (Теплица Модуль) в «в продвижении»"},
        {"id": "AL6", "text": "Согласовать контент-план на август"}
      ]
    }
  ]'::jsonb,
  NOW(),
  'Екатерина'
)
ON CONFLICT (id) DO UPDATE SET
  title      = EXCLUDED.title,
  horizon    = EXCLUDED.horizon,
  scenarios  = EXCLUDED.scenarios,
  updated_at = NOW(),
  updated_by = EXCLUDED.updated_by;

COMMIT;

-- ---------------------------------------------------
-- Проверка после выполнения:
-- SELECT COUNT(*) FROM calendar_events;  -- ожидаем >= 5
-- SELECT COUNT(*) FROM team_skills;      -- ожидаем 7
-- SELECT jsonb_array_length(scenarios) FROM strategy WHERE id='strategy_main'; -- 3
-- ---------------------------------------------------
