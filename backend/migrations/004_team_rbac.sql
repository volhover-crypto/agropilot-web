-- 004_team_rbac.sql -- Stage 2, Блок E (§11 CONTRACTS.md)
-- Аддитивное расширение team под RBAC/маршрутизацию. Идемпотентно (IF NOT EXISTS).
-- FK deals/goals/tasks -> team(id) не затрагиваются (только ADD COLUMN).

ALTER TABLE team ADD COLUMN IF NOT EXISTS competencies JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE team ADD COLUMN IF NOT EXISTS permissions  JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE team ADD COLUMN IF NOT EXISTS status       VARCHAR(16) NOT NULL DEFAULT 'active';
ALTER TABLE team ADD COLUMN IF NOT EXISTS role_key     VARCHAR(32);

-- Нормализация ролей U1-U5 (role_key рядом с человекочитаемым role, role НЕ трогаем)
UPDATE team SET role_key = 'manager'  WHERE id IN ('U1','U2') AND role_key IS NULL;
UPDATE team SET role_key = 'engineer' WHERE id IN ('U3','U5') AND role_key IS NULL;
UPDATE team SET role_key = 'smm'      WHERE id = 'U4'         AND role_key IS NULL;
