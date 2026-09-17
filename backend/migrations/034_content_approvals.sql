-- 034_content_approvals.sql -- §35: согласование постов в Telegram (SLA)
--
-- POST /v1/content/{id}/submit_review шлёт пост владельцу в TG с кнопками
-- «Опубликовать / Правка / Отложить»; SLA: срочные 15 мин, плановые 2 ч,
-- иначе expired (pending_manual). Решения приходят callback_query бота.

CREATE TABLE IF NOT EXISTS content_approvals (
    id            serial PRIMARY KEY,
    content_id    int NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    urgent        boolean NOT NULL DEFAULT false,
    auto_urgent   boolean NOT NULL DEFAULT false,   -- срочность определена авто-правилом
    channel_id    int,                              -- канал публикации для кнопки «Опубликовать»
    sent_at       timestamptz NOT NULL DEFAULT now(),
    deadline_at   timestamptz NOT NULL,
    status        text NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'approved', 'rejected', 'deferred', 'edited', 'expired')),
    tg_message_id int,
    decided_at    timestamptz,
    decided_by    text
);
CREATE INDEX IF NOT EXISTS idx_approvals_content ON content_approvals (content_id, id DESC);

-- «Правка» возвращает пост на доработку (draft); «Отложить» — approved + слот
-- назначается в календаре публикаций; повторная отправка закрывает прежний
-- approval как expired.
