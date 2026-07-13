-- =============================================================
-- AgroPILOT — PROD SEED (идемпотентный)
-- Источник: js/mock.objects.js (main)
-- Обновлён: 2026-07-13 (добавлены team/clients/goals/deals/tasks — fix issue#1-3)
-- Запуск: psql -U postgres -d agropilot -f /opt/agropilot-web/backend/seed/seed_prod.sql
-- Даты — относительные: CURRENT_DATE (не хардкод)
-- =============================================================

BEGIN;

-- ---------------------------------------------------
-- 0. TEAM (U1–U5)
-- ---------------------------------------------------
INSERT INTO team (id, name, role, avatar, cap, can_confirm)
VALUES
  ('U1', 'Екатерина',  'Руководитель продаж', '👤', 8, true),
  ('U2', 'Оксана',     'Менеджер проектов',   '👤', 5, true),
  ('U3', 'Дмитрий',    'Инженер-проектировщик','👤', 5, false),
  ('U4', 'Марина',     'Контент / SMM',        '👤', 5, false),
  ('U5', 'Сергей',     'Аналитик',             '👤', 5, false)
ON CONFLICT (id) DO UPDATE SET
  name        = EXCLUDED.name,
  role        = EXCLUDED.role,
  can_confirm = EXCLUDED.can_confirm;

-- ---------------------------------------------------
-- 1. CLIENTS (C1–C5)
-- ---------------------------------------------------
INSERT INTO clients (id, name, industry, region, need, health, deals_count)
VALUES
  ('C1', 'КФХ «Заря»',           'зерновые',    'Краснодарский край',  ARRAY['орошение','фертигация'],   'green',  2),
  ('C2', 'ООО «АгроТеплица»',    'овощеводство','Ставропольский край', ARRAY['теплицы','автоматизация'], 'yellow', 1),
  ('C3', 'ИП Степанов',          'садоводство', 'Ростовская обл.',     ARRAY['орошение'],                'green',  1),
  ('C4', 'ООО «ЮгХранение»',     'хранение',    'Краснодарский край',  ARRAY['хранение','логистика'],    'red',    1),
  ('C5', 'КФХ «Степь-Зерно»',    'зерновые',    'Волгоградская обл.',  ARRAY['логистика'],               'red',    1)
ON CONFLICT (id) DO UPDATE SET
  name        = EXCLUDED.name,
  industry    = EXCLUDED.industry,
  region      = EXCLUDED.region,
  need        = EXCLUDED.need,
  health      = EXCLUDED.health,
  deals_count = EXCLUDED.deals_count;

-- ---------------------------------------------------
-- 2. GOALS (G1–G3)
-- ---------------------------------------------------
INSERT INTO goals (id, title, description, kind, period_start, period_end,
                   owner_id, status, progress, metric, signal)
VALUES
  ('G1', 'Выручка Q3-2026',
   'Объём закрытых сделок за квартал',
   'revenue', '2026-07-01', '2026-09-30', 'U1', 'active', 34,
   '{"name":"Выручка","target":25000000,"current":8500000,"unit":"₽"}'::jsonb, 'slow'),
  ('G2', 'Новые клиенты H2-2026',
   'Привлечение новых клиентов',
   'clients', '2026-07-01', '2026-12-31', 'U1', 'active', 20,
   '{"name":"Новые клиенты","target":10,"current":2,"unit":"шт"}'::jsonb, NULL),
  ('G3', 'Продуктовое продвижение',
   'Три упаковки в статусе «в продвижении» к концу H2',
   'product', '2026-07-01', '2026-12-31', 'U4', 'active', 33,
   '{"name":"Упаковки в продвижении","target":3,"current":1,"unit":"шт"}'::jsonb, NULL)
ON CONFLICT (id) DO UPDATE SET
  title = EXCLUDED.title, description = EXCLUDED.description,
  status = EXCLUDED.status, progress = EXCLUDED.progress,
  metric = EXCLUDED.metric;

-- ---------------------------------------------------
-- 3. DEALS (D1–D8)
-- ---------------------------------------------------
INSERT INTO deals (id, name, stage, client_id, owner_id, owner_sales,
                   finance, need_type, industry, region, score, signal,
                   goal_id, created_at, updated_at)
VALUES
  ('D1', 'Капельное орошение 12 га',     'deal',     'C1','U1','Екатерина', '{"budget":4800000}'::jsonb, 'орошение',   'зерновые',    'Краснодарский край',88,'warning', 'G1',NOW()-INTERVAL '45 days',NOW()-INTERVAL '2 days'),
  ('D2', 'Фертигационная станция',        'proposal', 'C1','U3','Дмитрий',  '{"budget":1900000}'::jsonb, 'фертигация', 'зерновые',    'Краснодарский край',74,NULL,      'G1',NOW()-INTERVAL '30 days',NOW()-INTERVAL '5 days'),
  ('D3', 'Теплица модульная 0.5 га',      'assess',   'C2','U2','Оксана',   '{"budget":6500000}'::jsonb, 'теплицы',    'овощеводство','Ставропольский край',65,NULL,      'G1',NOW()-INTERVAL '20 days',NOW()-INTERVAL '8 days'),
  ('D4', 'Система орошения сад 8 га',     'lead',     'C3','U3','Дмитрий',  '{"budget":2100000}'::jsonb, 'орошение',   'садоводство', 'Ростовская обл.',   52,NULL,      'G1',NOW()-INTERVAL '10 days',NOW()-INTERVAL '10 days'),
  ('D5', 'Зерновая логистика (хранение)', 'lead',     'C4','U5','Сергей',   '{"budget":3300000}'::jsonb, 'хранение',   'хранение',    'Краснодарский край',41,'critical','G1',NOW()-INTERVAL '60 days',NOW()-INTERVAL '30 days'),
  ('D6', 'Теплица 1 га (2-я очередь)',    'assess',   'C2','U3','Дмитрий',  '{"budget":8200000}'::jsonb, 'теплицы',    'овощеводство','Ставропольский край',78,NULL,      'G1',NOW()-INTERVAL '15 days',NOW()-INTERVAL '1 day'),
  ('D7', 'Логистика зерна — КФХ Степь',  'lead',     'C5','U5','Сергей',   '{"budget":1500000}'::jsonb, 'логистика',  'зерновые',    'Волгоградская обл.',38,'critical','G1',NOW()-INTERVAL '90 days',NOW()-INTERVAL '45 days'),
  ('D8', 'Доукомплектация оборудования',  'proposal', 'C3','U4','Марина',   '{"budget":950000}'::jsonb,  'оборудование','садоводство', 'Ростовская обл.',  60,NULL,      'G1',NOW()-INTERVAL '7 days', NOW()-INTERVAL '3 days')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name, stage = EXCLUDED.stage,
  score = EXCLUDED.score, signal = EXCLUDED.signal, updated_at = NOW();

-- ---------------------------------------------------
-- 4. TASKS (T1–T8)
-- ---------------------------------------------------
INSERT INTO tasks (id, title, status, assignee, owner_id, goal_id,
                   due_at, priority, deal_id, created_at, updated_at)
VALUES
  ('T1', 'Созвон по КП — орошение 12 га',     'active', 'Екатерина','U1','G1', CURRENT_DATE+INTERVAL '1 day',  'high',  'D1',NOW(),NOW()),
  ('T2', 'Подготовить схему фертигации',          'active', 'Дмитрий', 'U3','G1', CURRENT_DATE+INTERVAL '3 days', 'normal','D2',NOW(),NOW()),
  ('T3', 'Согласовать смету теплицы 0.5 га',    'overdue','Оксана',  'U2','G1', CURRENT_DATE-INTERVAL '1 day',  'high',  'D3',NOW(),NOW()),
  ('T4', 'Выезд на объект: сад 8 га',            'active', 'Дмитрий', 'U3','G2', CURRENT_DATE+INTERVAL '5 days', 'normal','D4',NOW(),NOW()),
  ('T5', 'Реанимировать D5 — назначить созвон',  'active', 'Сергей',  'U5','G1', CURRENT_DATE,                   'high',  'D5',NOW(),NOW()),
  ('T6', 'КП по доукомплектации — отправить',    'active', 'Марина',  'U4','G3', CURRENT_DATE,                   'high',  'D8',NOW(),NOW()),
  ('T7', 'Согласовать ТЗ теплица 2-я очередь',  'active', 'Дмитрий', 'U3','G1', CURRENT_DATE+INTERVAL '2 days', 'normal','D6',NOW(),NOW()),
  ('T8', 'Подготовить контент-план на август',   'active', 'Марина',  'U4','G3', CURRENT_DATE+INTERVAL '7 days', 'normal','',  NOW(),NOW())
ON CONFLICT (id) DO UPDATE SET
  title = EXCLUDED.title, status = EXCLUDED.status,
  due_at = EXCLUDED.due_at, priority = EXCLUDED.priority, updated_at = NOW();

-- ---------------------------------------------------
-- 5. CALENDAR EVENTS (EV1–EV5)
-- ---------------------------------------------------
INSERT INTO calendar_events
  (id, title, description, start_at, end_at, all_day, deal_id, owner_id, owner_name, kind, created_at, updated_at)
VALUES
  ('EV1','Встреча: Теплица 1 га (2-я очередь)','Обсуждение ТЗ', CURRENT_DATE+TIME '10:00:00',CURRENT_DATE+TIME '11:00:00',false,'D6','U3','Дмитрий','meeting',NOW(),NOW()),
  ('EV2','Звонок: логистика зерна','',               CURRENT_DATE+TIME '14:30:00',NULL,false,'D7','U5','Сергей','call',   NOW(),NOW()),
  ('EV3','Дедлайн КП: доукомплектация','Отправить КП',     CURRENT_DATE+TIME '09:00:00',NULL,true, 'D8','U4','Марина','deadline',NOW(),NOW()),
  ('EV4','Демо капельного орошения',     'Выезд на объект',    CURRENT_DATE+TIME '16:00:00',CURRENT_DATE+TIME '17:00:00',false,'D1','U1','Екатерина','meeting',NOW(),NOW()),
  ('EV5','Планёрка команды','',                       CURRENT_DATE+TIME '08:30:00',CURRENT_DATE+TIME '09:00:00',false,'', 'U2','Оксана','other',  NOW(),NOW())
ON CONFLICT (id) DO UPDATE SET
  title = EXCLUDED.title, start_at = EXCLUDED.start_at,
  end_at = EXCLUDED.end_at, updated_at = NOW();

-- ---------------------------------------------------
-- 6. TEAM SKILLS (SK1–SK7)
-- ---------------------------------------------------
INSERT INTO team_skills (id, user_id, user_name, skill, level, note, updated_at)
VALUES
  ('SK1','U1','Екатерина','Переговоры',           5,'Крупные сделки, закрытие','2026-06-20'),
  ('SK2','U1','Екатерина','Орошение',              4,'',                        '2026-06-18'),
  ('SK3','U2','Оксана',   'Управление проектами', 5,'Монтаж под ключ',        '2026-06-22'),
  ('SK4','U3','Дмитрий',  'Проектирование',        5,'Теплицы, поливные узлы',  '2026-06-19'),
  ('SK5','U3','Дмитрий',  'Автоматизация',         3,'Контроллеры',           '2026-06-15'),
  ('SK6','U4','Марина',   'Контент / SMM',         4,'Telegram + VK',           '2026-06-21'),
  ('SK7','U5','Сергей',   'Мониторинг / аналитика',4,'Источники, тендеры',     '2026-06-23')
ON CONFLICT (user_id, skill) DO UPDATE SET
  user_name = EXCLUDED.user_name, level = EXCLUDED.level,
  note = EXCLUDED.note, updated_at = EXCLUDED.updated_at;

-- ---------------------------------------------------
-- 7. STRATEGY
-- ---------------------------------------------------
INSERT INTO strategy (id, title, horizon, scenarios, updated_at, updated_by)
VALUES (
  'strategy_main',
  'Стратегия 2026: рост в орошении и продвижение продукта', '2026',
  '[{"id":"SC1","title":"Орошение и автоматизация","description":"Капельное орошение, фертигация, контроллеры — приоритетная ниша года","indicators":[{"id":"IND1","text":"Воронка орошения > 15 млн ₽","status":"green"},{"id":"IND2","text":"Конверсия Оценка→Договор > 40%","status":"yellow"},{"id":"IND3","text":"Срок сделки < 60 дней","status":"green"}],"action_lines":[{"id":"AL1","text":"Дожать 3 сделки в Assess до Договора (Q3)"},{"id":"AL2","text":"Запустить пакет «Автополив Умный» в активное продвижение"}]},{"id":"SC2","title":"Хранение и логистика","description":"Холодное хранение, складская логистика","indicators":[{"id":"IND4","text":"Воронка хранения > 9 млн ₽","status":"yellow"},{"id":"IND5","text":"Хотя бы 1 сделка закрыта в сегменте","status":"red"},{"id":"IND6","text":"КФХ Степь-Зерно реанимирован","status":"red"}],"action_lines":[{"id":"AL3","text":"Реанимировать D5: созвон на этой неделе"},{"id":"AL4","text":"Подготовить шаблон КП для сегмента хранения"}]},{"id":"SC3","title":"Продуктовое продвижение","description":"Три упаковки в продвижении к концу H2 2026","indicators":[{"id":"IND7","text":"Упаковок в продвижении ≥ 3","status":"yellow"},{"id":"IND8","text":"Охват публикаций > 500/мес","status":"green"}],"action_lines":[{"id":"AL5","text":"Перевести P2 (Теплица Модуль) в продвижение"},{"id":"AL6","text":"Согласовать контент-план на август"}]}]'::jsonb,
  NOW(), 'Екатерина'
)
ON CONFLICT (id) DO UPDATE SET
  title = EXCLUDED.title, scenarios = EXCLUDED.scenarios,
  updated_at = NOW(), updated_by = EXCLUDED.updated_by;

-- ---------------------------------------------------
-- 8. Обновить счётчики сделок у клиентов
-- ---------------------------------------------------
UPDATE clients SET deals_count = (
  SELECT COUNT(*) FROM deals WHERE deals.client_id = clients.id
);

COMMIT;

-- Проверка после выполнения:
-- SELECT COUNT(*) FROM team;             -- 5
-- SELECT COUNT(*) FROM clients;          -- 5
-- SELECT COUNT(*) FROM goals;            -- 3
-- SELECT COUNT(*) FROM deals;            -- 8
-- SELECT COUNT(*) FROM tasks;            -- 8
-- SELECT COUNT(*) FROM calendar_events;  -- 5
-- SELECT COUNT(*) FROM team_skills;      -- 7
