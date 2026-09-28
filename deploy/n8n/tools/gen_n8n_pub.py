# -*- coding: utf-8 -*-
"""Генератор workflow n8n для §46 (Ф1 кросспостинга), ревизия 2.

Изменения ревизии 2 (после отладки на сервере):
- publish-core стартует собственным webhook-триггером (POST /pub-core, тот же
  X-PUB-TOKEN), а НЕ Execute Workflow Trigger: в n8n 2.20 sub-workflow-вызовы
  через Execute Workflow падали с WorkflowHasIssuesError, при этом
  webhook-запуски того же графа проходили. pub-publish вызывает core
  HTTP-запросом на 127.0.0.1:5678 (n8n в host network).
- HTTP-код ответа у Respond to Webhook передаётся через options.responseCode
  (в новых версиях корневой параметр responseCode игнорируется).

Выход: agropilot-web/deploy/n8n/pub-publish-core.workflow.json и
pub-publish-webhook.workflow.json. Плейсхолдеры __CRED_DB_ID__,
__CRED_TOK_ID__ заменяются на сервере после импорта credentials.
"""
import json, os

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------- Code-узлы publish-core ----------

js_prepare = r"""// Валидация входа: {"post_id": N}. Webhook отдаёт тело в $json.body.
const raw = $input.first().json;
const b = (raw && raw.body && typeof raw.body === 'object') ? raw.body : raw;
const pid = Number(b.post_id);
if (!Number.isInteger(pid) || pid <= 0) {
  throw new Error('post_id (positive integer) required');
}
return [{ json: { post_id: pid } }];
"""

sql_mark_load = (
    "=UPDATE pub_posts SET status = 'publishing', last_error = NULL, updated_at = now()\n"
    "WHERE id = {{ $('Prepare').first().json.post_id }}\n"
    "RETURNING id AS post_id, body_md, media"
)

sql_load_channels = (
    "=SELECT COALESCE(jsonb_agg(t), '[]'::jsonb) AS channels\n"
    "FROM (SELECT c.id AS channel_id, c.name, c.platform, c.target, c.secrets, c.template,\n"
    "             pc.body_override\n"
    "      FROM pub_post_channels pc\n"
    "      JOIN pub_channels c ON c.id = pc.channel_id AND c.status = 'active'\n"
    "      WHERE pc.post_id = {{ $('Prepare').first().json.post_id }} AND pc.status = 'pending'\n"
    "      ORDER BY c.sort_order, c.id) t"
)

js_build_jobs = r"""// Пост + каналы -> задания; 0 каналов -> skip-маркер (отдельная ветка ответа).
// Load channels всегда возвращает одну строку {channels: [...]} (jsonb_agg).
const post = $('Mark publishing & load post').first().json;
const chans = $input.first().json.channels || [];
if (chans.length === 0) {
  return [{ json: { skip: true, post_id: post.post_id, reason: 'no active pending channels' } }];
}
return chans.map(c => ({ json: {
  post: { post_id: post.post_id, body_md: post.body_md || '', media: post.media || [] },
  channel: c,
} }));
"""

js_format_tg = r"""// formatTG (§46.3): markdown-lite -> HTML Telegram, обрезка 4096/1024,
// media: 1 фото -> sendPhoto, 2-10 -> sendMediaGroup, иначе sendMessage
const { post, channel } = $input.first().json;
function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function mdToTgHtml(md) {
  let h = escHtml(md);
  h = h.replace(/\*\*(.+?)\*\*/gs, '<b>$1</b>');
  h = h.replace(/(^|\s)\*(?!\s)(.+?)\*(?=\s|$)/gs, '$1<i>$2</i>');
  h = h.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2">$1</a>');
  return h;
}
const src = channel.body_override != null ? channel.body_override : post.body_md;
let text = mdToTgHtml(src);
if (text.length > 4096) text = text.slice(0, 4090) + '\n…';
const tok = (channel.secrets || {}).bot_token;
if (!tok) throw new Error('telegram channel without bot_token: ' + channel.name);
const media = (post.media || []).filter(m => m && m.type === 'photo' && m.url);
let method, body;
if (media.length >= 2) {
  method = 'sendMediaGroup';
  const group = media.slice(0, 10).map((m, i) => ({
    type: 'photo', media: m.url,
    caption: i === 0 ? text.slice(0, 1024) : '', parse_mode: 'HTML',
  }));
  body = { chat_id: channel.target, media: JSON.stringify(group) };
} else if (media.length === 1) {
  method = 'sendPhoto';
  body = { chat_id: channel.target, photo: media[0].url, caption: text.slice(0, 1024), parse_mode: 'HTML' };
} else {
  method = 'sendMessage';
  body = { chat_id: channel.target, text, parse_mode: 'HTML' };
}
return [{ json: {
  post_id: post.post_id, channel_id: channel.channel_id, channel_name: channel.name,
  http: { url: 'https://api.telegram.org/bot' + tok + '/' + method, method: 'POST', body },
} }];
"""

