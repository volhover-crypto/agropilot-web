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
        tab: 'channels',            // Ф2: только 'channels'
        channels: [], loaded: false, loading: false, err: null,
        drawer: {                   // форма добавления/правки (паттерн §45.7)
          open: false, mode: 'create', id: null,
          form: {}, err: null, saving: false,
        },
      },

      pubCanEdit() {
        const uid = this.currentUserId();
        const u = (this.M.team || []).find(t => String(t.id) === String(uid));
        return !!(u && u.role_key === 'admin');
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
            <span class="btn" style="opacity:.45;cursor:default" title="Ф3">✍️ Редактор (Ф3)</span>
            <span class="btn" style="opacity:.45;cursor:default" title="Ф4">🕓 Отложка (Ф4)</span>
          </div>`;
        const body = st.tab === 'channels' ? this.vPubChannels() : '';
        return `
        <div class="mb-4 flex items-center justify-between flex-wrap gap-2">
          <div>
            <div class="text-2xl font-semibold">Публикации</div>
            <div class="text-sm" style="color:var(--text-mute)">Кросспостинг: одна публикация → все каналы, формат под каждую платформу (§46)</div>
          </div>
          ${this.pubCanEdit() ? '<button class="btn btn-accent" data-pub-add>+ Добавить канал</button>' : ''}
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
      },
    };
  };
})();
