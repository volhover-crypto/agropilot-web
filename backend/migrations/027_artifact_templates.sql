-- 027_artifact_templates.sql -- §27/A5: шаблоны артефактов + рендер черновиков
-- Артефакт-результат хранит отрендеренный текст в artifacts.body (status:
-- draft -> approved -> sent по ТЗ п. 8.6).

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS body text;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS client_id varchar(16);

CREATE TABLE IF NOT EXISTS artifact_templates (
    id             serial PRIMARY KEY,
    code           varchar(32) UNIQUE NOT NULL,
    kind           varchar(32) NOT NULL,
    title_template varchar(300) NOT NULL,
    body_template  text NOT NULL,
    note           text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

INSERT INTO artifact_templates (code, kind, title_template, body_template, note) VALUES
('kp', 'kp',
 'Коммерческое предложение — {{deal.name}}',
 E'ООО «АгроЭлемент»\n\nКому: {{client.name}}\nИНН: {{client.inn}}\nАдрес: {{client.address}}\n\nКоммерческое предложение по проекту «{{deal.name}}»\nЭтап: {{deal.stage}}\nПараметры: {{deal.need_type}}\n\nУважаемый(-ая) {{client.ceo}}!\n\nНаправляем коммерческое предложение по вашему запросу.\n[ОПИСАНИЕ РЕШЕНИЯ И СТОИМОСТИ — ЗАПОЛНИТЬ]\n\nС уважением,\nкоманда АгроЭлемент',
 'КП по сделке; переменные из карточек сделки и клиента (ЕГРЮЛ)'),
('letter', 'other',
 'Письмо — {{deal.name}}',
 E'Кому: {{client.name}}\n\nУважаемый(-ая) {{client.ceo}}!\n\n[ТЕКСТ ПИСЬМА — ЗАПОЛНИТЬ]\n\nПо вопросу: {{deal.name}} (этап: {{deal.stage}}).\n\nС уважением,\nкоманда АгроЭлемент\nтел. +7 (000) 000-00-00',
 'Коммерческое письмо'),
('contract', 'contract',
 'Договор (рамочный) — {{client.name}}',
 E'РАМОЧНЫЙ ДОГОВОР № ___\n\n{{client.name}}, ИНН {{client.inn}}, ОГРН {{client.ogrn}}, адрес: {{client.address}}\n\n1. Предмет договора: поставка и монтаж систем орошения «АгроЭлемент».\n2. [УСЛОВИЯ — ЗАПОЛНИТЬ]\n3. Сделка: {{deal.name}}; потребность: {{deal.need_type}}.\n\nПодписи сторон: ____ / ____',
 'Рамочный договор; после правок — на подпись')
ON CONFLICT (code) DO NOTHING;
