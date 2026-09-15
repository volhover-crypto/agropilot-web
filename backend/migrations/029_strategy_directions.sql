-- 029_strategy_directions.sql -- §30: блоки «Стратегии»/«Цели» до production
-- Направления стратегии (цепочка Стратегия -> Цели -> Маркетинг, ТЗ v1.1 п. 2)
-- + цели read-write (target/unit/current, привязка к направлению).

CREATE TABLE IF NOT EXISTS strategy_directions (
    id          varchar(16) PRIMARY KEY,          -- SD1, SD2...
    title       text NOT NULL,
    description text,
    keywords    jsonb NOT NULL DEFAULT '[]'::jsonb, -- фильтр медиа-мониторинга A1
    status      varchar(16) NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'paused', 'done')),
    goal_ids    jsonb NOT NULL DEFAULT '[]'::jsonb,
    owner_id    varchar(16),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE goals ADD COLUMN IF NOT EXISTS direction_id varchar(16)
    REFERENCES strategy_directions(id) ON DELETE SET NULL;
ALTER TABLE goals ADD COLUMN IF NOT EXISTS target  numeric(14,2);
ALTER TABLE goals ADD COLUMN IF NOT EXISTS unit    varchar(16);
ALTER TABLE goals ADD COLUMN IF NOT EXISTS current numeric(14,2) NOT NULL DEFAULT 0;

-- сид: направления из концепции («аграрная тема» + «нейросети», ТЗ 8.2)
INSERT INTO strategy_directions (id, title, description, keywords, goal_ids)
VALUES
  ('SD1', 'Аграрная тема', 'Отраслевая экспертиза: орошение, агрономия, кейсы',
   '["орошение","агроном","урожай","виноградник","сад","ирригация"]'::jsonb, '["G1","G2"]'),
  ('SD2', 'Применение нейросетей', 'Цифровизация агробизнеса, ИИ-кейсы',
   '["нейросет","искусственный интеллект","ИИ","цифровизац","агротех"]'::jsonb, '["G3"]')
ON CONFLICT (id) DO NOTHING;

UPDATE goals SET direction_id = 'SD1', target = 30000000, unit = '₽' WHERE id = 'G1' AND direction_id IS NULL;
UPDATE goals SET direction_id = 'SD1', target = 10, unit = 'кл' WHERE id = 'G2' AND direction_id IS NULL;
UPDATE goals SET direction_id = 'SD2', target = 12, unit = 'пост' WHERE id = 'G3' AND direction_id IS NULL;
UPDATE goals SET current = round(progress * coalesce(target,100) / 100.0, 2)
WHERE current = 0 AND progress > 0;
