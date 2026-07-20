-- 007_packages.sql — M10-4: пакеты услуг/КП
CREATE TABLE IF NOT EXISTS packages (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(300)  NOT NULL,
    description TEXT,
    price       NUMERIC(12,2),
    status      VARCHAR(16)   NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft','active','archived')),
    deal_id     VARCHAR(16)   REFERENCES deals(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);