js_format_vk = r"""// formatVK (§46.3): markdown снимается (plain), хэштеги остаются,
// лимит 4096; wall.post от имени сообщества. photo_url — первое фото поста
// (есть → ветка multipart-загрузки VK, ревизия 6).
const { post, channel } = $input.first().json;
function stripMd(s) {
  return s
    .replace(/\*\*(.+?)\*\*/gs, '$1')
    .replace(/(^|\s)\*(?!\s)(.+?)\*(?=\s|$)/gs, '$1$2')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '$1 ($2)');
}
const src = channel.body_override != null ? channel.body_override : post.body_md;
let text = stripMd(src);
if (text.length > 4096) text = text.slice(0, 4090) + '\n…';
const tok = (channel.secrets || {}).vk_token;
if (!tok) throw new Error('vk channel without vk_token: ' + channel.name);
const photo = (post.media || []).filter(m => m && m.type === 'photo' && m.url)[0] || null;
return [{ json: {
  post_id: post.post_id, channel_id: channel.channel_id, channel_name: channel.name,
  photo_url: photo ? photo.url : null,
  vk: {
    owner_id: channel.target,
    group_id: String(Math.abs(Number(channel.target))),
    token: tok,
  },
  http: {
    url: 'https://api.vk.com/method/wall.post', method: 'POST',
    body: { owner_id: channel.target, from_group: 1, message: text, v: '5.199', access_token: tok },
  },
} }];
"""

js_vk_attach = r"""// VK: собрать attachments из сохранённого фото + исходный wall.post body
const it = $('formatVK').first().json;
const saved = $input.first().json.response && $input.first().json.response[0];
const body = { ...it.http.body };
if (saved && saved.owner_id != null && saved.id != null) {
  body.attachments = 'photo' + saved.owner_id + '_' + saved.id;
} else {
  throw new Error('VK saveWallPhoto: пустой ответ');
}
return [{ json: { ...it, http: { ...it.http, body } } }];
"""

def result_code(fmt_node):
    if fmt_node == 'formatTG':
        ok_expr = "resp.ok === true"
        pid_expr = "String(resp.result && resp.result.message_id != null ? resp.result.message_id : '')"
        err_expr = "resp.description || JSON.stringify(resp)"
    else:
        ok_expr = "resp.response != null"
        pid_expr = "String(resp.response && resp.response.post_id != null ? resp.response.post_id : '')"
        err_expr = "(resp.error && resp.error.error_msg) || JSON.stringify(resp)"
    return r"""// Сбор результата платформы (paired item -> метаданные задания)
const src = $('%s');
const out = [];
for (const item of $input.all()) {
  const pi = item.pairedItem ? (item.pairedItem.item ?? item.pairedItem) : null;
  const meta = (pi != null && src.all()[pi]) ? src.all()[pi].json : src.all()[0].json;
  const resp = item.json || {};
  const ok = %s;
  out.push({ json: {
    post_id: meta.post_id, channel_id: meta.channel_id,
    status: ok ? 'ok' : 'failed',
    platform_post_id: %s,
    error: ok ? null : String(%s).slice(0, 500),
  } });
}
return out;
""" % (fmt_node, ok_expr, pid_expr, err_expr)

js_skipped = r"""// Платформа без ветки в этой фазе (instagram/dzen — Ф5/Ф6)
const it = $input.first().json;
return [{ json: {
  post_id: it.post.post_id, channel_id: it.channel.channel_id,
  status: 'skipped', platform_post_id: null,
  error: 'platform branch not implemented yet: ' + it.channel.platform,
} }];
"""

