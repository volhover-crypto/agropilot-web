-- 040_artifact_folders.sql -- раздел «Артефакты» как файловый менеджер:
-- персистентные папки + folder_id у артефактов (раньше папки жили только
-- в мок-структуре фронтенда и пропадали при перезагрузке).
-- Идемпотентно.

CREATE TABLE IF NOT EXISTS artifact_folders (
    id          SERIAL PRIMARY KEY,
    parent_id   INTEGER REFERENCES artifact_folders(id) ON DELETE SET NULL,
    name        VARCHAR(200) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS artifact_folders_parent_idx ON artifact_folders (parent_id);

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS folder_id
    INTEGER REFERENCES artifact_folders(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS artifacts_folder_idx ON artifacts (folder_id);
