// js/app.pub.js -- §46: раздел «Публикации» (кросспостинг), фаза Ф2
//
// Подмешивается в appObjects() в конце js/app.objects.js (APP_PUB_MIXIN,
// паттерн APP_CATALOGS_MIXIN из §45). Ф2 — вкладка «Каналы»: карточки
// реестра pub_channels (тумблер active/frozen, значок токена), drawer-форма
// добавления/правки с полями по платформе и блоком шаблона форматирования.
// Ф3 добавит вкладки «Редактор» (нативные превью) и «Список публикаций».
// Права: чтение — все вошедшие; мутации — admin (role_key, сервер дублирует).

(function () {
  'use strict';

  window.APP_PUB_MIXIN = function () {
    return {

      // ---- состояние раздела «Публикации» (§46) ----
      pubState: {
        tab: 'channels',            // 'channels' | 'editor' | 'list'
        channels: [], loaded: false, loading: false, err: null,
        drawer: {                   // форма добавления/правки (паттерн §45.7)
          open: false, mode: 'create', id: null,
          form: {}, err: null, saving: false,
        },
        posts: [], postsLoading: false,
        editor: {                   // Ф3: редактор публикации
          open: false, id: null,          // id поста при правке
          body_md: '', media: [],         // [{type:'photo', url}]
          sel: new Set(),                 // channel_id выбранных
          overrides: {},                  // channel_id -> текст
          previewTab: null,               // channel_id активного превью
          scheduled: '',                  // Ф4: datetime-local запланированного
          err: null, busy: false,
        },
      },

      pubCanEdit() {
        const uid = this.currentUserId();
        const u = (this.M.team || []).find(t => String(t.id) === String(uid));
        return !!(u && u.role_key === 'admin');
      },
      pubCanPublish() {
        const uid = this.currentUserId();
        const u = (this.M.team || []).find(t => String(t.id) === String(uid));
        return !!(u && (u.role_key === 'admin' || u.role_key === 'manager'));
      },

      // ---- загрузка ----
      async pubInit() {
        const st = this.pubState;
        if (st.loaded || st.loading) return;
        if (!window.AGL || !AGL.token) { st.err = 'Раздел работает после входа в API'; return; }
        st.loading = true;
        try {
          st.channels = await AGL.pubChannels();
          st.loaded = true; st.err = null;
        } catch (e) {
          st.err = (e && e.message) || 'Не удалось загрузить каналы';
        } finally {
          st.loading = false;
          this.render();
        }
      },
      async pubReload() {
        const st = this.pubState;
        st.loaded = false;
        await this.pubInit();
      },

      pubPlatMeta() {
        return {
          telegram: { label: 'Telegram', ico: '📨', targetLabel: 'chat_id канала (-100… или @username)', tokenLabel: 'Токен бота (BotFather)', hint: 'Бот должен быть админом канала' },
          vk:       { label: 'ВКонтакте', ico: '🅥', targetLabel: 'owner_id сообщества (со знаком −, напр. -12345678)', tokenLabel: 'Токен сообщества (Управление → Работа с API)', hint: 'Права wall, photos' },
          dzen:     { label: 'Дзен', ico: '∞', targetLabel: 'chat_id relay-канала Telegram (бот Дзена — админ)', tokenLabel: 'Токен бота relay-канала', hint: 'Публикация через официального бота Дзена (Ф5)' },
          instagram:{ label: 'Instagram', ico: '📸', targetLabel: '—', tokenLabel: '—', hint: 'Подключается в Ф6: нужен бизнес-аккаунт + Facebook Page' },
        };
      },

      // ---- форма (drawer) ----
      pubOpenCreate() {
        const f = { platform: 'telegram', name: '', target: '', token: '',
                    sort_order: 0, max_len: '', hashtags: 'keep', tpl_extra: '' };
        this.pubState.drawer = { open: true, mode: 'create', id: null, form: f, err: null, saving: false };
        this.render();
      },
      pubOpenEdit(ch) {
        const t = ch.template || {};
        const f = { platform: ch.platform, name: ch.name, target: ch.target || '', token: '',
                    sort_order: ch.sort_order || 0,
                    max_len: (t.max_len != null ? String(t.max_len) : ''),
                    hashtags: t.hashtags || 'keep',
                    tpl_extra: Object.keys(t).filter(k => !['max_len', 'hashtags'].includes(k)).length
                      ? JSON.stringify(Object.fromEntries(Object.entries(t).filter(([k]) => !['max_len', 'hashtags'].includes(k))), null, 1) : '' };
        this.pubState.drawer = { open: true, mode: 'edit', id: ch.id, form: f, err: null, saving: false };
        this.render();
      },
      pubCloseDrawer() {
        this.pubState.drawer.open = false;
        this.render();
      },
      async pubSave() {
        const d = this.pubState.drawer, f = d.form;
        d.err = null;
        const template = {};
        if (f.max_len !== '') {
          const n = Number(f.max_len);
          if (!Number.isInteger(n) || n < 100 || n > 4096) { d.err = 'max_len: целое 100..4096 или пусто'; this.render(); return; }
          template.max_len = n;
        }
        template.hashtags = f.hashtags || 'keep';
        if (f.tpl_extra && f.tpl_extra.trim()) {
          try { Object.assign(template, JSON.parse(f.tpl_extra)); }
          catch (e) { d.err = 'Дополнительно (JSON): некорректный JSON'; this.render(); return; }
        }
        const payload = { name: f.name.trim(), target: String(f.target).trim(),
                          sort_order: Number(f.sort_order) || 0, template };
        if (d.mode === 'create') {
          payload.platform = f.platform;
          payload.token = f.token.trim();
        } else if (f.token.trim()) {
          payload.token = f.token.trim();
        }
        d.saving = true; this.render();
        try {
          if (d.mode === 'create') await AGL.pubChannelCreate(payload);
          else await AGL.pubChannelUpdate(d.id, payload);
          this.toast('Канал сохранён');
          d.open = false;
          await this.pubReload();
        } catch (e) {
          d.err = (e && (e.error && e.error.message || e.message)) || 'Ошибка сохранения';
        } finally {
          d.saving = false;
          this.render();
        }
      },
      async pubToggle(ch) {
        const to = ch.status === 'active' ? 'frozen' : 'active';
        try {
          await AGL.pubChannelUpdate(ch.id, { status: to });
          this.toast(to === 'frozen' ? 'Канал заморожен' : 'Канал активен');
          await this.pubReload();
        } catch (e) {
          this.toast(((e && e.error && e.error.message) || 'Не удалось изменить статус'), 'err');
        }
      },

      // ---- view раздела ----
      vPub() {
        const st = this.pubState;
        this.pubInit();
        const tabs = `
          <div class="flex gap-2 mb-4 flex-wrap">
            <button class="btn ${st.tab === 'channels' ? 'btn-accent' : ''}" data-pub-tab="channels">Каналы</button>
            <button class="btn ${st.tab === 'editor' ? 'btn-accent' : ''}" data-pub-tab="editor">✍️ Редактор</button>
            <button class="btn ${st.tab === 'list' ? 'btn-accent' : ''}" data-pub-tab="list">📚 Список публикаций</button>
            <span class="btn" style="opacity:.45;cursor:default" title="Ф4">🕓 Отложка (Ф4)</span>
          </div>`;
        let body = '';
        if (st.tab === 'channels') body = this.vPubChannels();
        else if (st.tab === 'editor') body = this.vPubEditor();
        else if (st.tab === 'list') body = this.vPubPostsList();
        return `
        <div class="mb-4 flex items-center justify-between flex-wrap gap-2">
          <div>
            <div class="text-2xl font-semibold">Публикации</div>
            <div class="text-sm" style="color:var(--text-mute)">Кросспостинг: одна публикация → все каналы, формат под каждую платформу (§46)</div>
          </div>
          ${this.pubCanEdit() && st.tab === 'channels' ? '<button class="btn btn-accent" data-pub-add>+ Добавить канал</button>' : ''}
        </div>
        ${tabs}
        ${body}
        ${this.vPubDrawer()}`;
      },

      vPubChannels() {
        const st = this.pubState;
        if (st.loading && !st.loaded) {
          return '<div class="card p-6 text-center" style="color:var(--text-mute)">Загрузка каналов…</div>';
        }
        if (st.err) {
          return `<div class="card p-6 text-center"><div style="color:var(--err)">${this.esc(st.err)}</div>
            <button class="btn mt-3" data-pub-retry>Повторить</button></div>`;
        }
        const list = st.channels || [];
        if (!list.length) {
          return `<div class="card p-8 text-center" style="color:var(--text-mute)">
            <div class="text-lg mb-2">Каналов пока нет</div>
            <div class="text-sm mb-4">Добавьте Telegram-канал или группу ВК — движок публикаций (n8n) подхватит их без перенастройки.</div>
            ${this.pubCanEdit() ? '<button class="btn btn-accent" data-pub-add>+ Добавить канал</button>' : ''}
          </div>`;
        }
        const canEdit = this.pubCanEdit();
        const meta = this.pubPlatMeta();
        const cards = list.map(ch => {
          const m = meta[ch.platform] || { label: ch.platform, ico: '❔', targetLabel: 'target', tokenLabel: '', hint: '' };
          const frozen = ch.status === 'frozen';
          const tok = ch.has_token
            ? '<span class="pill text-[11px]" style="background:var(--ok-soft,#e6f4ea);color:#1a7f37">🔑 токен есть</span>'
            : '<span class="pill text-[11px]" style="background:var(--warn-soft,#fff4e0);color:#a15c00">⚠ нет токена</span>';
          const tgl = canEdit ? `
            <button class="btn ${frozen ? '' : 'btn-accent'}" data-pub-toggle="${ch.id}"
                    title="${frozen ? 'Разморозить' : 'Заморозить: канал не публикуется, история остаётся'}">
              ${frozen ? '❄️ Заморожен — разморозить' : '🟢 Активен — заморозить'}
            </button>` : `<span class="pill text-[11px]">${frozen ? '❄️ заморожен' : '🟢 активен'}</span>`;
          const tpl = ch.template || {};
          const tplBits = [
            tpl.max_len ? 'лимит ' + this.esc(String(tpl.max_len)) : '',
            tpl.hashtags ? 'хэштеги: ' + this.esc(tpl.hashtags) : '',
          ].filter(Boolean).join(' · ');
          return `
          <div class="card p-4 mb-3" style="${frozen ? 'opacity:.65' : ''}">
            <div class="flex items-start justify-between gap-3 flex-wrap">
              <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-lg">${m.ico}</span>
                  <span class="font-semibold">${this.esc(ch.name)}</span>
                  <span class="pill text-[11px]">${this.esc(m.label)}</span>
                  ${tok}
                </div>
                <div class="text-sm mt-1" style="color:var(--text-mute)">
                  ${this.esc(ch.platform === 'vk' ? 'Сообщество ' : 'Канал ')}<code>${this.esc(ch.target || '—')}</code>
                </div>
                ${tplBits ? `<div class="text-[12px] mt-1" style="color:var(--text-mute)">Шаблон: ${tplBits}</div>` : ''}
                ${m.hint ? `<div class="text-[11px] mt-1" style="color:var(--text-dim)">${this.esc(m.hint)}</div>` : ''}
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                ${tgl}
                ${canEdit ? `<button class="btn" data-pub-edit="${ch.id}">✏️ Изменить</button>` : ''}
              </div>
            </div>
          </div>`;
        }).join('');
        return cards;
      },

      vPubDrawer() {
        const d = this.pubState.drawer;
        if (!d.open) return '';
        const f = d.form, meta = this.pubPlatMeta(), m = meta[f.platform] || meta.telegram;
        const isEdit = d.mode === 'edit';
        const inp = 'class="input"';
        return `
        <div class="nsi-drawer-mask" data-pub-close></div>
        <div class="nsi-drawer">
          <div class="flex items-center justify-between p-4" style="border-bottom:1px solid var(--border)">
            <div class="font-semibold">${isEdit ? 'Канал публикаций' : 'Новый канал'}</div>
            <button class="btn" data-pub-close>✕</button>
          </div>
          <div class="p-4 flex-1" style="overflow:auto">
            <div class="label mb-1">Платформа</div>
            <select ${inp} data-pub-f="platform" ${isEdit ? 'disabled' : ''}>
              ${['telegram', 'vk', 'dzen'].map(p => `<option value="${p}" ${f.platform === p ? 'selected' : ''}>${meta[p].ico} ${meta[p].label}</option>`).join('')}
              <option disabled ${f.platform === 'instagram' ? 'selected' : ''}>${meta.instagram.ico} ${meta.instagram.label} (Ф6)</option>
            </select>
            ${isEdit ? '' : `<div class="text-[11px] mt-1" style="color:var(--text-dim)">${this.esc(m.hint)}</div>`}

            <div class="label mt-3 mb-1">Название</div>
            <input ${inp} data-pub-f="name" value="${this.esc(f.name)}" placeholder="TG — основной / VK — компания">

            <div class="label mt-3 mb-1">${this.esc(m.targetLabel)}</div>
            <input ${inp} data-pub-f="target" value="${this.esc(f.target)}" placeholder="${f.platform === 'vk' ? '-12345678' : '@channel или -1001234567890'}">

            <div class="label mt-3 mb-1">${isEdit ? 'Новый токен (пусто = не менять)' : this.esc(m.tokenLabel)}</div>
            <input ${inp} type="password" data-pub-f="token" value="${this.esc(f.token)}" placeholder="${isEdit ? '••••••••' : 'вставьте токен'}" autocomplete="new-password">

            <div class="label mt-4 mb-1">Шаблон форматирования</div>
            <div class="text-[11px] mb-2" style="color:var(--text-dim)">Как движок адаптирует текст под эту платформу (§46.3)</div>
            <div class="flex gap-2">
              <div class="flex-1">
                <div class="label mb-1">Лимит текста</div>
                <input ${inp} data-pub-f="max_len" value="${this.esc(f.max_len)}" placeholder="по умолчанию платформы">
              </div>
              <div class="flex-1">
                <div class="label mb-1">Хэштеги</div>
                <select ${inp} data-pub-f="hashtags">
                  ${['keep', 'append', 'strip'].map(h => `<option value="${h}" ${f.hashtags === h ? 'selected' : ''}>${h === 'keep' ? 'оставлять' : h === 'append' ? 'добавлять' : 'убирать'}</option>`).join('')}
                </select>
              </div>
            </div>
            <div class="label mt-2 mb-1">Дополнительно (JSON)</div>
            <textarea ${inp} rows="3" data-pub-f="tpl_extra" placeholder='{"llm_prompt": "перепиши короче"}'>${this.esc(f.tpl_extra)}</textarea>

            <div class="label mt-3 mb-1">Порядок в списке</div>
            <input ${inp} type="number" data-pub-f="sort_order" value="${this.esc(String(f.sort_order))}">

            ${d.err ? `<div class="mt-3 text-sm" style="color:var(--err)">${this.esc(d.err)}</div>` : ''}
          </div>
          <div class="p-4 flex gap-2" style="border-top:1px solid var(--border)">
            <button class="btn btn-accent flex-1" data-pub-save ${d.saving ? 'disabled' : ''}>${d.saving ? 'Сохранение…' : 'Сохранить'}</button>
            <button class="btn" data-pub-close>Отмена</button>
          </div>
        </div>`;
      },

      // =================================================================
      // Ф3: форматтеры (дубль Code-узлов n8n §46.3 — править синхронно!)
      // =================================================================
      pubEscHtml(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      },
      pubFmtTg(md) {
        let h = this.pubEscHtml(md);
        h = h.replace(/\*\*(.+?)\*\*/gs, '<b>$1</b>');
        h = h.replace(/(^|\s)\*(?!\s)(.+?)\*(?=\s|$)/gs, '$1<i>$2</i>');
        h = h.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" style="color:#5aa9e6">$1</a>');
        return h.length > 4096 ? h.slice(0, 4090) + '\n…' : h;
      },
      pubFmtVk(md) {
        let t = String(md || '')
          .replace(/\*\*(.+?)\*\*/gs, '$1')
          .replace(/(^|\s)\*(?!\s)(.+?)\*(?=\s|$)/gs, '$1$2')
          .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '$1 ($2)');
        return t.length > 4096 ? t.slice(0, 4090) + '\n…' : t;
      },
      pubFmtDzen(md) {
        const s = String(md || '');
        const nl = s.indexOf('\n');
        const title = (nl > 0 ? s.slice(0, nl) : s).replace(/^#+\s*/, '').slice(0, 120);
        return { title, body: nl > 0 ? s.slice(nl + 1) : '' };
      },
      pubPreviewText(ch) {
        const ed = this.pubState.editor;
        return ed.overrides[ch.id] != null && ed.overrides[ch.id] !== ''
          ? ed.overrides[ch.id] : ed.body_md;
      },

      // ---- мокапы превью (нативные карточки платформ) ----
      pubPreviewHtml(ch) {
        const meta = this.pubPlatMeta();
        const ed = this.pubState.editor;
        const photo = (ed.media || [])[0];
        const ph = photo
          ? `<div style="border-radius:8px 8px 0 0;background:#2a3b4d url('${this.esc(photo.url)}') center/cover;height:150px"></div>` : '';
        const time = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        if (ch.platform === 'telegram') {
          return `
          <div style="background:#0e1621;border-radius:12px;padding:14px;max-width:360px">
            <div style="background:#182533;border-radius:10px;overflow:hidden;color:#e8edf2;font-size:13.5px;line-height:1.45">
              ${ph}
              <div style="padding:10px 12px">
                <div style="color:#6ab3f3;font-weight:600;font-size:13px">${this.esc(ch.name)}</div>
                <div style="margin-top:2px">${this.pubFmtTg(this.pubPreviewText(ch))}</div>
                <div style="color:#7f91a4;font-size:11px;text-align:right">${time} ✓✓</div>
              </div>
            </div>
          </div>`;
        }
        if (ch.platform === 'vk') {
          const initial = (ch.name || '?').trim().charAt(0).toUpperCase();
          return `
          <div style="background:#fff;border:1px solid #e7e8ec;border-radius:12px;padding:12px;max-width:360px;color:#000;font-size:13.5px">
            <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px">
              <div style="width:36px;height:36px;border-radius:50%;background:#0077ff;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700">${this.esc(initial)}</div>
              <div><div style="font-weight:600">${this.esc(ch.name)}</div>
                   <div style="color:#99a2ad;font-size:12px">только что</div></div>
            </div>
            ${photo ? `<div style="border-radius:8px;background:#f0f2f5 url('${this.esc(photo.url)}') center/cover;height:160px;margin:8px 0"></div>` : ''}
            <div style="white-space:pre-wrap;line-height:1.45">${this.pubEscHtml(this.pubFmtVk(this.pubPreviewText(ch)))}</div>
            <div style="display:flex;gap:18px;color:#99a2ad;font-size:20px;margin-top:10px;border-top:1px solid #e7e8ec;padding-top:8px">❤ 💬 ↻</div>
          </div>`;
        }
        if (ch.platform === 'dzen') {
          const d = this.pubFmtDzen(this.pubPreviewText(ch));
          return `
          <div style="background:#fff;border:1px solid #e5e5e5;border-radius:12px;padding:14px;max-width:360px;color:#000">
            ${photo ? `<div style="border-radius:8px;background:#eee url('${this.esc(photo.url)}') center/cover;height:120px;margin-bottom:10px"></div>` : ''}
            <div style="font-size:17px;font-weight:700;line-height:1.3">${this.esc(d.title || 'Заголовок (первая строка)')}</div>
            <div style="font-size:13.5px;color:#555;margin-top:8px;max-height:150px;overflow:hidden;white-space:pre-wrap">${this.pubEscHtml(d.body)}</div>
            <div style="color:#999;font-size:12px;margin-top:10px">${this.esc(ch.name)} · Дзен</div>
          </div>`;
        }
        // instagram (Ф6) — карточка-заглушка
        return `
        <div style="background:#fff;border:1px solid #dbdbdb;border-radius:12px;max-width:360px;color:#000">
          <div style="display:flex;gap:8px;align-items:center;padding:10px 12px">
            <div style="width:30px;height:30px;border-radius:50%;background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888)"></div>
            <b style="font-size:13px">${this.esc(ch.name)}</b>
          </div>
          <div style="background:repeating-linear-gradient(45deg,#fafafa,#fafafa 12px,#f0f0f0 12px,#f0f0f0 24px);height:200px;display:flex;align-items:center;justify-content:center;color:#a5a5a5;font-size:13px">📸 подключение в Ф6</div>
          <div style="padding:8px 12px;font-size:12px;color:#8e8e8e">${this.pubEscHtml(meta.instagram.hint)}</div>
        </div>`;
      },

      // ---- редактор ----
      pubOpenEditor(post) {
        this.pubState.tab = 'editor';
        const ed = this.pubState.editor;
        ed.err = null; ed.busy = false;
        if (post) {
          ed.id = post.id;
          ed.body_md = post.body_md || '';
          ed.media = (post.media || []).slice();
          ed.sel = new Set((post.channels || []).map(c => c.channel_id));
          ed.overrides = {};
          (post.channels || []).forEach(c => { if (c.body_override) ed.overrides[c.channel_id] = c.body_override; });
          ed.previewTab = ((post.channels || [])[0] || {}).channel_id || null;
          ed.scheduled = this._pubIsoToLocal(post.scheduled_at);
        } else {
          ed.id = null; ed.body_md = ''; ed.media = []; ed.sel = new Set(); ed.overrides = {};
          ed.previewTab = null; ed.scheduled = '';
        }
        this.render();
      },
      pubEditorCount() {
        const ed = this.pubState.editor;
        const ch = [...ed.sel].length ? [...ed.sel][0] : null;
        const v = ed.body_md || '';
        return `${v.length} симв.`;
      },
      async pubEditorUpload(input) {
        const ed = this.pubState.editor;
        const file = input.files && input.files[0];
        if (!file) return;
        ed.busy = true; this.render();
        try {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('kind', 'other');
          fd.append('title', 'pub_' + file.name);
          const res = await AGL.uploadArtifact(fd);
          const d = (res && res.data) || res;
          if (!d || !d.blob_uri) throw new Error('upload: нет blob_uri');
          ed.media.push({ type: 'photo', url: d.blob_uri });
          this.toast('Фото добавлено');
        } catch (e) {
          this.toast('Загрузка не удалась: ' + (e.message || ''), 'err');
        } finally {
          ed.busy = false;
          this.render();
        }
      },
      pubEditorRemoveMedia(i) {
        this.pubState.editor.media.splice(i, 1);
        this.render();
      },
      pubEditorToggle(ch) {
        const ed = this.pubState.editor;
        if (ed.sel.has(ch.id)) { ed.sel.delete(ch.id); if (ed.previewTab === ch.id) ed.previewTab = null; }
        else { ed.sel.add(ch.id); if (!ed.previewTab) ed.previewTab = ch.id; }
        this.render();
      },
      _pubIsoToLocal(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d)) return '';
        const pad = n => String(n).padStart(2, '0');
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
             + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
      },
      async pubEditorSchedule() {
        const ed = this.pubState.editor;
        if (!(ed.body_md || '').trim()) { ed.err = 'Текст публикации обязателен'; this.render(); return; }
        if (!ed.sel.size) { ed.err = 'Выберите хотя бы один канал'; this.render(); return; }
        if (!ed.scheduled) { ed.err = 'Укажите время публикации'; this.render(); return; }
        const when = new Date(ed.scheduled);
        if (!(when > new Date())) { ed.err = 'Время должно быть в будущем'; this.render(); return; }
        ed.busy = true; this.render();
        try {
          const payload = this._pubEditorPayload();
          payload.scheduled_at = when.toISOString();
          if (ed.id) await AGL.pubPostUpdate(ed.id, payload);
          else ed.id = ((await AGL.pubPostCreate(payload)).data || {}).id;
          this.toast('Запланировано на ' + when.toLocaleString('ru-RU'));
          await this.pubLoadPosts();
        } catch (e) {
          ed.err = (e && (e.error && e.error.message || e.message)) || 'Ошибка планирования';
          this.toast(ed.err, 'err');
        } finally {
          ed.busy = false;
          this.render();
        }
      },
      _pubEditorPayload() {
        const ed = this.pubState.editor;
        const overrides = {};
        Object.entries(ed.overrides).forEach(([k, v]) => { if (v && v.trim()) overrides[k] = v.trim(); });
        return {
          body_md: ed.body_md,
          media: ed.media,
          channel_ids: [...ed.sel],
          overrides,
        };
      },
      async pubEditorSave() {
        const ed = this.pubState.editor;
        if (!(ed.body_md || '').trim()) { ed.err = 'Текст публикации обязателен'; this.render(); return; }
        if (!ed.sel.size) { ed.err = 'Выберите хотя бы один канал'; this.render(); return; }
        ed.busy = true; this.render();
        try {
          const payload = this._pubEditorPayload();
          if (ed.id) await AGL.pubPostUpdate(ed.id, payload);
          else ed.id = ((await AGL.pubPostCreate(payload)).data || {}).id;
          this.toast('Черновик сохранён');
          await this.pubLoadPosts();
        } catch (e) {
          ed.err = (e && (e.error && e.error.message || e.message)) || 'Ошибка сохранения';
        } finally {
          ed.busy = false;
          this.render();
        }
      },
      async pubEditorPublish() {
        const ed = this.pubState.editor;
        if (!(ed.body_md || '').trim()) { ed.err = 'Текст публикации обязателен'; this.render(); return; }
        if (!ed.sel.size) { ed.err = 'Выберите хотя бы один канал'; this.render(); return; }
        ed.busy = true; this.render();
        try {
          const payload = this._pubEditorPayload();
          let id = ed.id;
          if (id) await AGL.pubPostUpdate(id, payload);
          else id = ((await AGL.pubPostCreate(payload)).data || {}).id;
          const res = await AGL.pubPostPublish(id);
          ed.id = id;
          await this.pubLoadPosts();
          const d = (res && res.data) || {};
          if (d.skipped) this.toast('Нет активных каналов: ' + (d.reason || ''), 'err');
          else {
            const okN = (d.results || []).filter(r => r.status === 'ok').length;
            this.toast(`Опубликовано: ${okN}/${(d.results || []).length} каналов (${d.post_status})`,
                       d.post_status === 'done' ? 'ok' : 'info');
          }
        } catch (e) {
          ed.err = (e && (e.error && e.error.message || e.message)) || 'Ошибка публикации';
          this.toast(ed.err, 'err');
        } finally {
          ed.busy = false;
          this.render();
        }
      },
      vPubEditor() {
        const st = this.pubState, ed = st.editor;
        const canPub = this.pubCanPublish();
        const chans = (st.channels || []).filter(c => c.status === 'active');
        const sel = [...ed.sel];
        const activeCh = sel.map(id => chans.find(c => c.id === id)).filter(Boolean);
        const tab = ed.previewTab != null && activeCh.some(c => c.id === ed.previewTab)
          ? ed.previewTab : (activeCh[0] || {}).id ?? null;
        const curCh = activeCh.find(c => c.id === tab) || null;
        ed._curCh = curCh; // для live-обновления превью без полного render()
        const inp = 'class="input"';
        const chBoxes = chans.length ? chans.map(ch => {
          const on = ed.sel.has(ch.id);
          const meta = this.pubPlatMeta()[ch.platform] || { ico: '❔', label: ch.platform };
          return `<label class="card" style="display:flex;gap:8px;align-items:center;padding:8px 10px;margin-bottom:6px;cursor:pointer;${on ? 'border-color:var(--accent)' : ''}">
            <input type="checkbox" data-pub-ch="${ch.id}" ${on ? 'checked' : ''}>
            <span>${meta.ico}</span><span style="font-size:13px">${this.esc(ch.name)}</span>
            ${ch.has_token ? '' : '<span class="pill text-[10px]" style="background:#fff4e0;color:#a15c00">нет токена</span>'}
          </label>`;
        }).join('') : '<div class="text-sm" style="color:var(--text-mute)">Нет активных каналов — добавьте во вкладке «Каналы»</div>';
        return `
        <div class="flex gap-4 flex-wrap" style="align-items:flex-start">
          <div style="flex:1 1 380px;min-width:340px">
            <div class="card p-4">
              <div class="flex items-center justify-between mb-2">
                <div class="font-semibold">${ed.id ? 'Публикация #' + ed.id : 'Новая публикация'}</div>
                <span class="text-[12px]" style="color:var(--text-mute)">${this.pubEditorCount()}</span>
              </div>
              <textarea ${inp} rows="10" data-pub-ed-body placeholder="Текст (markdown-lite: **жирный**, *курсив*, [ссылка](url); первая строка = заголовок Дзена)">${this.esc(ed.body_md)}</textarea>
              <div class="flex gap-2 items-center mt-2 flex-wrap">
                <label class="btn" style="cursor:pointer">📷 Фото<input type="file" accept="image/*" data-pub-ed-photo hidden></label>
                ${(ed.media || []).map((m, i) => `
                  <span style="display:inline-flex;gap:6px;align-items:center;border:1px solid var(--border);border-radius:6px;padding:2px 6px;font-size:12px">
                    🖼 ${this.esc((m.url || '').split('/').pop().slice(0, 18))}
                    <a href="#" data-pub-ed-rmphoto="${i}" style="color:var(--err)">✕</a>
                  </span>`).join('')}
              </div>
              ${ed.err ? `<div class="mt-2 text-sm" style="color:var(--err)">${this.esc(ed.err)}</div>` : ''}
              <div class="flex items-center gap-2 mt-3 flex-wrap">
                <input type="datetime-local" ${inp} style="width:auto" data-pub-ed-when value="${this.esc(ed.scheduled)}">
                <button class="btn" data-pub-ed-sched ${ed.busy || !canPub ? 'disabled' : ''} title="Опубликовать в заданное время (scheduler каждые 5 минут)">⏱ Запланировать</button>
              </div>
              <div class="flex gap-2 mt-2 flex-wrap">
                <button class="btn" data-pub-ed-save ${ed.busy || !canPub ? 'disabled' : ''}>💾 Черновик</button>
                <button class="btn btn-accent" data-pub-ed-pub ${ed.busy || !canPub ? 'disabled' : ''}>🚀 Опубликовать сейчас</button>
                ${ed.id ? '<button class="btn" data-pub-ed-new>✨ Новый</button>' : ''}
              </div>
            </div>
            <div class="card p-4 mt-3">
              <div class="font-semibold mb-2">Каналы публикации</div>
              ${chBoxes}
            </div>
          </div>
          <div style="flex:1 1 380px;min-width:340px">
            <div class="card p-4">
              <div class="flex gap-2 mb-3 flex-wrap">
                ${activeCh.length ? activeCh.map(ch => `
                  <button class="btn ${tab === ch.id ? 'btn-accent' : ''}" data-pub-prev-tab="${ch.id}"
                          title="${this.esc(ch.name)}">${(this.pubPlatMeta()[ch.platform] || { ico: '❔' }).ico} ${this.esc(ch.name)}</button>`).join('')
                  : '<span class="text-sm" style="color:var(--text-mute)">Выберите каналы — появится нативное превью</span>'}
              </div>
              ${curCh ? `<div id="pubPreviewBox">${this.pubPreviewHtml(curCh)}</div>` : ''}
              ${curCh ? `
                <div class="label mt-3 mb-1">Переопределить текст для «${this.esc(curCh.name)}»</div>
                <textarea ${inp} rows="3" data-pub-ed-override="${curCh.id}"
                  placeholder="Пусто — автоформат по шаблону канала">${this.esc(ed.overrides[curCh.id] || '')}</textarea>
                <div class="text-[11px] mt-1" style="color:var(--text-dim)">Опубликуется этот текст вместо основного, только в этом канале</div>` : ''}
            </div>
          </div>
        </div>`;
      },

      // ---- список публикаций ----
      async pubLoadPosts() {
        const st = this.pubState;
        st.postsLoading = true;
        try {
          st.posts = await AGL.pubPosts();
        } catch (e) {
          st.posts = [];
        } finally {
          st.postsLoading = false;
          if (st.tab === 'list') this.render();
        }
      },
      _pubStatusPill(s) {
        const map = {
          draft:    ['черновик', '#eef1f4', '#5a6b7b'],
          scheduled:['⏱ запланирован', '#e8f0fe', '#1a56c4'],
          publishing:['публикуется…', '#fff4e0', '#a15c00'],
          done:     ['✓ опубликован', '#e6f4ea', '#1a7f37'],
          partial:  ['⚠ частично', '#fff4e0', '#a15c00'],
          failed:   ['✗ ошибка', '#fde8e8', '#b3261e'],
        };
        const m = map[s] || [s, '#eef1f4', '#5a6b7b'];
        return `<span class="pill text-[11px]" style="background:${m[1]};color:${m[2]}">${m[0]}</span>`;
      },
      vPubPostsList() {
        const st = this.pubState;
        this.pubLoadPosts();
        if (st.postsLoading && !st.posts.length) {
          return '<div class="card p-6 text-center" style="color:var(--text-mute)">Загрузка…</div>';
        }
        if (!st.posts.length) {
          return `<div class="card p-8 text-center" style="color:var(--text-mute)">
            <div class="text-lg mb-2">Публикаций пока нет</div>
            <button class="btn btn-accent" data-pub-new>✍️ Написать публикацию</button>
          </div>`;
        }
        const canPub = this.pubCanPublish();
        const rows = st.posts.map(p => {
          const chans = (p.channels || []).map(c => {
            const st = { ok: '✅', failed: '❌', pending: '⏳', skipped: '⏭', publishing: '⏳' }[c.status] || '•';
            const meta = this.pubPlatMeta()[c.platform] || { ico: '' };
            return `<span class="pill text-[11px]" title="${this.esc(c.error || c.status)}">${meta.ico} ${st}</span>`;
          }).join(' ');
          const retry = canPub && ['failed', 'partial'].includes(p.status)
            ? `<button class="btn" data-pub-republish="${p.id}" title="Повторить публикацию упавших каналов">↻ Повторить</button>` : '';
          const unsched = canPub && p.status === 'scheduled'
            ? `<button class="btn" data-pub-unsched="${p.id}" title="Вернуть в черновики">⏱ Снять</button>` : '';
          const del = canPub && p.status === 'draft'
            ? `<button class="btn" data-pub-del="${p.id}" title="Удалить черновик">🗑</button>` : '';
          return `
          <div class="card p-3 mb-2 flex items-center gap-3 flex-wrap">
            <div class="flex-1 min-width-200" style="min-width:220px">
              <div class="text-sm" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:520px">${this.esc((p.body_md || '').replace(/\n/g, ' ').slice(0, 90))}</div>
              <div class="text-[11px] mt-1" style="color:var(--text-mute)">
                ${this.esc((p.created_at || '').replace('T', ' ').slice(0, 16))} · ${(p.media || []).length} 📷
                ${p.scheduled_at ? ' · ⏱ ' + this.esc(p.scheduled_at.replace('T', ' ').slice(0, 16)) : ''}
              </div>
            </div>
            <div>${chans}</div>
            ${this._pubStatusPill(p.status)}
            <div class="flex gap-2">
              <button class="btn" data-pub-open="${p.id}">Открыть</button>
              ${retry}${unsched}${del}
            </div>
            ${p.last_error ? `<div class="text-[11px] w-full" style="color:var(--err)">${this.esc(p.last_error)}</div>` : ''}
          </div>`;
        }).join('');
        return `
        <div class="flex justify-end mb-2"><button class="btn btn-accent" data-pub-new>✍️ Новая публикация</button></div>
        ${rows}`;
      },

      // ---- привязки после innerHTML ----
      pubBind(root) {
        root.querySelectorAll('[data-pub-tab]').forEach(b => {
          b.onclick = () => { this.pubState.tab = b.getAttribute('data-pub-tab'); this.render(); };
        });
        root.querySelectorAll('[data-pub-add]').forEach(b => { b.onclick = () => this.pubOpenCreate(); });
        root.querySelectorAll('[data-pub-edit]').forEach(b => {
          b.onclick = () => {
            const id = Number(b.getAttribute('data-pub-edit'));
            const ch = (this.pubState.channels || []).find(c => c.id === id);
            if (ch) this.pubOpenEdit(ch);
          };
        });
        root.querySelectorAll('[data-pub-toggle]').forEach(b => {
          b.onclick = () => {
            const id = Number(b.getAttribute('data-pub-toggle'));
            const ch = (this.pubState.channels || []).find(c => c.id === id);
            if (ch) this.pubToggle(ch);
          };
        });
        root.querySelectorAll('[data-pub-retry]').forEach(b => { b.onclick = () => this.pubReload(); });
        root.querySelectorAll('[data-pub-close]').forEach(b => { b.onclick = () => this.pubCloseDrawer(); });
        root.querySelectorAll('[data-pub-save]').forEach(b => { b.onclick = () => this.pubSave(); });
        // живой сбор полей формы (platform меняет подписи, поэтому перерисовка)
        root.querySelectorAll('[data-pub-f]').forEach(el => {
          const k = el.getAttribute('data-pub-f');
          const handler = () => {
            this.pubState.drawer.form[k] = el.value;
            if (k === 'platform') this.render(); // подписи/подсказки по платформе
          };
          if (el.tagName === 'SELECT' || el.type === 'number') el.onchange = handler;
          el.oninput = (e) => { this.pubState.drawer.form[k] = e.target.value; };
        });

        // ---- редактор (Ф3) ----
        const ed = this.pubState.editor;
        const body = root.querySelector('[data-pub-ed-body]');
        if (body) {
          body.oninput = () => {
            ed.body_md = body.value;
            // live-превью: точечно обновляем только мокап (полный render()
            // пересоздал бы textarea и сбрасывал фокус)
            const box = root.querySelector('#pubPreviewBox');
            if (box && ed._curCh) box.innerHTML = this.pubPreviewHtml(ed._curCh);
          };
        }
        root.querySelectorAll('[data-pub-ed-photo]').forEach(inp => {
          inp.onchange = () => this.pubEditorUpload(inp);
        });
        root.querySelectorAll('[data-pub-ed-rmphoto]').forEach(a => {
          a.onclick = (e) => { e.preventDefault(); this.pubEditorRemoveMedia(Number(a.getAttribute('data-pub-ed-rmphoto'))); };
        });
        root.querySelectorAll('[data-pub-ch]').forEach(cb => {
          cb.onchange = () => {
            const id = Number(cb.getAttribute('data-pub-ch'));
            const ch = (this.pubState.channels || []).find(c => c.id === id);
            if (ch) { this.pubEditorToggle(ch); } // toggle + render (checkbox уже в DOM)
          };
        });
        root.querySelectorAll('[data-pub-prev-tab]').forEach(b => {
          b.onclick = () => { ed.previewTab = Number(b.getAttribute('data-pub-prev-tab')); this.render(); };
        });
        root.querySelectorAll('[data-pub-ed-override]').forEach(t => {
          t.oninput = () => {
            const id = Number(t.getAttribute('data-pub-ed-override'));
            ed.overrides[id] = t.value;
            const box = root.querySelector('#pubPreviewBox');
            if (box && ed._curCh && ed._curCh.id === id) box.innerHTML = this.pubPreviewHtml(ed._curCh);
          };
        });
        root.querySelectorAll('[data-pub-ed-save]').forEach(b => { b.onclick = () => this.pubEditorSave(); });
        root.querySelectorAll('[data-pub-ed-pub]').forEach(b => { b.onclick = () => this.pubEditorPublish(); });
        root.querySelectorAll('[data-pub-ed-new]').forEach(b => { b.onclick = () => this.pubOpenEditor(null); });
        const when = root.querySelector('[data-pub-ed-when]');
        if (when) when.onchange = () => { ed.scheduled = when.value; };
        root.querySelectorAll('[data-pub-ed-sched]').forEach(b => { b.onclick = () => this.pubEditorSchedule(); });
        root.querySelectorAll('[data-pub-unsched]').forEach(b => {
          b.onclick = async () => {
            const id = Number(b.getAttribute('data-pub-unsched'));
            try {
              await AGL.pubPostUpdate(id, { scheduled_at: null });
              this.toast('Расписание снято — пост в черновиках');
              await this.pubLoadPosts();
            } catch (e) {
              this.toast((e && e.error && e.error.message) || 'Ошибка', 'err');
            }
          };
        });

        // ---- список публикаций (Ф3) ----
        root.querySelectorAll('[data-pub-new]').forEach(b => { b.onclick = () => this.pubOpenEditor(null); });
        root.querySelectorAll('[data-pub-open]').forEach(b => {
          b.onclick = () => {
            const id = Number(b.getAttribute('data-pub-open'));
            const p = (this.pubState.posts || []).find(x => x.id === id);
            if (p) this.pubOpenEditor(p);
          };
        });
        root.querySelectorAll('[data-pub-republish]').forEach(b => {
          b.onclick = async () => {
            const id = Number(b.getAttribute('data-pub-republish'));
            b.disabled = true;
            try {
              const res = await AGL.pubPostPublish(id);
              const d = (res && res.data) || {};
              this.toast(d.skipped ? 'Пропуск: ' + (d.reason || '') : 'Повторная публикация выполнена', 'info');
              await this.pubLoadPosts();
            } catch (e) {
              this.toast((e && e.error && e.error.message) || 'Ошибка публикации', 'err');
              b.disabled = false;
            }
          };
        });
        root.querySelectorAll('[data-pub-del]').forEach(b => {
          b.onclick = async () => {
            const id = Number(b.getAttribute('data-pub-del'));
            try {
              await AGL.pubPostDelete(id);
              this.toast('Черновик удалён');
              await this.pubLoadPosts();
            } catch (e) {
              this.toast((e && e.error && e.error.message) || 'Ошибка удаления', 'err');
            }
          };
        });
      },
    };
  };
})();
