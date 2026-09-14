-- 020_roles_seed.sql -- §23: карта ролей ТЗ v1.1 -> team
-- U6/U7 — плейсхолдеры «Р.» и «П.» (переименовать при первом входе).
-- Пароли НЕ задаются здесь: только через backend.auth.set_password (§19).

INSERT INTO team (id, name, role, role_key, status, competencies, permissions, login)
VALUES ('U6', 'Р. (руководитель)', 'Руководитель', 'admin', 'active', '[]',
        '["*:*"]'::jsonb, 'u6')
ON CONFLICT (id) DO NOTHING;

INSERT INTO team (id, name, role, role_key, status, competencies, permissions, login)
VALUES ('U7', 'П. (разработчик)', 'Администратор систем', 'admin', 'active', '[]',
        '["*:*"]'::jsonb, 'u7')
ON CONFLICT (id) DO NOTHING;

-- Уникальный индекс login мог ещё не существовать, если 016 применялся до его создания
CREATE UNIQUE INDEX IF NOT EXISTS idx_team_login_unique ON team (login) WHERE login IS NOT NULL;

-- Оксана (U2) — редактор конвейера контента
UPDATE team SET permissions =
  '["content:edit", "content:approve", "sources:approve"]'::jsonb
WHERE id = 'U2' AND permissions = '[]'::jsonb;

-- Марина (U4) — SMM-поддержка
UPDATE team SET permissions = '["content:edit"]'::jsonb
WHERE id = 'U4' AND permissions = '[]'::jsonb;
