-- 046_pub_tables.sql -- §46 (фаза Ф1 кросспостинга): реестр каналов
-- публикаций, посты и результаты по каналам. Движок публикаций -- n8n
-- (workflow publish-core, deploy/n8n/): реестр читается из БД на каждом
-- прогоне, поэтому добавление/заморозка канала (строка в pub_channels)
-- правки workflow не требует. Роль n8n_pub для движка создаётся отдельным
-- серверным шагом (пароль не коммитится), гранты -- здесь. Секреты каналов
-- (bot_token/vk_token) лежат в pub_channels.secrets и читаются только
-- ролями agropilot (backend) и n8n_pub (движок). Идемпотентно.

CREATE TABLE IF NOT EXISTS pub_channels (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    platform    TEXT NOT NULL
                CHECK (platform IN ('telegram','vk','instagram','dzen')),
    target      TEXT,                         -- chat_id / owner_id группы / relay-канал TG / ig_user_id
    secrets     JSONB NOT NULL DEFAULT '{}',  -- {bot_token | vk_token}
    template    JSONB NOT NULL DEFAULT '{}',  -- правила форматирования, §46.3
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','frozen')),
    frozen_at   TIMESTAMPTZ,
    sort_order  INT NOT NULL DEFAULT 0,
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pub_posts (
    id           BIGSERIAL PRIMARY KEY,
    body_md      TEXT NOT NULL DEFAULT '',
    media        JSONB NOT NULL DEFAULT '[]', -- [{type:'photo',url,caption}]
    status       TEXT NOT NULL DEFAULT 'draft'
                 CHECK (status IN ('draft','scheduled','publishing','done','partial','failed')),
    scheduled_at TIMESTAMPTZ,                 -- плановое время (scheduler Ф4)
    last_error   TEXT,
    created_by   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pub_post_channels (
    post_id          BIGINT NOT NULL REFERENCES pub_posts(id) ON DELETE CASCADE,
    channel_id       BIGINT NOT NULL REFERENCES pub_channels(id),
    body_override    TEXT,                    -- свой текст для канала; NULL = автоформат
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','publishing','ok','failed','skipped')),
    platform_post_id TEXT,                    -- message_id TG / post_id VK
    error            TEXT,
    published_at     TIMESTAMPTZ,
    PRIMARY KEY (post_id, channel_id)
);

CREATE INDEX IF NOT EXISTS pub_channels_status_idx ON pub_channels (status, sort_order);
CREATE INDEX IF NOT EXISTS pub_posts_status_idx ON pub_posts (status, scheduled_at);

-- Роль движка n8n_pub: SELECT секретов каналов + ведение статусов постов.
-- Создание роли с паролем -- серверный шаг (см. §46.4), здесь только гранты.
GRANT USAGE ON SCHEMA public TO n8n_pub;
GRANT SELECT ON pub_channels TO n8n_pub;
GRANT SELECT, INSERT, UPDATE ON pub_posts TO n8n_pub;
GRANT SELECT, INSERT, UPDATE ON pub_post_channels TO n8n_pub;
