// js/app.catalogs.js -- §45: раздел «Справочники» (НСИ), фаза 1a
//
// Подмешивается в appObjects() в конце js/app.objects.js (APP_CATALOGS_MIXIN):
// состояние, методы и metadata-driven UI — таблицы/формы/фильтры строятся из
// схемы GET /v1/catalogs (backend/catalogs/registry.py). this у методов —
// Alpine-компонент appObjects (доступны esc/toast/openModal/go/render и т.д.).
//
// Режимы раздела: «НСИ» (этот файл) и «Навигатор» (старый read-only архив §18,
// vCatalog в app.objects.js). Права: мутации — все вошедшие; удаление —
// manager (кнопка 🗑 скрывается по isManager(), сервер проверяет роль).

(function () {
  'use strict';

  window.APP_CATALOGS_MIXIN = function () {
    return {

      // ---- состояние раздела «Справочники» (§45) ----
      nsiState: {
        mode: 'nsi',            // 'nsi' | 'nav'
        specs: [], loaded: false, loadingSpecs: false, err: null,
        type: null,             // ключ текущего справочника
        items: [], total: 0, limit: 50, offset: 0,
        q: '', status: 'active', sort: 'code',
        sel: new Set(),         // выбранные строки (bulk)
      },

      nsiSpec() {
        const st = this.nsiState;
        return (st.specs || []).find(s => s.key === st.type) || null;
      },

      // ---- инициализация ----
      async nsiInit() {
        const st = this.nsiState;
        if (st.loaded || st.loadingSpecs) return;
        if (!window.AGL || !AGL.token) { st.err = 'Справочники работают после входа в API'; return; }
        st.loadingSpecs = true;
        try {
          let ui = {};
          try { ui = JSON.parse(localStorage.getItem('agropilot_nsi_ui') || '{}'); } catch (e) {}
          st.specs = await window.AGL.catalogSpecs();
          st.type = (ui.type && st.specs.some(s => s.key === ui.type)) ? ui.type
            : ((st.specs[0] && st.specs[0].key) || null);
          if (ui.status) st.status = ui.status;
          if (ui.sort) st.sort = ui.sort;
          st.loaded = true;
          st.err = null;
          await this.nsiLoad();
        } catch (e) {
          console.warn('[NSI] specs load failed:', e && e.message);
          st.err = 'Не удалось загрузить схему справочников: ' + (e && e.message || '');
        } finally {
          st.loadingSpecs = false;
          this.render();
        }
      },

      nsiSaveUi() {
        const st = this.nsiState;
        try { localStorage.setItem('agropilot_nsi_ui', JSON.stringify({ type: st.type, status: st.status, sort: st.sort })); } catch (e) {}
      },

      async nsiLoad() {
        const st = this.nsiState;
        if (!st.type || !window.AGL || !AGL.token) return;
        try {
          const d = await window.AGL.catalogList(st.type, {
            q: st.q, status: st.status, sort: st.sort,
            limit: st.limit, offset: st.offset,
          });
          st.items = (d && d.items) || [];
          st.total = (d && d.total) || 0;
        } catch (e) {
          console.warn('[NSI] list failed:', e && e.message);
          this.toast('Ошибка загрузки: ' + (e && e.message || ''), 'err');
        }
        this.render();
      },

      // ---- верхний уровень: вкладки режимов ----
      vCatalogs() {
        const st = this.nsiState;
        if (st.mode !== 'nav') this.nsiInit();
        const tab = (m, label) => `<button class="btn ${st.mode === m ? 'btn-accent' : ''}" data-nsi-mode="${m}">${label}</button>`;
        const body = st.mode === 'nav' ? this.vCatalog() : this.nsiView();
        return `<div class="flex items-center gap-2 mb-3">
          ${tab('nsi', '📚 Справочники')}
          ${tab('nav', '🧭 Навигатор')}
          <span class="pill text-[11px]" style="color:var(--text-mute)">НСИ · фаза 1a</span>
        </div>${body}`;
      },

      // ---- режим НСИ: дерево типов + таблица ----
      nsiView() {
        const st = this.nsiState, e = v => this.esc(v == null ? '' : String(v));
        if (!window.AGL || !AGL.token) {
          return `<div class="card p-8 text-center">
            <div class="text-lg font-semibold mb-2">Справочники (НСИ)</div>
            <div class="text-[13px] mb-4" style="color:var(--text-dim)">Раздел работает после входа в API — демонстрационных данных у справочников нет.</div>
          </div>`;
        }
        if (st.loadingSpecs || !st.loaded) {
          return `<div class="card p-8 text-center text-[13px]" style="color:var(--text-mute)">${st.err ? e(st.err) : 'Загрузка справочников…'}</div>`;
        }
        if (st.err) {
          return `<div class="card p-8 text-center"><div class="text-[13px] mb-3" style="color:var(--err)">${e(st.err)}</div>
            <button class="btn" data-nsi-retry>Повторить</button></div>`;
        }

        const groups = {};
        (st.specs || []).forEach(s => { const g = s.group || 'Прочие'; (groups[g] = groups[g] || []).push(s); });
        const tree = Object.entries(groups).map(([g, list]) =>
          `<div class="label px-1 mt-2 mb-1">${e(g)}</div>` +
          list.map(s => `<div class="nav-item ${s.key === st.type ? 'active' : ''}" data-nsi-type="${e(s.key)}">
            <span>${s.icon || '📁'}</span><span class="flex-1">${e(s.title)}</span></div>`).join('')
        ).join('');

        return `<div class="flex gap-4 items-start flex-wrap">
          <div class="card p-2" style="flex:0 0 220px; min-width:200px">
            <div class="label px-2 pt-1 pb-2">Справочники</div>
            ${tree}
          </div>
          <div class="card p-3" style="flex:1 1 620px; min-width:480px">${this.nsiTable()}</div>
        </div>`;
      },

      nsiVal(f, v) {
        const e = x => this.esc(x == null ? '' : String(x));
        if (v == null || v === '') return '<span style="color:var(--text-mute)">—</span>';
        if (f.type === 'enum' && f.options && f.options[v] != null) return e(f.options[v]);
        if (f.key === 'color' && /^#?[0-9a-fA-F]{6}$/.test(String(v))) {
          const hex = String(v)[0] === '#' ? v : '#' + v;
          return `<span class="inline-block w-3 h-3 rounded-sm align-middle mr-1" style="background:${hex};border:1px solid var(--border)"></span>${e(v)}`;
        }
        return e(v);
      },

      nsiTable() {
        const st = this.nsiState, e = v => this.esc(v == null ? '' : String(v));
        const spec = this.nsiSpec();
        if (!spec) return '<div class="text-[13px]" style="color:var(--text-mute)">Выберите справочник слева.</div>';
        const cols = spec.fields.filter(f => f.grid);
        const canDel = this.isManager();
        const selCount = st.sel.size;

        const from = st.total ? st.offset + 1 : 0;
        const to = Math.min(st.offset + st.limit, st.total);
        const pages = Math.max(1, Math.ceil(st.total / st.limit));
        const page = Math.floor(st.offset / st.limit) + 1;

        const bulk = selCount ? `<span class="pill text-[11px]" style="background:var(--accent);color:#fff;border:0">Выбрано: ${selCount}</span>
          <button class="btn text-[11px]" data-nsi-bulk="archive">🗄 В архив</button>
          <button class="btn text-[11px]" data-nsi-bulk="restore">↩ Восстановить</button>
          <button class="btn text-[11px]" data-nsi-bulk="clear">✕ Снять</button>` : '';

        const head = cols.map(f => {
          const dir = st.sort === f.key ? ' ▲' : st.sort === '-' + f.key ? ' ▼' : '';
          const w = f.width ? ` style="width:${f.width}px"` : '';
          return `<th class="px-2 py-1 text-left cursor-pointer select-none"${w} data-nsi-sort="${e(f.key)}" title="Сортировать">${e(f.label)}${dir}</th>`;
        }).join('');

        const rows = (st.items || []).map(it => {
          const checked = st.sel.has(String(it.id)) ? 'checked' : '';
          const cells = cols.map(f => `<td class="px-2 py-1 text-[13px] truncate" title="${e(it[f.key])}">${this.nsiVal(f, it[f.key])}</td>`).join('');
          const arch = it.status === 'active'
            ? `<button class="btn text-[11px] py-0.5" data-nsi-arch="${it.id}" title="В архив">🗄</button>`
            : `<button class="btn text-[11px] py-0.5" data-nsi-rest="${it.id}" title="Вернуть из архива">↩</button>`;
          return `<tr class="${it.status === 'archived' ? 'opacity-55' : ''} ${st.sel.has(String(it.id)) ? 'font-semibold' : ''}">
            <td class="px-2 py-1"><input type="checkbox" data-nsi-check="${it.id}" ${checked} /></td>
            ${cells}
            <td class="px-2 py-1 text-right whitespace-nowrap">
              ${it.is_system ? '<span title="Системная запись">🔒</span> ' : ''}
              <button class="btn text-[11px] py-0.5" data-nsi-edit="${it.id}" title="Изменить">✎</button>
              <button class="btn text-[11px] py-0.5" data-nsi-hist="${it.id}" title="История изменений">⟳</button>
              ${arch}
              ${canDel && !it.is_system ? `<button class="btn text-[11px] py-0.5" data-nsi-del="${it.id}" title="Удалить безвозвратно">🗑</button>` : ''}
            </td>
          </tr>`;
        }).join('');

        const empty = !(st.items || []).length
          ? `<tr><td colspan="${cols.length + 2}" class="px-2 py-6 text-center text-[13px]" style="color:var(--text-mute)">
              Здесь пока нет ни одной записи — создайте первую или измените фильтр.
            </td></tr>` : '';

        return `
          <div class="flex items-center gap-2 mb-2 flex-wrap">
            <input id="nsiSearch" class="input text-[13px]" style="width:220px" placeholder="Поиск по названию/коду…" value="${e(st.q)}" />
            <select id="nsiStatus" class="input text-[13px]">
              <option value="active" ${st.status === 'active' ? 'selected' : ''}>Активные</option>
              <option value="archived" ${st.status === 'archived' ? 'selected' : ''}>Архив</option>
              <option value="all" ${st.status === 'all' ? 'selected' : ''}>Все</option>
            </select>
            <span class="pill text-[11px]">Показано ${from}–${to} из ${st.total}</span>
            <div class="flex-1"></div>
            ${bulk}
            <button class="btn btn-accent" data-nsi-add>＋ Добавить</button>
          </div>
          <div id="nsiTable" class="mb-2">
            <table class="w-full" style="border-collapse:separate; border-spacing:0">
              <thead><tr>
                <th style="width:28px"><input type="checkbox" data-nsi-check-all ${selCount && selCount === st.items.length ? 'checked' : ''} /></th>
                ${head}
                <th style="width:170px"></th>
              </tr></thead>
              <tbody>${rows || empty}</tbody>
            </table>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px]" style="color:var(--text-mute)">Код назначается автоматически (${e((spec.key === 'currencies') ? 'ISO или авто' : 'ПРЕФИКС-0001')})</span>
            <div class="flex items-center gap-2">
              <button class="btn text-[12px]" data-nsi-page="prev" ${page <= 1 ? 'disabled' : ''}>◂</button>
              <span class="text-[12px]">стр. ${page} из ${pages}</span>
              <button class="btn text-[12px]" data-nsi-page="next" ${page >= pages ? 'disabled' : ''}>▸</button>
            </div>
          </div>`;
      },

      // ---- формы создания/редактирования (метадата-driven) ----
      nsiFieldInput(f, val) {
        const e = v => this.esc(v == null ? '' : String(v));
        const id = 'nsi-f-' + f.key;
        const lbl = `<div class="label mb-1">${e(f.label)}${f.required ? ' <span style="color:var(--err)">*</span>' : ''}</div>`;
        if (f.type === 'enum') {
          const opts = f.options || {};
          const cur = (val != null && val !== '') ? String(val) : '';
          return `<label class="block mb-2">${lbl}
            <select id="${id}" class="input w-full text-[13px]">
              <option value="">— не выбрано —</option>
              ${Object.keys(opts).map(v => `<option value="${e(v)}" ${v === cur ? 'selected' : ''}>${e(opts[v])}</option>`).join('')}
            </select></label>`;
        }
        const type = f.type === 'int' ? 'number' : 'text';
        const ph = f.key === 'code' ? 'авто, если пусто' : '';
        return `<label class="block mb-2">${lbl}
          <input id="${id}" class="input w-full text-[13px]" type="${type}" value="${e(val)}" placeholder="${e(ph)}" /></label>`;
      },

      nsiFormBody(spec, item, parents) {
        const e = v => this.esc(v == null ? '' : String(v));
        const fields = spec.fields.map(f => this.nsiFieldInput(f, item ? item[f.key] : null)).join('');
        const parent = spec.hierarchical ? `<label class="block mb-2"><div class="label mb-1">Родительский элемент</div>
          <select id="nsi-f-parent" class="input w-full text-[13px]">
            <option value="">— верхний уровень —</option>
            ${(parents || []).filter(p => !item || String(p.id) !== String(item.id))
              .map(p => `<option value="${p.id}" ${item && String(item.parent_id) === String(p.id) ? 'selected' : ''}>${e(p.name)} (${e(p.code)})</option>`).join('')}
          </select></label>` : '';
        return `<div id="nsiDup" class="mb-1"></div>
          ${fields}${parent}
          <div id="nsiFormErr" class="text-[12px] mt-1" style="color:var(--err)"></div>`;
      },

      nsiDupHtml(items) {
        const e = v => this.esc(v == null ? '' : String(v));
        if (!items || !items.length) return '';
        return `<div class="card-2 p-2 mb-2" style="border-color:var(--warn)">
          <div class="label mb-1" style="color:var(--warn)">⚠ Похожие записи уже есть</div>
          ${items.map(i => `<div class="text-[12px] flex items-center gap-2 py-0.5">
            <span class="flex-1 truncate">${e(i.name)} <span style="color:var(--text-mute)">${e(i.code || '')}${i.score ? ' · схожесть ' + Math.round(i.score * 100) + '%' : ''}</span></span>
            <button class="btn text-[11px] py-0.5" data-nsi-dup-open="${i.id}">Открыть</button>
          </div>`).join('')}
          <div class="text-[11px] mt-1" style="color:var(--text-mute)">Если это всё-таки другая запись — продолжайте сохранение.</div>
        </div>`;
      },

      // item === null → создание; иначе редактирование
      async nsiForm(item) {
        if (!window.AGL || !AGL.token) { this.toast('В демо-режиме недоступно', 'warn'); return; }
        const st = this.nsiState;
        const spec = this.nsiSpec();
        if (!spec) return;
        let parents = [];
        if (spec.hierarchical) {
          try {
            const d = await window.AGL.catalogList(spec.key, { limit: 200, status: 'all', sort: 'name' });
            parents = (d && d.items) || [];
          } catch (e) { console.warn('[NSI] parents load failed:', e && e.message); }
        }
        this.openModal((item ? 'Изменить · ' : 'Новая запись · ') + spec.title,
          this.nsiFormBody(spec, item, parents),
          async () => {
            const payload = {};
            for (const f of spec.fields) {
              const el = document.getElementById('nsi-f-' + f.key);
              if (!el) continue;
              payload[f.key] = (f.type === 'int')
                ? (el.value === '' ? null : parseInt(el.value, 10))
                : el.value.trim();
            }
            if (spec.hierarchical) {
              const pe = document.getElementById('nsi-f-parent');
              if (pe) payload.parent_id = pe.value === '' ? null : parseInt(pe.value, 10);
            }
            const errEl = document.getElementById('nsiFormErr');
            const showErr = (m) => { if (errEl) errEl.textContent = m; this.toast(m, 'err'); };
            for (const f of spec.fields) {
              if (f.required && (payload[f.key] == null || payload[f.key] === '')) {
                showErr('Заполните обязательное поле: ' + f.label); return false;
              }
            }
            try {
              const saved = item
                ? await window.AGL.catalogUpdate(spec.key, item.id, payload)
                : await window.AGL.catalogCreate(spec.key, payload);
              this.toast(item ? 'Сохранено' : 'Создано: ' + ((saved && saved.name) || ''), 'ok');
              this.nsiLoad();
              return true;
            } catch (e2) {
              showErr((e2 && e2.message) || 'Ошибка сохранения');
              return false;
            }
          }, { wide: spec.fields.length > 4 });

        // дедуп-предупреждение при вводе наименования (только создание)
        if (!item) {
          const nameEl = document.getElementById('nsi-f-name');
          if (nameEl) {
            let t = null;
            nameEl.addEventListener('input', () => {
              clearTimeout(t);
              t = setTimeout(async () => {
                const v = nameEl.value.trim();
                const box = document.getElementById('nsiDup');
                if (!box) return;
                if (v.length < 2) { box.innerHTML = ''; return; }
                try {
                  const d = await window.AGL.catalogDuplicates(spec.key, v);
                  box.innerHTML = this.nsiDupHtml((d && d.items) || []);
                  box.querySelectorAll('[data-nsi-dup-open]').forEach(b => {
                    b.onclick = () => { this.closeModal(); this.nsiForm(null); this.nsiEdit(b.getAttribute('data-nsi-dup-open')); };
                  });
                } catch (e) { /* дедуп-чек не критичен */ }
              }, 350);
            });
          }
        }
        this.$nextTick(() => { const el = document.getElementById('nsi-f-name'); if (el) el.focus(); });
      },

      nsiAdd() { this.nsiForm(null); },

      nsiEdit(id) {
        const st = this.nsiState;
        const it = (st.items || []).find(x => String(x.id) === String(id));
        if (!it) return;
        this.nsiForm(it);
      },

      // ---- история изменений ----
      async nsiHist(id) {
        if (!window.AGL || !AGL.token) return;
        const st = this.nsiState, spec = this.nsiSpec();
        if (!spec) return;
        const it = (st.items || []).find(x => String(x.id) === String(id));
        try {
          const h = await window.AGL.catalogHistory(spec.key, id);
          const ACT = { create: '➕ создано', update: '✎ изменено', archive: '🗄 в архив', restore: '↩ из архива', delete: '🗑 удалено', merge: '🔀 слито' };
          const rows = (h.items || []).map(x => {
            const dl = Object.entries(x.diff || {}).map(([k, v]) =>
              `<div class="text-[12px] mt-0.5">${e2(k)}: <s style="color:var(--text-mute)">${e2(v && v.old !== null && v.old !== undefined ? v.old : '—')}</s> → <b>${e2(v && v.new !== null && v.new !== undefined ? v.new : '—')}</b></div>`).join('');
            return `<div class="card-2 p-2 mb-1">
              <div class="flex justify-between gap-2 text-[12px]"><b>${ACT[x.action] || e2(x.action)}</b>
              <span style="color:var(--text-dim)">${e2(x.user_name || '—')} · ${String(x.created_at || '').slice(0, 16).replace('T', ' ')}</span></div>
              ${dl}</div>`;
          }).join('') || '<div class="text-[13px]" style="color:var(--text-mute)">Изменений ещё не было.</div>';
          this.openModal('История · ' + (it ? it.name : spec.title), rows, null, { noFooter: true, wide: true });
        } catch (e) {
          this.toast('Ошибка истории: ' + (e && e.message || ''), 'err');
        }
        function e2(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); }
      },

      // ---- архив / удаление / bulk ----
      async nsiArch(id, restore) {
        if (!window.AGL || !AGL.token) { this.toast('В демо-режиме недоступно', 'warn'); return; }
        const st = this.nsiState, spec = this.nsiSpec();
        try {
          if (restore) await window.AGL.catalogRestore(spec.key, id);
          else await window.AGL.catalogArchive(spec.key, id);
          this.toast(restore ? 'Возвращено из архива' : 'Перемещено в архив', 'ok');
        } catch (e) { this.toast((e && e.message) || 'Ошибка', 'err'); }
        this.nsiLoad();
      },

      async nsiDel(id) {
        if (!window.AGL || !AGL.token) { this.toast('В демо-режиме недоступно', 'warn'); return; }
        const st = this.nsiState, spec = this.nsiSpec();
        const it = (st.items || []).find(x => String(x.id) === String(id));
        if (!window.confirm(`Удалить безвозвратно «${it ? it.name : id}»?\nОбычно достаточно архивации — удаление доступно только руководителю.`)) return;
        try {
          await window.AGL.catalogDelete(spec.key, id);
          this.toast('Удалено', 'ok');
        } catch (e) { this.toast((e && e.message) || 'Ошибка удаления', 'err'); }
        this.nsiLoad();
      },

      async nsiBulk(action) {
        const st = this.nsiState, spec = this.nsiSpec();
        if (action === 'clear') { st.sel.clear(); this.render(); return; }
        if (!window.AGL || !AGL.token) return;
        const ids = [...st.sel];
        if (!ids.length || !spec) return;
        if (action === 'archive' && !window.confirm(`Архивировать выбранные записи (${ids.length})?`)) return;
        let ok = 0, lastErr = null;
        for (const id of ids) {
          try {
            if (action === 'archive') await window.AGL.catalogArchive(spec.key, id);
            else await window.AGL.catalogRestore(spec.key, id);
            ok++;
          } catch (e) { lastErr = e; }
        }
        st.sel.clear();
        this.toast((action === 'archive' ? 'Заархивировано: ' : 'Восстановлено: ') + ok +
          (lastErr ? ' (ошибка: ' + (lastErr.message || '') + ')' : ''), ok ? 'ok' : 'err');
        this.nsiLoad();
      },

      // ---- служебные ----
      nsiSetType(key) {
        const st = this.nsiState;
        st.type = key; st.offset = 0; st.q = ''; st.sel.clear();
        this.nsiSaveUi();
        this.nsiLoad();
      },

      nsiSort(key) {
        const st = this.nsiState;
        st.sort = (st.sort === key) ? '-' + key : key;
        st.offset = 0;
        this.nsiSaveUi();
        this.nsiLoad();
      },

      nsiPage(dir) {
        const st = this.nsiState;
        const next = st.offset + (dir === 'prev' ? -st.limit : st.limit);
        if (next < 0 || next >= st.total) return;
        st.offset = next;
        this.nsiLoad();
      },

      nsiCheck(id) {
        const st = this.nsiState;
        const k = String(id);
        if (st.sel.has(k)) st.sel.delete(k); else st.sel.add(k);
        this.render();
      },

      nsiCheckAll() {
        const st = this.nsiState;
        const ids = (st.items || []).map(i => String(i.id));
        const all = ids.length && ids.every(id => st.sel.has(id));
        if (all) ids.forEach(id => st.sel.delete(id));
        else ids.forEach(id => st.sel.add(id));
        this.render();
      },

      // ---- события раздела (вызывается из bindView() app.objects.js) ----
      nsiBind(el) {
        const st = this.nsiState;

        el.querySelectorAll('[data-nsi-mode]').forEach(n => {
          n.onclick = () => {
            const m = n.getAttribute('data-nsi-mode');
            this.go(m === 'nav' ? 'catalog' : 'catalogs');
          };
        });
        el.querySelectorAll('[data-nsi-retry]').forEach(n => {
          n.onclick = () => { st.loaded = false; st.err = null; this.nsiInit(); };
        });
        el.querySelectorAll('[data-nsi-type]').forEach(n => {
          n.onclick = () => this.nsiSetType(n.getAttribute('data-nsi-type'));
        });
        el.querySelectorAll('[data-nsi-add]').forEach(n => { n.onclick = () => this.nsiAdd(); });
        el.querySelectorAll('[data-nsi-edit]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiEdit(n.getAttribute('data-nsi-edit')); };
        });
        el.querySelectorAll('[data-nsi-hist]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiHist(n.getAttribute('data-nsi-hist')); };
        });
        el.querySelectorAll('[data-nsi-arch]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiArch(n.getAttribute('data-nsi-arch'), false); };
        });
        el.querySelectorAll('[data-nsi-rest]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiArch(n.getAttribute('data-nsi-rest'), true); };
        });
        el.querySelectorAll('[data-nsi-del]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiDel(n.getAttribute('data-nsi-del')); };
        });
        el.querySelectorAll('[data-nsi-bulk]').forEach(n => {
          n.onclick = () => this.nsiBulk(n.getAttribute('data-nsi-bulk'));
        });
        el.querySelectorAll('[data-nsi-check]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiCheck(n.getAttribute('data-nsi-check')); };
        });
        el.querySelectorAll('[data-nsi-check-all]').forEach(n => {
          n.onclick = () => this.nsiCheckAll();
        });
        el.querySelectorAll('[data-nsi-sort]').forEach(n => {
          n.onclick = () => this.nsiSort(n.getAttribute('data-nsi-sort'));
        });
        el.querySelectorAll('[data-nsi-page]').forEach(n => {
          n.onclick = () => this.nsiPage(n.getAttribute('data-nsi-page'));
        });

        const search = el.querySelector('#nsiSearch');
        if (search) {
          search.oninput = () => {
            st.q = search.value; st.offset = 0;
            clearTimeout(this._nsiSearchT);
            this._nsiWantFocus = 'nsiSearch';
            this._nsiSearchT = setTimeout(() => this.nsiLoad(), 300);
          };
          // после перерисовки возвращаем фокус в поиск (каретка в конец)
          if (this._nsiWantFocus === 'nsiSearch') {
            this._nsiWantFocus = null;
            search.focus();
            const v = search.value; search.value = ''; search.value = v;
          }
        }
        const statusSel = el.querySelector('#nsiStatus');
        if (statusSel) {
          statusSel.onchange = () => { st.status = statusSel.value; st.offset = 0; this.nsiSaveUi(); this.nsiLoad(); };
        }
      },
    };
  };
})();
