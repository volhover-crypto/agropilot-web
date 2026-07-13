-- backend/calendar/migrations/001_create_calendar_events.sql
-- AgroPILOT M7 — initial schema for calendar_events
--
-- Run once against the target database:
--   psql "$DATABASE_URL" -f backend/calendar/migrations/001_create_calendar_events.sql
--
-- Idempotent: CREATE TYPE / CREATE TABLE use IF NOT EXISTS guards.

BEGIN;

-- ENUM type for event kind
DO $$ BEGIN
    CREATE TYPE event_kind AS ENUM ('meeting', 'call', 'deadline', 'other');
EXCEPTION
    WHEN duplicate_object THEN NULL;  -- already exists, skip
END $$;

CREATE TABLE IF NOT EXISTS calendar_events (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    start_at    TIMESTAMPTZ  NOT NULL,
    end_at      TIMESTAMPTZ,
    all_day     BOOLEAN      NOT NULL DEFAULT FALSE,
    deal_id     VARCHAR(64),
    owner_id    VARCHAR(64)  NOT NULL,
    owner_name  VARCHAR(255) NOT NULL,
    kind        event_kind   NOT NULL DEFAULT 'other',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_calendar_events_owner_id
    ON calendar_events (owner_id);

COMMIT;
