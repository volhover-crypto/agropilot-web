-- 011_team_competencies_seed.sql -- Block E-seed (Stage-2): наполнение competencies[]
-- Предусловие маршрутизации proposed (Блок D, D-5.2/D-5.3 по совпадению competencies).
-- Идемпотентно: обновляет только пустые competencies ('[]'), заполненные не трогает.
-- Значения привязаны к role_key (утверждено Архитектором 2026-07-23).

UPDATE team SET competencies = '["стратегия","клиенты","сделки"]'::jsonb
  WHERE role_key = 'manager'  AND competencies = '[]'::jsonb;

UPDATE team SET competencies = '["поставщики оборудования","агротех","сопредельные рынки"]'::jsonb
  WHERE role_key = 'engineer' AND competencies = '[]'::jsonb;

UPDATE team SET competencies = '["агро-инфополе","соцсети","контент"]'::jsonb
  WHERE role_key = 'smm'      AND competencies = '[]'::jsonb;