js_quote_sql = r"""// Экранирование строковых полей в SQL-литералы (stringify в выражениях
// SQL ненадёжен — готовим литералы здесь, в запросе только подстановка).
const q = (v) => (v == null || v === '') ? 'NULL' : "'" + String(v).replace(/'/g, "''") + "'";
return $input.all().map(item => {
  const j = item.json;
  return { json: { ...j,
    status_q: q(j.status),
    pid_q: q(j.platform_post_id || null),
    err_q: q(j.error || null),
  } };
});
"""

sql_save_results = (
    "=INSERT INTO pub_post_channels (post_id, channel_id, status, platform_post_id, error, published_at)\n"
    "SELECT {{ $json.post_id }}, {{ $json.channel_id }}::bigint, {{ $json.status_q }},\n"
    "       {{ $json.pid_q }}, {{ $json.err_q }},\n"
    "       CASE WHEN {{ $json.status_q }} = 'ok' THEN now() ELSE NULL END\n"
    "WHERE {{ $json.channel_id }}::bigint IS NOT NULL\n"
    "ON CONFLICT (post_id, channel_id) DO UPDATE SET\n"
    "  status = EXCLUDED.status, platform_post_id = EXCLUDED.platform_post_id,\n"
    "  error = EXCLUDED.error, published_at = EXCLUDED.published_at\n"
    "RETURNING post_id"
)

sql_finalize = (
    "=UPDATE pub_posts p SET\n"
    "  status = CASE WHEN cnt.ok > 0 AND cnt.fail = 0 THEN 'done'\n"
    "               WHEN cnt.ok > 0 THEN 'partial'\n"
    "               ELSE 'failed' END,\n"
    "  last_error = CASE WHEN cnt.ok = 0 THEN\n"
    "               CASE WHEN cnt.fail > 0 THEN 'all channels failed'\n"
    "                    ELSE 'no publishable channels' END\n"
    "               ELSE NULL END,\n"
    "  updated_at = now()\n"
    "FROM (SELECT count(*) FILTER (WHERE status = 'ok') AS ok,\n"
    "             count(*) FILTER (WHERE status = 'failed') AS fail\n"
    "      FROM pub_post_channels WHERE post_id = {{ $('Prepare').first().json.post_id }}) cnt\n"
    "WHERE p.id = {{ $('Prepare').first().json.post_id }}\n"
    "RETURNING p.id AS post_id, p.status AS post_status"
)

js_final = r"""// Итог: статус поста + результаты по каналам
const fin = $input.first().json;
const results = $('Merge results').all().map(i => ({
  channel_id: i.json.channel_id, status: i.json.status,
  platform_post_id: i.json.platform_post_id || null, error: i.json.error || null,
}));
return [{ json: { post_id: fin.post_id, post_status: fin.post_status, results } }];
"""

# ---------- publish-core ----------

