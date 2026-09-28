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
        parent: 'all',          // 'all' | 'none' | id группы (иерархические)
        groups: [],             // группы/родители для панели иерархии
        sel: new Set(),         // выбранные строки (bulk/merge)
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
        const spec = this.nsiSpec();
        try {
          if (spec && spec.hierarchical) this.nsiLoadGroups();
          const d = await window.AGL.catalogList(st.type, {
            q: st.q, status: st.status, sort: st.sort, parent: st.parent,
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

      // группы/родители для панели иерархии (номенклатура: только is_group)
      async nsiLoadGroups() {
        const st = this.nsiState;
        const spec = this.nsiSpec();
        if (!spec || !spec.hierarchical) { st.groups = []; return; }
        try {
          const d = await window.AGL.catalogList(spec.key,
            { limit: 200, status: 'all', sort: 'code', parent: 'all' });
          let items = (d && d.items) || [];
          if (spec.group_items) items = items.filter(i => i.is_group);
          st.groups = items;
        } catch (e) { st.groups = []; }
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
          <span class="pill text-[11px]" style="color:var(--text-mute)">НСИ</span>
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

        const admin = this.nsiIsAdmin();
        const active = (st.specs || []).filter(s => s.status !== 'archived');
        const archived = admin ? (st.specs || []).filter(s => s.status === 'archived') : [];
        const groups = {};
        active.forEach(s => { const g = s.group || 'Прочие'; (groups[g] = groups[g] || []).push(s); });
        const tree = Object.entries(groups).map(([g, list]) =>
          `<div class="label px-1 mt-2 mb-1">${e(g)}</div>` +
          list.map(s => `<div class="nav-item ${s.key === st.type ? 'active' : ''}" data-nsi-type="${e(s.key)}">
            <span>${s.icon || '📁'}</span><span class="flex-1">${e(s.title)}</span>
            ${s.managed ? '<span class="pill text-[9px]" title="Создан администратором">моё</span>' : ''}</div>`).join('')
        ).join('');
        const archBlock = archived.length ? `
          <div class="label px-1 mt-3 mb-1" style="color:var(--text-mute)">Архив справочников</div>
          ${archived.map(s => `<div class="nav-item" style="color:var(--text-mute)">
            <span>${s.icon || '📁'}</span><span class="flex-1 truncate">${e(s.title)}</span>
            ${this.artActionBtn(`data-nsi-type-restore="${s.type_id}"`, 'Восстановить справочник', '↩')}
          </div>`).join('')}` : '';
        const addBtn = admin
          ? `<button class="btn text-[11px] w-full mt-2" data-nsi-type-add>＋ Добавить справочник</button>` : '';

        return `<div class="flex gap-4 items-start flex-wrap">
          <div class="card p-2" style="flex:0 0 220px; min-width:200px">
            <div class="label px-2 pt-1 pb-2">Справочники</div>
            ${tree}
            ${archBlock}
            ${addBtn}
          </div>
          <div class="card p-3" style="flex:1 1 620px; min-width:480px">${this.nsiTable()}</div>
        </div>`;
      },

      nsiVal(f, v, it) {
        const e = x => this.esc(x == null ? '' : String(x));
        if (f.type === 'ref') {
          const label = it ? it[f.key + '_label'] : null;
          return label ? e(label) : '<span style="color:var(--text-mute)">—</span>';
        }
        if (v == null || v === '') return '<span style="color:var(--text-mute)">—</span>';
        if (f.type === 'enum' && f.options && f.options[v] != null) return e(f.options[v]);
        if (f.type === 'decimal') return e(Number(v).toLocaleString('ru-RU'));
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
        // §45.10: управление самим справочником — админ, кнопки как у артефактов
        const typeBtns = (spec.managed && this.nsiIsAdmin()) ? `
          <span class="inline-flex items-center gap-1 ml-1" title="Действия со справочником">
            ${this.artActionBtn(`data-nsi-type-edit="${spec.type_id}"`, 'Изменить справочник (название, поля, иконка)', '✎')}
            ${this.artActionBtn(`data-nsi-type-hist="${spec.type_id}"`, 'История справочника', '⟳')}
            ${this.artActionBtn(`data-nsi-type-arch="${spec.type_id}"`, 'Справочник в архив', '🗄', true)}
          </span>` : '';

        const from = st.total ? st.offset + 1 : 0;
        const to = Math.min(st.offset + st.limit, st.total);
        const pages = Math.max(1, Math.ceil(st.total / st.limit));
        const page = Math.floor(st.offset / st.limit) + 1;

        const bulk = selCount ? `<span class="pill text-[11px]" style="background:var(--accent);color:#fff;border:0">Выбрано: ${selCount}</span>
          <button class="btn text-[11px]" data-nsi-bulk="archive">🗄 В архив</button>
          <button class="btn text-[11px]" data-nsi-bulk="restore">↩ Восстановить</button>
          ${canDel && selCount >= 2 ? '<button class="btn text-[11px]" data-nsi-merge>🔀 Слить…</button>' : ''}
          <button class="btn text-[11px]" data-nsi-bulk="clear">✕ Снять</button>` : '';

        const head = cols.map(f => {
          const dir = st.sort === f.key ? ' ▲' : st.sort === '-' + f.key ? ' ▼' : '';
          const w = f.width ? ` style="width:${f.width}px"` : '';
          return `<th class="px-2 py-1 text-left cursor-pointer select-none"${w} data-nsi-sort="${e(f.key)}" title="Сортировать">${e(f.label)}${dir}</th>`;
        }).join('');

        const rows = (st.items || []).map(it => {
          const checked = st.sel.has(String(it.id)) ? 'checked' : '';
          const cells = cols.map(f => {
            let val = this.nsiVal(f, it[f.key], it);
            if (f.key === 'name' && it.is_group) val = '📁 ' + val;
            return `<td class="px-2 py-1 text-[13px] truncate" title="${e(it[f.key])}">${val}</td>`;
          }).join('');
          // круглые кнопки в стиле артефактов (artActionBtn, 22px)
          const arch = it.status === 'active'
            ? this.artActionBtn(`data-nsi-arch="${it.id}"`, 'В архив', '🗄', true, 22)
            : this.artActionBtn(`data-nsi-rest="${it.id}"`, 'Вернуть из архива', '↩', false, 22);
          return `<tr class="${it.status === 'archived' ? 'opacity-55' : ''} ${st.sel.has(String(it.id)) ? 'font-semibold' : ''}">
            <td class="px-2 py-1"><input type="checkbox" data-nsi-check="${it.id}" ${checked} /></td>
            ${cells}
            <td class="px-2 py-1 text-right whitespace-nowrap">
              <span class="inline-flex items-center gap-1">
                ${it.is_system ? '<span class="pill text-[11px]" title="Системная запись">🔒</span>' : ''}
                ${this.artActionBtn(`data-nsi-edit="${it.id}"`, 'Изменить', '✎', false, 22)}
                ${this.artActionBtn(`data-nsi-hist="${it.id}"`, 'История изменений', '⟳', false, 22)}
                ${arch}
                ${canDel && !it.is_system ? this.artActionBtn(`data-nsi-del="${it.id}"`, 'Удалить безвозвратно', '🗑', true, 22) : ''}
              </span>
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
            ${typeBtns}
          </div>
          <div class="flex items-stretch" style="min-width:0">
            ${this.nsiGroupsHtml()}
            <div id="nsiTable" class="mb-2" style="flex:1 1 auto; min-width:0">
              <table class="w-full" style="border-collapse:separate; border-spacing:0">
                <thead><tr>
                  <th style="width:28px"><input type="checkbox" data-nsi-check-all ${selCount && selCount === st.items.length ? 'checked' : ''} /></th>
                  ${head}
                  <th style="width:170px"></th>
                </tr></thead>
                <tbody>${rows || empty}</tbody>
              </table>
            </div>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[11px]" style="color:var(--text-mute)">Код назначается автоматически (ПРЕФИКС-0001)</span>
            <div class="flex items-center gap-2">
              <button class="btn text-[12px]" data-nsi-page="prev" ${page <= 1 ? 'disabled' : ''}>◂</button>
              <span class="text-[12px]">стр. ${page} из ${pages}</span>
              <button class="btn text-[12px]" data-nsi-page="next" ${page >= pages ? 'disabled' : ''}>▸</button>
            </div>
          </div>`;
      },

      // панель групп/иерархии слева от таблицы (regions, nomenclature)
      nsiGroupsHtml() {
        const st = this.nsiState, e = v => this.esc(v == null ? '' : String(v));
        const spec = this.nsiSpec();
        if (!spec || !spec.hierarchical) return '';
        const byParent = {};
        st.groups.forEach(g => {
          const p = g.parent_id == null ? 'root' : String(g.parent_id);
          (byParent[p] = byParent[p] || []).push(g);
        });
        const row = (g, depth) => {
          const active = String(st.parent) === String(g.id);
          return `<div class="nav-item ${active ? 'active' : ''}" style="padding-left:${6 + depth * 12}px" data-nsi-group="${g.id}" title="${e(g.code || '')}">
              <span style="color:var(--text-mute)">${active ? '●' : '▸'}</span>
              <span class="flex-1 truncate">${e(g.name)}</span></div>`
            + (byParent[String(g.id)] || []).map(c => row(c, depth + 1)).join('');
        };
        const tree = (byParent['root'] || []).map(g => row(g, 0)).join('')
          || '<div class="text-[12px] p-2" style="color:var(--text-mute)">Пока нет — создайте первым</div>';
        return `<div class="border-r pr-2 mr-3" style="flex:0 0 190px; border-color:var(--border)">
          <div class="label mb-1">${spec.group_items ? 'Группы' : 'Иерархия'}</div>
          <div class="nav-item ${st.parent === 'all' ? 'active' : ''}" data-nsi-group="all"><span>☰</span><span class="flex-1">Все элементы</span></div>
          <div class="nav-item ${st.parent === 'none' ? 'active' : ''}" data-nsi-group="none"><span>⌂</span><span class="flex-1">Верхний уровень</span></div>
          ${tree}
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
        if (f.type === 'ref') {
          const opts = (this._nsiRefOpts && this._nsiRefOpts[f.key]) || [];
          const cur = (val != null && val !== '') ? String(val) : '';
          return `<label class="block mb-2">${lbl}
            <select id="${id}" class="input w-full text-[13px]">
              <option value="">— не выбрано —</option>
              ${opts.map(o => `<option value="${o.id}" ${String(o.id) === cur ? 'selected' : ''}>${e(o.name)}${o.code ? ' (' + e(o.code) + ')' : ''}</option>`).join('')}
            </select></label>`;
        }
        // int — number; decimal — text (чтобы принимал запятую «123,50»)
        const type = f.type === 'int' ? 'number' : 'text';
        const ph = f.key === 'code' ? 'авто, если пусто' : '';
        return `<label class="block mb-2">${lbl}
          <input id="${id}" class="input w-full text-[13px]" type="${type}" value="${e(val)}" placeholder="${e(ph)}" /></label>`;
      },

      nsiFormBody(spec, item, parents) {
        const e = v => this.esc(v == null ? '' : String(v));
        const grp = (spec.group_items && !item)
          ? `<label class="flex items-center gap-2 mb-3 text-[13px] cursor-pointer">
              <input type="checkbox" id="nsi-f-is-group" /> <span>Это группа (папка без единиц и цен)</span></label>` : '';
        const grpBadge = (item && spec.group_items && item.is_group)
          ? '<div class="pill text-[11px] mb-2" style="background:var(--accent-soft)">📁 Группа — поля элементов скрыты</div>' : '';
        const fields = spec.fields.map(f => this.nsiFieldInput(f, item ? item[f.key] : null)).join('');
        const parent = spec.hierarchical ? `<label class="block mb-2"><div class="label mb-1">Родительский элемент</div>
          <select id="nsi-f-parent" class="input w-full text-[13px]">
            <option value="">— верхний уровень —</option>
            ${(parents || []).filter(p => !item || String(p.id) !== String(item.id))
              .map(p => `<option value="${p.id}" ${item && String(item.parent_id) === String(p.id) ? 'selected' : ''}>${e(p.name)} (${e(p.code)})</option>`).join('')}
          </select></label>` : '';
        return `<div id="nsiDup" class="mb-1"></div>
          ${grp}${grpBadge}${fields}${parent}
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
        // опции ref-полей (единицы/валюты/регионы) — параллельно
        this._nsiRefOpts = {};
        await Promise.all(spec.fields.filter(f => f.type === 'ref').map(async f => {
          try {
            const d = await window.AGL.catalogList(f.ref, { limit: 200, status: 'active', sort: 'name' });
            this._nsiRefOpts[f.key] = ((d && d.items) || []).map(o => ({ id: o.id, name: o.name, code: o.code }));
          } catch (e) { this._nsiRefOpts[f.key] = []; }
        }));

        const title = (item ? 'Изменить · ' : 'Новая запись · ') + spec.title;
        const onSave = async () => {
          const payload = {};
          for (const f of spec.fields) {
            const el = document.getElementById('nsi-f-' + f.key);
            if (!el) continue;
            payload[f.key] = (f.type === 'int' || f.type === 'ref')
              ? (el.value === '' ? null : parseInt(el.value, 10))
              : el.value.trim();
          }
          if (spec.group_items) {
            const gc = document.getElementById('nsi-f-is-group');
            if (gc) payload.is_group = gc.checked;
          }
          if (spec.hierarchical) {
            const pe = document.getElementById('nsi-f-parent');
            if (pe) payload.parent_id = pe.value === '' ? null : parseInt(pe.value, 10);
          }
          const errEl = document.getElementById('nsiFormErr');
          const showErr = (m) => { if (errEl) errEl.textContent = m; this.toast(m, 'err'); };
          for (const f of spec.fields) {
            if (f.required && (payload[f.key] == null || payload[f.key] === '')
                && !(payload.is_group && (spec.element_fields || []).includes(f.key))) {
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
        };

        if (spec.form === 'drawer') {
          this.nsiDrawerOpen(title, this.nsiFormBody(spec, item, parents), onSave);
        } else {
          this.openModal(title, this.nsiFormBody(spec, item, parents), onSave,
            { wide: spec.fields.length > 4 });
        }

        // чекбокс «это группа» скрывает поля элементов (element_fields)
        const grpCb = document.getElementById('nsi-f-is-group');
        if (grpCb) {
          const apply = () => {
            (spec.element_fields || []).forEach(k => {
              const el2 = document.getElementById('nsi-f-' + k);
              if (el2 && el2.parentElement) el2.parentElement.style.display = grpCb.checked ? 'none' : '';
            });
          };
          grpCb.onchange = apply;
          apply();
        }
        // при редактировании группы поля элементов недоступны
        if (item && spec.group_items && item.is_group) {
          (spec.element_fields || []).forEach(k => {
            const el2 = document.getElementById('nsi-f-' + k);
            if (el2 && el2.parentElement) el2.parentElement.style.display = 'none';
          });
        }

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
                    b.onclick = () => { this.nsiCloseForm(); this.nsiEdit(b.getAttribute('data-nsi-dup-open')); };
                  });
                } catch (e) { /* дедуп-чек не критичен */ }
              }, 350);
            });
          }
        }
        this.$nextTick(() => { const el = document.getElementById('nsi-f-name'); if (el) el.focus(); });
      },

      // ---- drawer: боковая панель для форм 7+ полей (контрагенты, номенклатура) ----
      nsiDrawerOpen(title, bodyHtml, onSave) {
        this.nsiDrawerClose();
        const wrap = document.createElement('div');
        wrap.id = 'nsiDrawerWrap';
        wrap.innerHTML = `
          <div class="nsi-drawer-mask"></div>
          <aside class="nsi-drawer">
            <div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--border)">
              <div class="font-semibold text-[15px]">${title}</div>
              <button class="btn text-[12px]" data-nsi-drawer-close title="Закрыть (Esc)">✕</button>
            </div>
            <div class="p-4 overflow-y-auto" style="flex:1 1 auto; min-height:0">${bodyHtml}</div>
            <div class="flex justify-end gap-2 px-4 py-3 border-t" style="border-color:var(--border)">
              <button class="btn" data-nsi-drawer-close>Отмена</button>
              <button class="btn btn-accent" id="nsiDrawerSave">Сохранить</button>
            </div>
          </aside>`;
        document.body.appendChild(wrap);
        wrap.querySelectorAll('[data-nsi-drawer-close]').forEach(b => {
          b.onclick = () => this.nsiDrawerClose();
        });
        wrap.querySelector('.nsi-drawer-mask').onclick = () => this.nsiDrawerClose();
        wrap.querySelector('#nsiDrawerSave').onclick = async () => {
          const r = await onSave();
          if (r !== false) this.nsiDrawerClose();
        };
        this._nsiDrawerEsc = (ev) => { if (ev.key === 'Escape') this.nsiDrawerClose(); };
        document.addEventListener('keydown', this._nsiDrawerEsc);
      },

      nsiDrawerClose() {
        const w = document.getElementById('nsiDrawerWrap');
        if (w) w.remove();
        if (this._nsiDrawerEsc) {
          document.removeEventListener('keydown', this._nsiDrawerEsc);
          this._nsiDrawerEsc = null;
        }
      },

      nsiCloseForm() { this.closeModal(); this.nsiDrawerClose(); },

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

      // ---- слияние дублей (manager): target = golden record ----
      nsiMergeModal() {
        const st = this.nsiState, spec = this.nsiSpec();
        const e = v => this.esc(v == null ? '' : String(v));
        const ids = [...st.sel];
        const items = (st.items || []).filter(i => ids.includes(String(i.id)));
        if (!spec || items.length < 2) { this.toast('Отметьте две и более записи', 'warn'); return; }
        const rows = items.map((i, n) => `
          <label class="card-2 p-2 mb-1 flex items-center gap-2 cursor-pointer text-[13px]">
            <input type="radio" name="nsiMergeTarget" value="${i.id}" ${n === 0 ? 'checked' : ''} />
            <span class="flex-1 truncate">${i.is_group ? '📁 ' : ''}${e(i.name)} <span style="color:var(--text-mute)">${e(i.code || '')}</span></span>
          </label>`).join('');
        this.openModal('Слияние дублей · ' + spec.title, `
          <div class="text-[12px] mb-2" style="color:var(--text-dim)">Целевая запись (отмечена точкой) остаётся без изменений;
          остальные архивируются, их вложенные элементы и связи переезжают к цели.</div>
          ${rows}`,
          async () => {
            const sel = document.querySelector('input[name="nsiMergeTarget"]:checked');
            if (!sel) { this.toast('Выберите целевую запись', 'warn'); return false; }
            const targetId = sel.value;
            const targetItem = items.find(i => String(i.id) === String(targetId));
            const sources = ids.filter(x => x !== targetId).map(x => parseInt(x, 10));
            try {
              const r = await window.AGL.catalogMerge(spec.key, { target_id: parseInt(targetId, 10), source_ids: sources });
              st.sel.clear();
              this.toast(`Слито записей: ${(r && r.merged && r.merged.length) || sources.length} → «${targetItem ? targetItem.name : targetId}»`, 'ok');
              this.nsiLoad();
              return true;
            } catch (e2) {
              this.toast((e2 && e2.message) || 'Ошибка слияния', 'err');
              return false;
            }
          });
      },

      // ---- §45.10: управление типами справочников (admin, фаза 1d) ----

      nsiIsAdmin() {
        const uid = this.currentUserId();
        const u = (this.M.team || []).find(t => String(t.id) === String(uid));
        return !!(u && u.role_key === 'admin');
      },

      // транслитерация RU→EN для автоключа/префикса
      nsiSlug(text) {
        const TR = { а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ё:'e',ж:'zh',з:'z',и:'i',й:'y',к:'k',л:'l',м:'m',
          н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'h',ц:'ts',ч:'ch',ш:'sh',щ:'sch',ъ:'',
          ы:'y',ь:'',э:'e',ю:'yu',я:'ya' };
        const s = String(text || '').trim().toLowerCase().split('')
          .map(ch => TR[ch] !== undefined ? TR[ch] : ch).join('')
          .replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
        return s.slice(0, 32);
      },

      nsiResetSpecs(selectKey) {
        const st = this.nsiState;
        st.loaded = false; st.loadingSpecs = false; st.specs = []; st.err = null;
        if (selectKey) st.type = selectKey;
        this.nsiInit();
      },

      // строка редактора полей типа: label | ключ | тип | обяз. | в таблице | варианты | ✕
      nsiTypeFieldRow(f) {
        const e = v => this.esc(v == null ? '' : String(v));
        f = f || {};
        const types = [['string', 'строка'], ['int', 'целое'], ['decimal', 'число'], ['enum', 'перечисление']];
        return `<div class="nsi-tf-row card-2 p-2 mb-1 flex flex-wrap items-center gap-1">
          <input class="input text-[12px]" data-tf="label" placeholder="Название поля" style="width:150px" value="${e(f.label || '')}">
          <input class="input text-[12px] mono" data-tf="key" placeholder="ключ (авто)" style="width:120px" value="${e(f.key || '')}">
          <select class="input text-[12px]" data-tf="type" style="width:130px">
            ${types.map(([v, l]) => `<option value="${v}" ${f.type === v ? 'selected' : ''}>${l}</option>`).join('')}
          </select>
          <label class="text-[11px] flex items-center gap-1 cursor-pointer" title="Обязательное"><input type="checkbox" data-tf="required" ${f.required ? 'checked' : ''}>обяз.</label>
          <label class="text-[11px] flex items-center gap-1 cursor-pointer" title="Показывать колонку в таблице"><input type="checkbox" data-tf="grid" ${f.grid !== false ? 'checked' : ''}>таблица</label>
          <input class="input text-[12px]" data-tf="options" placeholder="варианты через ," style="width:160px" value="${e(f.options && Array.isArray(f.options) ? f.options.join(',') : (f.options ? Object.keys(f.options).join(',') : ''))}" title="Только для типа «перечисление»">
          <button class="btn text-[11px] py-0.5" data-tf-del title="Убрать поле">✕</button>
        </div>`;
      },

      nsiTypeCollectFields() {
        const rows = [...document.querySelectorAll('.nsi-tf-row')];
        const fields = [];
        for (const r of rows) {
          const get = k => r.querySelector(`[data-tf="${k}"]`);
          const label = (get('label').value || '').trim();
          let key = (get('key').value || '').trim();
          if (!label && !key) continue;               // пустая строка — пропускаем
          if (!key) key = this.nsiSlug(label);
          const type = get('type').value;
          const f = { key, type, label: label || key };
          if (get('required').checked) f.required = true;
          if (get('grid').checked) f.grid = true;
          const opts = (get('options').value || '').trim();
          if (type === 'enum') {
            if (!opts) throw new Error(`Поле «${label || key}» (перечисление): задайте варианты через запятую`);
            f.options = opts.split(',').map(x => x.trim()).filter(Boolean);
          }
          fields.push(f);
        }
        const seen = new Set();
        for (const f of fields) {
          if (seen.has(f.key)) throw new Error(`Ключ поля «${f.key}» повторяется`);
          seen.add(f.key);
        }
        return fields;
      },

      // existing — уже сохранённые поля (при редактировании не меняются)
      nsiTypeModal(existing) {
        const e = v => this.esc(v == null ? '' : String(v));
        const locked = (existing && existing.fields ? existing.fields : [])
          .map(f => `<div class="flex items-center gap-2 text-[12px] py-0.5">
            <span class="pill">${e(f.type)}</span>
            <span class="flex-1 truncate">🔒 ${e(f.label)} <span class="mono" style="color:var(--text-mute)">${e(f.key)}</span>${f.required ? ' <span style="color:var(--err)">*</span>' : ''}</span>
          </div>`).join('');
        const meta = existing ? {
          title: existing.title, group: existing.group, icon: existing.icon,
          prefix: existing.code_prefix,
        } : { title: '', group: 'Мои справочники', icon: '📁', prefix: '' };
        this.openModal(existing ? '✎ Изменить справочник' : '＋ Новый справочник', `
          <label class="block mb-2"><div class="label mb-1">Название <span style="color:var(--err)">*</span></div>
            <input id="nsiTypeTitle" class="input w-full text-[13px]" value="${e(meta.title)}" placeholder="напр. Виноградники" /></label>
          <div class="flex gap-2 mb-2 flex-wrap">
            <label class="block" style="flex:1 1 150px"><div class="label mb-1">Группа в дереве</div>
              <input id="nsiTypeGroup" class="input w-full text-[13px]" value="${e(meta.group)}" /></label>
            <label class="block" style="flex:0 0 80px"><div class="label mb-1">Иконка</div>
              <input id="nsiTypeIcon" class="input w-full text-[13px]" value="${e(meta.icon)}" maxlength="4" /></label>
            <label class="block" style="flex:0 0 110px"><div class="label mb-1">Префикс кода</div>
              <input id="nsiTypePrefix" class="input w-full text-[13px] mono" value="${e(meta.prefix)}" placeholder="авто" maxlength="6" /></label>
          </div>
          <label class="flex items-center gap-2 mb-2 text-[13px] cursor-pointer">
            <input type="checkbox" id="nsiTypeHier" ${existing ? (existing.hierarchical ? 'checked' : '') : 'checked'} />
            <span>Подразделы внутри справочника (группы-папки, напр. «Виноградники» → хозяйства)</span></label>
          <div class="label mb-1">Поля справочника</div>
          <div id="nsiTypeFields">${locked ? `<div class="card-2 p-2 mb-2">${locked}<div class="text-[11px] mt-1" style="color:var(--text-mute)">Существующие поля неизменяемы (в записях уже есть данные) — можно только добавить новые.</div></div>` : ''}</div>
          <button class="btn text-[11px] mb-3" data-nsi-tf-add>＋ Добавить поле</button>
          <div class="text-[11px]" style="color:var(--text-mute)">Код (ПРЕФИКС-0001) и наименование у каждого справочника есть всегда. Типы полей: строка / целое / число / перечисление.</div>
          <div id="nsiTypeErr" class="text-[12px] mt-1" style="color:var(--err)"></div>
        `, async () => {
          const v = id => (document.getElementById(id) || {}).value || '';
          const errEl = document.getElementById('nsiTypeErr');
          const showErr = m => { if (errEl) errEl.textContent = m; this.toast(m, 'err'); };
          const title = v('nsiTypeTitle').trim();
          if (!title) { showErr('Укажите название справочника'); return false; }
          let fields;
          try { fields = this.nsiTypeCollectFields(); }
          catch (er) { showErr(er.message); return false; }
          const payload = {
            title,
            group: v('nsiTypeGroup').trim() || 'Мои справочники',
            icon: v('nsiTypeIcon').trim() || '📁',
            hierarchical: !!(document.getElementById('nsiTypeHier') || {}).checked,
            code_prefix: v('nsiTypePrefix').trim(),
          };
          try {
            if (existing) {
              payload.fields = (existing.fields || []).concat(fields);
              const r = await window.AGL.catalogTypeUpdate(existing.type_id, payload);
              this.toast('Справочник обновлён', 'ok');
              this.nsiResetSpecs(existing.key);
              return true;
            }
            payload.fields = fields;
            const r = await window.AGL.catalogTypeCreate(payload);
            this.toast('Справочник «' + ((r && r.title) || title) + '» создан', 'ok');
            this.nsiResetSpecs(r && r.key);
            return true;
          } catch (er2) {
            showErr((er2 && er2.message) || 'Ошибка сохранения');
            return false;
          }
        }, { wide: true });

        const box = document.getElementById('nsiTypeFields');
        const addRow = f => box.insertAdjacentHTML('beforeend', this.nsiTypeFieldRow(f));
        const addBtn = document.querySelector('[data-nsi-tf-add]');
        if (addBtn) addBtn.onclick = () => addRow({});
        document.querySelectorAll('.nsi-tf-row [data-tf-del]').forEach(b => {
          b.onclick = () => b.closest('.nsi-tf-row').remove();
        });
        // живые обработчики для строк, добавляемых позже
        box.addEventListener('click', ev => {
          const del = ev.target.closest('[data-tf-del]');
          if (del) del.closest('.nsi-tf-row').remove();
        });
        if (!existing) addRow({ label: '', key: '' });
      },

      nsiTypeEdit(id) {
        const st = this.nsiState;
        const spec = (st.specs || []).find(s => s.managed && String(s.type_id) === String(id));
        if (!spec) return;
        this.nsiTypeModal({
          type_id: spec.type_id, key: spec.key, title: spec.title, group: spec.group,
          icon: spec.icon, hierarchical: spec.hierarchical, code_prefix: spec.code_prefix,
          fields: (spec.fields || []).filter(f => !['code', 'name'].includes(f.key)),
        });
      },

      async nsiTypeHist(id) {
        if (!window.AGL || !AGL.token) return;
        const st = this.nsiState;
        const spec = (st.specs || []).find(s => s.managed && String(s.type_id) === String(id));
        try {
          const h = await window.AGL.catalogTypeHistory(id);
          const ACT = { create: '➕ создано', update: '✎ изменено', archive: '🗄 в архив', restore: '↩ из архива' };
          const esc2 = v => String(v == null ? '' : v).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
          const rows = (h.items || []).map(x => {
            const dl = Object.entries(x.diff || {}).map(([k, v]) =>
              `<div class="text-[12px] mt-0.5">${esc2(k)}: <s style="color:var(--text-mute)">${esc2(v && v.old !== null && v.old !== undefined ? (Array.isArray(v.old) ? v.old.join(', ') : v.old) : '—')}</s> → <b>${esc2(v && v.new !== null && v.new !== undefined ? (Array.isArray(v.new) ? v.new.join(', ') : v.new) : '—')}</b></div>`).join('');
            return `<div class="card-2 p-2 mb-1">
              <div class="flex justify-between gap-2 text-[12px]"><b>${ACT[x.action] || esc2(x.action)}</b>
                <span style="color:var(--text-dim)">${esc2(x.user_name || '—')} · ${String(x.created_at || '').slice(0, 16).replace('T', ' ')}</span></div>
              ${dl}</div>`;
          }).join('') || '<div class="text-[13px]" style="color:var(--text-mute)">Изменений ещё не было.</div>';
          this.openModal('История справочника · ' + (spec ? spec.title : id), rows, null, { noFooter: true, wide: true });
        } catch (er) {
          this.toast('Ошибка истории: ' + (er && er.message || ''), 'err');
        }
      },

      async nsiTypeArch(id) {
        if (!window.AGL || !AGL.token) { this.toast('В демо-режиме недоступно', 'warn'); return; }
        const st = this.nsiState;
        const spec = (st.specs || []).find(s => s.managed && String(s.type_id) === String(id));
        if (!spec) return;
        if (!window.confirm(`Переместить справочник «${spec.title}» в архив?\nОн и его записи скроются из дерева (данные сохранятся) — вернуть можно будет из раздела «Архив справочников».`)) return;
        try {
          await window.AGL.catalogTypeArchive(id);
          this.toast('Справочник в архиве', 'ok');
          if (st.type === spec.key) st.type = null;
          this.nsiResetSpecs();
        } catch (er) { this.toast((er && er.message) || 'Ошибка', 'err'); }
      },

      async nsiTypeRestore(id) {
        if (!window.AGL || !AGL.token) return;
        try {
          const r = await window.AGL.catalogTypeRestore(id);
          this.toast('Справочник восстановлен', 'ok');
          this.nsiResetSpecs(r && r.key);
        } catch (er) { this.toast((er && er.message) || 'Ошибка', 'err'); }
      },

      // ---- служебные ----
      nsiSetType(key) {
        const st = this.nsiState;
        st.type = key; st.offset = 0; st.q = ''; st.sel.clear(); st.parent = 'all'; st.groups = [];
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
        el.querySelectorAll('[data-nsi-group]').forEach(n => {
          n.onclick = () => {
            st.parent = n.getAttribute('data-nsi-group');
            st.offset = 0;
            this.nsiLoad();
          };
        });
        const mrg = el.querySelector('[data-nsi-merge]');
        if (mrg) mrg.onclick = () => this.nsiMergeModal();

        // §45.10: управление типами справочников (admin)
        el.querySelectorAll('[data-nsi-type-add]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiTypeModal(null); };
        });
        el.querySelectorAll('[data-nsi-type-edit]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiTypeEdit(n.getAttribute('data-nsi-type-edit')); };
        });
        el.querySelectorAll('[data-nsi-type-hist]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiTypeHist(n.getAttribute('data-nsi-type-hist')); };
        });
        el.querySelectorAll('[data-nsi-type-arch]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiTypeArch(n.getAttribute('data-nsi-type-arch')); };
        });
        el.querySelectorAll('[data-nsi-type-restore]').forEach(n => {
          n.onclick = (ev) => { ev.stopPropagation(); this.nsiTypeRestore(n.getAttribute('data-nsi-type-restore')); };
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
