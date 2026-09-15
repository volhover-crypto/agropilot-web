-- 023_inbound_fk_fix.sql -- §22: ссылочные колонки inbounds приводятся к типам id
-- leads (varchar B<N>) и clients (varchar C<N>) + FK

ALTER TABLE inbounds ALTER COLUMN lead_id   TYPE varchar(16);
ALTER TABLE inbounds ALTER COLUMN client_id TYPE varchar(16);

ALTER TABLE inbounds
  ADD CONSTRAINT inbounds_lead_fk
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL;
ALTER TABLE inbounds
  ADD CONSTRAINT inbounds_client_fk
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL;
