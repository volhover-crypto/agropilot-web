#!/bin/bash
# Dry-run §46 Ф1: webhook без каналов
set -u
TOKEN=$(grep ^PUB_ENGINE_TOKEN= /opt/agropilot-web/.env | cut -d= -f2)
URL=https://mdked.hlab.kz/n8n/webhook/pub-publish

PID=$(sudo -u postgres psql -d agropilot -Atc "INSERT INTO pub_posts (body_md) VALUES ('Dry-run test F1') RETURNING id;" | head -1)
echo "post_id=$PID"

echo "--- 1) без токена (ожидаем 401) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST "$URL" -H "Content-Type: application/json" -d "{\"post_id\": $PID}"

echo "--- 2) кривое тело (ожидаем 400) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST "$URL" -H "X-PUB-TOKEN: $TOKEN" -H "Content-Type: application/json" -d "{}"

echo "--- 3) несуществующий post_id (ожидаем 404) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST "$URL" -H "X-PUB-TOKEN: $TOKEN" -H "Content-Type: application/json" -d '{"post_id": 999999}'

echo "--- 4) реальный post_id без каналов (ожидаем skipped=true) ---"
curl -s -w "\nHTTP %{http_code}\n" -X POST "$URL" -H "X-PUB-TOKEN: $TOKEN" -H "Content-Type: application/json" -d "{\"post_id\": $PID}"

echo "--- статус поста в БД (ожидаем failed / no active pending channels) ---"
sudo -u postgres psql -d agropilot -Atc "SELECT id, status, last_error FROM pub_posts WHERE id=$PID;"
