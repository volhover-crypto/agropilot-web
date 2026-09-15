-- 028_agent_registry.sql -- §29: карточки агентов + версионирование промтов
-- (ТЗ п. 6.4: промт — единица конфигурации, versioning, дата/автор, откат)

CREATE TABLE IF NOT EXISTS agent_cards (
    code         varchar(16) PRIMARY KEY,          -- a1..a7
    name         text NOT NULL,
    role         text,
    model        varchar(64) NOT NULL DEFAULT 'openai/gpt-4o-mini',
    limits       jsonb NOT NULL DEFAULT '{}'::jsonb,
    active       boolean NOT NULL DEFAULT true,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prompts (
    id           serial PRIMARY KEY,
    agent_code   varchar(16) NOT NULL REFERENCES agent_cards(code) ON DELETE CASCADE,
    version      int NOT NULL,
    text         text NOT NULL,
    note         text,
    author_id    varchar(16),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (agent_code, version)
);

CREATE INDEX IF NOT EXISTS prompts_agent_idx ON prompts (agent_code, version DESC);

-- сид карточек по ТЗ п. 5
INSERT INTO agent_cards (code, name, role) VALUES
  ('a1', 'A1 Медиа-мониторинг', 'Сбор и релевантность материалов источников'),
  ('a2', 'A2 Контентмейкер',    'Черновики постов из материалов'),
  ('a3', 'A3 Паблишер',         'Адаптация под канал и публикация'),
  ('a4', 'A4 Входящие',         'Классификация обращений, черновик ответа'),
  ('a5', 'A5 Артефакты',        'КП/письма/договоры по шаблонам'),
  ('a6', 'A6 Напоминания',      'Утренняя сводка «Мой день»'),
  ('a7', 'A7 Чат-ассистент',    'Ответы по контексту системы')
ON CONFLICT (code) DO NOTHING;
