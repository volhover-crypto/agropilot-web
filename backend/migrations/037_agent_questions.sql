-- 037_agent_questions.sql -- §40 (О3 ТЗ_ИНТЕГРАЦИЯ_OCTOP): вопросы агента
-- Раскрывает §10.1: добавляются expires_at (TTL), presented_at (идемпотентность
-- показа), round_id (гашение при новом раунде ПЕТРУШКИ).
-- Идемпотентно.

CREATE TABLE IF NOT EXISTS agent_questions (
    id            serial PRIMARY KEY,
    ts            timestamptz NOT NULL DEFAULT now(),
    user_id       varchar(16) NOT NULL,
    question      text NOT NULL,
    context_ref   varchar(128),
    round_id      varchar(64),                -- раунд ПЕТРУШКИ (§40.3)
    status        varchar(16) NOT NULL DEFAULT 'asked'
                  CHECK (status IN ('asked', 'deferred', 'answered', 'expired')),
    expires_at    timestamptz NOT NULL,       -- TTL (AGENT_QUESTION_TTL, default 72ч)
    presented_at  timestamptz,                -- первый показ фронтенду (§40.2)
    answered_at   timestamptz,
    answer_text   text,
    insight_id    integer
);

CREATE INDEX IF NOT EXISTS agent_questions_user_status_idx
    ON agent_questions (user_id, status);
CREATE INDEX IF NOT EXISTS agent_questions_expire_idx
    ON agent_questions (status, expires_at);
CREATE INDEX IF NOT EXISTS agent_questions_round_idx
    ON agent_questions (round_id) WHERE round_id IS NOT NULL;
