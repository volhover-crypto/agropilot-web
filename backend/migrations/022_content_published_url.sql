-- 022_content_published_url.sql -- §21/A3: ссылка на опубликованный пост
ALTER TABLE content ADD COLUMN IF NOT EXISTS published_url varchar(1000);
