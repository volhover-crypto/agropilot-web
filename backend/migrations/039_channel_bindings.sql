-- 039_channel_bindings.sql -- §42 (О6 ТЗ_ИНТЕГРАЦИЯ_OCTOP): Telegram-канал
-- ПЕТРУШКИ. Привязка chat<->user командой /start <код> в боте (подтверждение
-- пользователя -- сам код, полученный в вебе под своим логином).
-- notify_mask хранится строкой через запятую ('digest,questions') --
-- кросс-диалектно и просто патчится.

CREATE TABLE IF NOT EXISTS channel_bindings (
    id                  serial PRIMARY KEY,
    user_id             varchar(16) NOT NULL,
    channel             varchar(16) NOT NULL DEFAULT 'telegram'
                        CHECK (channel IN ('telegram')),
    chat_id             varchar(64),
    verified_at         timestamptz,
    notify_mask         varchar(64) NOT NULL DEFAULT '',
    bind_code           varchar(8),
    bind_code_expires   timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (channel, chat_id)
);

CREATE INDEX IF NOT EXISTS channel_bindings_user_idx
    ON channel_bindings (user_id, channel);
