-- §15.6 п.4 / §15.7 P1 — «Дела» по лиду в минимальном виде.
-- Idempotent, ADD-only. FK НЕТ и не требуется (протокол 4 дефектов).
ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_action    text;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_action_at date;

-- Сортировка GET /leads?sort=next_action_at (§15.7 D) + подсветка просроченных.
CREATE INDEX IF NOT EXISTS leads_next_action_at_idx ON leads(next_action_at);
