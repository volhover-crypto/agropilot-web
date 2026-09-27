-- 038_knowledge.sql -- §41 (О1 ТЗ_ИНТЕГРАЦИЯ_OCTOP): RAG-контур M11
-- knowledge_bases (§9.1 + corpus_version), конвейер документов, чанки.
-- Векторное хранилище -- Qdrant (коллекция agropilot_kb, создаётся кодом);
-- точки хранят qdrant_point_id в knowledge_chunks. Идемпотентно.

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id              serial PRIMARY KEY,
    title           varchar(200) NOT NULL,
    corpus_version  int NOT NULL DEFAULT 0,     -- §9.1: инкремент при изменении корпуса
    doc_count       int NOT NULL DEFAULT 0,
    indexed_at      timestamptz,
    verified_by     varchar(16),
    status          varchar(16) NOT NULL DEFAULT 'active',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_docs (
    id          serial PRIMARY KEY,
    kb_id       int NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    title       varchar(300) NOT NULL,
    -- Конвейер (§41.1): uploaded -> parsed -> chunked -> indexed -> ready | failed
    status      varchar(16) NOT NULL DEFAULT 'uploaded'
                CHECK (status IN ('uploaded','parsed','chunked','indexed','ready','failed')),
    fail_reason varchar(64),    -- no_text | encoding | ocr_unavailable | parse | empty
    charset     varchar(16),    -- utf-8 | cp1251 (фолбэк-кодировки)
    size_bytes  int,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS knowledge_docs_kb_idx ON knowledge_docs (kb_id, status);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id              serial PRIMARY KEY,
    doc_id          int NOT NULL REFERENCES knowledge_docs(id) ON DELETE CASCADE,
    kb_id           int NOT NULL,
    ord             int NOT NULL,             -- порядковый номер чанка в документе
    quote_start     int NOT NULL,             -- диапазон цитаты в тексте документа
    quote_end       int NOT NULL,
    qdrant_point_id varchar(64),
    text            text NOT NULL
);
CREATE INDEX IF NOT EXISTS knowledge_chunks_doc_idx ON knowledge_chunks (doc_id, ord);
CREATE INDEX IF NOT EXISTS knowledge_chunks_kb_idx ON knowledge_chunks (kb_id);
