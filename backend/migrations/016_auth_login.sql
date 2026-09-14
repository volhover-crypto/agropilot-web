-- 016_auth_login.sql -- AgroPILOT миграция 016: учётные данные для JWT (контракт §19)
--
-- Добавляет колонки login/password_hash в таблицу team.
-- login генерируется из id (u1@local ...), пароли НЕ задаются здесь --
-- их устанавливает оператор скриптом backend/auth/set_password.py.
-- Идемпотентно: безопасно повторное применение.

ALTER TABLE team ADD COLUMN IF NOT EXISTS login VARCHAR(64);
ALTER TABLE team ADD COLUMN IF NOT EXISTS password_hash TEXT;

UPDATE team
SET    login = lower(id)
WHERE  login IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_team_login_unique ON team (login) WHERE login IS NOT NULL;
