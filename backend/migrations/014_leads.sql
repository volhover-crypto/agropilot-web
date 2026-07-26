-- A-6.1 leads (CONTRACTS.md 14). Idempotent, ADD-only.
CREATE TABLE IF NOT EXISTS leads (
  id                  varchar(16) PRIMARY KEY,
  name                varchar(255) NOT NULL,
  status              varchar(16) NOT NULL DEFAULT 'new',
  contact_person      varchar(255),
  phone               varchar(32),
  phone_extra         text[],
  email               varchar(255),
  owner               varchar(64),
  region              varchar(100),
  industry            varchar(100),
  ext_id              varchar(32),
  comment             varchar(255),
  source              varchar(32) DEFAULT 'bitrix24',
  converted_client_id varchar(16),
  created_at          date,
  imported_at         timestamptz DEFAULT now(),
  CONSTRAINT leads_converted_client_id_fkey
    FOREIGN KEY (converted_client_id) REFERENCES clients(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS leads_status_idx ON leads(status);
CREATE INDEX IF NOT EXISTS leads_ext_id_idx ON leads(ext_id);