core_nodes = [
  {"id": "n01", "name": "On call", "type": "n8n-nodes-base.webhook",
   "typeVersion": 2, "position": [-660, 0], "webhookId": "pub-core",
   "credentials": {"httpHeaderAuth": {"id": "__CRED_TOK_ID__", "name": "PUB webhook token"}},
   "parameters": {"httpMethod": "POST", "path": "pub-core",
     "authentication": "headerAuth", "responseMode": "responseNode", "options": {}}},
  {"id": "n02", "name": "Prepare", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [-440, 0], "parameters": {"jsCode": js_prepare}},
  {"id": "n03", "name": "Mark publishing & load post", "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [-220, 0],
   "credentials": {"postgres": {"id": "__CRED_DB_ID__", "name": "AgroPILOT PUB DB"}},
   "parameters": {"operation": "executeQuery", "query": sql_mark_load, "options": {}}},
  {"id": "n04", "name": "Load channels", "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [0, 0],
   "credentials": {"postgres": {"id": "__CRED_DB_ID__", "name": "AgroPILOT PUB DB"}},
   "parameters": {"operation": "executeQuery", "query": sql_load_channels, "options": {}}},
  {"id": "n05", "name": "Build jobs", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [220, 0], "parameters": {"jsCode": js_build_jobs}},
  {"id": "n06", "name": "By platform", "type": "n8n-nodes-base.switch",
   "typeVersion": 3.2, "position": [440, 0],
   "parameters": {"rules": {"values": [
     {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
       "conditions": [{"leftValue": "={{ $json.channel.platform }}", "rightValue": "telegram",
         "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
      "renameOutput": True, "outputKey": "telegram"},
     {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
       "conditions": [{"leftValue": "={{ $json.channel.platform }}", "rightValue": "vk",
         "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
      "renameOutput": True, "outputKey": "vk"},
     {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
       "conditions": [{"leftValue": "={{ $json.skip }}", "rightValue": True,
         "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
       "combinator": "and"},
      "renameOutput": True, "outputKey": "skip"},
   ]}, "options": {"fallbackOutput": "extra"}}},
  {"id": "n07", "name": "formatTG", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [660, -180], "parameters": {"jsCode": js_format_tg}},
  {"id": "n08", "name": "TG API", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [880, -180], "onError": "continueRegularOutput",
   "parameters": {"method": "POST", "url": "={{ $json.http.url }}", "sendBody": True,
     "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.http.body) }}", "options": {}}},
  {"id": "n09", "name": "tgResult", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [1100, -180], "parameters": {"jsCode": result_code('formatTG')}},
  {"id": "n10", "name": "formatVK", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [660, 0], "parameters": {"jsCode": js_format_vk}},
  {"id": "n22", "name": "VK: фото?", "type": "n8n-nodes-base.if", "typeVersion": 2.2,
   "position": [760, 0],
   "parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"leftValue": "={{ $json.photo_url }}",
       "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
     "combinator": "and"}}},
  # --- ветка с фото: upload-сервер → download → multipart → save → attach ---
  {"id": "n23", "name": "VK upload URL", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [880, 80], "onError": "continueRegularOutput",
   "parameters": {"method": "POST", "url": "https://api.vk.com/method/photos.getWallUploadServer",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": "={{ JSON.stringify({group_id: Number($('formatVK').first().json.vk.group_id), v: '5.199', access_token: $('formatVK').first().json.vk.token}) }}",
     "options": {}}},
  {"id": "n24", "name": "VK download photo", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [1060, 80], "onError": "continueRegularOutput",
   "parameters": {"method": "GET", "url": "={{ $('formatVK').first().json.photo_url }}",
     "options": {"response": {"response": {"responseFormat": "file", "outputPropertyName": "photo"}}}}},
  {"id": "n25", "name": "VK upload photo", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [1240, 80], "onError": "continueRegularOutput",
   "parameters": {"method": "POST", "url": "={{ $('VK upload URL').first().json.response.upload_url }}",
     "sendBody": True, "contentType": "multipart-form-data",
     "bodyParameters": {"parameters": [
       {"parameterType": "formBinaryData", "name": "photo", "inputDataFieldName": "photo"}]},
     "options": {}}},
  {"id": "n26", "name": "VK save photo", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [1420, 80], "onError": "continueRegularOutput",
   "parameters": {"method": "POST", "url": "https://api.vk.com/method/photos.saveWallPhoto",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": "={{ JSON.stringify({group_id: Number($('formatVK').first().json.vk.group_id), server: $json.server, photo: $json.photo, hash: $json.hash, v: '5.199', access_token: $('formatVK').first().json.vk.token}) }}",
     "options": {}}},
  {"id": "n27", "name": "VK attach", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [1600, 80], "parameters": {"jsCode": js_vk_attach}},
  {"id": "n11", "name": "VK API", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [880, -80], "onError": "continueRegularOutput",
   "parameters": {"method": "POST", "url": "={{ $json.http.url }}", "sendBody": True,
     "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.http.body) }}", "options": {}}},
  {"id": "n12", "name": "vkResult", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [1820, 0], "parameters": {"jsCode": result_code('formatVK')}},
  {"id": "n13", "name": "Skip: no channels", "type": "n8n-nodes-base.noOp",
   "typeVersion": 1, "position": [660, 180], "parameters": {}},
  {"id": "n19", "name": "Respond skipped", "type": "n8n-nodes-base.respondToWebhook",
   "typeVersion": 1.1, "position": [880, 180],
   "parameters": {"respondWith": "firstIncomingItem", "options": {"responseCode": 200}}},
  {"id": "n14", "name": "skippedResult", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [660, 340], "parameters": {"jsCode": js_skipped}},
  {"id": "n15", "name": "Merge results", "type": "n8n-nodes-base.merge",
   "typeVersion": 3, "position": [1320, 0], "parameters": {"mode": "append", "numberInputs": 3}},
  {"id": "n21", "name": "Quote for SQL", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [1430, 0], "parameters": {"jsCode": js_quote_sql}},
  {"id": "n16", "name": "Save channel results", "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [1540, 0],
   "credentials": {"postgres": {"id": "__CRED_DB_ID__", "name": "AgroPILOT PUB DB"}},
   "parameters": {"operation": "executeQuery", "query": sql_save_results, "options": {}}},
  {"id": "n17", "name": "Finalize post status", "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [1760, 0],
   "credentials": {"postgres": {"id": "__CRED_DB_ID__", "name": "AgroPILOT PUB DB"}},
   "parameters": {"operation": "executeQuery", "query": sql_finalize, "options": {}}},
  {"id": "n18", "name": "Final", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [1980, 0], "parameters": {"jsCode": js_final}},
  {"id": "n20", "name": "Respond final", "type": "n8n-nodes-base.respondToWebhook",
   "typeVersion": 1.1, "position": [2200, 0],
   "parameters": {"respondWith": "firstIncomingItem", "options": {"responseCode": 200}}},
]

core_connections = {
  "On call": {"main": [[{"node": "Prepare", "type": "main", "index": 0}]]},
  "Prepare": {"main": [[{"node": "Mark publishing & load post", "type": "main", "index": 0}]]},
  "Mark publishing & load post": {"main": [[{"node": "Load channels", "type": "main", "index": 0}]]},
  "Load channels": {"main": [[{"node": "Build jobs", "type": "main", "index": 0}]]},
  "Build jobs": {"main": [[{"node": "By platform", "type": "main", "index": 0}]]},
  "By platform": {"main": [
      [{"node": "formatTG", "type": "main", "index": 0}],
      [{"node": "formatVK", "type": "main", "index": 0}],
      [{"node": "Skip: no channels", "type": "main", "index": 0}],
      [{"node": "skippedResult", "type": "main", "index": 0}],
  ]},
  "formatTG": {"main": [[{"node": "TG API", "type": "main", "index": 0}]]},
  "TG API": {"main": [[{"node": "tgResult", "type": "main", "index": 0}]]},
  "tgResult": {"main": [[{"node": "Merge results", "type": "main", "index": 0}]]},
  "formatVK": {"main": [[{"node": "VK: фото?", "type": "main", "index": 0}]]},
  "VK: фото?": {"main": [
      [{"node": "VK API", "type": "main", "index": 0}],          # без фото — сразу wall.post
      [{"node": "VK upload URL", "type": "main", "index": 0}],   # с фото — цепочка
  ]},
  "VK upload URL": {"main": [[{"node": "VK download photo", "type": "main", "index": 0}]]},
  "VK download photo": {"main": [[{"node": "VK upload photo", "type": "main", "index": 0}]]},
  "VK upload photo": {"main": [[{"node": "VK save photo", "type": "main", "index": 0}]]},
  "VK save photo": {"main": [[{"node": "VK attach", "type": "main", "index": 0}]]},
  "VK attach": {"main": [[{"node": "VK API", "type": "main", "index": 0}]]},
  "VK API": {"main": [[{"node": "vkResult", "type": "main", "index": 0}]]},
  "vkResult": {"main": [[{"node": "Merge results", "type": "main", "index": 1}]]},
  "Skip: no channels": {"main": [[{"node": "Respond skipped", "type": "main", "index": 0}]]},
  "skippedResult": {"main": [[{"node": "Merge results", "type": "main", "index": 2}]]},
  "Merge results": {"main": [[{"node": "Quote for SQL", "type": "main", "index": 0}]]},
  "Quote for SQL": {"main": [[{"node": "Save channel results", "type": "main", "index": 0}]]},
  "Save channel results": {"main": [[{"node": "Finalize post status", "type": "main", "index": 0}]]},
  "Finalize post status": {"main": [[{"node": "Final", "type": "main", "index": 0}]]},
  "Final": {"main": [[{"node": "Respond final", "type": "main", "index": 0}]]},
}

core = {"name": "AgroPILOT PUB — publish-core (§46)", "nodes": core_nodes,
        "connections": core_connections, "settings": {"executionOrder": "v1"}}

# ---------- webhook workflow ----------

js_validate = r"""// Разбор тела webhook: ожидаем {"post_id": N}.
// Webhook-узел отдаёт {headers, body, ...} — тело в $json.body.
const raw = $input.first().json;
const b = (raw && raw.body && typeof raw.body === 'object') ? raw.body : raw;
const pid = Number(b.post_id);
const valid = Number.isInteger(pid) && pid > 0;
return [{ json: { post_id: pid, valid } }];
"""

sql_check_post = (
    "=SELECT {{ $json.post_id }}::bigint AS post_id,\n"
    "       EXISTS (SELECT 1 FROM pub_posts WHERE id = {{ $json.post_id }}) AS found"
)

js_summarize = r"""// Итог publish-core (HTTP-ответ) -> ГОТОВЫЙ ответ контракта {ok, data}.
// Ветку skip (data.skipped) IF ниже уводит на Mark failed.
const items = $input.all().map(i => i.json);
let out;
if (items.length === 0) {
  out = { ok: false, error: { code: 'not_found', message: 'post not found' } };
} else {
  const first = items[0];
  if (first.skip) {
    out = { ok: true, data: { post_id: first.post_id, skipped: true, reason: first.reason } };
  } else {
    out = { ok: true, data: {
      post_id: first.post_id, post_status: first.post_status,
      results: (first.results || []).map(r => ({
        channel_id: r.channel_id, status: r.status,
        platform_post_id: r.platform_post_id, error: r.error,
      })),
    } };
  }
}
return [{ json: out }];
"""

sql_mark_failed = (
    "=UPDATE pub_posts SET status = 'failed', last_error = 'no active pending channels',\n"
    "       updated_at = now()\n"
    "WHERE id = {{ $json.data.post_id }} RETURNING id AS post_id"
)

hook_nodes = [
  {"id": "w01", "name": "On publish", "type": "n8n-nodes-base.webhook",
   "typeVersion": 2, "position": [-660, 0], "webhookId": "pub-publish",
   "credentials": {"httpHeaderAuth": {"id": "__CRED_TOK_ID__", "name": "PUB webhook token"}},
   "parameters": {"httpMethod": "POST", "path": "pub-publish",
     "authentication": "headerAuth", "responseMode": "responseNode", "options": {}}},
  {"id": "w02", "name": "Validate", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [-440, 0], "parameters": {"jsCode": js_validate}},
  {"id": "w03", "name": "Valid?", "type": "n8n-nodes-base.if", "typeVersion": 2.2,
   "position": [-220, 0], "parameters": {"conditions": {"options": {"caseSensitive": True,
     "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"leftValue": "={{ $json.valid }}", "rightValue": True,
       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
     "combinator": "and"}}},
  {"id": "w04", "name": "Bad request 400", "type": "n8n-nodes-base.respondToWebhook",
   "typeVersion": 1.1, "position": [0, 180],
   "parameters": {"respondWith": "text",
     "responseBody": '{"ok":false,"error":{"code":"bad_request","message":"post_id (number) required in JSON body"}}',
     "options": {"responseCode": 400}}},
  {"id": "w05", "name": "Check post", "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [0, 0],
   "credentials": {"postgres": {"id": "__CRED_DB_ID__", "name": "AgroPILOT PUB DB"}},
   "parameters": {"operation": "executeQuery", "query": sql_check_post, "options": {}}},
  {"id": "w06", "name": "Found?", "type": "n8n-nodes-base.if", "typeVersion": 2.2,
   "position": [220, 0], "parameters": {"conditions": {"options": {"caseSensitive": True,
     "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"leftValue": "={{ $json.found }}", "rightValue": True,
       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
     "combinator": "and"}}},
  {"id": "w07", "name": "Not found 404", "type": "n8n-nodes-base.respondToWebhook",
   "typeVersion": 1.1, "position": [440, 180],
   "parameters": {"respondWith": "text",
     "responseBody": '{"ok":false,"error":{"code":"not_found","message":"post not found"}}',
     "options": {"responseCode": 404}}},
  {"id": "w08", "name": "Call publish-core", "type": "n8n-nodes-base.httpRequest",
   "typeVersion": 4.2, "position": [440, 0],
   "credentials": {"httpHeaderAuth": {"id": "__CRED_TOK_ID__", "name": "PUB webhook token"}},
   "parameters": {"method": "POST", "url": "http://127.0.0.1:5678/webhook/pub-core",
     "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
     "sendBody": True, "specifyBody": "json",
     "jsonBody": "={{ JSON.stringify({post_id: $json.post_id}) }}",
     "options": {"timeout": 120000}}},
  {"id": "w09", "name": "Summarize", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [660, 0], "parameters": {"jsCode": js_summarize}},
  {"id": "w10", "name": "Skipped?", "type": "n8n-nodes-base.if", "typeVersion": 2.2,
   "position": [880, 0], "parameters": {"conditions": {"options": {"caseSensitive": True,
     "leftValue": "", "typeValidation": "loose"},
     "conditions": [{"leftValue": "={{ $json.data && $json.data.skipped }}", "rightValue": True,
       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
     "combinator": "and"}}},
  {"id": "w11", "name": "Mark failed", "type": "n8n-nodes-base.postgres",
   "typeVersion": 2.5, "position": [1100, 180],
   "credentials": {"postgres": {"id": "__CRED_DB_ID__", "name": "AgroPILOT PUB DB"}},
   "parameters": {"operation": "executeQuery", "query": sql_mark_failed, "options": {}}},
  {"id": "w14", "name": "Skip payload", "type": "n8n-nodes-base.code",
   "typeVersion": 2, "position": [1320, 180],
   "parameters": {"jsCode": "return $('Summarize').all();"}},
  {"id": "w12", "name": "Skipped respond", "type": "n8n-nodes-base.respondToWebhook",
   "typeVersion": 1.1, "position": [1540, 180],
   "parameters": {"respondWith": "firstIncomingItem", "options": {"responseCode": 200}}},
  {"id": "w13", "name": "Respond", "type": "n8n-nodes-base.respondToWebhook",
   "typeVersion": 1.1, "position": [1100, 0],
   "parameters": {"respondWith": "firstIncomingItem", "options": {"responseCode": 200}}},
]

hook_connections = {
  "On publish": {"main": [[{"node": "Validate", "type": "main", "index": 0}]]},
  "Validate": {"main": [[{"node": "Valid?", "type": "main", "index": 0}]]},
  "Valid?": {"main": [
      [{"node": "Check post", "type": "main", "index": 0}],
      [{"node": "Bad request 400", "type": "main", "index": 0}],
  ]},
  "Check post": {"main": [[{"node": "Found?", "type": "main", "index": 0}]]},
  "Found?": {"main": [
      [{"node": "Call publish-core", "type": "main", "index": 0}],
      [{"node": "Not found 404", "type": "main", "index": 0}],
  ]},
  "Call publish-core": {"main": [[{"node": "Summarize", "type": "main", "index": 0}]]},
  "Summarize": {"main": [[{"node": "Skipped?", "type": "main", "index": 0}]]},
  "Skipped?": {"main": [
      [{"node": "Mark failed", "type": "main", "index": 0}],
      [{"node": "Respond", "type": "main", "index": 0}],
  ]},
  "Mark failed": {"main": [[{"node": "Skip payload", "type": "main", "index": 0}]]},
  "Skip payload": {"main": [[{"node": "Skipped respond", "type": "main", "index": 0}]]},
}

hook = {"name": "AgroPILOT PUB — publish webhook (§46)", "nodes": hook_nodes,
        "connections": hook_connections, "settings": {"executionOrder": "v1"}}

os.makedirs(OUT, exist_ok=True)
for fname, data in [("pub-publish-core.workflow.json", core),
                    ("pub-publish-webhook.workflow.json", hook)]:
    path = os.path.join(OUT, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("written", path)
