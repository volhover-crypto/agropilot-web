-- AgroPILOT M9 — Team Skills
-- Migration: 002_create_team_skills
-- Applies to: backend/versions/models.py → TeamSkill

CREATE TABLE IF NOT EXISTS team_skills (
    id         TEXT        PRIMARY KEY,
    user_id    TEXT        NOT NULL,
    user_name  TEXT        NOT NULL,
    skill      TEXT        NOT NULL,
    level      INTEGER     DEFAULT 3,
    note       TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_skill
    ON team_skills (user_id, skill);

CREATE INDEX IF NOT EXISTS idx_team_skills_user_id
    ON team_skills (user_id);

-- Seed: пустой — данные поставляются через PUT /v1/team/skills
