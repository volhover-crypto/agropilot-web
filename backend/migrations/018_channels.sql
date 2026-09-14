-- 018_channels.sql -- §21: каналы публикаций (Этап 1 — каркас; A3 реализуется в Этапе 2)
-- Секреты в connection НЕ хранятся: только ссылка на имя переменной .env,
-- например {"chat_id": "-100...", "token_env": "TG_TOKEN_OKSANA"}.

CREATE TABLE IF NOT EXISTS channels (
    id            serial PRIMARY KEY,
    type          varchar(16) NOT NULL
                  CHECK (type IN ('telegram', 'instagram', 'site')),
    name          text NOT NULL,
    connection    jsonb NOT NULL DEFAULT '{}'::jsonb,
    adapt_prompt  text,
    active        boolean NOT NULL DEFAULT true,
    stats         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS channels_type_idx ON channels (type);
