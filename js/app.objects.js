// ===== AgroPILOT — ЭСКИЗ: ядро (роутер + диспетчер, навигация ОТ ОБЪЕКТОВ) =====
// Экраны дозаписываются в следующих чанках (1.4 Мой день, 1.5 карточка, 1.6 списки, 1.7 ПЕТРУШКА).
console.log('[AgroPILOT] appObjects.js loaded, MOCKO:', typeof window.MOCKO);
function appObjects() {
  return {
    M: window.MOCKO,
    apiMode: false,  // true = data from BFF API, false = mock
    apiData: {},     // cached API data
    _persistKey: 'agropilot_data_v1',
    theme: (function(){ try { var st = window['local'+'Storage']; return (st && st.getItem('agropilot_theme')) || 'light'; } catch(e){ return 'light'; } })(),
    route: 'myday', routeArg: null,
    cmdkOpen: false, cmdkQuery: '',
    clock: '',
    toasts: [],
    owl: { open: false },
    owlGrade: 'all',
    cliQuery: '', cliSort: 'name',
    dealOwner: 'all',
    collapsedStages: {},
    kanbanFilter: { owner: 'all', need: 'all', goal: 'all' },
    kanbanDrag: null,
    // ======== ЧАНК 6.23: BULK-ДЕЙСТВИЯ — раздел 1: state выбора ========
    sel: { deals: new Set(), tasks: new Set() }, // множества id выбранных объектов
    selMode: false,                              // режим мультивыбора (показ чекбоксов)
    mobNav: false,
    _charts: {},

    async _loadAllData() {
      // Don't swallow errors — let 401/403 propagate so loadFromAPI can refresh
      const [deals, goals, tasks, team, packages, artifacts, content, reports, clients] = await Promise.all([
        window.AGL.loadDeals(),
        window.AGL.loadGoals(),
        window.AGL.loadTasks(),
        window.AGL.loadTeam(),
        window.AGL.loadPackages(),
        window.AGL.loadArtifacts(),
        window.AGL.loadContent(),
        window.AGL.loadReports(),
        window.AGL.loadClients(),
      ]);
      return { deals, goals, tasks, team, packages, artifacts, content, reports, clients };
    },

    async loadFromAPI() {
      if (!window.AGL) { console.warn('[AGL] window.AGL not found'); return false; }
      window.AGL.initAuth();
      console.log('[AGL] loadFromAPI: token?', AGL.token ? 'yes (' + AGL.token.substring(0, 20) + '...)' : 'NO');

      // If no token, try to show login
      if (!AGL.token) {
        console.warn('[AGL] no token, showing login');
        const lm = document.getElementById('loginModal');
        if (lm) lm.style.display = 'flex';
        this.apiMode = false;
        return false;
      }

      let tryCount = 0;
      while (tryCount < 2) {
        tryCount++;
        try {
          const data = await this._loadAllData();
          const { deals, goals, tasks, team, packages, artifacts, content, reports, clients } = data;

        // Deals: map BFF fields to mock format
        // BFF: name, stage, region, culture, finance, score, signal, need_type, industry, owner_id, owner_sales, goal_id
        // Mock: title, stage, region, culture, amount, score, signal, need, owner, ownerId, clientId, industry, goalId

        console.log('[AGL] loadFromAPI results: deals=' + (deals?.length||0) + ' goals=' + (goals?.length||0) + ' tasks=' + (tasks?.length||0) + ' team=' + (team?.length||0) + ' packages=' + (packages?.length||0) + ' artifacts=' + (artifacts?.length||0) + ' content=' + (content?.length||0) + ' reports=' + (reports?.length||0) + ' clients=' + (clients?.length||0));

        // If ALL API calls returned empty, keep mock data (don't overwrite MOCKO)
        const allEmpty = [deals, goals, tasks, team, packages, artifacts, content, reports, clients].every(a => !a || a.length === 0);
        if (allEmpty) {
          console.warn('[AGL] all API calls empty, keeping mock data');
          this.apiMode = false;
          return false;
        }

        this.apiData = { deals, goals, tasks, team, packages, artifacts, content, reports, clients };

        // Map BFF format to mock format
        const STAGE_MAP = { lead: 'Зацепка', assess: 'Оценка', proposal: 'Договор', deal: 'Проектирование', won: 'Выиграна', lost: 'Проиграна', service: 'Сервис', cancelled: 'Отменена' };
        const STAGE_REVERSE = Object.fromEntries(Object.entries(STAGE_MAP).map(([k,v]) => [v, k]));
        this.M.deals = (deals || []).map(d => ({
          id: d.id,
          title: d.name,
          stage: STAGE_MAP[d.stage] || d.stage || 'Зацепка',
          amount: d.finance?.budget || d.amount || 0,
          need: d.need_type || d.industry || '',
          owner: d.owner_sales || d.owner_id || '',
          ownerId: d.owner_id || '',
          clientId: d.client_id || '',
          industry: d.industry || '',
          region: d.region || '',
          culture: d.culture || '',
          score: d.score || 0,
          signal: d.signal || null,
          goalId: d.goal_id || '',
          updated: d.updated_at || d.created_at,
          created: d.created_at,
          history: [{ date: d.updated_at || d.created_at, kind: 'create', text: 'Сделка создана' }],
        }));

        this.M.goals = (goals || []).map(g => {
          const metric = typeof g.metric === 'object' ? g.metric : { name: g.metric || '' };
          return {
            id: g.id,
            title: g.title,
            metric: g.description || metric.name || '',
            target: metric.target || g.target || 0,
            unit: metric.unit || g.unit || '',
            current: metric.current || 0,
            period: g.period_start ? `${g.period_start}-${g.period_end}` : '',
            owner: g.owner_id || '',
            kind: g.kind || 'revenue',
            needMatch: g.need_match || [],
            periodStart: g.period_start || '',
            periodEnd: g.period_end || '',
            status: g.status || 'active',
            signal: g.signal || null,
            progress: g.progress || 0,
          };
        });

        this.M.tasks = (tasks || []).map(t => ({
          id: t.id,
          title: t.title,
          status: t.status || 'active',
          assignee: t.assignee || '',
          ownerId: t.owner_id || '',
          goalId: t.goal_id || '',
          due: t.due_at || '',
          priority: t.priority || 'normal',
          dealId: t.deal_id || '',
          updated: t.updated_at || t.created_at,
        }));

        this.M.team = (team || []).map(u => ({
          id: u.id,
          name: u.name,
          role: u.role || '',
          avatar: u.avatar || '',
          cap: u.cap || 5,
          canConfirm: u.can_confirm || false,
        }));

        this.M.clients = (clients || []).map(c => ({
          id: c.id,
          name: c.name,
          industry: c.industry || '',
          region: c.region || '',
          need: c.need || [],
          health: c.health || 'green',
          dealsCount: c.dealsCount || 0,
        }));

        this.M.packages = (packages || []).map(p => ({
          id: p.id,
          title: p.title,
          status: p.status || 'active',
          description: p.description || '',
        }));

        this.M.artifacts = (artifacts || []).map(a => ({
          id: a.id,
          blobUri: a.blob_uri || '',
          type: a.type || '',
          linkedType: a.linked_type || '',
          linkedId: a.linked_id || '',
          title: a.name || a.title || 'Артефакт',
          kind: a.kind || '',
          ext: a.ext || '',
          date: a.date || '',
          status: a.status || '',
        }));

        this.M.content = (content || []).map(c => ({
          id: c.id,
          title: c.title,
          body: c.body || '',
          status: c.status || 'draft',
          channel: c.channel || '',
        }));

        this.M.reports = (reports || []).map(r => ({
          id: r.id,
          summary: r.summary || '',
          author: r.author || '',
          sourceType: r.source_type || '',
          linkedType: r.linked_type || '',
          linkedId: r.linked_id || '',
          created: r.created_at,
        }));

        this.apiMode = true;
        return true;
      } catch (e) {
        const isAuthError = e.message && (e.message.includes('401') || e.message.includes('403'));
        if (isAuthError && tryCount < 2) {
          console.warn('[AGL] auth error on try ' + tryCount + ', attempting refresh...');
          try {
            const refreshed = await AGL.refresh();
            if (refreshed) {
              console.log('[AGL] refresh successful, retrying...');
              continue;
            }
          } catch(refreshErr) {
            console.warn('[AGL] refresh failed:', refreshErr);
          }
          // Refresh failed — clear token and show login
          console.warn('[AGL] refresh failed, clearing token');
          AGL.token = null;
          localStorage.removeItem('agropilot_token');
          localStorage.removeItem('agropilot_refresh');
          const lm = document.getElementById('loginModal');
          if (lm) lm.style.display = 'flex';
        }
        console.warn('[AGL] API load failed, using mock:', e);
        this.apiMode = false;
        return false;
      }
    } // end while
    },

    // ── localStorage persistence ──
    persist() {
      try {
        const data = {
          deals: this.M.deals, clients: this.M.clients, goals: this.M.goals,
          projects: this.M.projects, tasks: this.M.tasks, packages: this.M.packages,
          artifacts: this.M.artifacts, strategy: this.M.strategy,
          owlSuggestions: this.M.owlSuggestions, signals: this.M.signals,
          inbox: this.M.inbox, posts: this.M.posts,
        };
        window.localStorage.setItem(this._persistKey, JSON.stringify(data));
      } catch(e) { console.warn('[persist] failed:', e); }
    },
    restore() {
      try {
        const raw = window.localStorage.getItem(this._persistKey);
        if (!raw) return false;
        const data = JSON.parse(raw);
        if (data.deals) this.M.deals = data.deals;
        if (data.clients) this.M.clients = data.clients;
        if (data.goals) this.M.goals = data.goals;
        if (data.projects) this.M.projects = data.projects;
        if (data.tasks) this.M.tasks = data.tasks;
        if (data.packages) this.M.packages = data.packages;
        if (data.artifacts) this.M.artifacts = data.artifacts;
        if (data.strategy) this.M.strategy = data.strategy;
        if (data.owlSuggestions) this.M.owlSuggestions = data.owlSuggestions;
        if (data.signals) this.M.signals = data.signals;
        if (data.inbox) this.M.inbox = data.inbox;
        if (data.posts) this.M.posts = data.posts;
        console.log('[restore] data loaded from localStorage');
        return true;
      } catch(e) { console.warn('[restore] failed:', e); return false; }
    },

    init() {
      console.log('[AgroPILOT] init() called');
      this.applyTheme();
      // Restore persisted data before anything else
      this.restore();
      this.tick(); setInterval(() => this.tick(), 1000);
      // seed истории по сделкам
      console.log('[AgroPILOT] deals count:', this.M.deals?.length || 0);
      this.M.deals.forEach(d => { if (!d.history) d.history = [{ date: d.updated, kind: 'stage', text: `Стадия: ${d.stage}` }, { date: d.updated, kind: 'create', text: 'Сделка создана' }]; });
      window.addEventListener('hashchange', () => this.parseHash());
      this.parseHash();
      console.log('[AgroPILOT] route:', this.route);
      this.render();

      // Try to load real data from BFF API
      if (window.AGL) {
        this.loadFromAPI().then(ok => {
          if (ok) {
            this.toast('Данные загружены с сервера', 'ok');
            this.render();
            // seed history for API-loaded deals
            this.M.deals.forEach(d => { if (!d.history) d.history = [{ date: d.updated, kind: 'create', text: 'Сделка создана' }]; });
          } else {
            this.toast('Работа в демо-режиме (mock)', 'info');
            // Show login modal if no token
            const lm = document.getElementById('loginModal');
            if (lm && !AGL.token) lm.style.display = 'flex';
          }
        });
      }
      this.$nextTick(() => { const f = document.getElementById('owlInput'); if (f) f.addEventListener('keydown', e => { if (e.key === 'Enter') this.owlAsk(); }); });
      this.$watch('route', () => this.render());
      this.$watch('routeArg', () => this.render());
      // Init resizable splitter
      this.$nextTick(() => this.initSplitter());
      // Init directions management
      this.initDirections();
      // Init project creation
      this.initProjectForm();
      // Init goal status change
      this.initGoalStatus();
      // чанк 3.2 / 6.20: глобальный поиск Ctrl/Cmd-K
      window.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); if (!this.cmdkOpen) this.cmdkShow(); return; }
        if (!this.cmdkOpen) return;
        if (e.key === 'Escape') { e.preventDefault(); this.cmdkClose(); }
        else if (e.key === 'Enter') {
          const first = this.cmdkFirst();
          if (first) { e.preventDefault(); this.cmdkClose(); this.go(first.type, first.id); }
        }
      });
    },
    tick() { this.clock = new Date().toLocaleTimeString('ru-RU'); },
    applyTheme() {
      const r = document.documentElement; r.classList.remove('dark', 'light'); r.classList.add(this.theme);
    },
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      this.applyTheme();
      try { var st = window['local'+'Storage']; if (st) st.setItem('agropilot_theme', this.theme); } catch(e){}
    },
    async logout() {
      if (window.AGL) await window.AGL.logout();
      window.location.reload();
    },

    // ---- routing (объектные маршруты) ----
    parseHash() {
      const h = (location.hash || '#/myday').replace(/^#\//, '').split('/');
      const nr = h[0] || 'myday';
      if (nr !== this.route) this.selClearAll(); // 6.23: сброс выбора при смене route
      this.route = nr; this.routeArg = h[1] || null;
    },
    go(r, arg) { if (r !== this.route) this.selClearAll(); location.hash = '#/' + r + (arg ? '/' + arg : ''); this.route = r; this.routeArg = arg; this.mobNav = false; },

    pageTitle() {
      return ({
        myday: 'Мой день',
        clients: 'Клиенты',
        deals: 'Сделки · Проекты',
        tasks: 'Задачи',
        packages: 'Упаковки',
        artifacts: 'Артефакты',
        graph: 'Граф объектов',
        monitoring: 'Мониторинг рынка',
        client: 'Карточка клиента',
        deal: 'Карточка сделки',
        settings: 'Настройки',
      })[this.route] || 'AgroPILOT';
    },

    // ---- toast ----
    toast(msg, kind = 'ok') {
      const c = { ok: 'var(--ok)', err: 'var(--err)', info: 'var(--info)' }[kind] || 'var(--ok)';
      const i = { ok: '✓', err: '✕', info: 'ℹ' }[kind] || '✓';
      const id = Date.now() + Math.random();
      this.toasts.push({ id, msg, color: c, icon: i });
      setTimeout(() => this.toasts = this.toasts.filter(t => t.id !== id), 3000);
    },

    // ---- helpers (используются экранами) ----
    esc(s) { return String(s ?? '').replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m])); },
    money(n) { return (n / 1000000).toFixed(1).replace('.0', '') + ' млн ₽'; },
    // 6.9-иконка: маскот ПЕТРУШКИ (вместо эмодзи 🌿)
    petIco(px) { const s = px || 18; return `<img src="assets/petrushka_icon.jpg" alt="ПЕТРУШКА" class="inline-block rounded-full object-cover align-text-bottom" style="width:${s}px;height:${s}px" />`; },
    sevColor(s) { return s === 'critical' ? 'var(--err)' : s === 'warning' ? 'var(--warn)' : 'var(--info)'; },
    gradeColor(g) { return g === 'AUTO' ? 'var(--ok)' : g === 'CONFIRM' ? 'var(--warn)' : 'var(--info)'; },
    gradeLabel(g) { return { AUTO: 'Автономно', CONFIRM: 'Черновик на проверку', HINT: 'Подсказка' }[g] || g; },
    healthColor(h) { return h === 'green' ? 'var(--ok)' : h === 'yellow' ? 'var(--warn)' : 'var(--err)'; },
    clientById(id) { return this.M.clients.find(c => c.id === id); },
    clientName(c) { if (!c) return ''; if (typeof c === 'string') return c; return c.name || c.title || c.id || ''; },
    dealById(id) { return this.M.deals.find(d => d.id === id); },
    daysSince(dateStr) { if (!dateStr) return null; const a = new Date(this.M.TODAY), b = new Date(dateStr); return Math.max(0, Math.round((a - b) / 86400000)); },
    toggleStage(st) { this.collapsedStages = { ...this.collapsedStages, [st]: !this.collapsedStages[st] }; this.render(); },

    // ======== ЧАНК 6.23 — раздел 1: хелперы выбора ========
    // kind: 'deals' | 'tasks'. Выбор хранится в Set; сбрасывается при смене route/фильтра.
    selHas(kind, id) { return this.sel[kind] && this.sel[kind].has(id); },
    selCount(kind) { return this.sel[kind] ? this.sel[kind].size : 0; },
    selItems(kind) { return this.sel[kind] ? [...this.sel[kind]] : []; },
    selToggle(kind, id) {
      const s = this.sel[kind]; if (!s) return;
      if (s.has(id)) s.delete(id); else s.add(id);
      this.render();
    },
    selAll(kind, ids) {
      const s = this.sel[kind]; if (!s) return;
      const all = (ids || []).every(id => s.has(id));
      if (all) { (ids || []).forEach(id => s.delete(id)); }       // всё выбрано → снять
      else { (ids || []).forEach(id => s.add(id)); }              // иначе → выбрать всё
      this.render();
    },
    selClear(kind) { if (this.sel[kind]) this.sel[kind].clear(); this.render(); },
    selClearAll() { this.sel.deals.clear(); this.sel.tasks.clear(); }, // без render (вызывается из go/parseHash)
    selDeals() { return this.selItems('deals').map(id => this.dealById(id)).filter(Boolean); },
    selTasks() { return this.selItems('tasks').map(id => this.taskById(id)).filter(Boolean); },
    logDeal(d, kind, text) { if (!d) return; if (!d.history) d.history = []; d.history.unshift({ date: this.M.TODAY, kind, text }); },

    // ---- render dispatcher ----
    render() {
      this.$nextTick(() => {
        const el = document.getElementById('view');
        console.log('[AgroPILOT] render() route:', this.route, 'view el:', !!el);
        if (!el) return;
        let html = '';
        if (this.route === 'myday') html = this.vMyDay4();
        else if (this.route === 'dashboard') html = this.vDashboard();
        else if (this.route === 'inbox') html = this.vInbox();
        else if (this.route === 'goals') html = this.vGoals();
        else if (this.route === 'goal') html = this.vGoalCard(this.routeArg);
        else if (this.route === 'projects') html = this.vProjects();
        else if (this.route === 'project') html = this.vProjectCard(this.routeArg);
        else if (this.route === 'kanban') html = this.vKanban();
        else if (this.route === 'clients') html = this.vClients();
        else if (this.route === 'deals') html = this.vDeals();
        else if (this.route === 'tasks') html = this.vTasks();
        else if (this.route === 'task') html = this.vTaskCard(this.routeArg);
        else if (this.route === 'packages') html = this.vPackages();
        else if (this.route === 'artifacts') html = this.vArtifacts();
        else if (this.route === 'monitoring') html = this.vMonitoring();
        else if (this.route === 'content') html = this.vContent();
        else if (this.route === 'team') html = this.vTeam();
        else if (this.route === 'graph') html = this.vGraph();
        else if (this.route === 'client') html = this.vClientCard(this.routeArg);
        else if (this.route === 'deal') html = this.vDealCard(this.routeArg);
        else if (this.route === 'settings') html = this.vSettings();
        else html = this.stub('Раздел не найден');
        el.innerHTML = `<div class="fade-in">${html}</div>`;
        this.bindView();
        this.owlRender();
      });
    },

    // ---- временные заглушки (заменяются в чанках 1.4-1.7) ----
    stub(name) { return `<div class="card p-8 text-center" style="color:var(--text-mute)">[заглушка] ${this.esc(name)}</div>`; },
    focusTile(label, val, col) {
      return `<div class="card-2 p-3"><div class="text-2xl font-semibold" style="color:${col}">${val}</div><div class="label mt-1">${label}</div></div>`;
    },
    scoreCol(s) { return s >= 80 ? 'var(--err)' : s >= 65 ? 'var(--warn)' : 'var(--text-dim)'; },
    taskTypeIcon(ty) { return ({ call: '☎', email: '✉', meet: '🤝', kp: '📄' }[ty] || '•'); },
    taskStatusLabel(t) { return t.status === 'done' ? 'выполнена' : t.status === 'overdue' ? 'просрочена' : 'открыта'; },
    taskStatusColor(t) { return t.status === 'done' ? 'var(--ok)' : t.status === 'overdue' ? 'var(--err)' : 'var(--text-dim)'; },
    // 5.6: дашборд-метрики (pipeline, средний score, конверсия по стадиям)
    vMetrics() {
      const M = this.M;
      const active = M.deals.filter(d => d.stage !== 'Сервис');
      const pipeline = active.reduce((s, d) => s + (d.amount || 0), 0);
      const avgScore = M.deals.length ? Math.round(M.deals.reduce((s, d) => s + (d.score || 0), 0) / M.deals.length) : 0;
      const won = M.deals.filter(d => ['Реализация', 'Сервис'].includes(d.stage)).length;
      const conv = M.deals.length ? Math.round(won / M.deals.length * 100) : 0;
      // распределение по стадиям
      const byStage = M.STAGES.map(st => ({ st, n: M.deals.filter(d => d.stage === st).length }));
      const maxN = Math.max(1, ...byStage.map(x => x.n));
      const bars = byStage.map(x => `<div class="flex items-center gap-2"><div class="text-[11px] w-[92px] shrink-0" style="color:var(--text-dim)">${x.st}</div><div class="flex-1 h-3 rounded" style="background:var(--border)"><div class="h-3 rounded" style="width:${x.n / maxN * 100}%;background:var(--accent)"></div></div><div class="text-[11px] w-5 text-right" style="color:var(--text-mute)">${x.n}</div></div>`).join('');
      const tile = (val, label) => `<div class="card-2 p-3"><div class="text-xl font-semibold" style="color:var(--accent)">${val}</div><div class="label mt-1">${label}</div></div>`;
      return `<div class="card p-4"><div class="label mb-3">Аналитика воронки</div>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-3">${tile(this.money(pipeline), 'Pipeline (активные)')}${tile(avgScore, 'Средний score')}${tile(conv + '%', 'Конверсия → реализация')}</div>
          <div class="lg:col-span-2 flex flex-col gap-2 justify-center">${bars}</div>
        </div></div>`;
    },
    // ======== ЧАНК 1.4: «МОЙ ДЕНЬ» — 4 ЗОНЫ ========
    vMyDay4() {
      const M = this.M;
      console.log('[AgroPILOT] vMyDay4() M.deals:', M.deals?.length, 'M.tasks:', M.tasks?.length, 'M.TODAY:', M.TODAY);
      const todayTasks = M.tasks.filter(t => t.status !== 'done');
      const overdue = todayTasks.filter(t => t.status === 'overdue');
      const dueToday = todayTasks.filter(t => t.date === M.TODAY && t.status !== 'overdue');
      const hot = todayTasks.filter(t => t.score >= 80);
      const activeDeals = M.deals.filter(d => d.stage !== 'Сервис');
      // Зона 1: Фокус
      const z1 = `<div class="card p-4"><div class="label mb-3">Зона 1 · Фокус дня</div><div class="grid grid-cols-2 lg:grid-cols-4 gap-3">${this.focusTile('Просрочено', overdue.length, 'var(--err)')}${this.focusTile('Горячие', hot.length, 'var(--warn)')}${this.focusTile('На сегодня', dueToday.length, 'var(--info)')}${this.focusTile('Сделок в работе', activeDeals.length, 'var(--accent)')}</div></div>`;
      // Зона 2: Объекты в работе
      const tIcon = t => ({ call: '☎', email: '✉', meet: '🤝', kp: '📄' }[t.type] || '•');
      const rows = [...todayTasks].sort((a, b) => (b.status === 'overdue') - (a.status === 'overdue') || b.score - a.score).map(t => {
        const d = this.dealById(t.dealId), c = this.clientById(t.clientId), od = t.status === 'overdue';
        return `<div class="card-2 p-3 flex items-start gap-3"><span class="text-lg shrink-0">${tIcon(t)}</span><div class="flex-1 min-w-0"><div class="text-sm font-medium leading-snug">${this.esc(t.title)}</div><div class="text-[12px]" style="color:var(--text-dim)"><a class="underline cursor-pointer" data-go="deal:${d ? d.id : ''}">${this.esc(d ? d.title : '')}</a> · <a class="underline cursor-pointer" data-go="client:${c ? c.id : ''}">${this.esc(this.clientName(c))}</a></div></div><div class="flex flex-col items-end gap-1 shrink-0"><span class="pill whitespace-nowrap" style="color:${od ? 'var(--err)' : 'var(--text-dim)'};border-color:${od ? 'var(--err)' : 'var(--border)'}">${od ? 'просрочено' : t.date.slice(5)}</span><span class="pill whitespace-nowrap" style="color:${this.scoreCol(t.score)}">score ${t.score}</span></div></div>`;
      }).join('');
      const z2 = `<div class="card p-4"><div class="flex items-center justify-between mb-3"><div class="label">Зона 2 · Объекты в работе</div><a class="btn text-[12px]" data-go="tasks">Все задачи →</a></div><div class="flex flex-col gap-2">${rows}</div></div>`;
      // Зона 3: Сигналы/риски
      const sig = M.signals.map(s => { const d = this.dealById(s.dealId); return `<div class="card-2 p-3 flex items-start gap-3"><span style="color:${this.sevColor(s.sev)}">●</span><div class="flex-1"><div class="text-sm">${this.esc(s.text)}</div><a class="text-[12px] underline cursor-pointer" style="color:var(--text-dim)" data-go="deal:${d ? d.id : ''}">${this.esc(s.objectTitle)}</a></div><span class="pill" style="color:${this.sevColor(s.sev)};border-color:${this.sevColor(s.sev)}">${s.sev}</span></div>`; }).join('');
      const z3 = `<div class="card p-4"><div class="label mb-3">Зона 3 · Сигналы и риски</div><div class="flex flex-col gap-2">${sig}</div></div>`;
      // Зона 4 (ПЕТРУШКА) перенесена в правую AI-панель (чанк 2.2). Здесь — компактная ссылка.
      const z4 = `<div class="card p-3 flex items-center gap-2 text-[13px]" style="color:var(--text-dim)">${this.petIco(18)} ПЕТРУШКА-модератор и его ${this.owlPending()} подсказок — в панели справа.</div>`;
      // S9: онбординг пустой базы — мастер «Клиент → Источник → Сделка»
      const wiz = (M.clients.length === 0 || M.deals.length === 0) ? this.wizardCard() : '';
      const metrics = wiz ? '' : this.vMetrics();
      return `<div class="grid grid-cols-1 gap-4">${wiz}${z1}${metrics}<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">${z2}${z3}</div>${z4}</div>`;
    },
    // Мастер первого запуска (S9): 3 шага, галочки по факту наличия данных
    wizardCard() {
      const M = this.M;
      const hasCli = M.clients.length > 0, hasSrc = M.sources.length > 0, hasDeal = M.deals.length > 0;
      const step = (done, n, title, desc, btn, attr) => `<div class="card-2 p-3 flex items-center gap-3">
        <span class="text-lg" style="color:${done ? 'var(--ok)' : 'var(--text-mute)'}">${done ? '✔' : n}</span>
        <div class="flex-1 min-w-0"><div class="text-sm font-medium">${title}</div><div class="text-[12px]" style="color:var(--text-dim)">${desc}</div></div>
        <button class="btn ${done ? '' : 'btn-accent'} text-[12px]" ${attr}>${done ? 'Готово' : btn}</button>
      </div>`;
      return `<div class="card p-4" style="border-color:var(--accent)">
        <div class="flex items-center gap-2 mb-1">${this.petIco(18)}<div class="label">Начнём работу</div></div>
        <div class="text-[12px] mb-3" style="color:var(--text-dim)">База пуста. ПЕТРУШКА поможет настроить всё за 3 шага.</div>
        <div class="flex flex-col gap-2">
          ${step(hasCli, 1, 'Добавить первого клиента', 'Укажите название — ПЕТРУШКА автозаполнит карточку', '+ Клиент', 'data-cli-add')}
          ${step(hasSrc, 2, 'Подключить источник мониторинга', 'Сайт/RSS, Telegram, тендеры, ключевые слова', '+ Источник', 'data-src-add')}
          ${step(hasDeal, 3, 'Создать первую сделку', 'ПЕТРУШКА предложит упаковку по отрасли', '+ Сделка', 'data-deal-add')}
        </div>
      </div>`;
    },
    // ======== ЧАНК 1.7: ОРЁЛ — ГЛОБАЛЬНЫЙ DOCK-МОДЕРАТОР ========
    // ПЕТРУШКА = Level-2 модератор НАД объектами (не роутер→агент). Подсказки по объектам, 3 грации.
    owlToggle() { this.owl.open = !this.owl.open; if (this.owl.open) this.$nextTick(() => this.owlRender()); },
    // ===== Goal status change =====
    initGoalStatus() {
      document.addEventListener('change', (e) => {
        const sel = e.target.closest('[data-goal-status]');
        if (sel) {
          const goalId = sel.getAttribute('data-goal-status');
          const newStatus = sel.value;
          const g = this.goalById(goalId);
          if (g) {
            g.status = newStatus;
            this.toast(`Статус цели «${g.title}» → ${newStatus}`, 'ok');
            this.render();
          }
        }
      });
    },
    // ===== Project creation =====
    initProjectForm() {
      document.addEventListener('click', (e) => {
        const addBtn = e.target.closest('[data-proj-add]');
        if (addBtn) { e.preventDefault(); this.addProject(); }
      });
    },
    addProject() {
      if (!this.M.projects) this.M.projects = [];
      const goals = this.M.goals || [];
      const targetGoal = goals.length > 0 ? goals[0].id : '';
      const id = 'PR' + Date.now().toString(36);
      const newProj = {
        id, title: 'Новый проект', goalId: targetGoal, need: '',
        status: 'активен', ownerId: '',
        periodStart: this.M.TODAY || '2026-06-29',
        periodEnd: '2026-12-31', target: 0, dealPin: [],
      };
      this.M.projects.push(newProj);
      this.persist();
      this.toast('Проект создан', 'ok');
      this.render();
    },
    // ===== Directions management =====
    initDirections() {
      document.addEventListener('click', (e) => {
        const addBtn = e.target.closest('[data-dir-add]');
        if (addBtn) { e.preventDefault(); this.addDirection(); return; }
        const delBtn = e.target.closest('[data-dir-del]');
        if (delBtn) {
          e.preventDefault();
          const id = delBtn.getAttribute('data-dir-del');
          if (this.M.strategy && this.M.strategy.directions) {
            this.M.strategy.directions = this.M.strategy.directions.filter(d => d.id !== id);
            this.toast('Направление удалено', 'info');
            this.render();
          }
        }
      });
    },
    addDirection() {
      const title = prompt('Название направления:');
      if (!title || !title.trim()) return;
      if (!this.M.strategy) this.M.strategy = { title: 'Стратегия', horizon: '', directions: [] };
      if (!this.M.strategy.directions) this.M.strategy.directions = [];
      const id = 'D' + Date.now().toString(36);
      const newDir = { id, title: title.trim(), needMatch: [], description: '' };
      this.M.strategy.directions.push(newDir);
      // Also create a corresponding goal
      if (!this.M.goals) this.M.goals = [];
      const goalId = 'G' + Date.now().toString(36);
      this.M.goals.push({
        id: goalId, title: title.trim(), metric: '', target: 0, unit: '',
        period: '', owner: '', kind: 'revenue', needMatch: [],
        periodStart: '', periodEnd: '', directionId: id,
        status: 'active', progress: 0, signal: null,
      });
      this.persist();
      this.toast(`Направление «${title.trim()}» добавлено`, 'ok');
      this.render();
    },
    // ===== Resizable splitter (plain JS) =====
    initSplitter() {
      const sp = document.getElementById('owlSplitter');
      if (!sp) { console.warn('[Splitter] #owlSplitter not found'); return; }
      // Show splitter only on desktop (lg+)
      const mq = window.matchMedia('(min-width: 1024px)');
      const toggleSp = () => { sp.style.display = mq.matches ? 'flex' : 'none'; };
      mq.addEventListener('change', toggleSp);
      toggleSp();
      // Find the owl panel: it's the aside that comes after the splitter div
      let aside = null;
      let el = sp.nextElementSibling;
      while (el) {
        if (el.tagName === 'ASIDE') { aside = el; break; }
        el = el.nextElementSibling;
      }
      if (!aside) { console.warn('[Splitter] aside panel not found after splitter'); return; }
      console.log('[Splitter] init OK, panel width:', aside.offsetWidth);
      // Restore saved width
      const saved = localStorage.getItem('agropilot_owl_width');
      if (saved) aside.style.width = saved + 'px';
      let startX = 0, startW = 0;
      const onDown = (e) => {
        e.preventDefault();
        startX = e.clientX;
        startW = aside.offsetWidth;
        sp.classList.add('owl-active');
        document.body.classList.add('owl-resizing');
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      };
      const onMove = (e) => {
        const delta = startX - e.clientX;
        const w = Math.max(280, Math.min(640, startW + delta));
        aside.style.width = w + 'px';
      };
      const onUp = () => {
        sp.classList.remove('owl-active');
        document.body.classList.remove('owl-resizing');
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        localStorage.setItem('agropilot_owl_width', aside.offsetWidth);
      };
      sp.addEventListener('mousedown', onDown);
    },
    // ===== ЧАНК 2.2: reactive-запрос к Орлу (мок) =====
    // ЧАНК 6.15: ПЕТРУШКА-чат. owlChat эфемерен в Alpine-state (в ТЗ персист истории — будущее расширение).
    // Модель сообщения: {role:'user'|'owl', text, grade?, action?, ts}. Ответы — эвристики на mock (не LLM).
    owlChat: [],
    petTs() { const d = new Date(); return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); },
    owlAsk() {
      const f = document.getElementById('owlInput'); if (!f || !f.value.trim()) return;
      const q = f.value.trim(); f.value = '';
      this.petSend(q);
    },
    async petSend(q) {
      this.owlChat.push({ role: 'user', text: q, ts: this.petTs() });
      // Show typing indicator
      this.owlChat.push({ role: 'owl', text: '⏳ думаю…', ts: this.petTs(), typing: true });
      this.owlRender();
      this.$nextTick(() => { const b = document.getElementById('owlBody'); if (b) b.scrollTop = b.scrollHeight; });
      // Try BFF LLM chat first if API mode
      if (this.apiMode && window.AGL && AGL.token) {
        try {
          const resp = await AGL.orchChat(q);
          // Remove typing indicator
          this.owlChat = this.owlChat.filter(m => !m.typing);
          this.owlChat.push({ role: 'owl', text: resp.reply || resp.text || resp.message || '(пусто)', ts: this.petTs() });
          this.owlRender();
          this.$nextTick(() => { const b = document.getElementById('owlBody'); if (b) b.scrollTop = b.scrollHeight; });
          return;
        } catch(e) {
          console.warn('[Owl] BFF chat failed, using heuristic:', e);
        }
      }
      // Fallback to heuristic
      this.owlChat = this.owlChat.filter(m => !m.typing);
      const reply = this.petReply(q);
      this.owlChat.push(Object.assign({ role: 'owl', ts: this.petTs() }, reply));
      this.owlRender();
      this.$nextTick(() => { const b = document.getElementById('owlBody'); if (b) b.scrollTop = b.scrollHeight; });
    },
    petQuick(cmd) {
      const map = { today: 'Что важно сегодня?', risks: 'Риски по целям', drafts: 'Черновики на проверку', object: 'Сводка по объекту' };
      this.petSend(map[cmd] || cmd);
    },
    // эвристический ответ по ключевым словам + контекст текущего объекта
    petReply(q) {
      const M = this.M;
      const s = (q || '').toLowerCase();
      const oc = this.owlContext();
      // Черновики на проверку (CONFIRM из owlSuggestions)
      if (/черновик|проверк|confirm/.test(s)) {
        const drafts = (M.owlSuggestions || []).filter(o => o.grade === 'CONFIRM');
        if (!drafts.length) return { text: 'Черновиков на проверку нет — всё разобрано.', grade: 'HINT' };
        const o = drafts[0]; const d = this.dealById(o.dealId);
        return { text: `На проверке ${drafts.length} черновик(ов). Ближайший${d ? ' по «' + d.title + '»' : ''}: ${o.text}`, grade: 'CONFIRM', action: { kind: 'owl', owlId: o.id } };
      }
      // Риски по целям
      if (/риск|цел|отста|букс/.test(s)) {
        const risky = (M.goals || []).map(g => ({ g, sg: this.goalSignal(g), pr: this.goalProgress(g) })).filter(x => x.sg.sig === 'behind' || x.sg.sig === 'slow');
        if (!risky.length) return { text: 'Цели в норме — критичного отставания нет.', grade: 'HINT' };
        const lines = risky.map(x => `• ${x.g.title} — ${x.pr.pct}% (${x.sg.label})`).join('\n');
        return { text: `В риске ${risky.length} цел(и):\n${lines}\nРекомендую разобрать сделки без движения.`, grade: 'HINT' };
      }
      // Нагрузка команды
      if (/команд|нагруз|кто занят|перегруз/.test(s)) {
        const team = M.team || [], deals = M.deals || [], tasks = M.tasks || [], projs = M.projects || [];
        const rows = team.map(u => { const l = deals.filter(d => d.owner === u.name && d.stage !== 'Сервис').length + tasks.filter(t => t.owner === u.name && t.status !== 'done').length + projs.filter(p => p.ownerId === u.id && p.status === 'активен').length; return { u, l }; }).sort((a, b) => b.l - a.l);
        const top = rows[0];
        return { text: `Самый загруженный: ${top.u.avatar} ${top.u.name} (${top.l} объектов). Откройте Дашборд → Нагрузка команды.`, grade: 'HINT', action: { kind: 'nav', go: 'dashboard:' } };
      }
      // Сводка по текущему объекту (чанк 6.21: ветки goal/project/task/client/deal)
      if (/свод|объект|сделк/.test(s) || oc.type) {
        if (oc.type === 'deal') {
          const d = oc.obj, c = this.clientById(d.clientId);
          return { text: `Сделка «${d.title}»: клиент ${c ? this.clientName(c) : '—'}, стадия ${d.stage}, сумма ${this.money(d.amount)}, score ${d.score}. Могу подготовить черновик ответа клиенту.`, grade: 'CONFIRM', action: { kind: 'draftReply', dealId: d.id } };
        }
        if (oc.type === 'goal') {
          const g = oc.obj, pr = this.goalProgress(g), sg = this.goalSignal(g);
          const prj = (this.projectsByGoal ? this.projectsByGoal(g) : []).length;
          return { text: `Цель «${g.title}»: прогресс ${pr.pct}% (${sg.label}), проектов ${prj}, связанных сделок ${oc.count}. Рекомендую разобрать сделки без движения по нише.`, grade: 'HINT', action: { kind: 'nav', go: 'goal:' + g.id } };
        }
        if (oc.type === 'project') {
          const p = oc.obj, pr = this.projectProgress(p);
          return { text: `Проект «${p.title}»: прогресс ${pr.pct}%, сделок ${oc.count}, ниша ${p.need || '—'}. Могу показать задачи и артефакты проекта.`, grade: 'HINT', action: { kind: 'nav', go: 'project:' + p.id } };
        }
        if (oc.type === 'task') {
          const t = oc.obj, d = this.dealById(t.dealId);
          const deps = (t.deps || []).length;
          return { text: `Задача «${t.title}»: статус ${t.status}, владелец ${t.owner || '—'}${deps ? ', блокеров ' + deps : ''}${d ? ', сделка «' + d.title + '»' : ''}.`, grade: 'HINT', action: d ? { kind: 'nav', go: 'deal:' + d.id } : null };
        }
        if (oc.type === 'client') {
          const c = oc.obj;
          return { text: `Клиент «${c.name || c.title}»: сделок ${oc.count}${c.niche ? ', ниша ' + c.niche : ''}. Откройте карточку сделки для действий.`, grade: 'HINT' };
        }
        return { text: `Откройте карточку объекта — дам сводку с действиями. Всего сделок: ${(M.deals || []).length}.`, grade: 'HINT' };
      }
      // «Что важно сегодня» и fallback
      const overdue = (M.tasks || []).filter(t => t.status === 'overdue').length;
      const sig = (M.signals || []).length;
      const drafts = (M.owlSuggestions || []).filter(o => o.grade === 'CONFIRM').length;
      if (/важн|сегодн|приорит/.test(s)) {
        return { text: `Сегодня: сигналов ${sig}, просроченных задач ${overdue}, черновиков на проверку ${drafts}. Начните с «Черновики на проверку».`, grade: 'HINT', action: { kind: 'nav', go: 'myday:' } };
      }
      return { text: 'Могу показать: «Что важно сегодня», «Риски по целям», «Черновики на проверку» или сводку по открытой сделке.', grade: 'HINT' };
    },
    owlPending() { return this.M.owlSuggestions.filter(o => o.grade !== 'AUTO').length; },
    // И5: счётчики для бейджей сайдбара
    cntOverdue() { return this.M.tasks.filter(t => t.status === 'overdue').length; },
    cntSignals() { return (this.M.signals || []).length; },
    cntDrafts() { return (this.M.posts || []).filter(p => p.status === 'согласование').length; },
    cntInbox() { return (this.M.inbox || []).filter(i => i.status === 'new').length; },
    // ======== ЧАНК 6.22: ТАЙМЛАЙН АКТИВНОСТИ ОБЪЕКТА — раздел 1: хелпер агрегации ========
    // objActivity(type,id) → отсортированный (новые сверху) массив {date,kind,icon,text}.
    // Агрегирует СУЩЕСТВУЮЩИЕ данные (без нового поля activity[]):
    //   deal.history (create/stage), задачи (по dealId), артефакты (по dealId), owlSuggestions grade=AUTO.
    // goal/project — агрегируют по связанным сделкам (goalDeals/projectDeals).
    // client — по сделкам клиента; deal — сама сделка; task — её сделка (если есть).
    objActivityDealIds(type, id) {
      try {
        const M = this.M;
        if (type === 'deal') return [id];
        if (type === 'task') { const t = this.taskById(id); return t && t.dealId ? [t.dealId] : []; }
        if (type === 'client') return M.deals.filter(d => d.clientId === id).map(d => d.id);
        if (type === 'goal') { const g = this.goalById(id); const ds = (g && this.goalDeals) ? this.goalDeals(g) : []; return ds.map(d => d.id); }
        if (type === 'project') { const p = this.projectById(id); const ds = (p && this.projectDeals) ? this.projectDeals(p) : []; return ds.map(d => d.id); }
      } catch (e) { return []; }
      return [];
    },
    objActivity(type, id) {
      const M = this.M;
      const ev = [];
      let dealIds = [];
      try { dealIds = this.objActivityDealIds(type, id) || []; } catch (e) { dealIds = []; }
      const set = new Set(dealIds);
      const dealLabel = (did) => { const d = this.dealById(did); return d ? d.title : did; };
      const multi = dealIds.length > 1; // для goal/project/client показываем, к какой сделке относится событие
      // 1) deal.history (create/stage)
      dealIds.forEach(did => {
        const d = this.dealById(did); if (!d || !d.history) return;
        d.history.forEach(h => {
          const icon = h.kind === 'stage' ? '🔀' : h.kind === 'create' ? '🆕' : '•';
          const pre = multi ? `[${this.esc(dealLabel(did))}] ` : '';
          ev.push({ date: h.date, kind: h.kind, icon, text: pre + h.text });
        });
      });
      // 2) задачи (создание/срок/статус)
      (M.tasks || []).filter(t => set.has(t.dealId)).forEach(t => {
        const st = t.status === 'done' ? 'выполнена' : t.status === 'overdue' ? 'просрочена' : 'в работе';
        const pre = multi ? `[${this.esc(dealLabel(t.dealId))}] ` : '';
        ev.push({ date: t.date, kind: 'task', icon: '✅', text: `${pre}Задача: ${this.esc(t.title)} — ${st}${t.owner ? ' · ' + this.esc(t.owner) : ''}` });
      });
      // 3) артефакты
      (M.artifacts || []).filter(a => a.dealId && set.has(a.dealId)).forEach(a => {
        const pre = multi ? `[${this.esc(dealLabel(a.dealId))}] ` : '';
        ev.push({ date: a.date, kind: 'artifact', icon: '📄', text: `${pre}Артефакт: ${this.esc(a.kind)} «${this.esc(a.title)}»${a.by ? ' · ' + this.esc(a.by) : ''}` });
      });
      // 4) автодействия ПЕТРУШКИ (только grade=AUTO — свершившееся)
      (M.owlSuggestions || []).filter(o => o.grade === 'AUTO' && set.has(o.dealId)).forEach(o => {
        const pre = multi ? `[${this.esc(dealLabel(o.dealId))}] ` : '';
        ev.push({ date: M.TODAY, kind: 'ai', icon: '🤖', text: `${pre}ПЕТРУШКА: ${this.esc(o.text)}` });
      });
      // сортировка: новые сверху (по дате-строке YYYY-MM-DD), пустые даты — вниз
      ev.sort((a, b) => {
        const da = a.date || '', db = b.date || '';
        return da < db ? 1 : da > db ? -1 : 0;
      });
      return ev;
    },

    // ======== ЧАНК 6.22 — раздел 2: vTimeline(items) — переиспользуемая лента ========
    // items: [{date,kind,icon,text}] (из objActivity). Топ-8, без пагинации.
    // Вертикальная лента: линия слева, точки-иконки, текст + дата.
    vTimeline(items) {
      const list = (items || []).slice(0, 8);
      if (!list.length) return `<div class="text-[13px]" style="color:var(--text-mute)">Активности пока нет</div>`;
      const rows = list.map((it, i) => {
        const last = i === list.length - 1;
        return `<div class="relative pl-7 ${last ? '' : 'pb-3'}">
          ${last ? '' : `<div class="absolute left-[10px] top-5 bottom-0 w-px" style="background:var(--border)"></div>`}
          <div class="absolute left-0 top-0 w-[21px] h-[21px] rounded-full flex items-center justify-center text-[11px]" style="background:var(--accent-soft,rgba(99,102,241,.12));border:1px solid var(--border)">${it.icon || '•'}</div>
          <div class="text-[13px] leading-snug">${this.esc(it.text)}</div>
          <div class="text-[11px]" style="color:var(--text-mute)">${this.esc(it.date || '')}</div>
        </div>`;
      }).join('');
      const more = (items || []).length > 8 ? `<div class="text-[11px] pl-7" style="color:var(--text-mute)">+ ещё ${(items || []).length - 8}</div>` : '';
      return `<div class="relative">${rows}${more}</div>`;
    },
    // Готовый блок-карточка «Активность» для встраивания в карточки объектов.
    activityBlock(type, id) {
      const items = this.objActivity(type, id);
      return `<div class="card p-4"><div class="label mb-3">Активность</div>${this.vTimeline(items)}</div>`;
    },

    // ======== ЧАНК 6.21: КОНТЕКСТ ПЕТРУШКИ ПО ROUTE/ОБЪЕКТУ — раздел 1: хелпер ========
    // Возвращает {type,id,obj,icon,label,sub,count} по текущему route.
    // type: 'goal'|'project'|'client'|'deal'|'task'|null (null = общий контекст «Все объекты»).
    owlContext() {
      const r = this.route, a = this.routeArg;
      const all = () => ({ type: null, id: null, obj: null, icon: '🗂', label: 'Все объекты', sub: `${this.M.deals.length} сделок`, count: this.M.deals.length });
      if (!a) return all();
      try {
        if (r === 'goal') {
          const g = this.goalById(a); if (!g) return all();
          const deals = this.goalDeals ? this.goalDeals(g) : [];
          const pr = (this.goalProgress ? this.goalProgress(g) : { pct: 0 });
          return { type: 'goal', id: g.id, obj: g, icon: '🎯', label: 'Цель: ' + g.title, sub: `Сделок: ${deals.length} · Прогресс: ${pr.pct}%`, count: deals.length };
        }
        if (r === 'project') {
          const p = this.projectById(a); if (!p) return all();
          const deals = this.projectDeals ? this.projectDeals(p) : [];
          const pr = (this.projectProgress ? this.projectProgress(p) : { pct: 0 });
          return { type: 'project', id: p.id, obj: p, icon: '📁', label: 'Проект: ' + p.title, sub: `Сделок: ${deals.length} · Прогресс: ${pr.pct}%`, count: deals.length };
        }
        if (r === 'client') {
          const c = this.clientById(a); if (!c) return all();
          const deals = this.M.deals.filter(d => d.clientId === c.id);
          return { type: 'client', id: c.id, obj: c, icon: '👤', label: 'Клиент: ' + (c.name || c.title || ''), sub: `Сделок: ${deals.length}${c.niche ? ' · ' + c.niche : ''}`, count: deals.length };
        }
        if (r === 'deal') {
          const d = this.dealById(a); if (!d) return all();
          const c = this.clientById(d.clientId);
          return { type: 'deal', id: d.id, obj: d, icon: '🤝', label: 'Сделка: ' + d.title, sub: `${c ? (c.name || c.title) : ''}${d.stage ? ' · ' + d.stage : ''}`, count: 1 };
        }
        if (r === 'task') {
          const t = this.taskById(a); if (!t) return all();
          return { type: 'task', id: t.id, obj: t, icon: '✅', label: 'Задача: ' + t.title, sub: `${t.status || ''}${t.owner ? ' · ' + t.owner : ''}`, count: 1 };
        }
      } catch (e) { return all(); }
      return all();
    },

    // ======== ЧАНК 6.21 — раздел 3: контекстные подсказки ========
    // Набор dealId, относящихся к текущему контексту.
    owlContextDealIds() {
      const oc = this.owlContext();
      if (!oc.type) return null; // null = общий контекст (все)
      try {
        if (oc.type === 'deal') return [oc.id];
        if (oc.type === 'task') { const t = oc.obj; return t && t.dealId ? [t.dealId] : []; }
        if (oc.type === 'client') return this.M.deals.filter(d => d.clientId === oc.id).map(d => d.id);
        if (oc.type === 'goal') { const ds = this.goalDeals ? this.goalDeals(oc.obj) : []; return ds.map(d => d.id); }
        if (oc.type === 'project') { const ds = this.projectDeals ? this.projectDeals(oc.obj) : []; return ds.map(d => d.id); }
      } catch (e) { return null; }
      return null;
    },
    // Разбивка подсказок: {related:[], other:[]} по контексту (учёт фильтра грифа — снаружи).
    owlSuggestionsCtx() {
      const ids = this.owlContextDealIds();
      const all = this.M.owlSuggestions || [];
      if (ids === null) return { related: all.slice(), other: [] };
      const set = new Set(ids);
      const related = all.filter(o => set.has(o.dealId));
      const other = all.filter(o => !set.has(o.dealId));
      return { related, other };
    },

    owlRender() {
      const b = document.getElementById('owlBody'); if (!b) return;
      // --- разбивка подсказок по контексту (чанк 6.21) ---
      const sug = this.owlSuggestionsCtx();
      const gf = this.owlGrade; // 'all' | grade
      const byGrade = arr => gf === 'all' ? arr : arr.filter(o => o.grade === gf);
      const related = byGrade(sug.related);
      const other = byGrade(sug.other);
      // --- контекст-шапка из owlContext() (чанк 6.21) ---
      const oc = this.owlContext();
      const ocSub = oc.type
        ? `<div class="text-[11px]" style="color:var(--text-dim)">${this.esc(oc.sub)}</div>`
        : `<div class="text-[11px]" style="color:var(--text-dim)">${this.esc(oc.sub)} · откройте карточку — подсказки станут точнее</div>`;
      const head = `<div class="card-2 p-3 mb-3"><div class="label mb-1">${oc.type ? 'Контекст объекта' : 'Контекст'}</div><div class="text-[13px] font-medium flex items-start gap-1.5"><span>${oc.icon}</span><span class="flex-1" style="min-width:0">${this.esc(oc.label)}</span></div>${ocSub}</div><div class="label mb-2">Подсказки ПЕТРУШКА (proactive)</div>`;
      // --- фильтр по грейду автономии (счёт по связанным) ---
      const cnt = g => sug.related.filter(o => g === 'all' || o.grade === g).length;
      const gchip = (g, label) => `<button class="pill cursor-pointer" data-owl-grade="${g}" style="${this.owlGrade === g ? 'background:var(--accent-soft);color:var(--accent);border-color:var(--accent)' : 'color:var(--text-mute)'}">${label} · ${cnt(g)}</button>`;
      const gfilter = `<div class="flex flex-wrap gap-1 mb-3">${gchip('all', 'Все')}${gchip('AUTO', 'Авто')}${gchip('CONFIRM', 'Черновик')}${gchip('HINT', 'Подсказка')}</div>`;
      const renderSug = o => {
        const d = this.dealById(o.dealId);
        const actions = o.grade === 'AUTO'
          ? `<span class="text-[12px]" style="color:var(--ok)">✓ выполнено автоматически</span>`
          : `<button class="btn btn-accent text-[12px]" data-owl-ok="${o.id}">Принять</button><button class="btn text-[12px]" data-owl-no="${o.id}">Отклонить</button>`;
        return `<div class="card-2 p-3 mb-2"><div class="flex items-center gap-2 mb-1"><span class="pill" style="color:${this.gradeColor(o.grade)};border-color:${this.gradeColor(o.grade)}">${this.gradeLabel(o.grade)}</span><a class="text-[11px] underline cursor-pointer" style="color:var(--text-dim)" data-go="deal:${o.dealId}">${this.esc(d ? d.title : '')}</a></div><div class="text-[13px] mb-2">${this.esc(o.text)}</div><div class="flex gap-2">${actions}</div></div>`;
      };
      const ctxActive = !!oc.type;
      let items;
      if (!related.length && !(ctxActive && other.length)) {
        items = `<div class="text-[13px]" style="color:var(--text-mute)">Нет активных подсказок</div>`;
      } else {
        items = related.length ? related.map(renderSug).join('') : (ctxActive ? `<div class="text-[13px] mb-2" style="color:var(--text-mute)">По этому объекту подсказок нет</div>` : '');
        if (ctxActive && other.length) {
          items += `<div class="label mt-3 mb-2" style="opacity:.8">Прочее · ${other.length}</div>` + other.map(renderSug).join('');
        }
      }
      // --- диалог (reactive, 6.15: грифы + действия) ---
      const chat = this.owlChat.length
        ? `<div class="label mt-4 mb-2">Диалог с ПЕТРУШКОЙ</div>` + this.owlChat.map((m, idx) => {
            if (m.role === 'user') {
              return `<div class="text-[13px] mb-2 text-right"><span class="card-2 inline-block px-2 py-1 text-left" style="background:var(--accent-soft);border-color:var(--accent);white-space:pre-wrap">${this.esc(m.text)}</span>${m.ts ? `<div class="text-[10px] mt-0.5" style="color:var(--text-mute)">${m.ts}</div>` : ''}</div>`;
            }
            // typing indicator
            if (m.typing) {
              return `<div class="card-2 p-2.5 mb-2" style="opacity:.7">
                <div class="flex items-center gap-2"><span style="font-size:14px">${this.petIco(15)}</span><span class="text-[13px]" style="color:var(--text-mute)">${this.esc(m.text)}</span></div>
              </div>`;
            }
            // ответ ПЕТРУШКИ с грифом и действиями
            const gr = m.grade || 'HINT';
            const grCol = this.gradeColor(gr);
            let actBtns = '';
            if (m.done) {
              actBtns = `<div class="text-[12px] mt-1" style="color:${m.done === 'ok' ? 'var(--ok)' : 'var(--text-mute)'}">${m.done === 'ok' ? '✓ принято' : '✕ отклонено'}</div>`;
            } else if (gr === 'CONFIRM') {
              actBtns = `<div class="flex gap-2 mt-2"><button class="btn btn-accent text-[12px]" data-pet-ok="${idx}">Принять</button><button class="btn text-[12px]" data-pet-no="${idx}">Отклонить</button></div>`;
            } else if (m.action && m.action.kind === 'nav') {
              actBtns = `<div class="flex gap-2 mt-2"><button class="btn text-[12px]" data-pet-nav="${idx}">Перейти →</button><button class="btn text-[12px]" data-pet-ok2="${idx}">Понятно</button></div>`;
            } else {
              actBtns = `<div class="mt-1"><button class="btn text-[12px]" data-pet-ok2="${idx}">Понятно</button></div>`;
            }
            return `<div class="card-2 p-2.5 mb-2">
              <div class="flex items-center gap-2 mb-1"><span style="font-size:14px">${this.petIco(15)}</span><span class="pill text-[10px]" style="color:${grCol};border-color:${grCol}">${this.gradeLabel(gr)}</span>${m.ts ? `<span class="text-[10px] ml-auto" style="color:var(--text-mute)">${m.ts}</span>` : ''}</div>
              <div class="text-[13px]" style="white-space:pre-wrap">${this.esc(m.text)}</div>
              ${actBtns}
            </div>`;
          }).join('')
        : `<div class="label mt-4 mb-1">Диалог с ПЕТРУШКОЙ</div><div class="text-[12px]" style="color:var(--text-mute)">Задайте вопрос или выберите команду ниже.</div>`;
      b.innerHTML = head + gfilter + items + chat;
      // привязка обработчиков внутри dock
      b.querySelectorAll('[data-owl-grade]').forEach(n => n.onclick = () => { this.owlGrade = n.getAttribute('data-owl-grade'); this.owlRender(); });
      b.querySelectorAll('[data-go]').forEach(n => n.onclick = () => { const [r, a] = n.getAttribute('data-go').split(':'); this.go(r, a || null); });
      b.querySelectorAll('[data-owl-ok]').forEach(n => n.onclick = () => { const id = n.getAttribute('data-owl-ok'); this.owlApply(id); });
      b.querySelectorAll('[data-owl-no]').forEach(n => n.onclick = () => { const id = n.getAttribute('data-owl-no'); this.M.owlSuggestions = this.M.owlSuggestions.filter(o => o.id !== id); this.toast('Подсказка отклонена', 'info'); this.render(); });
      // 6.15: действия в ленте чата
      b.querySelectorAll('[data-pet-ok]').forEach(n => n.onclick = () => this.petAct(+n.getAttribute('data-pet-ok'), 'ok'));
      b.querySelectorAll('[data-pet-no]').forEach(n => n.onclick = () => this.petAct(+n.getAttribute('data-pet-no'), 'no'));
      b.querySelectorAll('[data-pet-ok2]').forEach(n => n.onclick = () => this.petAct(+n.getAttribute('data-pet-ok2'), 'ok'));
      b.querySelectorAll('[data-pet-nav]').forEach(n => n.onclick = () => this.petAct(+n.getAttribute('data-pet-nav'), 'nav'));
      b.querySelectorAll('[data-pet-quick]').forEach(n => n.onclick = () => this.petQuick(n.getAttribute('data-pet-quick')));
    },
    // 6.15: обработка кнопок сообщения ПЕТРУШКИ (Принять/Отклонить/Понятно/Перейти)
    petAct(idx, kind) {
      const m = this.owlChat[idx]; if (!m || m.role !== 'owl') return;
      const act = m.action || {};
      if (kind === 'nav' && act.go) { const [r, a] = act.go.split(':'); this.go(r, a || null); return; }
      if (kind === 'ok') {
        // связанный черновик owlSuggestions — применить реально
        if (act.kind === 'owl' && act.owlId) { this.owlApply(act.owlId); }
        else if (act.kind === 'draftReply') { this.toast('Черновик ответа подготовлен (эскиз)', 'ok'); }
        else { this.toast('Принято', 'ok'); }
        m.done = 'ok';
      } else if (kind === 'no') {
        m.done = 'no'; this.toast('Отклонено', 'info');
      }
      this.owlRender();
    },

    // ======== ЧАНК 3.3: РАБОЧИЕ ДЕЙСТВИЯ ОРЛА (Принять меняет объекты) ========
    owlApply(id) {
      const o = this.M.owlSuggestions.find(x => x.id === id); if (!o) return;
      const d = this.dealById(o.dealId);
      let msg = o.okMsg || 'Подсказка принята';
      if (o.action === 'task' && d) {
        const tid = 'T' + (this.M.tasks.length + 1) + '_' + Date.now() % 1000;
        this.M.tasks.unshift({ id: tid, dealId: d.id, clientId: d.clientId, title: o.taskTitle || 'Задача от ПЕТРУШКА', type: o.taskType || 'call', date: this.M.TODAY, owner: d.owner || '—', score: 70, status: 'open' });
        this.logDeal(d, 'task', `ПЕТРУШКА: создана задача «${o.taskTitle || 'Задача'}»`);
      } else if (o.action === 'stage' && d) {
        const i = this.M.STAGES.indexOf(d.stage);
        if (i >= 0 && i < this.M.STAGES.length - 1) { const from = d.stage; d.stage = this.M.STAGES[i + 1]; d.updated = this.M.TODAY; msg = o.okMsg || `Сделка переведена в «${d.stage}»`; this.logDeal(d, 'stage', `ПЕТРУШКА: ${from} → ${d.stage}`); }
      } else if (o.action === 'package' && d) {
        d.packageName = o.packageName || ''; msg = o.okMsg || `Упаковка применена к сделке`; this.logDeal(d, 'package', `ПЕТРУШКА: применена упаковка «${o.packageName || ''}»`);
      } else if (o.action === 'newdeal') {
        this.M.owlSuggestions = this.M.owlSuggestions.filter(x => x.id !== id);
        this.toast(msg, 'ok');
        this.dealAddModal(o.clientId || null);
        return;
      }
      this.M.owlSuggestions = this.M.owlSuggestions.filter(x => x.id !== id);
      this.persist();
      this.toast(msg, 'ok');
      this.render();
    },

    // ======== ЧАНК 1.6: СПИСКИ ОБЪЕКТОВ ========
    vClients() {
      // И1: поиск + сортировка
      const q = this.cliQuery.trim().toLowerCase();
      const healthRank = { red: 0, yellow: 1, green: 2 };
      let list = this.M.clients.filter(c => !q
        || c.name.toLowerCase().includes(q)
        || (c.industry || '').toLowerCase().includes(q)
        || (c.region || '').toLowerCase().includes(q)
        || (c.need || []).join(' ').toLowerCase().includes(q));
      list = [...list].sort((a, b) => {
        if (this.cliSort === 'deals') return (b.dealsCount || 0) - (a.dealsCount || 0);
        if (this.cliSort === 'health') return (healthRank[a.health] ?? 9) - (healthRank[b.health] ?? 9);
        return a.name.localeCompare(b.name, 'ru');
      });
      const rows = list.map(c => `<div class="card-2 p-3 flex items-center gap-3 cursor-pointer" data-go="client:${c.id}"><span style="color:${this.healthColor(c.health)}">●</span><div class="flex-1 min-w-0"><div class="text-sm font-medium">${this.esc(c.name)}</div><div class="text-[12px]" style="color:var(--text-dim)">${c.industry} · ${c.region} · контакт: ${this.esc(c.contact || '—')}</div></div><div class="flex flex-wrap gap-1">${c.need.map(n => `<span class="pill">${n}</span>`).join('')}</div><span class="pill">${c.dealsCount} сдел.</span></div>`).join('') || this.empty();
      const sortBtn = (key, label) => `<button class="btn text-[12px] ${this.cliSort === key ? 'btn-accent' : ''}" data-cli-sort="${key}">${label}</button>`;
      return `<div class="card p-4">
        <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
          <div class="label">Клиенты · ${list.length}${q ? ' из ' + this.M.clients.length : ''}</div>
          <div class="flex gap-2"><button class="btn text-[13px]" data-cli-import>Импорт CSV</button><button class="btn btn-accent text-[13px]" data-cli-add>+ Клиент</button></div>
        </div>
        <div class="flex items-center gap-2 mb-3 flex-wrap">
          <input id="cliSearch" class="input flex-1 min-w-[180px] text-[13px]" placeholder="Поиск: название, отрасль, регион, потребность…" value="${this.esc(this.cliQuery)}" />
          <span class="text-[12px]" style="color:var(--text-mute)">сорт:</span>${sortBtn('name', 'А→Я')}${sortBtn('deals', 'По сделкам')}${sortBtn('health', 'По риску')}
        </div>
        <div class="flex flex-col gap-2">${rows}</div>
      </div>`;
    },
    // ===== ЧАНК 2.4: добавление клиента =====
    // Сценарий: продажник вводит только название → ПЕТРУШКА «проводит поиск» и автозаполняет (мок).
    cliAddModal() {
      this.openModal('Новый клиент', `
        <label class="label">Название фирмы (минимум)</label>
        <input id="m_name" class="input w-full mb-2" placeholder="напр. ООО «АгроСтарт»" />
        <div class="card-2 p-2 text-[12px] mb-2" style="color:var(--text-dim)">${this.petIco(15)} ПЕТРУШКА проведёт поиск и автозаполнит отрасль, регион, контакт и потребности. Поля можно поправить в карточке.</div>
      `, () => {
        const name = document.getElementById('m_name').value.trim();
        if (!name) { this.toast('Укажите название', 'err'); return false; }
        const c = this.cliAutofill(name);
        this.M.clients.push(c);
        this.persist();
        this.toast('ПЕТРУШКА автозаполнил карточку', 'ok');
        // S3: открыть карточку + предложить сделку
        this.M.owlSuggestions.unshift({ id: 'O' + Date.now(), dealId: '', grade: 'HINT', text: `Новый клиент «${this.clientName(c)}» — создать первую сделку-проект?`, action: 'newdeal', clientId: c.id, okMsg: 'Открываю создание сделки' });
        this.go('client', c.id);
        return true;
      });
    },
    // мок-«поиск»: детерминированное автозаполнение по названию
    cliAutofill(name) {
      const h = Math.abs([...name].reduce((a, ch) => a + ch.charCodeAt(0), 0));
      const ind = this.M.IND[h % this.M.IND.length];
      const regions = ['Крым', 'Кубань', 'Ростов', 'Севастополь', 'Ставрополье'];
      const needs = this.M.NEED;
      const id = 'C' + (this.M.clients.length + 1) + '_' + (h % 97);
      return { id, name, industry: ind, region: regions[h % regions.length], contact: 'уточнить', need: [needs[h % needs.length]], health: ['green', 'yellow', 'red'][h % 3], dealsCount: 0 };
    },
    // импорт CSV: name,industry,region,contact,need(; )
    cliImportModal() {
      this.openModal('Импорт клиентов (CSV)', `
        <label class="label">Строки CSV: name,industry,region,contact,need</label>
        <textarea id="m_csv" class="input w-full" rows="6" placeholder="ООО Рост,зерновые,Ростов,Иванов,логистика"></textarea>
        <div class="text-[11px] mt-1" style="color:var(--text-mute)">По строке на клиента. need можно через ; </div>
      `, () => {
        const raw = document.getElementById('m_csv').value.trim();
        if (!raw) { this.toast('Пусто', 'err'); return false; }
        let n = 0;
        raw.split(/\n/).forEach(line => {
          const p = line.split(','); if (!p[0] || !p[0].trim()) return;
          this.M.clients.push({ id: 'C' + (this.M.clients.length + 1) + '_imp', name: p[0].trim(), industry: (p[1] || '').trim() || '—', region: (p[2] || '').trim() || '—', contact: (p[3] || '').trim() || '—', need: (p[4] || '').split(';').map(s => s.trim()).filter(Boolean), health: 'yellow', dealsCount: 0 });
          n++;
        });
        this.toast(`Импортировано: ${n}`, 'ok');
        this.persist();
        this.render();
        return true;
      });
    },
    // ======== ЧАНК 2.5: ДОБАВЛЕНИЕ СДЕЛКИ-ПРОЕКТА (S6) ========
    // Два входа: из карточки клиента (presetClientId) и из раздела Сделки.
    dealAddModal(presetClientId) {
      const cliOpts = this.M.clients.map(c => `<option value="${c.id}" ${c.id === presetClientId ? 'selected' : ''}>${this.esc(c.name)}</option>`).join('');
      const needOpts = this.M.NEED.map(n => `<option value="${n}">${n}</option>`).join('');
      this.openModal('Новая сделка-проект', `
        <label class="label">Клиент</label>
        <select id="m_cli" class="input w-full mb-2">${cliOpts}</select>
        <label class="label">Название</label>
        <input id="m_title" class="input w-full mb-2" placeholder="напр. Система орошения, 80 га" />
        <div class="flex gap-2 mb-2">
          <div class="flex-1"><label class="label">Потребность</label><select id="m_need" class="input w-full">${needOpts}</select></div>
          <div class="flex-1"><label class="label">Сумма, ₽</label><input id="m_amt" type="number" class="input w-full" placeholder="0" /></div>
        </div>
        <div class="card-2 p-2 text-[12px]" style="color:var(--text-dim)">Стартовая стадия: <b>Зацепка</b>. ${this.petIco(15)} ПЕТРУШКА подберёт упаковку по отрасли + потребности.</div>
      `, () => {
        const clientId = document.getElementById('m_cli').value;
        const title = document.getElementById('m_title').value.trim();
        const need = document.getElementById('m_need').value;
        const amount = parseInt(document.getElementById('m_amt').value, 10) || 0;
        if (!title) { this.toast('Укажите название', 'err'); return false; }
        const cl = this.clientById(clientId);
        const id = 'D' + (this.M.deals.length + 1) + '_' + Date.now() % 1000;
        const d = { id, clientId, title, stage: 'Зацепка', amount, need, owner: '—', updated: this.M.TODAY, score: 50, history: [{ date: this.M.TODAY, kind: 'create', text: 'Сделка создана (Зацепка)' }] };
        this.M.deals.push(d);
        if (cl) cl.dealsCount = (cl.dealsCount || 0) + 1;
        this.persist();
        this.toast('Сделка создана (Зацепка)', 'ok');
        // S6: ПЕТРУШКА предлагает упаковку по industry + need
        this.dealSuggestPackage(d, cl);
        this.go('deal', id);
        return true;
      });
    },
    // Подбор упаковки: сначала industry+need, иначе по need
    dealSuggestPackage(d, cl) {
      const ind = cl ? cl.industry : null;
      let pk = this.M.packages.find(p => p.need === d.need && p.industry === ind)
            || this.M.packages.find(p => p.need === d.need);
      if (pk) {
        this.M.owlSuggestions.unshift({ id: 'O' + Date.now(), dealId: d.id, grade: 'HINT', text: `Подходит упаковка «${pk.name}» (от ${this.money(pk.priceFrom)}, ${pk.ready}) — применить к сделке?`, action: 'package', packageName: pk.name, okMsg: `Упаковка «${pk.name}» применена к сделке` });
      } else {
        this.M.owlSuggestions.unshift({ id: 'O' + Date.now(), dealId: d.id, grade: 'HINT', text: `Готовой упаковки по «${d.need}» нет — собрать концепцию?`, action: 'task', taskTitle: `Собрать концепцию: ${d.need}`, taskType: 'kp', okMsg: 'Создана задача «Собрать концепцию»' });
      }
    },
    // Сделки — канбан по стадиям (И4: фильтр по ответственному + итоги по стадиям)
    vDeals() {
      const owners = [...new Set(this.M.deals.map(d => d.owner).filter(Boolean))];
      const flt = this.dealOwner === 'all' ? this.M.deals : this.M.deals.filter(d => d.owner === this.dealOwner);
      const cols = this.M.STAGES.map(st => {
        const ds = flt.filter(d => d.stage === st);
        const sum = ds.reduce((s, d) => s + (d.amount || 0), 0);
        const collapsed = !!this.collapsedStages[st];
        const cards = ds.map(d => { const c = this.clientById(d.clientId); const dn = this.daysSince(d.updated); const cold = dn != null && dn >= 5; const touch = dn != null ? `<span class="text-[10px] whitespace-nowrap" style="color:${cold ? 'var(--err)' : 'var(--text-mute)'}">${dn === 0 ? 'сегодня' : dn + ' дн. без касаний'}</span>` : ''; return `<div class="card-2 p-2 cursor-grab active:cursor-grabbing relative ${this.selHas('deals', d.id) ? 'ring-2' : ''}" style="${this.selHas('deals', d.id) ? 'box-shadow:0 0 0 2px var(--accent) inset' : ''}" draggable="true" data-deal-drag="${d.id}" data-go="deal:${d.id}"><label class="absolute top-1 right-1 z-10 flex items-center" data-deal-sel="${d.id}" title="Выбрать" style="cursor:pointer"><input type="checkbox" ${this.selHas('deals', d.id) ? 'checked' : ''} style="width:15px;height:15px;cursor:pointer" /></label><div class="text-[13px] font-medium leading-tight pr-5">${this.esc(d.title)}</div><div class="text-[11px] mt-1" style="color:var(--text-dim)">${this.esc(this.clientName(c))}</div><div class="flex items-center justify-between mt-1"><span class="text-[11px]" style="color:var(--text-mute)">${this.money(d.amount)}</span><span class="text-[11px]" style="color:${this.scoreCol(d.score)}">${d.score}</span></div><div class="mt-1">${touch}</div></div>`; }).join('') || `<div class="text-[11px]" style="color:var(--text-mute)">—</div>`;
        const body = collapsed ? '' : `<div class="text-[11px] mb-2" style="color:var(--text-dim)">${this.money(sum)}</div><div class="flex flex-col gap-2 min-h-[40px]">${cards}</div>`;
        const width = collapsed ? 'w-[44px] min-w-[44px]' : 'flex-1 min-w-[160px]';
        const hdr = collapsed
          ? `<button class="label w-full text-left" data-stage-toggle="${this.esc(st)}" title="${this.esc(st)} · ${ds.length}">▸ ${ds.length}</button>`
          : `<button class="label w-full text-left mb-1 flex items-center justify-between" data-stage-toggle="${this.esc(st)}"><span>${st} · ${ds.length}</span><span style="color:var(--text-mute)">▾</span></button>`;
        return `<div class="${width} rounded-lg p-1 transition-colors" data-stage-drop="${this.esc(st)}">${hdr}${body}</div>`;
      }).join('');
      const total = flt.reduce((s, d) => s + (d.amount || 0), 0);
      const chip = (val, label) => `<button class="btn text-[12px] ${this.dealOwner === val ? 'btn-accent' : ''}" data-deal-owner="${val}">${label}</button>`;
      const chips = chip('all', 'Все') + owners.map(o => chip(o, o)).join('');
      return `<div class="card p-4">
        <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
          <div class="label">Воронка · ${flt.length} сделок · ${this.money(total)}</div>
          <div class="flex items-center gap-2">
            <button class="btn text-[12px] ${this.selCount('deals') ? 'btn-accent' : ''}" data-deal-selall title="Выбрать/снять все видимые">☑ Выбрать видимые${this.selCount('deals') ? ' · ' + this.selCount('deals') : ''}</button>
            <button class="btn btn-accent text-[13px]" data-deal-add>+ Сделка</button>
          </div>
        </div>
        <div class="flex items-center gap-2 mb-3 flex-wrap"><span class="text-[12px]" style="color:var(--text-mute)">ответственный:</span>${chips}</div>
        <div class="flex gap-3 overflow-x-auto pb-2">${cols}</div>
      </div>${this.bulkBar('deals')}`;
    },
    // И12: перенос карточки сделки между стадиями (drag-and-drop)
    dragDealId: null,
    moveDeal(dealId, stage) {
      const d = this.dealById(dealId);
      if (!d || !this.M.STAGES.includes(stage) || d.stage === stage) return;
      const from = d.stage;
      d.stage = stage; d.updated = this.M.TODAY;
      this.logDeal(d, 'stage', `Стадия: ${from} → ${stage} (перетаскивание)`);
      this.toast(`«${d.title}»: ${from} → ${stage}`, 'ok');
      this.render();
    },
    // ======== ЧАНК 6.23 — раздел 2: bulk-действия над сделками ========
    // Плавающий тулбар появляется при selCount('deals')>0. Действия из STAGES/team; привязка к проекту — через dealPin (логика pin 6.18).
    bulkDealStage(stage) {
      if (!this.M.STAGES.includes(stage)) return;
      const ds = this.selDeals(); if (!ds.length) return;
      let n = 0;
      ds.forEach(d => { if (d.stage !== stage) { const from = d.stage; d.stage = stage; d.updated = this.M.TODAY; this.logDeal(d, 'stage', `Стадия: ${from} → ${stage} (групповое)`); n++; } });
      this.selClear('deals');
      this.toast(`Стадия «${stage}» применена к ${n} сделкам`, 'ok');
    },
    bulkDealStageModal() {
      const n = this.selCount('deals'); if (!n) return;
      const opts = this.M.STAGES.map(s => `<option value="${this.esc(s)}">${this.esc(s)}</option>`).join('');
      this.openModal(`Сменить стадию · ${n} сделок`, `<div class="label mb-1">Новая стадия</div><select id="bulkStage" class="input w-full">${opts}</select>`,
        () => { const v = (document.getElementById('bulkStage') || {}).value; if (v) this.bulkDealStage(v); });
    },
    bulkDealOwner(name) {
      const ds = this.selDeals(); if (!ds.length || !name) return;
      let n = 0;
      ds.forEach(d => { if (d.owner !== name) { d.owner = name; d.updated = this.M.TODAY; this.logDeal(d, 'stage', `Ответственный → ${name} (групповое)`); n++; } });
      this.selClear('deals');
      this.toast(`Ответственный «${name}» назначен на ${n} сделок`, 'ok');
    },
    bulkDealOwnerModal() {
      const n = this.selCount('deals'); if (!n) return;
      const owners = (this.M.team || []).map(u => u.name);
      if (!owners.length) { this.toast('Нет участников команды', 'warn'); return; }
      const opts = owners.map(o => `<option value="${this.esc(o)}">${this.esc(o)}</option>`).join('');
      this.openModal(`Назначить ответственного · ${n} сделок`, `<div class="label mb-1">Ответственный</div><select id="bulkOwner" class="input w-full">${opts}</select>`,
        () => { const v = (document.getElementById('bulkOwner') || {}).value; if (v) this.bulkDealOwner(v); });
    },
    // Привязка к проекту: добавляем выбранные сделки в project.dealPin (pin) — переиспользуем модель dealMatchesProject.
    bulkDealProject(projId) {
      const p = this.projectById(projId); if (!p) return;
      const ds = this.selDeals(); if (!ds.length) return;
      p.dealPin = p.dealPin || [];
      let n = 0;
      ds.forEach(d => {
        // снять возможный anti-pin и поставить pin
        p.dealPin = p.dealPin.filter(x => x !== '-' + d.id);
        if (!p.dealPin.includes(d.id)) { p.dealPin.push(d.id); n++; }
        this.logDeal(d, 'stage', `Привязана к проекту «${p.title}» (групповое)`);
      });
      this.selClear('deals');
      this.toast(`${n} сделок привязано к проекту «${p.title}»`, 'ok');
    },
    bulkDealProjectModal() {
      const n = this.selCount('deals'); if (!n) return;
      const projs = this.M.projects || [];
      if (!projs.length) { this.toast('Нет проектов', 'warn'); return; }
      const opts = projs.map(p => { const g = this.goalById(p.goalId); return `<option value="${p.id}">${this.esc(p.title)}${g ? ' · 🎯 ' + this.esc(g.title) : ''}</option>`; }).join('');
      this.openModal(`Привязать к проекту · ${n} сделок`, `<div class="label mb-1">Проект</div><select id="bulkProj" class="input w-full mb-2">${opts}</select><div class="text-[12px]" style="color:var(--text-dim)">Сделки будут закреплены в проекте (override связи, логика pin 6.18). Ниша при этом игнорируется.</div>`,
        () => { const v = (document.getElementById('bulkProj') || {}).value; if (v) this.bulkDealProject(v); });
    },
    // Плавающий bulk-тулбар (общий рендер для deals/tasks). Возвращает HTML или ''.
    bulkBar(kind) {
      const n = this.selCount(kind); if (!n) return '';
      const word = kind === 'deals' ? 'сделок' : 'задач';
      let actions = '';
      if (kind === 'deals') {
        actions = `<button class="btn text-[12px]" data-bulk="deal-stage">Сменить стадию</button>
          <button class="btn text-[12px]" data-bulk="deal-owner">Назначить владельца</button>
          <button class="btn text-[12px]" data-bulk="deal-project">Привязать к проекту</button>`;
      } else {
        actions = `<button class="btn text-[12px]" data-bulk="task-complete">Завершить</button>
          <button class="btn text-[12px]" data-bulk="task-owner">Сменить владельца</button>
          <button class="btn text-[12px]" data-bulk="task-date">Сменить срок</button>
          <button class="btn text-[12px]" data-bulk="task-deal">Перепривязать к сделке</button>`;
      }
      return `<div class="fixed left-1/2 -translate-x-1/2 bottom-6 z-50 card px-4 py-2.5 flex items-center gap-2 flex-wrap shadow-lg" style="box-shadow:0 8px 30px rgba(0,0,0,.18);border-color:var(--accent)">
        <span class="text-[13px] font-medium whitespace-nowrap">Выбрано ${n} ${word}</span>
        <span style="width:1px;height:18px;background:var(--border)"></span>
        ${actions}
        <span style="width:1px;height:18px;background:var(--border)"></span>
        <button class="btn text-[12px]" data-bulk="clear-${kind}">Снять выбор</button>
      </div>`;
    },

    vTasks() {
      const rows = [...this.M.tasks].sort((a, b) => (b.status === 'overdue') - (a.status === 'overdue') || b.score - a.score).map(t => {
        const d = this.dealById(t.dealId), c = this.clientById(t.clientId), od = t.status === 'overdue', done = this.taskDone(t);
        const deps = this.taskDeps(t).length, blocked = this.taskIsBlocked(t), parent = this.taskParent(t), subN = this.taskSubtasks(t).length;
        const badges = [
          blocked ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--err);border-color:var(--err)">⛔ заблокировано</span>` : '',
          deps ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">🔗 ${deps}</span>` : '',
          parent ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">⊂ подзадача</span>` : '',
          subN ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">☰ ${subN} подзад.</span>` : ''
        ].filter(Boolean).join('');
        return `<div class="card-2 p-3 flex items-start gap-3 cursor-pointer" data-go="task:${t.id}" style="${this.selHas('tasks', t.id) ? 'box-shadow:0 0 0 2px var(--accent) inset' : ''}"><label class="shrink-0 flex items-center pt-0.5" data-task-sel="${t.id}" title="Выбрать" style="cursor:pointer"><input type="checkbox" ${this.selHas('tasks', t.id) ? 'checked' : ''} style="width:15px;height:15px;cursor:pointer" /></label><span class="text-lg shrink-0">${done ? '☑' : this.taskTypeIcon(t.type)}</span><div class="flex-1 min-w-0"><div class="text-sm font-medium leading-snug" style="${done ? 'text-decoration:line-through;color:var(--text-mute)' : ''}">${this.esc(t.title)}</div><div class="text-[12px]" style="color:var(--text-dim)"><a class="underline cursor-pointer" data-go="deal:${d ? d.id : ''}">${this.esc(d ? d.title : '')}</a> · <a class="underline cursor-pointer" data-go="client:${c ? c.id : ''}">${this.esc(this.clientName(c))}</a></div>${badges ? `<div class="flex flex-wrap gap-1 mt-1.5">${badges}</div>` : ''}</div><div class="flex flex-col items-end gap-1 shrink-0"><span class="pill whitespace-nowrap" style="color:${od ? 'var(--err)' : 'var(--text-dim)'};border-color:${od ? 'var(--err)' : 'var(--border)'}">${done ? 'выполнена' : od ? 'просрочено' : t.date.slice(5)}</span><span class="pill whitespace-nowrap" style="color:${this.scoreCol(t.score)}">score ${t.score}</span></div></div>`;
      }).join('');
      const allIds = this.M.tasks.map(t => t.id);
      return `<div class="card p-4"><div class="flex items-center justify-between mb-3 gap-2 flex-wrap"><div class="label">Задачи · ${this.M.tasks.length}</div><button class="btn text-[12px] ${this.selCount('tasks') ? 'btn-accent' : ''}" data-task-selall title="Выбрать/снять все">☑ Выбрать все${this.selCount('tasks') ? ' · ' + this.selCount('tasks') : ''}</button></div><div class="flex flex-col gap-2">${rows}</div></div>${this.bulkBar('tasks')}`;
    },

    // ======== ЧАНК 6.23 — раздел 3: bulk-действия над задачами ========
    // Завершить — пропускает заблокированные (открытый блокер) и уже выполненные, сообщает сколько пропущено.
    bulkTaskComplete() {
      const ts = this.selTasks(); if (!ts.length) return;
      let done = 0, skipBlocked = 0, skipDone = 0;
      ts.forEach(t => {
        if (this.taskDone(t)) { skipDone++; return; }
        if (this.taskIsBlocked(t)) { skipBlocked++; return; }
        t.status = 'done';
        const d = this.dealById(t.dealId); if (d) this.logDeal(d, 'task', `Задача «${t.title}» завершена (групповое)`);
        done++;
      });
      this.selClear('tasks');
      let msg = `Завершено: ${done}`;
      const skips = [];
      if (skipBlocked) skips.push(`${skipBlocked} заблокировано`);
      if (skipDone) skips.push(`${skipDone} уже выполнено`);
      if (skips.length) msg += ` · пропущено: ${skips.join(', ')}`;
      this.toast(msg, done ? 'ok' : 'info');
    },
    bulkTaskOwner(name) {
      const ts = this.selTasks(); if (!ts.length || !name) return;
      let n = 0;
      ts.forEach(t => { if (t.owner !== name) { t.owner = name; n++; } });
      this.selClear('tasks');
      this.toast(`Владелец «${name}» назначен на ${n} задач`, 'ok');
    },
    bulkTaskOwnerModal() {
      const n = this.selCount('tasks'); if (!n) return;
      const owners = (this.M.team || []).map(u => u.name);
      if (!owners.length) { this.toast('Нет участников команды', 'warn'); return; }
      const opts = owners.map(o => `<option value="${this.esc(o)}">${this.esc(o)}</option>`).join('');
      this.openModal(`Сменить владельца · ${n} задач`, `<div class="label mb-1">Владелец</div><select id="bulkTOwner" class="input w-full">${opts}</select>`,
        () => { const v = (document.getElementById('bulkTOwner') || {}).value; if (v) this.bulkTaskOwner(v); });
    },
    bulkTaskDate(date) {
      const ts = this.selTasks(); if (!ts.length || !date) return;
      let n = 0;
      ts.forEach(t => {
        t.date = date;
        // пересчёт статуса по сроку (не трогаем выполненные)
        if (!this.taskDone(t)) t.status = (date < this.M.TODAY) ? 'overdue' : 'open';
        n++;
      });
      this.selClear('tasks');
      this.toast(`Срок ${date} установлен для ${n} задач`, 'ok');
    },
    bulkTaskDateModal() {
      const n = this.selCount('tasks'); if (!n) return;
      this.openModal(`Сменить срок · ${n} задач`, `<div class="label mb-1">Новый срок</div><input id="bulkTDate" type="date" class="input w-full" value="${this.M.TODAY}" /><div class="text-[12px] mt-1" style="color:var(--text-dim)">Статус «просрочено/открыта» пересчитается по дате (выполненные не меняются).</div>`,
        () => { const v = (document.getElementById('bulkTDate') || {}).value; if (v) this.bulkTaskDate(v); });
    },
    // Перепривязка к сделке: меняем dealId (и clientId — из сделки) у выбранных задач.
    bulkTaskDeal(dealId) {
      const d = this.dealById(dealId); if (!d) return;
      const ts = this.selTasks(); if (!ts.length) return;
      let n = 0;
      ts.forEach(t => { t.dealId = d.id; t.clientId = d.clientId; n++; });
      this.logDeal(d, 'task', `Перепривязано задач: ${n} (групповое)`);
      this.selClear('tasks');
      this.toast(`${n} задач перепривязано к сделке «${d.title}»`, 'ok');
    },
    bulkTaskDealModal() {
      const n = this.selCount('tasks'); if (!n) return;
      const deals = this.M.deals || [];
      if (!deals.length) { this.toast('Нет сделок', 'warn'); return; }
      const opts = deals.map(d => { const c = this.clientById(d.clientId); return `<option value="${d.id}">${this.esc(d.title)}${c ? ' · ' + this.esc(c.name) : ''}</option>`; }).join('');
      this.openModal(`Перепривязать к сделке · ${n} задач`, `<div class="label mb-1">Сделка</div><select id="bulkTDeal" class="input w-full mb-2">${opts}</select><div class="text-[12px]" style="color:var(--text-dim)">Клиент задачи возьмётся из выбранной сделки.</div>`,
        () => { const v = (document.getElementById('bulkTDeal') || {}).value; if (v) this.bulkTaskDeal(v); });
    },

    // ======== ЧАНК 6.17: КАРТОЧКА ЗАДАЧИ + ЗАВИСИМОСТИ ========
    // Зависимости: deps[] = блокеры («зависит от»), subtaskOf = родитель (иерархия).
    // Завершить нельзя пока есть открытый блокер. Защита: self-ref + циклы (wouldCycle).
    taskById(id) { return (this.M.tasks || []).find(t => t.id === id) || null; },
    taskDone(t) { return t && t.status === 'done'; },
    taskDeps(t) { return (t && t.deps || []).map(id => this.taskById(id)).filter(Boolean); },
    taskOpenBlockers(t) { return this.taskDeps(t).filter(b => !this.taskDone(b)); },
    taskIsBlocked(t) { return this.taskOpenBlockers(t).length > 0; },
    taskBlocks(t) { return (this.M.tasks || []).filter(x => (x.deps || []).includes(t.id)); }, // кого эта задача блокирует
    taskSubtasks(t) { return (this.M.tasks || []).filter(x => x.subtaskOf === t.id); },
    taskParent(t) { return t && t.subtaskOf ? this.taskById(t.subtaskOf) : null; },
    taskSubProgress(t) { const subs = this.taskSubtasks(t); return { done: subs.filter(s => this.taskDone(s)).length, total: subs.length }; },
    // проверка цикла: добавление depId в deps задачи taskId — не создаёт ли цикл
    wouldCycle(taskId, depId) {
      if (taskId === depId) return true; // self-ref
      // идём по блокерам depId: если достигнем taskId — цикл
      const seen = new Set();
      const stack = [depId];
      while (stack.length) {
        const cur = stack.pop();
        if (cur === taskId) return true;
        if (seen.has(cur)) continue;
        seen.add(cur);
        const t = this.taskById(cur);
        if (t) (t.deps || []).forEach(d => stack.push(d));
      }
      return false;
    },
    taskComplete(id) {
      const t = this.taskById(id); if (!t) return;
      const blk = this.taskOpenBlockers(t);
      if (blk.length) { this.toast(`Нельзя завершить: открыт блокер «${blk[0].title}»`, 'warn'); return; }
      t.status = 'done';
      const d = this.dealById(t.dealId); if (d) this.logDeal(d, 'task', `Задача «${t.title}» завершена`);
      this.toast('Задача завершена', 'ok'); this.render();
    },
    taskReopen(id) {
      const t = this.taskById(id); if (!t) return;
      t.status = 'open';
      this.toast('Задача открыта заново', 'info'); this.render();
    },
    taskAddDep(id, depId) {
      const t = this.taskById(id), dep = this.taskById(depId);
      if (!t || !dep) return;
      if (this.wouldCycle(id, depId)) { this.toast('Нельзя: возникнет цикл зависимостей', 'warn'); return; }
      if ((t.deps || []).includes(depId)) { this.toast('Блокер уже добавлен', 'info'); return; }
      t.deps = (t.deps || []).concat(depId);
      this.toast(`Добавлен блокер: «${dep.title}»`, 'ok'); this.render();
    },
    taskRemoveDep(id, depId) {
      const t = this.taskById(id); if (!t) return;
      t.deps = (t.deps || []).filter(x => x !== depId);
      this.toast('Блокер убран', 'info'); this.render();
    },
    taskAddDepModal(id) {
      const t = this.taskById(id); if (!t) return;
      const opts = (this.M.tasks || []).filter(x => x.id !== id && !(t.deps || []).includes(x.id) && !this.wouldCycle(id, x.id))
        .map(x => `<option value="${x.id}">${this.esc(x.title)}${this.taskDone(x) ? ' (выполнена)' : ''}</option>`).join('');
      if (!opts) { this.toast('Нет доступных задач для блокера', 'info'); return; }
      this.openModal('Добавить блокер', `<div class="label mb-1">Эта задача зависит от:</div><select id="depSel" class="input w-full mb-2">${opts}</select><div class="text-[12px]" style="color:var(--text-dim)">Циклы и самоссылки отфильтрованы.</div>`,
        () => { const v = (document.getElementById('depSel') || {}).value; if (v) this.taskAddDep(id, v); });
    },
    vTaskCard(id) {
      const t = this.taskById(id);
      if (!t) return this.stub('Задача не найдена');
      const d = this.dealById(t.dealId), c = this.clientById(t.clientId);
      const u = (this.M.team || []).find(x => x.name === t.owner);
      const blocked = this.taskIsBlocked(t), done = this.taskDone(t);
      const parent = this.taskParent(t);
      const subs = this.taskSubtasks(t), prog = this.taskSubProgress(t);
      const blocks = this.taskBlocks(t);
      const crumbs = `<div class="text-[12px] mb-2" style="color:var(--text-dim)"><a class="underline cursor-pointer" data-go="tasks:">Задачи</a>${parent ? ` › <a class="underline cursor-pointer" data-go="task:${parent.id}">${this.esc(parent.title)}</a>` : ''} › текущая</div>`;
      const statusPill = `<span class="pill" style="color:${this.taskStatusColor(t)};border-color:${this.taskStatusColor(t)}">${this.taskStatusLabel(t)}</span>`;
      const blockPill = blocked ? `<span class="pill" style="color:var(--err);border-color:var(--err)">⛔ заблокирована</span>` : '';
      const metaRow = (k, v) => `<div class="flex justify-between gap-3 py-1.5 border-b" style="border-color:var(--border)"><span class="text-[12px]" style="color:var(--text-dim)">${k}</span><span class="text-[13px] text-right">${v}</span></div>`;
      const meta = `<div class="card-2 p-3 mb-3">${metaRow('Сделка', d ? `<a class="underline cursor-pointer" data-go="deal:${d.id}">${this.esc(d.title)}</a>` : '—')}${metaRow('Клиент', c ? `<a class="underline cursor-pointer" data-go="client:${c.id}">${this.esc(c.name)}</a>` : '—')}${metaRow('Владелец', `${u ? u.avatar + ' ' : ''}${this.esc(t.owner)}`)}${metaRow('Срок', t.date)}${metaRow('Тип', `${this.taskTypeIcon(t.type)} ${t.type}`)}${metaRow('Score', `<span style="color:${this.scoreCol(t.score)}">${t.score}</span>`)}</div>`;
      const depRow = b => `<div class="card-2 p-2.5 flex items-center gap-2"><span style="color:${this.taskDone(b) ? 'var(--ok)' : 'var(--err)'}">${this.taskDone(b) ? '✓' : '⛔'}</span><a class="text-[13px] flex-1 underline cursor-pointer" data-go="task:${b.id}">${this.esc(b.title)}</a><span class="pill text-[10px]" style="color:${this.taskStatusColor(b)};border-color:${this.taskStatusColor(b)}">${this.taskStatusLabel(b)}</span><button class="btn text-[11px]" data-task-deldep="${b.id}">✕</button></div>`;
      const depsBlock = `<div class="mb-3"><div class="flex items-center justify-between mb-2"><span class="label">Блокеры (зависит от) · ${this.taskDeps(t).length}</span><button class="btn text-[12px]" data-task-adddep>+ Блокер</button></div>${this.taskDeps(t).length ? this.taskDeps(t).map(depRow).join('') : `<div class="text-[12px]" style="color:var(--text-mute)">Нет блокеров — задачу можно выполнять.</div>`}</div>`;
      const blocksBlock = blocks.length ? `<div class="mb-3"><div class="label mb-2">Блокирует · ${blocks.length}</div>${blocks.map(x => `<div class="card-2 p-2.5 flex items-center gap-2"><span style="color:var(--text-dim)">→</span><a class="text-[13px] flex-1 underline cursor-pointer" data-go="task:${x.id}">${this.esc(x.title)}</a><span class="pill text-[10px]" style="color:${this.taskStatusColor(x)};border-color:${this.taskStatusColor(x)}">${this.taskStatusLabel(x)}</span></div>`).join('')}</div>` : '';
      const subsBlock = subs.length ? `<div class="mb-3"><div class="label mb-2">Подзадачи · выполнено ${prog.done}/${prog.total}</div><div class="h-1.5 rounded-full mb-2" style="background:var(--border)"><div class="h-1.5 rounded-full" style="width:${prog.total ? Math.round(prog.done / prog.total * 100) : 0}%;background:var(--ok)"></div></div>${subs.map(s => `<div class="card-2 p-2.5 flex items-center gap-2"><span style="color:${this.taskDone(s) ? 'var(--ok)' : 'var(--text-dim)'}">${this.taskDone(s) ? '☑' : '☐'}</span><a class="text-[13px] flex-1 underline cursor-pointer" data-go="task:${s.id}">${this.esc(s.title)}</a><span class="pill text-[10px]" style="color:${this.taskStatusColor(s)};border-color:${this.taskStatusColor(s)}">${this.taskStatusLabel(s)}</span></div>`).join('')}</div>` : '';
      let ctrl;
      if (done) { ctrl = `<button class="btn text-[13px]" data-task-reopen="${t.id}">↺ Открыть заново</button>`; }
      else if (blocked) { const bn = this.taskOpenBlockers(t); ctrl = `<button class="btn text-[13px]" disabled style="opacity:.5;cursor:not-allowed">✓ Завершить</button><div class="text-[12px] mt-1" style="color:var(--err)">⛔ Нельзя завершить: открытых блокеров — ${bn.length} (напр. «${this.esc(bn[0].title)}»)</div>`; }
      else { ctrl = `<button class="btn btn-accent text-[13px]" data-task-complete="${t.id}">✓ Завершить</button>`; }
      return `<div class="max-w-[760px]">${crumbs}<div class="flex items-start gap-2 mb-3"><span class="text-xl">${this.taskTypeIcon(t.type)}</span><div class="flex-1"><h1 class="text-lg font-semibold leading-tight">${this.esc(t.title)}</h1><div class="flex flex-wrap gap-1.5 mt-1.5">${statusPill}${blockPill}${parent ? `<span class="pill text-[10px]">⊂ подзадача</span>` : ''}</div></div></div>${meta}${depsBlock}${subsBlock}${blocksBlock}<div class="card-2 p-3">${ctrl}</div>${this.activityBlock('task', id)}</div>`;
    },
    // ======== ЧАНК 6.5: РАБОЧИЕ УПАКОВКИ (ЭТАП 2: упаковка + продвижение) ========
    pkgReadyColor(r) { return r === 'в продвижении' ? 'var(--accent)' : r === 'готова' ? 'var(--ok)' : 'var(--warn)'; },
    pkgById(id) { return this.M.packages.find(p => p.id === id) || null; },
    pkgSetReady(id, ready) {
      const p = this.pkgById(id); if (!p) return;
      p.ready = ready;
      if (ready === 'в продвижении') this.toast('«' + p.name + '» передана в продвижение', 'ok');
      else this.toast('Статус «' + p.name + '»: ' + ready, 'ok');
      if (p.dealId) { const d = this.dealById(p.dealId); if (d) this.logDeal(d, 'package', `Упаковка «${p.name}» → ${ready}`); }
      this.render();
    },
    pkgFromDealModal() {
      const deals = this.M.deals;
      const opts = deals.map(d => { const c = this.clientById(d.clientId); return `<option value="${d.id}">${this.esc(d.title)} — ${c ? this.esc(c.name) : ''}</option>`; }).join('');
      this.openModal('Новая упаковка из сделки', `
        <div class="label mb-1">Исходная сделка</div>
        <select id="pkgDeal" class="input w-full mb-3">${opts}</select>
        <div class="label mb-1">Название упаковки</div>
        <input id="pkgName" class="input w-full mb-3" placeholder="Напр. «Орошение ПРО»" />
        <div class="text-[12px]" style="color:var(--text-dim)">Отрасль и потребность подтянутся из клиента сделки.</div>`,
        () => {
          const did = (document.getElementById('pkgDeal') || {}).value;
          const name = ((document.getElementById('pkgName') || {}).value || '').trim();
          const d = this.dealById(did); if (!d) { this.toast('Выберите сделку', 'warn'); return false; }
          if (!name) { this.toast('Укажите название', 'warn'); return false; }
          const c = this.clientById(d.clientId);
          this.M.packages.unshift({ id: 'P' + Date.now(), name, need: d.need || (c && c.need && c.need[0]) || '', industry: c ? c.industry : '', priceFrom: d.amount || 0, ready: 'черновик', dealId: did });
          this.logDeal(d, 'package', `Создана упаковка «${name}» (черновик)`);
          this.toast('Упаковка «' + name + '» создана', 'ok'); this.render();
        });
    },
    vPackages() {
      const rows = this.M.packages.map(p => {
        const d = p.dealId ? this.dealById(p.dealId) : null;
        let action = '';
        if (p.ready === 'черновик') action = `<button class="btn text-[12px]" data-pkg-ready="${p.id}" data-pkg-to="готова">✓ Отметить готовой</button>`;
        else if (p.ready === 'готова') action = `<button class="btn btn-accent text-[12px]" data-pkg-ready="${p.id}" data-pkg-to="в продвижении">→ В продвижение</button>`;
        else action = `<span class="pill text-[11px]" style="color:var(--accent);border-color:var(--accent)">↗ На продвижении</span>`;
        return `<div class="card-2 p-3 flex items-center gap-3 flex-wrap">
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium">${this.esc(p.name)}</div>
            <div class="text-[12px]" style="color:var(--text-dim)">${p.need || '—'} · ${p.industry || '—'}${d ? ` · из сделки <a class="underline cursor-pointer" data-go="deal:${d.id}">${this.esc(d.title)}</a>` : ''}</div>
          </div>
          <span class="pill">от ${p.priceFrom != null && !isNaN(p.priceFrom) ? this.money(p.priceFrom) : '—'}</span>
          <span class="pill" style="color:${this.pkgReadyColor(p.ready)};border-color:${this.pkgReadyColor(p.ready)}">${p.ready}</span>
          ${action}
        </div>`;
      }).join('');
      const promoCount = this.M.packages.filter(p => p.ready === 'в продвижении').length;
      return `<div class="card p-4">
        <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div class="label">Упаковки · ${this.M.packages.length} · в продвижении ${promoCount}</div>
          <button class="btn btn-accent text-[13px]" data-pkg-new>+ Упаковка из сделки</button>
        </div>
        <div class="flex flex-col gap-2">${rows}</div>
      </div>`;
    },
    // ======== ЧАНК 6.6: КОНТЕНТ И СОЦСЕТИ (SSM, макет hlab.kz) ========
    postSel: null,
    postStatusColor(s) {
      return s === 'одобрен' ? 'var(--ok)' : s === 'согласование' ? 'var(--err)' : s === 'отклонён' ? 'var(--text-mute)' : 'var(--warn)';
    },
    postSelect(id) { this.postSel = id; this.render(); },
    postAct(id, act) {
      const p = (this.M.posts || []).find(x => x.id === id); if (!p) return;
      if (act === 'approve') { p.status = 'одобрен'; this.toast('Пост «' + p.title + '» одобрен в публикацию', 'ok'); }
      else if (act === 'rework') { p.status = 'на переработку'; this.toast('Возвращён на переработку', 'info'); }
      else if (act === 'reject') { p.status = 'отклонён'; this.toast('Пост отклонён', 'info'); }
      this.render();
    },
    postField(id, field, val) { const p = (this.M.posts || []).find(x => x.id === id); if (p) p[field] = val; },
    vContent() {
      const M = this.M;
      const posts = M.posts || [];
      const sel = this.postSel ? posts.find(p => p.id === this.postSel) : null;
      const cntAppr = posts.filter(p => p.status === 'согласование').length;
      // левая колонка: очередь черновиков
      const queue = posts.map(p => {
        const on = sel && sel.id === p.id;
        const badge = p.status === 'согласование'
          ? `<span class="pill text-[10px]" style="background:var(--err);color:#fff;border:0">согласование</span>`
          : `<span class="pill text-[10px]" style="color:${this.postStatusColor(p.status)};border-color:${this.postStatusColor(p.status)}">${p.status}</span>`;
        return `<div class="card-2 p-2 cursor-pointer" data-post-sel="${p.id}" style="${on ? 'border-color:var(--accent)' : ''}">
          <div class="flex items-center gap-2"><span>${p.icon}</span><span class="text-[13px] font-medium flex-1 leading-snug">${this.esc(p.title)}</span></div>
          <div class="flex items-center justify-between mt-1"><span class="label">${p.kind}</span>${badge}</div>
        </div>`;
      }).join('');
      // правая колонка: редактор
      let editor;
      if (!sel) {
        editor = `<div class="text-[13px] p-6 text-center" style="color:var(--text-mute)">Выберите черновик слева</div>`;
      } else {
        const canAct = sel.status !== 'одобрен';
        editor = `
          <div class="flex items-center gap-2 mb-3"><span class="text-lg">${sel.icon}</span><div class="text-sm font-semibold flex-1">${this.esc(sel.title)}</div><span class="pill text-[11px]" style="color:${this.postStatusColor(sel.status)};border-color:${this.postStatusColor(sel.status)}">${sel.status}</span></div>
          <div class="label mb-1">Текст поста</div>
          <textarea class="input w-full mb-3" rows="4" data-post-field="body" data-post-id="${sel.id}">${this.esc(sel.body)}</textarea>
          <div class="label mb-1">Хэштеги</div>
          <input class="input w-full mb-3" data-post-field="hashtags" data-post-id="${sel.id}" value="${this.esc(sel.hashtags)}" />
          <div class="grid grid-cols-2 gap-2 mb-3">
            <div><div class="label mb-1">Слот публикации</div><input class="input w-full" data-post-field="slot" data-post-id="${sel.id}" value="${this.esc(sel.slot)}" placeholder="ГГГГ-ММ-ДД ЧЧ:ММ" /></div>
            <div><div class="label mb-1">Канал</div><input class="input w-full" data-post-field="channel" data-post-id="${sel.id}" value="${this.esc(sel.channel)}" /></div>
          </div>
          <div class="label mb-1">Описание медиа</div>
          <input class="input w-full mb-4" data-post-field="media" data-post-id="${sel.id}" value="${this.esc(sel.media)}" />
          <div class="flex gap-2 flex-wrap">
            ${canAct ? `<button class="btn btn-accent text-[13px]" data-post-act="approve" data-post-id="${sel.id}">✓ Одобрить в публикацию</button>
            <button class="btn text-[13px]" data-post-act="rework" data-post-id="${sel.id}">↺ На переработку</button>
            <button class="btn text-[13px]" data-post-act="reject" data-post-id="${sel.id}" style="color:var(--err)">✕ Отклонить</button>` : `<span class="pill text-[12px]" style="color:var(--ok);border-color:var(--ok)">✓ Одобрен — в очереди на публикацию</span>`}
          </div>`;
      }
      return `<div class="flex flex-col gap-3">
        <div class="card p-3 text-[13px]" style="color:var(--text-dim)">✍️ ПЕТРУШКА готовит черновики постов — вы проверяете, правите и одобряете перед публикацией. Красный бейдж «согласование» — требует решения.</div>
        <div class="grid gap-3" style="grid-template-columns:300px 1fr">
          <div class="card p-3">
            <div class="label mb-2">Очередь черновиков · ${posts.length} · 🔴 ${cntAppr}</div>
            <div class="flex flex-col gap-2">${queue}</div>
          </div>
          <div class="card p-4">${editor}</div>
        </div>
      </div>`;
    },
    // ======== ЧАНК 6.9: ВХОДЯЩИЕ (лента Telegram/уведомлений → быстрое создание объекта) ========
    inboxFilter: 'new', // 'new' | 'all'
    inboxSuggestLabel(s) { return { deal: '🤝 Сделка', task: '✅ Задача', client: '🏢 Клиент' }[s] || s; },
    inboxSetFilter(f) { this.inboxFilter = f; this.render(); },
    inboxDismiss(id) { const it = (this.M.inbox || []).find(i => i.id === id); if (it) { it.status = 'dismissed'; this.toast('Скрыто из входящих', 'info'); this.render(); } },
    inboxCreate(id) {
      const it = (this.M.inbox || []).find(i => i.id === id); if (!it) return;
      const f = it.fields || {};
      let go = null;
      if (it.suggest === 'deal') {
        // создать клиента (если нет) + сделку
        let cl = (this.M.clients || []).find(c => c.name === f.client);
        if (!cl) {
          cl = { id: 'C' + (this.M.clients.length + 1), name: f.client || 'Новый клиент', industry: '—', region: '—', contact: '—', need: f.need ? [f.need] : [], health: 'yellow', dealsCount: 0 };
          this.M.clients.push(cl);
        }
        const did = 'D' + (this.M.deals.length + 1);
        const nd = { id: did, clientId: cl.id, title: f.title || 'Новая сделка', stage: f.stage || 'Зацепка', amount: 0, need: f.need || '—', owner: 'Екатерина', updated: this.M.TODAY, score: 50, goalId: '', history: [] };
        this.M.deals.push(nd);
        cl.dealsCount = (cl.dealsCount || 0) + 1;
        this.logDeal(nd, 'create', 'Создана из входящих (' + it.src + ')');
        go = ['deal', did];
        this.toast('Сделка создана из входящих', 'ok');
      } else if (it.suggest === 'task') {
        const tid = 'T' + (this.M.tasks.length + 1);
        const dealId = f.dealHint || '';
        const d = dealId ? this.dealById(dealId) : null;
        this.M.tasks.unshift({ id: tid, dealId: dealId, clientId: d ? d.clientId : '', title: f.title || 'Задача', type: f.type || 'call', date: f.date || this.M.TODAY, owner: 'Екатерина', score: 60, status: 'open' });
        if (d) this.logDeal(d, 'task', 'Задача из входящих: ' + (f.title || ''));
        go = ['tasks', null];
        this.toast('Задача создана из входящих', 'ok');
      } else if (it.suggest === 'client') {
        let cl = (this.M.clients || []).find(c => c.name === f.client);
        if (!cl) {
          cl = { id: 'C' + (this.M.clients.length + 1), name: f.client || 'Новый клиент', industry: '—', region: '—', contact: '—', need: f.need ? [f.need] : [], health: 'yellow', dealsCount: 0 };
          this.M.clients.push(cl);
        }
        go = ['client', cl.id];
        this.toast('Клиент создан из входящих', 'ok');
      }
      it.status = 'done';
      this.persist();
      if (go) this.go(go[0], go[1]); else this.render();
    },
    vInbox() {
      const all = this.M.inbox || [];
      const list = this.inboxFilter === 'new' ? all.filter(i => i.status === 'new') : all.filter(i => i.status !== 'dismissed');
      const fBtn = (f, label) => `<button class="btn text-[12px] ${this.inboxFilter === f ? 'btn-accent' : ''}" data-inbox-filter="${f}">${label}</button>`;
      const cntNew = all.filter(i => i.status === 'new').length;
      const rows = list.length ? list.map(it => {
        const done = it.status === 'done';
        return `<div class="card p-3" style="${done ? 'opacity:.6' : ''}">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-lg">${it.icon}</span>
            <span class="pill text-[11px]">${it.src}</span>
            <span class="label flex-1">${this.esc(it.from)} · ${it.time}</span>
            ${done ? `<span class="pill text-[11px]" style="color:var(--ok);border-color:var(--ok)">✓ обработано</span>` : ''}
          </div>
          <div class="text-[13px] mb-2" style="color:var(--text)">${this.esc(it.text)}</div>
          <div class="flex items-center gap-2 flex-wrap">
            <span class="label">ПЕТРУШКА предлагает:</span>
            <span class="pill text-[12px]" style="color:var(--accent);border-color:var(--accent)">${this.inboxSuggestLabel(it.suggest)}</span>
            ${!done ? `<button class="btn btn-accent text-[12px]" data-inbox-create="${it.id}">⚡ Создать</button>
            <button class="btn text-[12px]" data-inbox-dismiss="${it.id}">Скрыть</button>` : ''}
          </div>
        </div>`;
      }).join('') : `<div class="card p-6 text-center text-[13px]" style="color:var(--text-mute)">Входящие пусты</div>`;
      return `<div class="flex flex-col gap-3">
        <div class="card p-3 text-[13px]" style="color:var(--text-dim)">📥 Лента из Telegram, почты и мониторинга. ПЕТРУШКА распознаёт событие и предлагает создать объект (сделку, задачу, клиента) одним кликом — с предзаполненными полями.</div>
        <div class="flex items-center gap-2">${fBtn('new', 'Новые · ' + cntNew)}${fBtn('all', 'Все')}</div>
        <div class="flex flex-col gap-2">${rows}</div>
      </div>`;
    },
    // ======== ЧАНК 6.10: ГРАФ ОБЪЕКТОВ (Neo4j-вид: интерактивная карта связей) ========
    graphSel: null,            // выбранный узел id (напр. 'D1') | null
    graphTypes: { goal: true, project: true, deal: true, task: true, artifact: true, client: true },
    graphTypeMeta() {
      return {
        strategy: { label: 'Стратегия', color: 'var(--info)' },
        goal: { label: 'Цели', color: 'var(--accent)' },
        project: { label: 'Проекты', color: '#0ea5e9' },
        deal: { label: 'Сделки', color: 'var(--ok)' },
        task: { label: 'Задачи', color: 'var(--warn)' },
        artifact: { label: 'Артефакты', color: 'var(--text-dim)' },
        client: { label: 'Клиенты', color: '#8b5cf6' },
      };
    },
    graphToggleType(t) { this.graphTypes[t] = !this.graphTypes[t]; this.graphSel = null; this.render(); },
    graphSelect(id) { this.graphSel = (this.graphSel === id ? null : id); this.render(); },
    // строим узлы и рёбра из существующих объектов
    graphBuild() {
      const M = this.M;
      const T = this.graphTypes;
      const nodes = []; const edges = [];
      const add = (id, type, label, sub) => nodes.push({ id, type, label, sub });
      // Стратегия (корень — всегда)
      add('S', 'strategy', 'Стратегия', M.strategy && M.strategy.title ? M.strategy.title : 'Курс компании');
      // Цели
      if (T.goal) M.goals.forEach(g => { add(g.id, 'goal', g.title, 'Цель'); edges.push(['S', g.id]); });
      // Проекты (6.13): жёсткая привязка goal→project
      if (T.project) (M.projects || []).forEach(p => {
        add(p.id, 'project', p.title, 'Проект');
        if (T.goal && M.goals.some(g => g.id === p.goalId)) edges.push([p.goalId, p.id]);
        else edges.push(['S', p.id]);
      });
      // Сделки
      if (T.deal) M.deals.forEach(d => {
        add(d.id, 'deal', d.title, d.stage);
        // 6.13: если сделка в проекте — ребро project→deal; иначе если в цели вне проектов — goal→deal; иначе S→deal
        const pm = T.project ? (M.projects || []).filter(p => this.dealMatchesProject(d, p)) : [];
        if (pm.length) { pm.forEach(p => edges.push([p.id, d.id])); }
        else {
          // 6.7 авто-агрегация: рёбра цель→сделка по нише (одна сделка может войти в несколько целей)
          const gm = T.goal ? M.goals.filter(g => this.dealMatchesGoal(d, g)) : [];
          if (gm.length) gm.forEach(g => edges.push([g.id, d.id]));
          else edges.push(['S', d.id]); // вне ниш — крепим к стратегии
        }
      });
      // Клиенты
      if (T.client) {
        const used = new Set(M.deals.map(d => d.clientId));
        M.clients.filter(c => used.has(c.id)).forEach(c => {
          add(c.id, 'client', c.name, 'Клиент');
          if (T.deal) M.deals.filter(d => d.clientId === c.id).forEach(d => edges.push([c.id, d.id]));
        });
      }
      // Задачи
      const taskNodeIds = new Set();
      if (T.task && T.deal) M.tasks.forEach(t => {
        if (t.dealId && M.deals.some(d => d.id === t.dealId)) { add(t.id, 'task', t.title, 'Задача'); edges.push([t.dealId, t.id]); taskNodeIds.add(t.id); }
      });
      // 6.17: рёбра task→task «зависит от» (блокеры). Пунктир, отдельный цвет — рисуем blocker→task.
      if (T.task && T.deal) M.tasks.forEach(t => {
        if (!taskNodeIds.has(t.id)) return;
        (t.deps || []).forEach(depId => {
          if (taskNodeIds.has(depId)) edges.push([depId, t.id, 'dep']);
        });
      });
      // Артефакты
      if (T.artifact && T.deal) M.artifacts.forEach(a => {
        if (a.dealId && M.deals.some(d => d.id === a.dealId)) { add(a.id, 'artifact', a.name || a.title || a.id, 'Артефакт'); edges.push([a.dealId, a.id]); }
      });
      return { nodes, edges };
    },
    // layout по «слоям» (колонкам) — глубина от Стратегии
    graphLayout(nodes, edges) {
      const order = { strategy: 0, client: 0, goal: 1, project: 2, deal: 3, task: 4, artifact: 4 };
      const cols = {};
      nodes.forEach(n => { const c = order[n.type] != null ? order[n.type] : 4; (cols[c] = cols[c] || []).push(n); });
      const colW = 230, rowH = 64, padX = 24, padY = 28;
      const pos = {};
      const maxCol = Math.max(...Object.keys(cols).map(Number));
      let maxRows = 0;
      Object.keys(cols).forEach(c => { maxRows = Math.max(maxRows, cols[c].length); });
      Object.keys(cols).forEach(c => {
        const arr = cols[c]; const n = arr.length;
        const colH = n * rowH;
        const totalH = maxRows * rowH;
        const off = (totalH - colH) / 2; // вертикальное центрирование колонки
        arr.forEach((nd, i) => { pos[nd.id] = { x: padX + Number(c) * colW, y: padY + off + i * rowH + 8 }; });
      });
      const W = padX * 2 + (maxCol) * colW + 180;
      const H = padY * 2 + maxRows * rowH + 16;
      return { pos, W, H };
    },
    graphNodeById(id) {
      const M = this.M;
      const g = M.goals.find(x => x.id === id); if (g) return { type: 'goal', obj: g };
      const pr = (M.projects || []).find(x => x.id === id); if (pr) return { type: 'project', obj: pr };
      const d = M.deals.find(x => x.id === id); if (d) return { type: 'deal', obj: d };
      const t = M.tasks.find(x => x.id === id); if (t) return { type: 'task', obj: t };
      const a = M.artifacts.find(x => x.id === id); if (a) return { type: 'artifact', obj: a };
      const c = M.clients.find(x => x.id === id); if (c) return { type: 'client', obj: c };
      if (id === 'S') return { type: 'strategy', obj: M.strategy || { title: 'Стратегия' } };
      return null;
    },
    graphDetail() {
      if (!this.graphSel) {
        return `<div class="card-2 p-4 text-[13px]" style="color:var(--text-mute)">Кликните узел графа — здесь появятся детали объекта и его связи.</div>`;
      }
      const meta = this.graphTypeMeta();
      const hit = this.graphNodeById(this.graphSel);
      if (!hit) return '';
      const o = hit.obj, ty = hit.type, m = meta[ty];
      const rows = [];
      const row = (k, v) => `<div class="flex justify-between gap-3 text-[13px]"><span style="color:var(--text-dim)">${k}</span><span class="text-right">${this.esc(String(v))}</span></div>`;
      let title = o.title || o.name || 'Объект'; let go = null;
      if (ty === 'goal') { rows.push(row('Тип', 'Цель')); const ds = this.goalDeals(o); rows.push(row('Сделок по нише', ds.length)); rows.push(row('Проектов', this.projectsByGoal(o).length)); const sg = this.goalSignal(o); rows.push(row('Сигнал', sg.label)); go = ['goal', o.id]; }
      else if (ty === 'project') { rows.push(row('Тип', 'Проект')); const gl = this.goalById(o.goalId); if (gl) rows.push(row('Цель', gl.title)); rows.push(row('Ниша', o.need)); const pds = this.projectDeals(o); rows.push(row('Сделок', pds.length)); const ppr = this.projectProgress(o); rows.push(row('Прогресс', ppr.pct + '%')); const psg = this.projectSignal(o); rows.push(row('Сигнал', psg.label)); go = ['project', o.id]; }
      else if (ty === 'deal') { rows.push(row('Стадия', o.stage)); rows.push(row('Сумма', o.amount ? this.money(o.amount) : '—')); const c = this.clientById(o.clientId); if (c) rows.push(row('Клиент', c.name)); rows.push(row('Score', o.score)); go = ['deal', o.id]; }
      else if (ty === 'task') { rows.push(row('Тип', 'Задача')); rows.push(row('Срок', o.date || '—')); const d = this.dealById(o.dealId); if (d) rows.push(row('Сделка', d.title)); go = ['tasks', null]; }
      else if (ty === 'artifact') { rows.push(row('Тип', 'Артефакт')); const d = this.dealById(o.dealId); if (d) rows.push(row('Сделка', d.title)); go = ['artifacts', null]; }
      else if (ty === 'client') { rows.push(row('Тип', 'Клиент')); if (o.industry) rows.push(row('Отрасль', o.industry)); rows.push(row('Сделок', this.M.deals.filter(d => d.clientId === o.id).length)); go = ['client', o.id]; }
      else if (ty === 'strategy') { title = 'Стратегия'; rows.push(row('Целей', this.M.goals.length)); rows.push(row('Сделок', this.M.deals.length)); go = ['goals', null]; }
      return `<div class="card-2 p-4 flex flex-col gap-2">
        <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full" style="background:${m.color}"></span><span class="font-semibold text-[14px]">${this.esc(title)}</span></div>
        <div class="flex flex-col gap-1 mt-1">${rows.join('')}</div>
        ${go ? `<button class="btn btn-accent text-[12px] mt-2 self-start" data-go="${go[0]}${go[1] ? ':' + go[1] : ''}">Открыть карточку →</button>` : ''}
      </div>`;
    },
    vGraph() {
      const { nodes, edges } = this.graphBuild();
      const { pos, W, H } = this.graphLayout(nodes, edges);
      const meta = this.graphTypeMeta();
      // связанные с выбранным узлом (для подсветки)
      const sel = this.graphSel;
      const related = new Set();
      if (sel) { related.add(sel); edges.forEach(([a, b]) => { if (a === sel) related.add(b); if (b === sel) related.add(a); }); }
      const isDim = id => sel && !related.has(id);
      // рёбра
      const NW = 168, NH = 40;
      const edgeSvg = edges.map((e) => {
        const a = e[0], b = e[1];
        const pa = pos[a], pb = pos[b]; if (!pa || !pb) return '';
        const x1 = pa.x + NW, y1 = pa.y + NH / 2, x2 = pb.x, y2 = pb.y + NH / 2;
        const mx = (x1 + x2) / 2;
        const active = sel && (a === sel || b === sel);
        const isDep = e[2] === 'dep'; // 6.17: ребро-зависимость task→task
        const depCol = '#ec4899'; // отдельный цвет связи-зависимости (отличен от иерархии и узлов)
        const col = active ? 'var(--accent)' : (isDep ? depCol : 'var(--border)');
        const wdt = active ? 2.2 : (isDep ? 1.6 : 1.2);
        const op = sel && !active ? 0.25 : (isDep ? 0.85 : 0.9);
        const dash = isDep ? ' stroke-dasharray="5 4"' : '';
        return `<path d="M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}" fill="none" stroke="${col}" stroke-width="${wdt}" opacity="${op}"${dash}/>`;
      }).join('');
      // узлы
      const nodeSvg = nodes.map(n => {
        const p = pos[n.id]; if (!p) return '';
        const m = meta[n.type];
        const dim = isDim(n.id) ? 0.32 : 1;
        const selected = n.id === sel;
        const lbl = n.label.length > 22 ? n.label.slice(0, 21) + '…' : n.label;
        return `<g class="cursor-pointer" data-graph-node="${n.id}" opacity="${dim}">
          <rect x="${p.x}" y="${p.y}" width="${NW}" height="${NH}" rx="9"
            fill="var(--card-2,rgba(127,127,127,.08))" stroke="${selected ? 'var(--accent)' : m.color}" stroke-width="${selected ? 2.4 : 1.4}"/>
          <rect x="${p.x}" y="${p.y}" width="4" height="${NH}" rx="2" fill="${m.color}"/>
          <text x="${p.x + 12}" y="${p.y + 17}" font-size="12" font-weight="600" fill="var(--text)">${this.esc(lbl)}</text>
          <text x="${p.x + 12}" y="${p.y + 31}" font-size="10" fill="var(--text-dim)">${this.esc(n.sub || '')}</text>
        </g>`;
      }).join('');
      // фильтр-кнопки типов
      const tBtn = (t) => { const m = meta[t]; const on = this.graphTypes[t]; return `<button class="btn text-[12px] flex items-center gap-1 ${on ? '' : 'opacity-50'}" data-graph-type="${t}"><span class="w-2.5 h-2.5 rounded-full" style="background:${m.color}"></span>${m.label}</button>`; };
      const filters = ['goal', 'project', 'client', 'deal', 'task', 'artifact'].map(tBtn).join('');
      const legend = Object.keys(meta).map(t => { const m = meta[t]; return `<span class="flex items-center gap-1 text-[11px]" style="color:var(--text-dim)"><span class="w-2.5 h-2.5 rounded-full" style="background:${m.color}"></span>${m.label}</span>`; }).join('')
        + `<span class="flex items-center gap-1 text-[11px]" style="color:var(--text-dim)"><svg width="22" height="8"><line x1="1" y1="4" x2="21" y2="4" stroke="#ec4899" stroke-width="1.6" stroke-dasharray="5 4"/></svg>зависит от (задача)</span>`;
      return `<div class="flex flex-col gap-3">
        <div class="card p-3 text-[13px]" style="color:var(--text-dim)">🕸 Граф объектов (Neo4j-вид). Все объекты связаны: <b>Стратегия → Цели → Проекты → Сделки → Задачи / Артефакты</b>, плюс связь <b>Клиент → Сделка</b>. <span style="color:#ec4899">Пунктир</span> — зависимость <b>задача → задача</b> (блокеры). Кликните узел — подсветятся связи и откроются детали.</div>
        <div class="flex items-center gap-2 flex-wrap">
          <span class="label">Показать:</span>${filters}
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-3">
          <div class="card p-2 overflow-auto" style="max-height:70vh">
            <svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="max-width:none">
              ${edgeSvg}${nodeSvg}
            </svg>
          </div>
          <div class="flex flex-col gap-3">
            ${this.graphDetail()}
            <div class="card-2 p-3 flex flex-wrap gap-x-3 gap-y-1">${legend}</div>
            <div class="card-2 p-3 text-[12px]" style="color:var(--text-dim)">Узлов: <b>${nodes.length}</b> · Связей: <b>${edges.length}</b></div>
          </div>
        </div>
      </div>`;
    },
    // ======== ЧАНК 6.8: КОМАНДА (Этап 1 — координация: загрузка по owner, переназначение) ========
    teamSel: null, // развёрнутый человек (null = все свёрнуты)
    teamMemberByName(name) { return (this.M.team || []).find(u => u.name === name) || null; },
    teamLoad(u) {
      const ds = (this.M.deals || []).filter(d => d.owner === u.name);
      const ts = (this.M.tasks || []).filter(t => t.owner === u.name);
      const overdue = ts.filter(t => t.status === 'overdue').length;
      const amount = ds.reduce((s, d) => s + (d.amount || 0), 0);
      const loadPct = u.cap ? Math.min(100, Math.round(ds.length / u.cap * 100)) : 0;
      return { ds, ts, overdue, amount, loadPct };
    },
    teamLoadColor(pct) { return pct >= 100 ? 'var(--err)' : pct >= 70 ? 'var(--warn)' : 'var(--ok)'; },
    teamToggle(id) { this.teamSel = this.teamSel === id ? null : id; this.render(); },
    teamReassignModal(dealId) {
      const d = this.dealById(dealId); if (!d) return;
      const opts = (this.M.team || []).map(u => `<option value="${u.name}" ${d.owner === u.name ? 'selected' : ''}>${u.avatar} ${this.esc(u.name)} — ${this.esc(u.role)}</option>`).join('');
      const body = `<div class="label mb-1">Сделка</div><div class="text-sm mb-3">${this.esc(d.title)}</div>
        <div class="label mb-1">Назначить ответственного</div>
        <select id="m_owner" class="input w-full">${opts}</select>`;
      this.openModal('Переназначить сделку', body, () => {
        const v = document.getElementById('m_owner').value;
        d.owner = v;
        this.toast('Сделка переназначена на ' + v, 'ok');
        this.render();
      });
    },
    vTeam() {
      const team = this.M.team || [];
      const totalDeals = (this.M.deals || []).length;
      const cards = team.map(u => {
        const L = this.teamLoad(u);
        const open = this.teamSel === u.id;
        const col = this.teamLoadColor(L.loadPct);
        const dealRows = L.ds.length ? L.ds.map(d => `
          <div class="flex items-center gap-2 py-1 text-[13px] border-t" style="border-color:var(--border)">
            <span class="flex-1 cursor-pointer hover:underline" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</span>
            <span class="pill text-[11px]">${d.stage}</span>
            <button class="btn text-[11px]" data-team-reassign="${d.id}" title="Переназначить">↪</button>
          </div>`).join('')
          : `<div class="text-[12px] py-2" style="color:var(--text-mute)">Нет сделок</div>`;
        const taskRows = L.ts.length ? L.ts.map(t => `
          <div class="flex items-center gap-2 py-1 text-[12px]" style="color:var(--text-dim)">
            <span>${t.status === 'overdue' ? '🔴' : '✅'}</span><span class="flex-1">${this.esc(t.title)}</span><span>${t.date}</span>
          </div>`).join('') : '';
        return `<div class="card p-3">
          <div class="flex items-center gap-3 cursor-pointer" data-team-toggle="${u.id}">
            <span class="text-2xl">${u.avatar}</span>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold">${this.esc(u.name)}</div>
              <div class="label">${this.esc(u.role)}</div>
            </div>
            <span class="text-[12px]" style="color:var(--text-mute)">${open ? '▲' : '▼'}</span>
          </div>
          <div class="mt-2">
            <div class="flex items-center justify-between text-[12px] mb-1">
              <span style="color:var(--text-dim)">Загрузка · ${L.ds.length}/${u.cap} сделок</span>
              <span class="font-medium" style="color:${col}">${L.loadPct}%</span>
            </div>
            <div style="height:7px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${L.loadPct}%;background:${col}"></div></div>
            <div class="flex gap-3 mt-2 text-[12px]" style="color:var(--text-dim)">
              <span>💰 ${this.money(L.amount)}</span><span>✅ задач: ${L.ts.length}</span>${L.overdue ? `<span style="color:var(--err)">🔴 просрочено: ${L.overdue}</span>` : ''}
            </div>
          </div>
          ${open ? `<div class="mt-2"><div class="label mb-1">Сделки</div>${dealRows}${taskRows ? `<div class="label mt-2 mb-1">Задачи</div>${taskRows}` : ''}</div>` : ''}
        </div>`;
      }).join('');
      return `<div class="flex flex-col gap-3">
        <div class="card p-3 text-[13px]" style="color:var(--text-dim)">👥 Команда из ${team.length} человек. Объекты закрепляются за людьми (owner) — загрузка считается по числу сделок и задач. Этап 1 ТЗ: координация команды. Разверните карточку, чтобы переназначить сделку.</div>
        <div class="grid gap-3" style="grid-template-columns:repeat(auto-fill,minmax(330px,1fr))">${cards}</div>
      </div>`;
    },
    // ======== ЧАНК 6.7: СТРАТЕГИЯ → ЦЕЛИ (экран «Цели», связь сделок с целями) ========
    goalSel: null, // развёрнутая цель (null = все свёрнуты)
    goalById(id) { return (this.M.goals || []).find(g => g.id === id) || null; },
    // 6.7 (авто-агрегация): сделки цели выводятся МЯГКО по need ∈ needMatch (ТЗ 2.1/3.1).
    // Ручной pin (goalPin===g.id) добавляет сделку; anti-pin (goalPin==='-') исключает из любой цели.
    dealMatchesGoal(d, g) {
      if (d.goalPin === '-') return false;            // anti-pin: исключена вручную
      if (d.goalPin === g.id) return true;            // pin: закреплена вручную
      if (d.goalPin && d.goalPin !== g.id) return false; // закреплена за другой целью
      return (g.needMatch || []).includes(d.need);    // мягкое совпадение по нише
    },
    goalDeals(g) { return (this.M.deals || []).filter(d => this.dealMatchesGoal(d, g)); },
    // сделка не попала ни в одну цель (ни по нише, ни по pin)
    dealUnassigned(d) { return !(this.M.goals || []).some(g => this.dealMatchesGoal(d, g)); },
    goalProgress(g) {
      let val;
      if (g.kind === 'packages') val = (this.M.packages || []).filter(p => p.ready === 'в продвижении').length;
      else val = this.goalDeals(g).reduce((s, d) => s + (d.amount || 0), 0); // revenue
      const pct = g.target ? Math.min(100, Math.round(val / g.target * 100)) : 0;
      return { val, pct };
    },
    // формула сигнала «отстаёт» (ресёрч 6.12 §4): pace = progress / time_elapsed
    goalSignal(g) {
      const pr = this.goalProgress(g);
      const progress = g.target ? Math.min(1, pr.val / g.target) : 0;
      const t0 = new Date(g.periodStart).getTime(), t1 = new Date(g.periodEnd).getTime();
      const now = new Date(this.M.TODAY).getTime();
      let elapsed = (now - t0) / Math.max(1, (t1 - t0));
      elapsed = Math.max(0, Math.min(1, elapsed));
      const dealCnt = this.goalDeals(g).length;
      if (g.kind !== 'packages' && dealCnt === 0) return { sig: 'plan', label: 'планируется', col: 'var(--info)', pace: 0 };
      const pace = progress / Math.max(elapsed, 0.01);
      let sig, label, col;
      if (pace >= 0.9) { sig = 'ok'; label = 'хорошо'; col = 'var(--ok)'; }
      else if (pace >= 0.6) { sig = 'slow'; label = 'буксует'; col = 'var(--warn)'; }
      else if (elapsed > 0.25) { sig = 'behind'; label = 'отстаёт'; col = 'var(--err)'; }
      else { sig = 'slow'; label = 'буксует'; col = 'var(--warn)'; }
      return { sig, label, col, pace, elapsed, progress };
    },
    goalFmt(g, n) { return g.unit === '₽' ? this.money(n) : (n + ' ' + g.unit); },
    goalToggle(id) { this.goalSel = this.goalSel === id ? null : id; this.render(); },
    // ручной override: закрепить сделку за целью (pin) либо исключить (anti-pin) — для краевых случаев
    goalPinModal(dealId) {
      const d = this.dealById(dealId); if (!d) return;
      const opts = (this.M.goals || []).map(g => `<option value="${g.id}" ${d.goalPin === g.id ? 'selected' : ''}>${this.esc(g.title)}</option>`).join('');
      const autoNiche = (this.M.goals || []).filter(g => (g.needMatch || []).includes(d.need)).map(g => g.title).join(', ') || 'нет совпадений';
      const body = `<div class="label mb-1">Сделка</div><div class="text-sm mb-2">${this.esc(d.title)} · потребность: <b>${this.esc(d.need)}</b></div>
        <div class="text-[12px] mb-3" style="color:var(--text-dim)">Авто-связь по нише: ${this.esc(autoNiche)}. Override нужен только для исключений.</div>
        <div class="label mb-1">Ручное закрепление (override)</div>
        <select id="m_pin" class="input w-full">
          <option value="" ${!d.goalPin ? 'selected' : ''}>— авто (по нише) —</option>
          ${opts}
          <option value="-" ${d.goalPin === '-' ? 'selected' : ''}>— исключить из всех целей —</option>
        </select>`;
      this.openModal('Override связи с целью', body, () => {
        const v = document.getElementById('m_pin').value;
        d.goalPin = v;
        this.toast(v === '-' ? 'Сделка исключена из целей' : v ? 'Сделка закреплена за целью' : 'Связь — авто (по нише)', v === '-' ? 'info' : 'ok');
        this.render();
      });
    },
    goalPinClear(dealId) { const d = this.dealById(dealId); if (d) { d.goalPin = ''; this.toast('Override снят — связь по нише', 'info'); this.render(); } },
    vGoals() {
      const M = this.M;
      const st = M.strategy || { title: 'Стратегия', horizon: '', directions: [] };
      const goals = M.goals || [];
      const unassigned = (M.deals || []).filter(d => this.dealUnassigned(d));
      // Directions list display
      const dirItems = st.directions && st.directions.length
        ? st.directions.map(d =>
            `<span class="pill text-[10px] inline-flex items-center gap-1" style="color:var(--text-dim);border-color:var(--border)">${this.esc(d.title)}<span class="cursor-pointer hover:text-[var(--err)]" data-dir-del="${d.id}">✕</span></span>`
          ).join('')
        : `<span class="text-[12px]" style="color:var(--text-mute)">Нет направлений. Добавьте первое.</span>`;
      const dirBlock = `
        <div class="card p-2 mt-2" style="background:var(--surface-2)">
          <div class="flex items-center justify-between mb-1">
            <div class="label">Направления</div>
            <button class="btn text-[11px]" data-dir-add="1">+ Добавить</button>
          </div>
          <div class="flex flex-wrap gap-1" id="dirList">${dirItems}</div>
        </div>`;
      const goalCards = goals.map(g => {
        const pr = this.goalProgress(g);
        const ds = this.goalDeals(g);
        const sg = this.goalSignal(g);
        const open = this.goalSel === g.id;
        const barCol = pr.pct >= 100 ? 'var(--ok)' : pr.pct >= 50 ? 'var(--accent)' : 'var(--warn)';
        const gProjects = this.projectsByGoal(g);
        const outsideDeals = this.goalDealsOutsideProjects(g);
        const projRows = gProjects.map(p => {
          const ppr = this.projectProgress(p);
          const psg = this.projectSignal(p);
          return `<div class="flex items-center gap-2 py-1 text-[13px] border-t" style="border-color:var(--border)">
            <span class="flex-1 cursor-pointer hover:underline" data-go="projects:">📁 ${this.esc(p.title)}</span>
            <span class="pill text-[10px]" style="color:var(--text-dim)">🔖 ${this.esc(p.need)}</span>
            <span class="pill text-[10px]" style="color:${psg.col};border-color:${psg.col}">${psg.label}</span>
            <span style="color:var(--text-dim)">${ppr.pct}%</span>
          </div>`;
        }).join('');
        const outsideRows = outsideDeals.map(d => `
          <div class="flex items-center gap-2 py-1 text-[13px] border-t" style="border-color:var(--border)">
            <span class="flex-1 cursor-pointer hover:underline" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</span>
            <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(d.need)}</span>
            <span class="pill text-[10px]" style="color:var(--warn);border-color:var(--warn)">вне проектов</span>
            <span style="color:var(--text-dim)">${this.money(d.amount)}</span>
            <button class="btn text-[11px]" data-goal-pin="${d.id}" title="Override">⋯</button>
          </div>`).join('');
        return `<div class="card p-3">
          <div class="flex items-start gap-2 cursor-pointer" data-goal-toggle="${g.id}">
            <span class="text-lg">🎯</span>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold">${this.esc(g.title)}</div>
              <div class="label mt-0.5">${this.esc(g.metric)} · период ${g.period} · ${this.esc(g.owner)}</div>
            </div>
            <a class="btn text-[11px] shrink-0" data-go="goal:${g.id}" title="Открыть карточку цели">открыть →</a>
            <span class="pill text-[11px] shrink-0" style="color:${sg.col};border-color:${sg.col}" title="Сигнал ставит оркестратор (формула pace)">${this.petIco(13)} ${sg.label}</span>
            <span class="text-[12px]" style="color:var(--text-mute)">${open ? '▲' : '▼'}</span>
          </div>
          ${g.needMatch && g.needMatch.length ? `<div class="flex flex-wrap gap-1 mt-2">${g.needMatch.map(n => `<span class="pill text-[10px]" style="color:var(--text-dim)">🔖 ${this.esc(n)}</span>`).join('')}</div>` : ''}
          <div class="mt-2">
            <div class="flex items-center justify-between text-[12px] mb-1">
              <span style="color:var(--text-dim)">${this.goalFmt(g, pr.val)} из ${this.goalFmt(g, g.target)}</span>
              <span class="font-medium" style="color:${barCol}">${pr.pct}%</span>
            </div>
            <div style="height:7px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${pr.pct}%;background:${barCol}"></div></div>
            <div class="label mt-2">Проектов · ${gProjects.length} · сделок ниши · ${ds.length}</div>
          </div>
          ${open ? `<div class="mt-1">
            ${gProjects.length ? `<div class="label mt-1 mb-0.5">Проекты цели</div>${projRows}` : ''}
            ${outsideDeals.length ? `<div class="label mt-2 mb-0.5">Сделки цели вне проектов · ${outsideDeals.length}</div>${outsideRows}` : ''}
            ${!gProjects.length && !outsideDeals.length ? `<div class="text-[12px] py-2" style="color:var(--text-mute)">Под нишу цели пока нет проектов и сделок</div>` : ''}
          </div>` : ''}
        </div>`;
      }).join('');
      const unassignedBlock = unassigned.length ? `<div class="card p-3">
        <div class="label mb-2">Сделки вне ниш целей · ${unassigned.length}</div>
        <div class="text-[12px] mb-2" style="color:var(--text-mute)">Потребность сделки не совпала ни с одной целью. Можно закрепить вручную (override) или оставить как есть.</div>
        <div class="flex flex-col">${unassigned.map(d => `
          <div class="flex items-center gap-2 py-1 text-[13px] border-t" style="border-color:var(--border)">
            <span class="flex-1 cursor-pointer hover:underline" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</span>
            <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(d.need)}</span>
            <span style="color:var(--text-dim)">${this.money(d.amount)}</span>
            <button class="btn btn-accent text-[11px]" data-goal-pin="${d.id}">📌 Закрепить</button>
          </div>`).join('')}</div>
      </div>` : '';
      return `<div class="flex flex-col gap-3">
        <div class="card p-4" style="background:var(--accent-soft)">
          <div class="label">Стратегия · ${st.horizon}</div>
          <div class="text-sm font-semibold mt-1">${this.esc(st.title)}</div>
          <div class="text-[13px] mt-1" style="color:var(--text-dim)">Связь сделок с целями — <b>мягкая, снизу вверх</b>: цель отслеживает нишу (🔖 потребности), сделки попадают в неё автоматически по своей потребности. Сигнал (${this.petIco(13)} хорошо/буксует/отстаёт) ставит оркестратор по формуле прогресс/время.</div>
        </div>
        ${dirBlock}
        <div class="grid gap-3" style="grid-template-columns:repeat(auto-fill,minmax(320px,1fr))">${goalCards}</div>
        ${unassignedBlock}
      </div>`;
    },
    // ======== ЧАНК 6.14: ДАШБОРД МЕТРИК (аналитический обзор) ========
    // helper: сумма «в работе» = сделки в нетерминальных стадиях
    dashTermStages() { return ['Сервис']; }, // терминальная стадия успеха (последняя); проигрыш в mock не моделируется
    dashKpis() {
      const M = this.M;
      const deals = M.deals || [];
      const active = deals.filter(d => d.stage !== 'Сервис');
      const sumWork = active.reduce((s, d) => s + (d.amount || 0), 0);
      const goalsRisk = (M.goals || []).filter(g => this.goalSignal(g).sig === 'behind').length;
      const drafts = (M.owlSuggestions || []).filter(o => o.grade === 'CONFIRM').length;
      return [
        { label: 'Выручка в работе', val: this.money(sumWork), sub: active.length + ' активных сделок', col: 'var(--accent)', ico: '💰' },
        { label: 'Сделок всего', val: deals.length, sub: active.length + ' в работе', col: 'var(--ok)', ico: '🤝' },
        { label: 'Цели в риске', val: goalsRisk, sub: 'сигнал «отстаёт»', col: goalsRisk ? 'var(--err)' : 'var(--text-mute)', ico: '⚠️' },
        { label: 'Черновики ПЕТРУШКИ', val: drafts, sub: 'на проверке', col: drafts ? 'var(--warn)' : 'var(--text-mute)', ico: this.petIco(15) },
      ];
    },
    // воронка: по стадиям STAGES (жизненный цикл); последняя «Сервис» — терминальная (завершено). Win/lose в модели нет.
    dashFunnel() {
      const M = this.M;
      const stages = M.STAGES || [];
      const deals = M.deals || [];
      const rows = stages.map((st, i) => {
        const ds = deals.filter(d => d.stage === st);
        const sum = ds.reduce((s, d) => s + (d.amount || 0), 0);
        return { stage: st, cnt: ds.length, sum, terminal: i === stages.length - 1 };
      });
      const maxSum = Math.max(1, ...rows.map(r => r.sum));
      return { rows, maxSum };
    },
    vDashboard() {
      const kpis = this.dashKpis();
      const kpiCards = kpis.map(k => `<div class="card p-3">
        <div class="flex items-center gap-2"><span class="text-lg">${k.ico}</span><span class="label">${k.label}</span></div>
        <div class="text-2xl font-bold mt-1" style="color:${k.col}">${k.val}</div>
        <div class="text-[12px] mt-0.5" style="color:var(--text-dim)">${k.sub}</div>
      </div>`).join('');
      // Виджет: воронка сделок
      const fn = this.dashFunnel();
      const funnelRows = fn.rows.map(r => {
        const w = Math.round(r.sum / fn.maxSum * 100);
        const col = r.terminal ? 'var(--ok)' : 'var(--accent)';
        return `<div class="flex items-center gap-2 text-[13px]">
          <span class="shrink-0" style="width:108px;color:var(--text-dim)">${r.stage}${r.terminal ? ' <span class="pill text-[10px]" style="color:var(--ok);border-color:var(--ok)">завершено</span>' : ''}</span>
          <div class="flex-1" style="height:22px;border-radius:6px;background:var(--border);overflow:hidden;position:relative">
            <div style="height:100%;width:${Math.max(w, r.cnt ? 6 : 0)}%;background:${col};opacity:.85"></div>
          </div>
          <span class="shrink-0 text-right" style="width:42px">${r.cnt} шт</span>
          <span class="shrink-0 text-right" style="width:96px;color:var(--text-dim)">${this.money(r.sum)}</span>
        </div>`;
      }).join('');
      const funnelWidget = `<div class="card p-4">
        <div class="flex items-center justify-between mb-2"><div class="text-sm font-semibold">📈 Воронка сделок</div><span class="label">по стадиям жизненного цикла</span></div>
        <div class="flex flex-col gap-1.5">${funnelRows}</div>
        <div class="text-[11px] mt-2" style="color:var(--text-mute)">«Сервис» — терминальная стадия (реализовано → обслуживание). Проигрыши в эскизе не моделируются.</div>
      </div>`;
      // Виджет: прогресс целей
      const goals = this.M.goals || [];
      const goalCards = goals.map(g => {
        const pr = this.goalProgress(g);
        const sg = this.goalSignal(g);
        const barCol = pr.pct >= 100 ? 'var(--ok)' : pr.pct >= 50 ? 'var(--accent)' : 'var(--warn)';
        return `<div class="card-2 p-3">
          <div class="flex items-start gap-2">
            <span class="text-base">🎯</span>
            <div class="flex-1 min-w-0"><div class="text-[13px] font-medium leading-snug">${this.esc(g.title)}</div></div>
            <span class="pill text-[10px] shrink-0" style="color:${sg.col};border-color:${sg.col}">${sg.label}</span>
          </div>
          <div class="flex items-center justify-between text-[12px] mt-2 mb-1">
            <span style="color:var(--text-dim)">${this.goalFmt(g, pr.val)} из ${this.goalFmt(g, g.target)}</span>
            <span class="font-semibold" style="color:${barCol}">${pr.pct}%</span>
          </div>
          <div style="height:6px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${pr.pct}%;background:${barCol}"></div></div>
        </div>`;
      }).join('');
      const goalsWidget = `<div class="card p-4">
        <div class="flex items-center justify-between mb-3"><div class="text-sm font-semibold">🎯 Прогресс целей</div><span class="label cursor-pointer hover:underline" data-go="goals:">все цели →</span></div>
        <div class="grid gap-3" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">${goalCards}</div>
      </div>`;
      // Виджет: прогресс проектов (топ по прогрессу)
      const projs = (this.M.projects || []).slice().sort((a, b) => this.projectProgress(b).pct - this.projectProgress(a).pct);
      const projCards = projs.map(p => {
        const pr = this.projectProgress(p);
        const sg = this.projectSignal(p);
        const owner = this.teamById(p.ownerId);
        const barCol = pr.pct >= 100 ? 'var(--ok)' : pr.pct >= 50 ? 'var(--accent)' : 'var(--warn)';
        return `<div class="card-2 p-3">
          <div class="flex items-start gap-2">
            <span class="text-base">📁</span>
            <div class="flex-1 min-w-0"><div class="text-[13px] font-medium leading-snug">${this.esc(p.title)}</div><div class="label mt-0.5">🔖 ${this.esc(p.need)}${owner ? ' · ' + owner.avatar + ' ' + this.esc(owner.name) : ''}</div></div>
            <span class="pill text-[10px] shrink-0" style="color:${sg.col};border-color:${sg.col}">${sg.label}</span>
          </div>
          <div class="flex items-center justify-between text-[12px] mt-2 mb-1">
            <span style="color:var(--text-dim)">${this.money(pr.val)} из ${this.money(p.target)}</span>
            <span class="font-semibold" style="color:${barCol}">${pr.pct}%</span>
          </div>
          <div style="height:6px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${pr.pct}%;background:${barCol}"></div></div>
        </div>`;
      }).join('');
      const projWidget = `<div class="card p-4">
        <div class="flex items-center justify-between mb-3"><div class="text-sm font-semibold">📁 Прогресс проектов</div><span class="label cursor-pointer hover:underline" data-go="projects:">все проекты →</span></div>
        <div class="grid gap-3" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">${projCards || '<div class="text-[12px]" style="color:var(--text-mute)">Нет проектов</div>'}</div>
      </div>`;
      // Виджет: нагрузка команды (сделки/задачи по owner-имени; проекты по ownerId)
      const team = this.M.team || [];
      const deals = this.M.deals || [];
      const tasks = this.M.tasks || [];
      const projsAll = this.M.projects || [];
      const loadRows = team.map(u => {
        const dCnt = deals.filter(d => d.owner === u.name && d.stage !== 'Сервис').length;
        const tCnt = tasks.filter(t => t.owner === u.name && t.status !== 'done').length;
        const pCnt = projsAll.filter(p => p.ownerId === u.id && p.status === 'активен').length;
        const load = dCnt + tCnt + pCnt;
        const cap = u.cap || 5;
        const pct = Math.min(100, Math.round(load / cap * 100));
        const col = pct >= 100 ? 'var(--err)' : pct >= 70 ? 'var(--warn)' : 'var(--ok)';
        return `<div class="flex items-center gap-3 text-[13px]">
          <span class="shrink-0" style="width:148px">${u.avatar} ${this.esc(u.name)} <span class="label">· ${this.esc(u.role)}</span></span>
          <div class="flex-1" style="height:18px;border-radius:6px;background:var(--border);overflow:hidden"><div style="height:100%;width:${Math.max(pct, load ? 5 : 0)}%;background:${col};opacity:.85"></div></div>
          <span class="shrink-0 text-right" style="width:52px;color:${col};font-weight:600">${load}/${cap}</span>
          <span class="shrink-0" style="width:128px;color:var(--text-dim);font-size:11px">🤝${dCnt} · ✅${tCnt} · 📁${pCnt}</span>
        </div>`;
      }).join('');
      const loadWidget = `<div class="card p-4">
        <div class="flex items-center justify-between mb-3"><div class="text-sm font-semibold">👥 Нагрузка команды</div><span class="label cursor-pointer hover:underline" data-go="team:">команда →</span></div>
        <div class="flex flex-col gap-2">${loadRows}</div>
        <div class="text-[11px] mt-2" style="color:var(--text-mute)">Нагрузка = активные сделки + открытые задачи + активные проекты / cap.</div>
      </div>`;
      // Виджет: лента активности (signals + последние inbox)
      const sigItems = (this.M.signals || []).map(s => {
        const d = this.dealById(s.dealId);
        return { col: this.sevColor(s.sev), ico: '●', text: s.text, sub: s.objectTitle, go: d ? 'deal:' + d.id : '', tag: s.sev };
      });
      const inboxItems = (this.M.inbox || []).slice(0, 4).map(n => ({
        col: 'var(--info)', ico: n.icon || '📥', text: n.text, sub: n.from + ' · ' + n.time, go: '', tag: n.src
      }));
      const feed = [...sigItems, ...inboxItems];
      const feedRows = feed.map(f => `<div class="flex items-start gap-2 py-1.5 text-[13px] border-t" style="border-color:var(--border)">
        <span class="shrink-0" style="color:${f.col}">${f.ico}</span>
        <div class="flex-1 min-w-0">
          <div class="leading-snug">${this.esc(f.text)}</div>
          ${f.sub ? `<div class="text-[12px]" style="color:var(--text-dim)">${f.go ? `<span class="underline cursor-pointer" data-go="${f.go}">${this.esc(f.sub)}</span>` : this.esc(f.sub)}</div>` : ''}
        </div>
        <span class="pill text-[10px] shrink-0" style="color:${f.col};border-color:${f.col}">${this.esc(f.tag)}</span>
      </div>`).join('');
      const feedWidget = `<div class="card p-4">
        <div class="flex items-center justify-between mb-2"><div class="text-sm font-semibold">🔔 Лента активности</div><span class="label cursor-pointer hover:underline" data-go="inbox:">входящие →</span></div>
        <div class="flex flex-col">${feedRows || '<div class="text-[12px] py-2" style="color:var(--text-mute)">Нет событий</div>'}</div>
      </div>`;
      return `<div class="flex flex-col gap-4">
        <div class="grid gap-3" style="grid-template-columns:repeat(auto-fit,minmax(190px,1fr))">${kpiCards}</div>
        ${funnelWidget}
        <div class="grid gap-4" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr))">${goalsWidget}${projWidget}</div>
        <div class="grid gap-4" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr))">${loadWidget}${feedWidget}</div>
      </div>`;
    },

    // ======== ЧАНК 6.16: КАНБАН СДЕЛОК (drag по STAGES + фильтры) ========
    // 6 колонок = STAGES (линейный жизненный цикл, без win/lose). Drag в любую сторону (эскиз).
    // Фильтры (Владелец/NEED/Цель) влияют на все колонки. Карточка → go('deal', id).
    kanbanFiltered() {
      const f = this.kanbanFilter;
      return (this.M.deals || []).filter(d => {
        if (f.owner !== 'all' && d.owner !== f.owner) return false;
        if (f.need !== 'all' && d.need !== f.need) return false;
        if (f.goal !== 'all') {
          const g = this.goalById(f.goal);
          if (!g || !this.dealMatchesGoal(d, g)) return false;
        }
        return true;
      });
    },
    kanbanColumns() {
      const deals = this.kanbanFiltered();
      return (this.M.STAGES || []).map(stage => {
        const items = deals.filter(d => d.stage === stage);
        const sum = items.reduce((s, d) => s + (d.amount || 0), 0);
        return { stage, items, cnt: items.length, sum };
      });
    },
    // связь сделки с проектом/целью для карточки
    dealProjectLink(d) {
      const p = (this.M.projects || []).find(pr => this.dealMatchesProject(d, pr));
      if (p) return { kind: 'project', icon: '📁', title: p.title, go: 'projects:' };
      const g = (this.M.goals || []).find(gl => this.dealMatchesGoal(d, gl));
      if (g) return { kind: 'goal', icon: '🎯', title: g.title, go: 'goals:' };
      return null;
    },
    kanbanFilterReset() { this.kanbanFilter = { owner: 'all', need: 'all', goal: 'all' }; this.render(); },
    vKanban() {
      const f = this.kanbanFilter;
      const cols = this.kanbanColumns();
      const total = cols.reduce((s, c) => s + c.cnt, 0);
      const totalSum = cols.reduce((s, c) => s + c.sum, 0);
      // --- бар фильтров ---
      const ownerOpts = ['<option value="all">Все владельцы</option>']
        .concat((this.M.team || []).map(u => `<option value="${this.esc(u.name)}" ${f.owner === u.name ? 'selected' : ''}>${u.avatar} ${this.esc(u.name)}</option>`)).join('');
      const needOpts = ['<option value="all">Все потребности</option>']
        .concat((this.M.NEED || []).map(n => `<option value="${n}" ${f.need === n ? 'selected' : ''}>${n}</option>`)).join('');
      const goalOpts = ['<option value="all">Все цели</option>']
        .concat((this.M.goals || []).map(g => `<option value="${g.id}" ${f.goal === g.id ? 'selected' : ''}>${this.esc(g.title)}</option>`)).join('');
      const active = f.owner !== 'all' || f.need !== 'all' || f.goal !== 'all';
      const filterBar = `<div class="card p-3 mb-4 flex flex-wrap items-center gap-2">
        <span class="label">Фильтры</span>
        <select id="kbOwner" class="input text-[13px]" style="width:auto">${ownerOpts}</select>
        <select id="kbNeed" class="input text-[13px]" style="width:auto">${needOpts}</select>
        <select id="kbGoal" class="input text-[13px]" style="width:auto">${goalOpts}</select>
        ${active ? '<button class="btn text-[12px]" id="kbReset">✕ Сбросить</button>' : ''}
        <span class="ml-auto text-[12px]" style="color:var(--text-dim)">На доске: <b>${total}</b> сделок · ${this.money(totalSum)}</span>
      </div>`;
      // --- колонки ---
      const columns = cols.map(col => {
        const cards = col.items.map(d => {
          const c = this.clientById(d.clientId);
          const u = (this.M.team || []).find(t => t.name === d.owner);
          const link = this.dealProjectLink(d);
          const linkHtml = link
            ? `<div class="text-[10px] mt-1 truncate" style="color:var(--text-mute)">${link.icon} ${this.esc(link.title)}</div>`
            : '';
          return `<div class="card-2 p-2.5 cursor-grab active:cursor-grabbing" draggable="true" data-kb-drag="${d.id}" data-go="deal:${d.id}">
            <div class="text-[13px] font-medium leading-tight">${this.esc(d.title)}</div>
            <div class="text-[11px] mt-1 truncate" style="color:var(--text-dim)">${this.esc(this.clientName(c))}</div>
            <div class="flex items-center justify-between mt-1.5">
              <span class="text-[12px] font-medium">${this.money(d.amount)}</span>
              <span class="text-[12px]" title="${this.esc(d.owner)}">${u ? u.avatar : '👤'}</span>
            </div>
            <div class="flex items-center gap-1 mt-1.5 flex-wrap"><span class="pill text-[10px]">${this.esc(d.need)}</span></div>
            ${linkHtml}
          </div>`;
        }).join('') || `<div class="text-[11px] py-4 text-center" style="color:var(--text-mute)">— пусто —</div>`;
        return `<div class="shrink-0 w-[230px] flex flex-col" data-kb-col="${this.esc(col.stage)}">
          <div class="flex items-center justify-between mb-2 px-1">
            <span class="text-[13px] font-semibold">${this.esc(col.stage)}</span>
            <span class="pill text-[10px]">${col.cnt}</span>
          </div>
          <div class="text-[11px] mb-2 px-1" style="color:var(--text-dim)">${this.money(col.sum)}</div>
          <div class="kb-drop flex flex-col gap-2 flex-1 rounded-lg p-1.5 transition-colors" data-kb-drop="${this.esc(col.stage)}" style="min-height:120px;background:var(--surface-2,rgba(0,0,0,0.02))">${cards}</div>
        </div>`;
      }).join('');
      return `<div>
        <div class="flex items-center gap-2 mb-1"><span class="text-xl">🗂</span><h1 class="text-lg font-semibold">Канбан сделок</h1></div>
        <p class="text-[12px] mb-3" style="color:var(--text-dim)">Перетащите карточку между стадиями · клик открывает карточку сделки</p>
        ${filterBar}
        <div class="flex gap-3 overflow-x-auto pb-3" style="scrollbar-width:thin">${columns}</div>
      </div>`;
    },

    // ======== ЧАНК 6.13: ПРОЕКТЫ (средний уровень иерархии Стратегия→Цели→ПРОЕКТЫ→Сделки) ========
    // Цель→Проект: ЖЁСТКАЯ (project.goalId). Проект→Сделка: SOFT auto — сделка матчит цель проекта
    // И deal.need===project.need; override: dealPin содержит d.id (закрепить) или '-'+d.id (исключить).
    projSel: null, // развёрнутый проект (null = все свёрнуты)
    projectById(id) { return (this.M.projects || []).find(p => p.id === id) || null; },
    teamById(id) { return (this.M.team || []).find(u => u.id === id) || null; },
    projectsByGoal(g) { return (this.M.projects || []).filter(p => p.goalId === g.id); },
    // сделка принадлежит проекту: anti-pin исключает; pin включает; иначе — её цель совпадает с целью проекта И ниша совпадает
    dealMatchesProject(d, p) {
      const pin = p.dealPin || [];
      if (pin.includes('-' + d.id)) return false;     // anti-pin: исключена из проекта
      if (pin.includes(d.id)) return true;            // pin: закреплена в проекте
      const g = this.goalById(p.goalId);
      if (!g || !this.dealMatchesGoal(d, g)) return false; // сделка не в цели проекта — не может быть в проекте
      return d.need === p.need;                        // мягкое совпадение по нише проекта
    },
    projectDeals(p) { return (this.M.deals || []).filter(d => this.dealMatchesProject(d, p)); },
    // сделки цели, не попавшие ни в один её проект (для блока «вне проектов»)
    goalDealsOutsideProjects(g) {
      const projs = this.projectsByGoal(g);
      return this.goalDeals(g).filter(d => !projs.some(p => this.dealMatchesProject(d, p)));
    },
    // прогресс проекта (вариант «а»): сумма сумм сделок проекта / target
    projectProgress(p) {
      const val = this.projectDeals(p).reduce((s, d) => s + (d.amount || 0), 0);
      const pct = p.target ? Math.min(100, Math.round(val / p.target * 100)) : 0;
      return { val, pct };
    },
    // сигнал проекта по формуле pace (как у целей): progress/elapsed
    projectSignal(p) {
      const pr = this.projectProgress(p);
      const progress = p.target ? Math.min(1, pr.val / p.target) : 0;
      const t0 = new Date(p.periodStart).getTime(), t1 = new Date(p.periodEnd).getTime();
      const now = new Date(this.M.TODAY).getTime();
      let elapsed = (now - t0) / Math.max(1, (t1 - t0));
      elapsed = Math.max(0, Math.min(1, elapsed));
      const cnt = this.projectDeals(p).length;
      if (cnt === 0) return { sig: 'plan', label: 'планируется', col: 'var(--info)', pace: 0 };
      const pace = progress / Math.max(elapsed, 0.01);
      let sig, label, col;
      if (pace >= 0.9) { sig = 'ok'; label = 'хорошо'; col = 'var(--ok)'; }
      else if (pace >= 0.6) { sig = 'slow'; label = 'буксует'; col = 'var(--warn)'; }
      else if (elapsed > 0.25) { sig = 'behind'; label = 'отстаёт'; col = 'var(--err)'; }
      else { sig = 'slow'; label = 'буксует'; col = 'var(--warn)'; }
      return { sig, label, col, pace, elapsed, progress };
    },
    projStatusColor(s) { return s === 'активен' ? 'var(--ok)' : s === 'пауза' ? 'var(--warn)' : 'var(--text-mute)'; },
    projToggle(id) { this.projSel = this.projSel === id ? null : id; this.render(); },
    // ручной override закрепления сделки в проекте (pin / исключить)
    projPinModal(projId) {
      const p = this.projectById(projId); if (!p) return;
      const g = this.goalById(p.goalId);
      // кандидаты: сделки цели проекта (можно закрепить даже с другой нишей) + уже закреплённые
      const pool = (this.M.deals || []).filter(d => (g && this.dealMatchesGoal(d, g)) || (p.dealPin || []).includes(d.id));
      const pin = p.dealPin || [];
      const rows = pool.map(d => {
        const isPin = pin.includes(d.id);
        const isAnti = pin.includes('-' + d.id);
        const sel = isPin ? 'pin' : isAnti ? 'off' : 'auto';
        return `<div class="flex items-center gap-2 py-1 text-[13px] border-t" style="border-color:var(--border)">
          <span class="flex-1">${this.esc(d.title)} <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(d.need)}</span></span>
          <select class="input text-[12px]" data-proj-pin-deal="${d.id}">
            <option value="auto" ${sel === 'auto' ? 'selected' : ''}>авто</option>
            <option value="pin" ${sel === 'pin' ? 'selected' : ''}>закрепить</option>
            <option value="off" ${sel === 'off' ? 'selected' : ''}>исключить</option>
          </select>
        </div>`;
      }).join('') || `<div class="text-[12px] py-2" style="color:var(--text-mute)">Нет сделок-кандидатов в цели проекта</div>`;
      const body = `<div class="label mb-1">Проект</div><div class="text-sm mb-2">${this.esc(p.title)} · ниша: <b>${this.esc(p.need)}</b></div>
        <div class="text-[12px] mb-2" style="color:var(--text-dim)">Сделки попадают в проект автоматически (ниша проекта внутри цели). Override — для краевых случаев.</div>
        ${rows}`;
      this.openModal('Сделки проекта (override)', body, () => {
        const next = [];
        document.querySelectorAll('[data-proj-pin-deal]').forEach(sel => {
          const did = sel.getAttribute('data-proj-pin-deal'); const v = sel.value;
          if (v === 'pin') next.push(did); else if (v === 'off') next.push('-' + did);
        });
        p.dealPin = next;
        this.toast('Связи сделок проекта обновлены', 'ok');
        this.render();
      });
    },
    vProjects() {
      const M = this.M;
      const goals = M.goals || [];
      const projs = M.projects || [];
      // группировка проектов по целям; цели без проектов не показываем как заголовок (но даём блок «вне проектов»)
      const groups = goals.map(g => {
        const gp = this.projectsByGoal(g);
        if (!gp.length) return '';
        const cards = gp.map(p => {
          const pr = this.projectProgress(p);
          const ds = this.projectDeals(p);
          const sg = this.projectSignal(p);
          const owner = this.teamById(p.ownerId);
          const open = this.projSel === p.id;
          const barCol = pr.pct >= 100 ? 'var(--ok)' : pr.pct >= 50 ? 'var(--accent)' : 'var(--warn)';
          const dealRows = ds.length ? ds.map(d => {
            const isPin = (p.dealPin || []).includes(d.id);
            return `<div class="flex items-center gap-2 py-1 text-[13px] border-t" style="border-color:var(--border)">
              <span class="flex-1 cursor-pointer hover:underline" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</span>
              <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(d.need)}</span>
              ${isPin ? `<span class="pill text-[10px]" style="color:var(--accent);border-color:var(--accent)">📌 pin</span>` : ''}
              <span class="pill text-[11px]">${d.stage}</span>
              <span style="color:var(--text-dim)">${this.money(d.amount)}</span>
            </div>`;
          }).join('') : `<div class="text-[12px] py-2" style="color:var(--text-mute)">Под нишу проекта пока нет сделок</div>`;
          return `<div class="card p-3">
            <div class="flex items-start gap-2 cursor-pointer" data-proj-toggle="${p.id}">
              <span class="text-lg">📁</span>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-semibold">${this.esc(p.title)}</div>
                <div class="label mt-0.5">🔖 ${this.esc(p.need)} · ${owner ? owner.avatar + ' ' + this.esc(owner.name) : '—'} · до ${p.periodEnd.slice(0, 7)}</div>
              </div>
              <a class="btn text-[11px] shrink-0" data-go="project:${p.id}" title="Открыть карточку проекта">открыть →</a>
              <span class="pill text-[10px] shrink-0" style="color:${this.projStatusColor(p.status)};border-color:${this.projStatusColor(p.status)}">${p.status}</span>
              <span class="pill text-[11px] shrink-0" style="color:${sg.col};border-color:${sg.col}" title="Сигнал по формуле pace">${this.petIco(13)} ${sg.label}</span>
              <span class="text-[12px]" style="color:var(--text-mute)">${open ? '▲' : '▼'}</span>
            </div>
            <div class="mt-2">
              <div class="flex items-center justify-between text-[12px] mb-1">
                <span style="color:var(--text-dim)">${this.money(pr.val)} из ${this.money(p.target)}</span>
                <span class="font-medium" style="color:${barCol}">${pr.pct}%</span>
              </div>
              <div style="height:7px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${pr.pct}%;background:${barCol}"></div></div>
              <div class="flex items-center justify-between mt-2">
                <span class="label">Сделки проекта (авто) · ${ds.length}</span>
                <button class="btn text-[11px]" data-proj-pin="${p.id}" title="Override связей сделок">⋯ override</button>
              </div>
            </div>
            ${open ? `<div class="mt-1">${dealRows}</div>` : ''}
          </div>`;
        }).join('');
        return `<div class="flex flex-col gap-2">
          <div class="flex items-center gap-2 mt-1"><span class="text-base">🎯</span><span class="text-[13px] font-semibold">${this.esc(g.title)}</span><span class="label">· проектов ${gp.length}</span></div>
          <div class="grid gap-3" style="grid-template-columns:repeat(auto-fill,minmax(320px,1fr))">${cards}</div>
        </div>`;
      }).filter(Boolean).join('');
      // сделки целей вне проектов (для прозрачности иерархии)
      const outside = [];
      goals.forEach(g => { this.goalDealsOutsideProjects(g).forEach(d => { if (!outside.find(x => x.d.id === d.id)) outside.push({ d, g }); }); });
      const outsideBlock = outside.length ? `<div class="card p-3">
        <div class="label mb-2">Сделки целей вне проектов · ${outside.length}</div>
        <div class="text-[12px] mb-2" style="color:var(--text-mute)">Сделка относится к цели, но не входит ни в один её проект. Можно закрепить в проекте через override проекта.</div>
        <div class="flex flex-col">${outside.map(({ d, g }) => `
          <div class="flex items-center gap-2 py-1 text-[13px] border-t" style="border-color:var(--border)">
            <span class="flex-1 cursor-pointer hover:underline" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</span>
            <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(d.need)}</span>
            <span class="pill text-[10px]" style="color:var(--text-dim)">🎯 ${this.esc(g.title)}</span>
            <span style="color:var(--text-dim)">${this.money(d.amount)}</span>
          </div>`).join('')}</div>
      </div>` : '';
      return `<div class="flex flex-col gap-4">
        <div class="card p-4" style="background:var(--accent-soft)">
          <div class="flex items-center justify-between">
            <div>
              <div class="label">Иерархия</div>
              <div class="text-sm font-semibold mt-1">Стратегия → Цели → Проекты → Сделки</div>
            </div>
            <button class="btn btn-accent text-[13px]" data-proj-add>+ Проект</button>
          </div>
          <div class="text-[13px] mt-1" style="color:var(--text-dim)">Проект — крупная инициатива под целью (📁 жёсткая привязка к одной цели). Сделки попадают в проект <b>автоматически</b>: их ниша совпадает с нишей проекта внутри его цели. Прогресс = сумма сделок / план; сигнал (${this.petIco(13)}) — по формуле прогресс/время.</div>
        </div>
        ${groups || `<div class="card p-8 text-center" style="color:var(--text-mute)">Проектов пока нет. Создайте первый!</div>`}
        ${outsideBlock}
      </div>`;
    },

    // ======== ЧАНК 6.20: СКВОЗНОЙ ПОИСК (Ctrl+K) — раздел 1: индекс + результаты ========
    // Единый индекс объектов: {type,id,title,sub,icon,hay}
    cmdkIndex() {
      const M = this.M, out = [];
      const push = (type, id, title, sub, icon, extra) => {
        const hay = ((title || '') + ' ' + (sub || '') + ' ' + (extra || '')).toLowerCase();
        out.push({ type, id, title: title || '', sub: sub || '', icon, hay });
      };
      // Цели
      (M.goals || []).forEach(g => {
        push('goal', g.id, g.title, 'Цель · ' + (g.owner || ''), '🎯', (g.needMatch || []).join(' ') + ' ' + (g.metric || ''));
      });
      // Проекты
      (M.projects || []).forEach(p => {
        const owner = (this.teamById && this.teamById(p.ownerId)) ? this.teamById(p.ownerId).name : (p.ownerId || '');
        push('project', p.id, p.title, 'Проект · ' + (p.need || ''), '📁', owner + ' ' + (p.status || ''));
      });
      // Клиенты
      (M.clients || []).forEach(c => {
        push('client', c.id, c.name || c.title, 'Клиент · ' + (c.niche || c.need || ''), '👤', (c.city || '') + ' ' + (c.contact || ''));
      });
      // Сделки
      (M.deals || []).forEach(d => {
        const cl = this.clientById ? this.clientById(d.clientId) : null;
        push('deal', d.id, d.title, 'Сделка · ' + ((cl && (cl.name || cl.title)) || '') , '🤝', (d.owner || '') + ' ' + (d.need || '') + ' ' + (d.stage || ''));
      });
      // Задачи
      (M.tasks || []).forEach(t => {
        push('task', t.id, t.title, 'Задача · ' + (t.status || ''), '✅', (t.owner || '') + ' ' + (t.kind || ''));
      });
      // Артефакты
      (M.artifacts || []).forEach(a => {
        push('artifact', a.id, a.title, 'Артефакт · ' + (a.kind || '') + (a.ext ? ('.' + a.ext) : ''), '📄', (a.by || '') + ' ' + (a.status || ''));
      });
      return out;
    },
    // Группировка результатов по фасетам, топ-5 + остаток
    cmdkResults() {
      const FACETS = [
        ['goal', 'Цели', '🎯'],
        ['project', 'Проекты', '📁'],
        ['client', 'Клиенты', '👤'],
        ['deal', 'Сделки', '🤝'],
        ['task', 'Задачи', '✅'],
        ['artifact', 'Артефакты', '📄']
      ];
      const q = (this.cmdkQuery || '').trim().toLowerCase();
      const idx = this.cmdkIndex();
      const matched = q ? idx.filter(o => o.hay.indexOf(q) !== -1) : idx;
      const groups = [];
      FACETS.forEach(([type, label, icon]) => {
        const items = matched.filter(o => o.type === type);
        if (!items.length) return;
        groups.push({ type, label, icon, items: items.slice(0, 5), more: Math.max(0, items.length - 5), total: items.length });
      });
      return { groups, total: matched.length, q };
    },
    // Первый результат (для Enter)
    cmdkFirst() {
      const r = this.cmdkResults();
      for (const g of r.groups) { if (g.items.length) return g.items[0]; }
      return null;
    },

    // ======== ЧАНК 6.20 — раздел 2: vCmdk (палитра поиска, императивный overlay) ========
    // Подсветка совпадений подстроки
    cmdkHl(text, q) {
      const s = this.esc(text || '');
      if (!q) return s;
      const lc = s.toLowerCase(), ql = q.toLowerCase();
      let out = '', i = 0;
      while (true) {
        const p = lc.indexOf(ql, i);
        if (p === -1) { out += s.slice(i); break; }
        out += s.slice(i, p) + '<mark style="background:var(--accent-soft,#fde68a);color:inherit;border-radius:3px;padding:0 1px">' + s.slice(p, p + ql.length) + '</mark>';
        i = p + ql.length;
      }
      return out;
    },
    // Внутренний HTML палитры (поле + результаты)
    cmdkInnerHtml() {
      const r = this.cmdkResults();
      const q = r.q;
      let body = '';
      if (!q) {
        // Пустой запрос → подсказка по фасетам
        const facets = [['🎯','Цели'],['📁','Проекты'],['👤','Клиенты'],['🤝','Сделки'],['✅','Задачи'],['📄','Артефакты']];
        body = `<div class="p-4 text-[13px]" style="color:var(--text-dim)">
          <div class="mb-2">Начните вводить — поиск по всем объектам:</div>
          <div class="flex flex-wrap gap-1.5">` +
          facets.map(([ic,lb]) => `<span class="pill text-[12px]">${ic} ${lb}</span>`).join('') +
          `</div><div class="mt-3 text-[11px]" style="color:var(--text-mute)">↑↓ Enter — открыть · Esc — закрыть</div></div>`;
      } else if (!r.total) {
        body = `<div class="p-6 text-center text-[13px]" style="color:var(--text-mute)">Ничего не найдено по «${this.esc(q)}»</div>`;
      } else {
        body = `<div class="max-h-[360px] overflow-auto py-1">` + r.groups.map(g => {
          const items = g.items.map(o => `
            <div class="cmdk-item flex items-center gap-2 px-3 py-2 cursor-pointer" data-go="${o.type}:${o.id}" style="border-radius:8px">
              <span class="text-[15px]">${o.icon}</span>
              <span class="flex-1 min-w-0">
                <span class="block text-[13px] truncate">${this.cmdkHl(o.title, q)}</span>
                <span class="block text-[11px] truncate" style="color:var(--text-mute)">${this.cmdkHl(o.sub, q)}</span>
              </span>
            </div>`).join('');
          const more = g.more > 0 ? `<div class="px-3 py-1 text-[11px]" style="color:var(--text-mute)">+${g.more} ещё</div>` : '';
          return `<div class="mb-1">
            <div class="px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style="color:var(--text-mute)">${g.icon} ${g.label} <span style="opacity:.6">${g.total}</span></div>
            ${items}${more}
          </div>`;
        }).join('') + `</div>`;
      }
      return `<div class="card w-[560px] max-w-full" style="overflow:hidden">
        <div class="flex items-center gap-2 px-3 py-2 border-b" style="border-color:var(--border)">
          <span class="text-[15px]" style="color:var(--text-mute)">🔍</span>
          <input id="cmdkInput" class="input flex-1 text-[14px]" style="border:0;background:transparent" placeholder="Поиск по объектам…" value="${this.esc(q)}" />
          <button class="btn text-[12px]" id="cmdk_x">Esc</button>
        </div>
        ${body}
      </div>`;
    },
    // Открыть/обновить overlay
    cmdkRender() {
      let m = document.getElementById('cmdkModal');
      if (!m) { m = document.createElement('div'); m.id = 'cmdkModal'; document.body.appendChild(m); }
      m.className = 'fixed inset-0 z-[60] flex items-start justify-center p-4';
      m.style.background = 'rgba(0,0,0,.45)';
      m.style.paddingTop = '12vh';
      m.innerHTML = this.cmdkInnerHtml();
      // overlay click closes
      m.onclick = (e) => { if (e.target === m) this.cmdkClose(); };
      // input live
      const inp = document.getElementById('cmdkInput');
      if (inp) {
        inp.oninput = (e) => {
          const pos = e.target.selectionStart;
          this.cmdkQuery = e.target.value;
          this.cmdkRerender();
          const ni = document.getElementById('cmdkInput');
          if (ni) { ni.focus(); try { ni.setSelectionRange(pos, pos); } catch(_){} }
        };
        inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length);
      }
      const xb = document.getElementById('cmdk_x'); if (xb) xb.onclick = () => this.cmdkClose();
      // data-go items
      m.querySelectorAll('[data-go]').forEach(n => {
        n.onclick = (e) => {
          e.stopPropagation();
          const [t, id] = (n.getAttribute('data-go') || '').split(':');
          this.cmdkClose();
          this.go(t, id);
        };
      });
    },
    // Перерисовать только тело при вводе (overlay уже открыт)
    cmdkRerender() {
      const m = document.getElementById('cmdkModal'); if (!m) return;
      this.cmdkRender();
    },
    cmdkToggle() { this.cmdkOpen ? this.cmdkClose() : this.cmdkShow(); },
    cmdkShow() { this.cmdkOpen = true; this.cmdkQuery = ''; this.cmdkRender(); },
    cmdkClose() {
      this.cmdkOpen = false; this.cmdkQuery = '';
      const m = document.getElementById('cmdkModal'); if (m) m.remove();
    },
    // Алиасы для кнопки в шапке (@click="paletteOpen()")
    paletteOpen() { this.cmdkShow(); },
    paletteClose() { this.cmdkClose(); },

    // ======== ЧАНК 6.19: КАРТОЧКА ЦЕЛИ (route #/goal/:id) ========
    // Задачи/артефакты цели — через ВСЕ сделки цели (goalDeals, вкл. вне проектов).
    goalTasks(g) {
      const ids = new Set(this.goalDeals(g).map(d => d.id));
      return (this.M.tasks || []).filter(t => t.dealId && ids.has(t.dealId));
    },
    goalArtifacts(g) {
      const ids = new Set(this.goalDeals(g).map(d => d.id));
      return (this.M.artifacts || []).filter(a => a.dealId && ids.has(a.dealId));
    },
    // breadcrumbs Цели › Цель
    goalCrumbs(g) {
      return `<div class="text-[13px] flex flex-wrap items-center gap-1" style="color:var(--text-dim)">`
        + `<a class="underline cursor-pointer" data-go="goals">🎯 Цели · Стратегия</a>`
        + `<span style="color:var(--text-mute)"> › </span><span style="color:var(--text)">${this.esc(g.title)}</span></div>`;
    },
    vGoalCard(id) {
      const g = this.goalById(id);
      if (!g) return this.stub('Цель не найдена');
      const pr = this.goalProgress(g);
      const sg = this.goalSignal(g);
      const deals = this.goalDeals(g);
      const projs = this.projectsByGoal(g);
      const outside = this.goalDealsOutsideProjects(g);
      const barCol = pr.pct >= 100 ? 'var(--ok)' : pr.pct >= 50 ? 'var(--accent)' : 'var(--warn)';
      // grade-pill сигнал
      const sigPill = `<span class="pill" style="color:${sg.col};border-color:${sg.col}" title="Сигнал по формуле pace (прогресс/время)">${this.petIco(13)} ${this.esc(sg.label)}</span>`;
      const kindPill = `<span class="pill" style="color:var(--text-dim)">${this.esc(g.kind === 'packages' ? 'упаковки' : 'выручка')}</span>`;
      // status dropdown
      const statuses = ['планируется','в работе','выполнена','приостановлена','отменена'];
      const statusOpts = statuses.map(s => `<option value="${s}" ${g.status === s ? 'selected' : ''}>${s}</option>`).join('');
      const statusBlock = `<div class="mt-2"><select class="input text-[12px] w-auto" data-goal-status="${g.id}">${statusOpts}</select></div>`;
      // meta-rows
      const row = (k, v) => `<div class="flex justify-between gap-3 text-[13px] py-1.5 border-t" style="border-color:var(--border)"><span style="color:var(--text-dim)">${k}</span><span class="text-right">${v}</span></div>`;
      const metaRows = [
        row('Метрика', this.esc(g.metric || '—')),
        row('Ниши', `🔖 ${this.esc((g.needMatch || []).join(', '))}`),
        row('Владелец', this.esc(g.owner || '—')),
        row('Период', `${this.esc(g.periodStart)} → ${this.esc(g.periodEnd)}`),
        row('Проектов', String(projs.length)),
        row('Сделок по нише', String(deals.length)),
      ].join('');
      const progBlock = `<div class="mt-1">
        <div class="flex items-center justify-between text-[12px] mb-1"><span style="color:var(--text-dim)">${this.goalFmt(g, pr.val)} из ${this.goalFmt(g, g.target)}</span><span class="font-medium" style="color:${barCol}">${pr.pct}%</span></div>
        <div style="height:8px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${pr.pct}%;background:${barCol}"></div></div>
      </div>`;
      // блок «Проекты цели» — компактные карточки с мини-прогресс-баром
      const projCards = projs.length ? projs.map(p => {
        const ppr = this.projectProgress(p);
        const psg = this.projectSignal(p);
        const owner = this.teamById(p.ownerId);
        const pbar = ppr.pct >= 100 ? 'var(--ok)' : ppr.pct >= 50 ? 'var(--accent)' : 'var(--warn)';
        return `<div class="card-2 p-3 cursor-pointer" data-go="project:${p.id}">
          <div class="flex items-start gap-2">
            <span>📁</span>
            <div class="flex-1 min-w-0">
              <div class="text-[13px] font-semibold leading-snug">${this.esc(p.title)}</div>
              <div class="label mt-0.5">🔖 ${this.esc(p.need)} · ${owner ? owner.avatar + ' ' + this.esc(owner.name) : '—'}</div>
            </div>
            <span class="pill text-[10px] shrink-0" style="color:${psg.col};border-color:${psg.col}">${this.esc(psg.label)}</span>
          </div>
          <div class="mt-2">
            <div class="flex items-center justify-between text-[11px] mb-1"><span style="color:var(--text-dim)">${this.money(ppr.val)} / ${this.money(p.target)}</span><span class="font-medium" style="color:${pbar}">${ppr.pct}%</span></div>
            <div style="height:6px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${ppr.pct}%;background:${pbar}"></div></div>
          </div>
        </div>`;
      }).join('') : `<div class="text-[12px] py-2" style="color:var(--text-mute)">У цели пока нет проектов</div>`;
      const projBlock = `<div class="card p-3"><div class="label mb-2">Проекты цели · ${projs.length}</div><div class="grid grid-cols-1 md:grid-cols-2 gap-3">${projCards}</div></div>`;
      // блок «Сделки вне проектов» с override (goalPinModal)
      const outRows = outside.length ? outside.map(d => {
        const cl = this.clientById(d.clientId);
        return `<div class="flex items-center gap-2 py-1.5 border-t text-[13px]" style="border-color:var(--border)">
          <span class="flex-1 min-w-0 cursor-pointer hover:underline" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</span>
          <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(d.need)}</span>
          <span class="pill text-[11px]">${this.esc(d.stage)}</span>
          <span style="color:var(--text-dim)">${this.money(d.amount)}</span>
          <button class="btn text-[11px] shrink-0" data-goal-pin="${d.id}" title="Override связи с целью">⋯</button>
        </div>`;
      }).join('') : `<div class="text-[12px] py-2" style="color:var(--text-mute)">Все сделки цели распределены по проектам</div>`;
      const outBlock = `<div class="card p-3">
        <div class="label mb-1">Сделки цели вне проектов · ${outside.length}</div>
        <div class="text-[12px] mb-1" style="color:var(--text-mute)">Сделка относится к цели по нише, но не входит ни в один проект. ⋯ — override связи с целью.</div>
        ${outRows}
      </div>`;
      // задачи цели (бейджи 6.17)
      const tasks = this.goalTasks(g);
      const taskRows = tasks.length ? tasks.map(t => {
        const deps = this.taskDeps(t).length, blocked = this.taskIsBlocked(t), parent = this.taskParent(t), subN = this.taskSubtasks(t).length, done = this.taskDone(t);
        const badges = [
          blocked ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--err);border-color:var(--err)">⛔ заблокировано</span>` : '',
          deps ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">🔗 ${deps}</span>` : '',
          parent ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">⊂ подзадача</span>` : '',
          subN ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">☰ ${subN} подзад.</span>` : ''
        ].filter(Boolean).join('');
        return `<div class="flex items-start gap-2 py-1.5 border-t cursor-pointer" style="border-color:var(--border)" data-go="task:${t.id}">
          <span class="shrink-0">${done ? '☑' : this.taskTypeIcon(t.type)}</span>
          <div class="flex-1 min-w-0">
            <div class="text-[13px] leading-snug" style="${done ? 'text-decoration:line-through;color:var(--text-mute)' : ''}">${this.esc(t.title)}</div>
            ${badges ? `<div class="flex flex-wrap gap-1 mt-1">${badges}</div>` : ''}
          </div>
          <span class="pill text-[11px] shrink-0" style="color:var(--text-dim)">${done ? 'выполнена' : t.date.slice(5)}</span>
        </div>`;
      }).join('') : `<div class="text-[12px] py-2" style="color:var(--text-mute)">Задач по сделкам цели нет</div>`;
      const tasksBlock = `<div class="card p-3"><div class="label mb-1">Задачи цели · ${tasks.length}</div>${taskRows}</div>`;
      // артефакты цели
      const arts = this.goalArtifacts(g);
      const artRows = arts.length ? arts.map(a => {
        const d = this.dealById(a.dealId);
        return `<div class="flex items-center gap-2 py-1.5 border-t text-[13px]" style="border-color:var(--border)">
          <span class="shrink-0">📄</span>
          <div class="flex-1 min-w-0">
            <div class="leading-snug">${this.esc(a.title)} <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(a.kind)}·${this.esc(a.ext)}</span></div>
            <div class="text-[11px]" style="color:var(--text-dim)">${d ? `<a class="underline cursor-pointer" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</a>` : ''} · ${this.esc(a.date)}</div>
          </div>
          <span class="pill text-[11px] shrink-0" style="color:var(--text-dim)">${this.esc(a.status)}</span>
        </div>`;
      }).join('') : `<div class="text-[12px] py-2" style="color:var(--text-mute)">Артефактов по сделкам цели нет</div>`;
      const artsBlock = `<div class="card p-3"><div class="label mb-1">Артефакты цели · ${arts.length}</div>${artRows}</div>`;
      // сборка
      return `<div class="flex flex-col gap-3">
        ${this.goalCrumbs(g)}
        <div class="card p-4 flex flex-col gap-2">
          <div class="flex items-start gap-2">
            <span class="text-2xl">🎯</span>
            <div class="flex-1 min-w-0"><div class="text-lg font-semibold leading-tight">${this.esc(g.title)}</div></div>
          </div>
          <div class="flex flex-wrap items-center gap-1.5">${sigPill}${kindPill}</div>
          ${statusBlock}
          <div class="flex flex-col mt-1">${metaRows}</div>
          ${progBlock}
        </div>
        ${projBlock}
        ${outBlock}
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">${tasksBlock}${artsBlock}</div>
        ${this.activityBlock('goal', g.id)}
      </div>`;
    },

    // ======== ЧАНК 6.18: КАРТОЧКА ПРОЕКТА (route #/project/:id) ========
    // Связанные объекты проекта собираются ЧЕРЕЗ его сделки (projectDeals). Мини-канбан переиспользует STAGES.
    projectTasks(p) {
      const ids = new Set(this.projectDeals(p).map(d => d.id));
      return (this.M.tasks || []).filter(t => t.dealId && ids.has(t.dealId));
    },
    projectArtifacts(p) {
      const ids = new Set(this.projectDeals(p).map(d => d.id));
      return (this.M.artifacts || []).filter(a => a.dealId && ids.has(a.dealId));
    },
    // мини-канбан проекта: те же STAGES, но только сделки проекта; read-only (без фильтров/DnD)
    projectMiniCols(p) {
      const deals = this.projectDeals(p);
      return (this.M.STAGES || []).map(stage => {
        const items = deals.filter(d => d.stage === stage);
        return { stage, items, cnt: items.length, sum: items.reduce((s, d) => s + (d.amount || 0), 0) };
      });
    },
    // breadcrumbs Проекты › Цель › Проект
    projectCrumbs(p) {
      const g = this.goalById(p.goalId);
      return `<div class="text-[13px] flex flex-wrap items-center gap-1" style="color:var(--text-dim)">`
        + `<a class="underline cursor-pointer" data-go="projects">📁 Проекты</a>`
        + (g ? `<span style="color:var(--text-mute)"> › </span><a class="underline cursor-pointer" data-go="goal:${g.id}">🎯 ${this.esc(g.title)}</a>` : '')
        + `<span style="color:var(--text-mute)"> › </span><span style="color:var(--text)">${this.esc(p.title)}</span></div>`;
    },
    vProjectCard(id) {
      const p = this.projectById(id);
      if (!p) return this.stub('Проект не найден');
      const g = this.goalById(p.goalId);
      const owner = this.teamById(p.ownerId);
      const pr = this.projectProgress(p);
      const sg = this.projectSignal(p);
      const ds = this.projectDeals(p);
      const barCol = pr.pct >= 100 ? 'var(--ok)' : pr.pct >= 50 ? 'var(--accent)' : 'var(--warn)';
      // grade-pills
      const statusPill = `<span class="pill" style="color:${this.projStatusColor(p.status)};border-color:${this.projStatusColor(p.status)}">${this.esc(p.status)}</span>`;
      const sigPill = `<span class="pill" style="color:${sg.col};border-color:${sg.col}" title="Сигнал по формуле pace">${this.petIco(13)} ${this.esc(sg.label)}</span>`;
      // meta-rows
      const row = (k, v) => `<div class="flex justify-between gap-3 text-[13px] py-1.5 border-t" style="border-color:var(--border)"><span style="color:var(--text-dim)">${k}</span><span class="text-right">${v}</span></div>`;
      const goalCell = g ? `<a class="underline cursor-pointer" data-go="goal:${g.id}">🎯 ${this.esc(g.title)}</a>` : '—'; // 6.19: перевязано на goal:id
      const metaRows = [
        row('Цель', goalCell),
        row('Ниша', `🔖 ${this.esc(p.need)}`),
        row('Владелец', owner ? `${owner.avatar} ${this.esc(owner.name)}` : '—'),
        row('Период', `${this.esc(p.periodStart)} → ${this.esc(p.periodEnd)}`),
        row('Сделок', String(ds.length)),
      ].join('');
      const progBlock = `<div class="mt-1">
        <div class="flex items-center justify-between text-[12px] mb-1"><span style="color:var(--text-dim)">${this.money(pr.val)} из ${this.money(p.target)}</span><span class="font-medium" style="color:${barCol}">${pr.pct}%</span></div>
        <div style="height:8px;border-radius:99px;background:var(--border);overflow:hidden"><div style="height:100%;width:${pr.pct}%;background:${barCol}"></div></div>
      </div>`;
      // мини-канбан read-only
      const cols = this.projectMiniCols(p);
      const miniCols = cols.map(c => {
        const cards = c.items.length ? c.items.map(d => {
          const cl = this.clientById(d.clientId);
          return `<div class="card-2 p-2 mb-2 cursor-pointer" data-go="deal:${d.id}">
            <div class="text-[12px] font-medium leading-snug">🤝 ${this.esc(d.title)}</div>
            <div class="text-[11px] mt-0.5" style="color:var(--text-dim)">${cl ? this.esc(cl.name) : ''}</div>
            <div class="text-[11px] mt-0.5" style="color:var(--text-dim)">${this.money(d.amount)}</div>
          </div>`;
        }).join('') : `<div class="text-[11px] py-2 text-center" style="color:var(--text-mute)">—</div>`;
        return `<div class="shrink-0" style="width:210px">
          <div class="flex items-center justify-between mb-2 px-1"><span class="text-[12px] font-semibold">${this.esc(c.stage)}</span><span class="pill text-[10px]">${c.cnt}</span></div>
          <div class="card-2 p-2" style="min-height:60px">${cards}</div>
        </div>`;
      }).join('');
      const kanbanBlock = `<div class="card p-3">
        <div class="label mb-2">Мини-канбан проекта (read-only) · сделок ${ds.length}</div>
        <div class="flex gap-3 overflow-x-auto pb-1">${miniCols}</div>
      </div>`;
      // задачи проекта с бейджами 6.17
      const tasks = this.projectTasks(p);
      const taskRows = tasks.length ? tasks.map(t => {
        const deps = this.taskDeps(t).length, blocked = this.taskIsBlocked(t), parent = this.taskParent(t), subN = this.taskSubtasks(t).length, done = this.taskDone(t);
        const badges = [
          blocked ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--err);border-color:var(--err)">⛔ заблокировано</span>` : '',
          deps ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">🔗 ${deps}</span>` : '',
          parent ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">⊂ подзадача</span>` : '',
          subN ? `<span class="pill text-[10px] whitespace-nowrap" style="color:var(--text-mute)">☰ ${subN} подзад.</span>` : ''
        ].filter(Boolean).join('');
        return `<div class="flex items-start gap-2 py-1.5 border-t cursor-pointer" style="border-color:var(--border)" data-go="task:${t.id}">
          <span class="shrink-0">${done ? '☑' : this.taskTypeIcon(t.type)}</span>
          <div class="flex-1 min-w-0">
            <div class="text-[13px] leading-snug" style="${done ? 'text-decoration:line-through;color:var(--text-mute)' : ''}">${this.esc(t.title)}</div>
            ${badges ? `<div class="flex flex-wrap gap-1 mt-1">${badges}</div>` : ''}
          </div>
          <span class="pill text-[11px] shrink-0" style="color:var(--text-dim)">${done ? 'выполнена' : t.date.slice(5)}</span>
        </div>`;
      }).join('') : `<div class="text-[12px] py-2" style="color:var(--text-mute)">Задач по сделкам проекта нет</div>`;
      const tasksBlock = `<div class="card p-3"><div class="label mb-1">Задачи проекта · ${tasks.length}</div>${taskRows}</div>`;
      // артефакты проекта
      const arts = this.projectArtifacts(p);
      const artRows = arts.length ? arts.map(a => {
        const d = this.dealById(a.dealId);
        return `<div class="flex items-center gap-2 py-1.5 border-t text-[13px]" style="border-color:var(--border)">
          <span class="shrink-0">📄</span>
          <div class="flex-1 min-w-0">
            <div class="leading-snug">${this.esc(a.title)} <span class="pill text-[10px]" style="color:var(--text-dim)">${this.esc(a.kind)}·${this.esc(a.ext)}</span></div>
            <div class="text-[11px]" style="color:var(--text-dim)">${d ? `<a class="underline cursor-pointer" data-go="deal:${d.id}">🤝 ${this.esc(d.title)}</a>` : ''} · ${this.esc(a.date)}</div>
          </div>
          <span class="pill text-[11px] shrink-0" style="color:var(--text-dim)">${this.esc(a.status)}</span>
        </div>`;
      }).join('') : `<div class="text-[12px] py-2" style="color:var(--text-mute)">Артефактов по сделкам проекта нет</div>`;
      const artsBlock = `<div class="card p-3"><div class="label mb-1">Артефакты проекта · ${arts.length}</div>${artRows}</div>`;
      // сборка
      return `<div class="flex flex-col gap-3">
        ${this.projectCrumbs(p)}
        <div class="card p-4 flex flex-col gap-2">
          <div class="flex items-start gap-2">
            <span class="text-2xl">📁</span>
            <div class="flex-1 min-w-0"><div class="text-lg font-semibold leading-tight">${this.esc(p.title)}</div></div>
            <button class="btn text-[12px] shrink-0" data-proj-pin="${p.id}" title="Override связей сделок">⋯ override</button>
          </div>
          <div class="flex flex-wrap items-center gap-1.5">${statusPill}${sigPill}</div>
          <div class="flex flex-col mt-1">${metaRows}</div>
          ${progBlock}
        </div>
        ${kanbanBlock}
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">${tasksBlock}${artsBlock}</div>
        ${this.activityBlock('project', p.id)}
      </div>`;
    },

    // ======== ЧАНК 6.3: АРТЕФАКТЫ — ПРОВОДНИК (папки+файлы, в стиле Windows Explorer) ========
    artFolder: null, // текущая папка (null = корень)
    folderById(id) { return this.M.folders.find(f => f.id === id) || null; },
    artBreadcrumb() {
      const chain = [];
      let cur = this.artFolder;
      while (cur) { const f = this.folderById(cur); if (!f) break; chain.unshift(f); cur = f.parent; }
      const root = `<a class="underline cursor-pointer" data-art-go="">🗂 Артефакты</a>`;
      const rest = chain.map((f, i) => i === chain.length - 1
        ? `<span style="color:var(--text)">${this.esc(f.name)}</span>`
        : `<a class="underline cursor-pointer" data-art-go="${f.id}">${this.esc(f.name)}</a>`).join('<span style="color:var(--text-mute)"> › </span>');
      return `<div class="text-[13px] flex flex-wrap items-center gap-1" style="color:var(--text-dim)">${root}${rest ? '<span style="color:var(--text-mute)"> › </span>' + rest : ''}</div>`;
    },
    artFileIcon(ext) { return ({ docx: '📄', pdf: '📕', pptx: '📊', xlsx: '📗' })[ext] || '📎'; },
    artNav(id) { this.artFolder = id || null; this.render(); },
    artUp() { const f = this.artFolder ? this.folderById(this.artFolder) : null; this.artFolder = f ? f.parent : null; this.render(); },
    artNewFolder() {
      const here = this.artFolder ? this.folderById(this.artFolder) : null;
      this.openModal('Новая папка', `
        <div class="text-[12px] mb-2" style="color:var(--text-dim)">Родитель: ${here ? this.esc(here.name) : 'Артефакты (корень)'}</div>
        <input id="artFolderName" class="input w-full" placeholder="Имя папки" />`,
        () => {
          const i = document.getElementById('artFolderName'); const name = (i && i.value || '').trim();
          if (!name) { this.toast('Укажите имя папки', 'warn'); return false; }
          this.M.folders.push({ id: 'F' + Date.now(), parent: this.artFolder, name });
          this.toast('Папка «' + name + '» создана', 'ok'); this.render();
        });
      this.$nextTick(() => { const i = document.getElementById('artFolderName'); if (i) i.focus(); });
    },
    artOpenFile(id) {
      const a = this.M.artifacts.find(x => x.id === id); if (!a) return;
      const d = a.dealId ? this.dealById(a.dealId) : null;
      this.toast('Открытие: ' + a.title + (d ? ' · сделка ' + d.title : '') + ' (эскиз)', 'ok');
    },
    // ======== ЧАНК 6.4: ГЕНЕРАЦИЯ / ВЫБОР АРТЕФАКТА ПЕТРУШКОЙ ИЗ КАРТОЧКИ СДЕЛКИ ========
    _artGenType: 'КП',
    artGenModal(dealId) {
      const d = this.dealById(dealId); if (!d) return;
      const c = d.clientId ? this.clientById(d.clientId) : null;
      this._artGenType = 'КП';
      const tpls = this.M.artifacts.filter(a => a.status === 'шаблон');
      const tplOpts = tpls.map(t => `<label class="card-2 p-2 flex items-center gap-2 cursor-pointer text-[13px]"><input type="radio" name="artTpl" value="${t.id}"><span>${this.artFileIcon(t.ext)} ${this.esc(t.title)}</span></label>`).join('');
      this.openModal('ПЕТРУШКА: артефакт для «' + this.esc(d.title) + '»', `
        <div class="label mb-1">Тип документа</div>
        <div class="flex gap-2 mb-3" id="artTypeRow">
          ${['КП', 'Письмо'].map(t => `<button type="button" class="btn text-[13px]" data-art-type="${t}">${t}</button>`).join('')}
        </div>
        <div class="label mb-1">Способ</div>
        <label class="card-2 p-2 flex items-center gap-2 cursor-pointer text-[13px] mb-1"><input type="radio" name="artMode" value="gen" checked><span>${this.petIco(15)} Сгенерировать новый (ПЕТРУШКА составит по данным сделки)</span></label>
        <label class="card-2 p-2 flex items-center gap-2 cursor-pointer text-[13px]"><input type="radio" name="artMode" value="pick"><span>📁 Выбрать готовый из хранилища</span></label>
        <div id="artTplBox" class="mt-2 flex flex-col gap-1" style="display:none">${tplOpts || '<div class="text-[12px]" style="color:var(--text-mute)">Нет шаблонов</div>'}</div>`,
        () => this.artGenApply(dealId));
      this.$nextTick(() => {
        document.querySelectorAll('[data-art-type]').forEach(b => {
          const set = () => { this._artGenType = b.getAttribute('data-art-type'); document.querySelectorAll('[data-art-type]').forEach(x => x.classList.toggle('btn-accent', x === b)); };
          if (b.getAttribute('data-art-type') === 'КП') set();
          b.onclick = set;
        });
        document.querySelectorAll('input[name="artMode"]').forEach(r => r.onchange = () => {
          const box = document.getElementById('artTplBox'); if (box) box.style.display = (document.querySelector('input[name="artMode"]:checked').value === 'pick') ? 'flex' : 'none';
        });
      });
    },
    artGenApply(dealId) {
      const d = this.dealById(dealId); if (!d) return false;
      const c = d.clientId ? this.clientById(d.clientId) : null;
      const mode = (document.querySelector('input[name="artMode"]:checked') || {}).value || 'gen';
      const type = this._artGenType || 'КП';
      const extByType = { 'КП': 'docx', 'Письмо': 'docx' };
      const folderByType = { 'КП': 'F_KP', 'Письмо': 'F_DOG' };
      if (mode === 'pick') {
        const sel = document.querySelector('input[name="artTpl"]:checked');
        if (!sel) { this.toast('Выберите шаблон', 'warn'); return false; }
        const tpl = this.M.artifacts.find(a => a.id === sel.value); if (!tpl) return false;
        const title = tpl.title.replace(/^Шаблон\s*/i, '').trim() + ' — ' + this.clientName(c) || d.title;
        const na = { id: 'A' + Date.now(), dealId, folderId: tpl.folderId, kind: type, ext: tpl.ext, title, by: 'PETRUSHKA (из шаблона)', date: this.M.TODAY, status: 'на проверке' };
        this.M.artifacts.push(na);
        this.logDeal(d, 'artifact', `ПЕТРУШКА: из шаблона «${tpl.title}» — ${type} «${title}»`);
        this.persist();
        this.toast('Создан из шаблона: ' + title, 'ok'); this.render(); return;
      }
      // генерация нового
      const title = type + ' «' + d.title + '»' + (' — ' + this.clientName(c));
      const na = { id: 'A' + Date.now(), dealId, folderId: folderByType[type] || 'F_KP', kind: type, ext: extByType[type] || 'docx', title, by: 'PETRUSHKA', date: this.M.TODAY, status: 'на проверке' };
      this.M.artifacts.push(na);
      this.logDeal(d, 'artifact', `ПЕТРУШКА: сгенерирован ${type} «${title}»`);
      this.persist();
      this.toast('ПЕТРУШКА сгенерировала: ' + title, 'ok'); this.render();
    },
    vArtifacts() {
      const M = this.M;
      const subFolders = M.folders.filter(f => (f.parent || null) === this.artFolder);
      const files = M.artifacts.filter(a => (a.folderId || null) === this.artFolder);
      const folderCards = subFolders.map(f => {
        const cnt = M.artifacts.filter(a => a.folderId === f.id).length + M.folders.filter(x => x.parent === f.id).length;
        return `<div class="card-2 p-3 flex items-center gap-3 cursor-pointer" data-art-open-folder="${f.id}">
          <span class="text-2xl">📁</span>
          <div class="flex-1 min-w-0"><div class="text-sm font-medium truncate">${this.esc(f.name)}</div><div class="text-[11px]" style="color:var(--text-mute)">${cnt} эл.</div></div>
        </div>`;
      }).join('');
      const fileCards = files.map(a => {
        const d = a.dealId ? this.dealById(a.dealId) : null;
        return `<div class="card-2 p-3 flex items-center gap-3 cursor-pointer" data-art-open-file="${a.id}">
          <span class="text-2xl">${this.artFileIcon(a.ext)}</span>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate">${this.esc(a.title)}</div>
            <div class="text-[11px] flex flex-wrap gap-2" style="color:var(--text-mute)"><span>${a.kind} · .${a.ext}</span><span>${a.date}</span>${d ? `<span>· ${this.esc(d.title)}</span>` : ''}</div>
          </div>
          <span class="pill text-[11px]">${a.status}</span>
        </div>`;
      }).join('');
      const items = folderCards + fileCards;
      const emptyMsg = `<div class="text-[13px] p-4" style="color:var(--text-mute)">Папка пуста</div>`;
      return `<div class="card p-4">
        <div class="flex items-center justify-between gap-2 mb-3 flex-wrap">
          ${this.artBreadcrumb()}
          <div class="flex gap-2">
            <button class="btn text-[13px]" data-art-up ${this.artFolder ? '' : 'disabled style="opacity:.4;cursor:default"'}>↑ Вверх</button>
            <button class="btn btn-accent text-[13px]" data-art-newfolder>+ Папка</button>
          </div>
        </div>
        <div class="grid gap-2" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr))">${items || emptyMsg}</div>
      </div>`;
    },
    // ======== ЧАНК 1.5: ЕДИНАЯ КАРТОЧКА ОБЪЕКТА ========
    // Стадийная полоса Зацепка→Сервис + вкладки Задачи/Артефакты/История
    cardTab: 'tasks',
    setCardTab(t) { this.cardTab = t; this.render(); },
    stageBar(active) {
      return `<div class="flex flex-wrap gap-1 mb-4">` + this.M.STAGES.map(s => {
        const on = s === active;
        return `<span class="pill" style="${on ? 'background:var(--accent-soft);color:var(--accent);border-color:var(--accent)' : 'color:var(--text-mute)'}">${s}</span>`;
      }).join('<span style="color:var(--text-mute)">›</span>') + `</div>`;
    },
    cardTabsNav() {
      const tabs = [['tasks', 'Задачи'], ['artifacts', 'Артефакты'], ['history', 'История']];
      return `<div class="flex gap-1 mb-3 border-b pb-2" style="border-color:var(--border)">` + tabs.map(([k, l]) =>
        `<button class="btn text-[13px] ${this.cardTab === k ? 'btn-accent' : ''}" data-cardtab="${k}">${l}</button>`).join('') + `</div>`;
    },
    cardTabBody(dealIds) {
      const M = this.M;
      if (this.cardTab === 'tasks') {
        const ts = M.tasks.filter(t => dealIds.includes(t.dealId));
        return ts.length ? ts.map(t => `<div class="card-2 p-2 flex items-center justify-between"><span class="text-sm">${this.esc(t.title)}</span><span class="pill" style="color:${t.status === 'overdue' ? 'var(--err)' : 'var(--text-dim)'}">${t.status === 'overdue' ? 'просрочено' : t.date.slice(5)}</span></div>`).join('') : this.empty();
      }
      if (this.cardTab === 'artifacts') {
        const as = M.artifacts.filter(a => dealIds.includes(a.dealId));
        const targetDeal = dealIds[0];
        const genBtn = targetDeal ? `<button class="btn btn-accent text-[13px] mb-3" data-art-gen="${targetDeal}">${this.petIco(15)} ПЕТРУШКА: создать артефакт</button>` : '';
        const list = as.length
          ? as.map(a => `<div class="card-2 p-2 flex items-center justify-between gap-2"><span class="text-sm">${this.artFileIcon(a.ext)} ${a.kind}: ${this.esc(a.title)}</span><span class="pill">${a.status}</span></div>`).join('')
          : this.empty();
        return genBtn + `<div class="flex flex-col gap-2">${list}</div>`;
      }
      // history (реальный журнал по сделкам)
      const ico = { create: '➕', stage: '➡️', task: '✅', package: '📦', artifact: '📄' };
      const ev = [];
      dealIds.forEach(did => { const d = this.dealById(did); if (d && d.history) d.history.forEach(h => ev.push({ ...h, did })); });
      ev.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
      return ev.length ? `<div class="relative pl-4">` + ev.map(h => `<div class="relative pb-3"><div class="absolute left-[-12px] top-1 w-2 h-2 rounded-full" style="background:var(--accent)"></div><div class="flex items-start gap-2"><span class="shrink-0">${ico[h.kind] || '•'}</span><div><div class="text-[13px]">${this.esc(h.text)}</div><div class="text-[11px]" style="color:var(--text-mute)">${h.date}</div></div></div></div>`).join('') + `</div>` : this.empty();
    },
    empty() { return `<div class="text-[13px]" style="color:var(--text-mute)">пусто</div>`; },
    vClientCard(id) {
      const c = this.clientById(id); if (!c) return this.stub('Клиент не найден');
      const deals = this.M.deals.filter(d => d.clientId === id);
      const dealIds = deals.map(d => d.id);
      const dealList = deals.map(d => `<div class="card-2 p-3 flex items-center justify-between cursor-pointer" data-go="deal:${d.id}"><div><div class="text-sm font-medium">${this.esc(d.title)}</div><div class="text-[12px]" style="color:var(--text-dim)">${d.stage} · ${this.money(d.amount)}</div></div><span class="pill" style="color:${this.scoreCol(d.score)}">score ${d.score}</span></div>`).join('');
      return `<div class="flex flex-col gap-4">
        <div class="text-[12px] flex items-center gap-1 flex-wrap" style="color:var(--text-mute)"><a class="underline cursor-pointer" data-go="myday">Мой день</a><span>›</span><a class="underline cursor-pointer" data-go="clients">Клиенты</a><span>›</span><span style="color:var(--text-dim)">${this.esc(c.name)}</span></div>
        <div class="card p-4">
          <div class="flex items-center gap-3 mb-2"><span style="color:${this.healthColor(c.health)}">●</span><div class="text-lg font-semibold">${this.esc(c.name)}</div></div>
          <div class="text-[13px]" style="color:var(--text-dim)">${c.industry} · ${c.region} · контакт: ${this.esc(c.contact)}</div>
          <div class="mt-2 flex flex-wrap gap-1">${c.need.map(n => `<span class="pill">${n}</span>`).join('')}</div>
        </div>
        <div class="card p-4"><div class="flex items-center justify-between mb-3"><div class="label">Сделки клиента</div><button class="btn btn-accent text-[13px]" data-deal-add="${c.id}">+ Сделка</button></div><div class="flex flex-col gap-2">${dealList || this.empty()}</div></div>
        ${this.miniGraph('client', id)}
        <div class="card p-4">${this.cardTabsNav()}${this.cardTabBody(dealIds)}</div>
      </div>`;
    },
    vDealCard(id) {
      const d = this.dealById(id); if (!d) return this.stub('Сделка не найдена');
      const c = this.clientById(d.clientId);
      const owl = this.M.owlSuggestions.filter(o => o.dealId === id);
      const owlHtml = owl.length ? owl.map(o => `<div class="card-2 p-2 flex items-center gap-2"><span class="pill" style="color:${this.gradeColor(o.grade)};border-color:${this.gradeColor(o.grade)}">${this.gradeLabel(o.grade)}</span><span class="text-[13px]">${this.esc(o.text)}</span></div>`).join('') : this.empty();
      return `<div class="flex flex-col gap-4">
        <div class="text-[12px] flex items-center gap-1 flex-wrap" style="color:var(--text-mute)"><a class="underline cursor-pointer" data-go="myday">Мой день</a><span>›</span>${c ? `<a class="underline cursor-pointer" data-go="client:${c.id}">${this.esc(c.name)}</a><span>›</span>` : ''}<a class="underline cursor-pointer" data-go="deals">Сделки</a><span>›</span><span style="color:var(--text-dim)">${this.esc(d.title)}</span></div>
        <div class="card p-4">
          <div class="text-lg font-semibold mb-1">${this.esc(d.title)}</div>
          <div class="text-[13px] mb-3" style="color:var(--text-dim)">Клиент: <a class="underline cursor-pointer" data-go="client:${c ? c.id : ''}">${this.esc(this.clientName(c))}</a> · ${this.money(d.amount)} · отв: ${this.esc(d.owner)}${d.packageName ? ` · 📦 ${this.esc(d.packageName)}` : ''}</div>
          ${this.stageBar(d.stage)}
        </div>
        <div class="card p-4"><div class="flex items-center gap-2 mb-3">${this.petIco(18)}<div class="label">ПЕТРУШКА по этому объекту</div></div><div class="flex flex-col gap-2">${owlHtml}</div></div>
        ${this.activityBlock('deal', id)}
        ${this.miniGraph('deal', id)}
        <div class="card p-4">${this.cardTabsNav()}${this.cardTabBody([id])}</div>
      </div>`;
    },
    // ======== ЧАНК 2.7: МИНИ-ГРАФ СВЯЗЕЙ (S10) ========
    // Компактная карта связей объекта: Клиент ↔ Сделки ↔ Задачи/Артефакты.
    graphNode(label, sub, goAttr, accent) {
      return `<div class="card-2 px-3 py-2 text-center min-w-[120px] ${goAttr ? 'cursor-pointer' : ''}" ${goAttr ? `data-go="${goAttr}"` : ''} style="${accent ? 'border-color:var(--accent)' : ''}">
        <div class="text-[13px] font-medium truncate">${this.esc(label)}</div>${sub ? `<div class="text-[11px]" style="color:var(--text-dim)">${this.esc(sub)}</div>` : ''}</div>`;
    },
    graphArrow() { return `<div class="flex items-center" style="color:var(--text-mute)">→</div>`; },
    miniGraph(type, id) {
      const M = this.M;
      let rows = '';
      if (type === 'client') {
        const c = this.clientById(id); if (!c) return '';
        const deals = M.deals.filter(d => d.clientId === id);
        if (!deals.length) {
          rows = `<div class="flex items-center gap-2">${this.graphNode(c.name, c.industry, null, true)}${this.graphArrow()}<span class="text-[12px]" style="color:var(--text-mute)">нет связанных сделок</span></div>`;
        } else {
          rows = deals.map(d => {
            const ts = M.tasks.filter(t => t.dealId === d.id);
            const arts = M.artifacts.filter(a => a.dealId === d.id);
            const leaf = `${ts.length} зад. · ${arts.length} арт.`;
            return `<div class="flex items-center gap-2 flex-wrap">${this.graphNode(c.name, c.industry, null, true)}${this.graphArrow()}${this.graphNode(d.title, d.stage, 'deal:' + d.id)}${this.graphArrow()}${this.graphNode(leaf, 'задачи/артефакты', null)}</div>`;
          }).join('');
        }
      } else {
        const d = this.dealById(id); if (!d) return '';
        const c = this.clientById(d.clientId);
        const ts = M.tasks.filter(t => t.dealId === id);
        const arts = M.artifacts.filter(a => a.dealId === id);
        const pk = M.packages.find(p => p.need === d.need);
        const leaf = `${ts.length} зад. · ${arts.length} арт.`;
        rows = `<div class="flex items-center gap-2 flex-wrap">${this.graphNode(this.clientName(c) || '—', c ? c.industry : '', c ? 'client:' + c.id : null)}${this.graphArrow()}${this.graphNode(d.title, d.stage, null, true)}${this.graphArrow()}${this.graphNode(leaf, 'задачи/артефакты', null)}</div>`;
        if (pk) rows += `<div class="flex items-center gap-2 mt-2"><span class="text-[12px]" style="color:var(--text-mute)">упаковка</span>${this.graphArrow()}${this.graphNode(pk.name, 'от ' + this.money(pk.priceFrom), 'packages')}</div>`;
      }
      return `<div class="card p-4"><div class="label mb-3">Связи объекта</div><div class="flex flex-col gap-2 overflow-x-auto">${rows}</div></div>`;
    },
    // ======== ЧАНК 2.3: МОНИТОРИНГ РЫНКА ========
    vMonitoring() {
      const rows = this.M.sources.map(s => `<div class="card-2 p-3 flex items-center gap-3">
        <span style="color:${s.active ? 'var(--ok)' : 'var(--text-mute)'}">●</span>
        <span class="pill">${s.type}</span>
        <div class="flex-1 min-w-0"><div class="text-sm font-medium truncate">${this.esc(s.value)}</div><div class="text-[12px]" style="color:var(--text-dim)">${s.scope}${s.industry ? ' · ' + s.industry : ''} · проверен ${s.last.slice(5)}</div></div>
        <button class="btn text-[12px]" data-src-scan="${s.id}">Проверить</button>
        <button class="btn text-[12px]" data-src-toggle="${s.id}">${s.active ? 'Пауза' : 'Вкл'}</button>
      </div>`).join('');
      const sigRows = this.M.signals.map(s => { const d = this.dealById(s.dealId); return `<div class="card-2 p-3 flex items-start gap-3"><span class="shrink-0" style="color:${this.sevColor(s.sev)}">●</span><div class="flex-1 min-w-0"><div class="text-sm">${this.esc(s.text)}</div><a class="text-[12px] underline cursor-pointer" style="color:var(--text-dim)" data-go="deal:${d ? d.id : ''}">${this.esc(s.objectTitle)}</a></div><div class="flex flex-col items-end gap-1 shrink-0"><span class="pill whitespace-nowrap" style="color:${this.sevColor(s.sev)};border-color:${this.sevColor(s.sev)}">${s.sev}</span><button class="btn btn-accent text-[12px] whitespace-nowrap" data-signal-act="${s.id}">Действие</button></div></div>`; }).join('') || this.empty();
      return `<div class="flex flex-col gap-4">
        <div class="card p-4">
          <div class="flex items-center justify-between mb-3"><div class="label">Сигналы · ${this.M.signals.length}</div></div>
          <div class="flex flex-col gap-2">${sigRows}</div>
        </div>
        <div class="card p-4">
          <div class="flex items-center justify-between mb-3"><div class="label">Источники · ${this.M.sources.length}</div><button class="btn btn-accent text-[13px]" data-src-add>+ Источник</button></div>
          <div class="flex flex-col gap-2">${rows}</div>
        </div>
        <div class="card p-3 text-[12px]" style="color:var(--text-mute)">На сигнале нажмите «Действие» — ПЕТРУШКА предложит создать сделку или задачу. При находке источник создаёт новый Сигнал (кнопка «Проверить»).</div>
      </div>`;
    },
    // демо: скан источника → новый сигнал + подсказка ПЕТРУШКА
    srcScan(id) {
      const s = this.M.sources.find(x => x.id === id); if (!s) return;
      const sid = 'S' + (this.M.signals.length + 1);
      this.M.signals.unshift({ id: sid, dealId: '', sev: 'info', text: `Новое из «${s.value}»: потенциальный запрос`, objectTitle: s.type });
      this.M.owlSuggestions.unshift({ id: 'O' + Date.now(), dealId: '', grade: 'HINT', text: `Сигнал из «${s.value}» — создать сделку / задачу / пост?` });
      this.toast('Найден сигнал — ПЕТРУШКА предложил действие', 'ok');
      this.render();
      this.$nextTick(() => this.owlRender());
    },
    // S5: сигнал → действие (ПЕТРУШКА предлагает сделку/задачу)
    signalAction(id) {
      const s = this.M.signals.find(x => x.id === id); if (!s) return;
      const d = this.dealById(s.dealId);
      let sug;
      if (d) {
        const sev = s.sev;
        const tType = sev === 'critical' ? 'call' : 'email';
        sug = { id: 'O' + Date.now(), dealId: d.id, grade: sev === 'critical' ? 'CONFIRM' : 'HINT', text: `По сигналу «${s.text}» — реагировать по сделке «${d.title}»?`, action: 'task', taskTitle: `Реакция на сигнал: ${s.objectTitle}`, taskType: tType, okMsg: `Создана задача по сигналу` };
      } else {
        sug = { id: 'O' + Date.now(), dealId: '', grade: 'HINT', text: `Сигнал «${s.text}» — оформить как новую сделку?`, action: 'newdeal', okMsg: 'Открываю создание сделки' };
      }
      this.M.owlSuggestions.unshift(sug);
      this.owl.open = true;
      this.toast('ПЕТРУШКА предложил действие по сигналу', 'ok');
      this.render();
      this.$nextTick(() => this.owlRender());
    },
    srcToggle(id) { const s = this.M.sources.find(x => x.id === id); if (s) { s.active = !s.active; this.render(); } },
    // модал добавления источника
    srcAddModal() {
      const opts = this.M.SRC_TYPES.map(t => `<option>${t}</option>`).join('');
      const inds = this.M.IND.map(i => `<option>${i}</option>`).join('');
      this.openModal('Добавить источник', `
        <label class="label">Тип</label><select id="m_type" class="input w-full mb-2">${opts}</select>
        <label class="label">Значение (URL / @канал / ключевые слова)</label><input id="m_value" class="input w-full mb-2" placeholder="напр. agro.ru/feed" />
        <label class="label">Привязка</label><select id="m_scope" class="input w-full mb-2"><option>глобальный</option><option>отрасль</option></select>
        <label class="label">Отрасль (если привязка = отрасль)</label><select id="m_ind" class="input w-full"><option value="">—</option>${inds}</select>
      `, () => {
        const v = (id) => document.getElementById(id);
        const val = v('m_value').value.trim(); if (!val) { this.toast('Укажите значение', 'err'); return false; }
        this.M.sources.push({ id: 'SRC' + (this.M.sources.length + 1), type: v('m_type').value, value: val, scope: v('m_scope').value, industry: v('m_scope').value === 'отрасль' ? v('m_ind').value : '', active: true, last: this.M.TODAY });
        this.toast('Источник добавлен', 'ok'); this.render(); return true;
      });
    },

    // ======== ОБЩИЙ МОДАЛ (используется в 2.3-2.5) ========
    _modalSave: null,
    openModal(title, bodyHtml, onSave) {
      this._modalSave = onSave;
      let m = document.getElementById('appModal');
      if (!m) { m = document.createElement('div'); m.id = 'appModal'; document.body.appendChild(m); }
      m.className = 'fixed inset-0 z-50 flex items-center justify-center p-4';
      m.style.background = 'rgba(0,0,0,.5)';
      m.innerHTML = `<div class="card w-[440px] max-w-full"><div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--border)"><div class="text-sm font-semibold">${this.esc(title)}</div><button class="btn text-[12px]" id="m_x">✕</button></div><div class="p-4">${bodyHtml}</div><div class="flex justify-end gap-2 px-4 py-3 border-t" style="border-color:var(--border)"><button class="btn text-[13px]" id="m_cancel">Отмена</button><button class="btn btn-accent text-[13px]" id="m_ok">Сохранить</button></div></div>`;
      document.getElementById('m_x').onclick = () => this.closeModal();
      document.getElementById('m_cancel').onclick = () => this.closeModal();
      document.getElementById('m_ok').onclick = () => { if (this._modalSave && this._modalSave() !== false) this.closeModal(); };
    },
    closeModal() { const m = document.getElementById('appModal'); if (m) m.remove(); this._modalSave = null; },

    // ======== ЧАНК 3.2: ГЛОБАЛЬНЫЙ ПОИСК (палитра Ctrl/Cmd-K) ========
    paletteQuery: '',
    paletteResults() {
      const q = this.paletteQuery.trim().toLowerCase();
      const out = [];
      // действия (команды) — выше объектов
      const cmds = [
        { icon: '➕', title: 'Создать клиента', kw: 'клиент создать новый добавить', act: 'cliAddModal' },
        { icon: '➕', title: 'Создать сделку', kw: 'сделка создать новая добавить проект', act: 'dealAddModal' },
        { icon: '📥', title: 'Импорт клиентов (CSV)', kw: 'импорт csv клиенты загрузить', act: 'cliImportModal' },
        { icon: '📡', title: 'Добавить источник мониторинга', kw: 'источник мониторинг добавить', act: 'srcAddModal' },
        { icon: '🌿', title: 'Открыть ПЕТРУШКУ', kw: 'петрушка орёл орел ai помощник подсказки модератор', act: 'owlOpenFromPalette' },
      ];
      cmds.forEach(cm => { if (!q || cm.title.toLowerCase().includes(q) || cm.kw.includes(q)) out.push({ icon: cm.icon, kind: 'Действие', title: cm.title, sub: 'команда', act: cm.act }); });
      this.M.clients.forEach(c => { if (!q || c.name.toLowerCase().includes(q) || (c.industry || '').toLowerCase().includes(q)) out.push({ icon: '🏢', kind: 'Клиент', title: c.name, sub: `${c.industry} · ${c.region}`, go: 'client:' + c.id }); });
      this.M.deals.forEach(d => { const c = this.clientById(d.clientId); const cn = this.clientName(c); if (!q || d.title.toLowerCase().includes(q) || (c && cn.toLowerCase().includes(q))) out.push({ icon: '💠', kind: 'Сделка', title: d.title, sub: `${cn} · ${d.stage}`, go: 'deal:' + d.id }); });
      this.M.tasks.forEach(t => { const d = this.dealById(t.dealId); if (!q || t.title.toLowerCase().includes(q)) out.push({ icon: '✅', kind: 'Задача', title: t.title, sub: d ? d.title : '', go: d ? 'deal:' + d.id : 'tasks' }); });
      this.M.packages.forEach(p => { if (!q || p.name.toLowerCase().includes(q)) out.push({ icon: '📦', kind: 'Упаковка', title: p.name, sub: 'от ' + this.money(p.priceFrom), go: 'packages' }); });
      return out.slice(0, 12);
    },
    paletteOpen() {
      this.paletteQuery = '';
      let m = document.getElementById('appPalette');
      if (!m) { m = document.createElement('div'); m.id = 'appPalette'; document.body.appendChild(m); }
      m.className = 'fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]';
      m.style.background = 'rgba(0,0,0,.5)';
      m.onclick = (e) => { if (e.target === m) this.paletteClose(); };
      this.paletteRender();
      this.$nextTick(() => { const f = document.getElementById('palInput'); if (f) f.focus(); });
    },
    paletteRender() {
      const m = document.getElementById('appPalette'); if (!m) return;
      const rs = this.paletteResults();
      const rows = rs.length ? rs.map(r => `<div class="card-2 p-2 flex items-center gap-3 cursor-pointer" ${r.act ? `data-pal-act="${r.act}"` : `data-pal-go="${r.go}"`}><span class="text-lg">${r.icon}</span><div class="flex-1 min-w-0"><div class="text-sm font-medium truncate">${this.esc(r.title)}</div><div class="text-[12px]" style="color:var(--text-dim)">${this.esc(r.sub)}</div></div><span class="pill text-[11px]">${r.kind}</span></div>`).join('') : `<div class="text-[13px] p-3 text-center" style="color:var(--text-mute)">Ничего не найдено</div>`;
      m.innerHTML = `<div class="card w-[560px] max-w-full">
        <div class="p-3 border-b" style="border-color:var(--border)"><input id="palInput" class="input w-full" placeholder="Поиск по клиентам, сделкам, задачам, упаковкам…" value="${this.esc(this.paletteQuery)}" /></div>
        <div class="p-2 flex flex-col gap-1 max-h-[55vh] overflow-y-auto">${rows}</div>
        <div class="px-3 py-2 border-t text-[11px]" style="border-color:var(--border);color:var(--text-mute)">Enter — первый результат · Esc — закрыть</div>
      </div>`;
      const inp = document.getElementById('palInput');
      inp.oninput = (e) => { this.paletteQuery = e.target.value; const pos = e.target.selectionStart; this.paletteRender(); this.$nextTick(() => { const f = document.getElementById('palInput'); if (f) { f.focus(); try { f.setSelectionRange(pos, pos); } catch (_) {} } }); };
      inp.onkeydown = (e) => { if (e.key === 'Enter') { const first = this.paletteResults()[0]; if (first) { if (first.act) this.paletteAct(first.act); else this.paletteGo(first.go); } } };
      m.querySelectorAll('[data-pal-go]').forEach(n => n.onclick = () => this.paletteGo(n.getAttribute('data-pal-go')));
      m.querySelectorAll('[data-pal-act]').forEach(n => n.onclick = () => this.paletteAct(n.getAttribute('data-pal-act')));
    },
    paletteGo(arg) { const [r, a] = arg.split(':'); this.paletteClose(); this.go(r, a); },
    paletteAct(act) { this.paletteClose(); if (typeof this[act] === 'function') this.$nextTick(() => this[act]()); },
    owlOpenFromPalette() { this.owl.open = true; this.$nextTick(() => this.owlRender()); },
    paletteClose() { const m = document.getElementById('appPalette'); if (m) m.remove(); },

    // ======== ЧАНК 6.11: РАБОЧИЕ НАСТРОЙКИ (грейды ПЕТРУШКА, гриф приватности/hybrid LLM, команда, инфра) ========
    settingsSetGrade(id, grade) {
      const g = (this.M.agentConfig.grades || []).find(x => x.id === id);
      if (g) { g.grade = grade; this.toast('Грейд обновлён: ' + this.gradeLabel(grade), 'ok'); this.render(); }
    },
    settingsTogglePrivacy() {
      this.M.agentConfig.privacyLocalOnly = !this.M.agentConfig.privacyLocalOnly;
      this.toast(this.M.agentConfig.privacyLocalOnly ? 'Приватные данные — только локальные LLM' : 'ВНИМАНИЕ: приватность ослаблена', this.M.agentConfig.privacyLocalOnly ? 'ok' : 'err');
      this.render();
    },
    vSettings() {
      const A = this.M.agentConfig;
      // 1) Грейды автономности
      const gradeChoices = ['AUTO', 'CONFIRM', 'HINT'];
      const gradeRows = A.grades.map(g => {
        const seg = gradeChoices.map(gc => {
          const on = g.grade === gc;
          return `<button class="btn text-[12px] ${on ? 'btn-accent' : ''}" data-set-grade="${g.id}" data-grade-val="${gc}" style="${on ? '' : 'opacity:.7'}">${this.gradeLabel(gc)}</button>`;
        }).join('');
        return `<div class="card-2 p-3 flex flex-col gap-2">
          <div><div class="text-[14px] font-medium">${this.esc(g.cat)}</div><div class="label">${this.esc(g.desc)}</div></div>
          <div class="flex items-center gap-2 flex-wrap"><span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${this.gradeColor(g.grade)}"></span>${seg}</div>
        </div>`;
      }).join('');
      // 2) Гибридная LLM-маршрутизация + гриф приватности
      const privOn = A.privacyLocalOnly;
      const routeRows = A.routing.map(r => `<tr style="border-top:1px solid var(--border)">
        <td class="py-2 pr-3 text-[13px]">${r.priv ? '🔒 ' : ''}${this.esc(r.data)}</td>
        <td class="py-2 pr-3 text-[13px]" style="color:var(--text-dim)">${this.esc(r.model)}</td>
        <td class="py-2 text-[12px]" style="color:${r.priv ? 'var(--ok)' : 'var(--text-mute)'}">${this.esc(r.note)}</td>
      </tr>`).join('');
      const privacyCard = `<div class="card-2 p-3 flex flex-col gap-3">
        <div class="flex items-center justify-between gap-3">
          <div><div class="text-[14px] font-medium">Приватные данные — только локальные LLM</div><div class="label">Финположение, договоры никогда не уходят во внешние API</div></div>
          <button class="btn ${privOn ? 'btn-accent' : ''}" data-toggle-privacy style="min-width:84px">${privOn ? '🔒 Вкл' : '⚠ Выкл'}</button>
        </div>
        <div class="overflow-x-auto"><table class="w-full text-left"><thead><tr class="label">
          <th class="pb-1 pr-3 font-normal">Тип данных</th><th class="pb-1 pr-3 font-normal">Модель</th><th class="pb-1 font-normal">Правило</th>
        </tr></thead><tbody>${routeRows}</tbody></table></div>
      </div>`;
      // 3) Команда (сводка, ред. — на экране «Команда»)
      const teamRows = (this.M.team || []).map(u => `<div class="card-2 p-2 flex items-center gap-2">
        <span class="w-7 h-7 rounded-full flex items-center justify-center text-[12px] shrink-0" style="background:var(--accent-soft);color:var(--accent)">${this.esc((u.name || '?').slice(0, 1))}</span>
        <div class="min-w-0 flex-1"><div class="text-[13px] font-medium truncate">${this.esc(u.name)}</div><div class="label truncate">${this.esc(u.role)}</div></div>
      </div>`).join('');
      // 4) Инфраструктура OPEN CLAW
      const infraRows = (this.M.infra || []).map(s => `<div class="card-2 p-2 flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${s.status === 'ok' ? 'var(--ok)' : 'var(--warn)'}"></span>
        <div class="min-w-0 flex-1"><div class="text-[13px] font-medium truncate">${this.esc(s.name)}</div><div class="label truncate">${this.esc(s.role)}</div></div>
        <span class="pill text-[11px]" style="color:var(--ok);border-color:var(--ok)">${s.status === 'ok' ? 'работает' : s.status}</span>
      </div>`).join('');
      const sec = (icon, title, sub, body) => `<div class="card p-4 flex flex-col gap-3">
        <div><div class="text-[15px] font-semibold flex items-center gap-2">${icon} ${title}</div>${sub ? `<div class="label mt-0.5">${sub}</div>` : ''}</div>
        ${body}</div>`;
      return `<div class="flex flex-col gap-4">
        ${sec(this.petIco(18), 'Грейды автономности ПЕТРУШКА', 'Уровень самостоятельности модератора по категориям действий (без редеплоя, через agent_config + CONFIRM)', `<div class="grid grid-cols-1 md:grid-cols-3 gap-2">${gradeRows}</div>`)}
        ${sec('🔐', 'Гибридная LLM-маршрутизация', 'Выбор модели по типу задачи и грифу приватности', privacyCard)}
        ${sec('👥', 'Команда', 'Этап 1 — координация (редактирование на экране «Команда»)', `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">${teamRows}</div><a class="btn text-[12px] self-start" data-go="team">Открыть «Команда» →</a>`)}
        ${sec('🖥', 'Инфраструктура OPEN CLAW', 'Jarvis Hub · 8 GB · последовательная LLM-работа', `<div class="grid grid-cols-1 md:grid-cols-2 gap-2">${infraRows}</div>`)}
      </div>`;
    },

    // ---- привязка обработчиков после innerHTML (data-* делегирование) ----
    bindView() {
      const el = document.getElementById('view'); if (!el) return;
      el.querySelectorAll('[data-go]').forEach(n => {
        n.onclick = (e) => { e.stopPropagation(); const [r, a] = n.getAttribute('data-go').split(':'); this.go(r, a || null); };
      });
      // 6.17: управление задачей на карточке
      el.querySelectorAll('[data-task-complete]').forEach(n => { n.onclick = (e) => { e.stopPropagation(); this.taskComplete(n.getAttribute('data-task-complete')); }; });
      el.querySelectorAll('[data-task-reopen]').forEach(n => { n.onclick = (e) => { e.stopPropagation(); this.taskReopen(n.getAttribute('data-task-reopen')); }; });
      el.querySelectorAll('[data-task-adddep]').forEach(n => { n.onclick = (e) => { e.stopPropagation(); this.taskAddDepModal(this.routeArg); }; });
      el.querySelectorAll('[data-task-deldep]').forEach(n => { n.onclick = (e) => { e.stopPropagation(); this.taskRemoveDep(this.routeArg, n.getAttribute('data-task-deldep')); }; });
      el.querySelectorAll('[data-owl-ok]').forEach(n => {
        n.onclick = () => { const id = n.getAttribute('data-owl-ok'); this.M.owlSuggestions = this.M.owlSuggestions.filter(o => o.id !== id); this.toast('Подсказка ПЕТРУШКИ принята', 'ok'); this.render(); };
      });
      el.querySelectorAll('[data-owl-no]').forEach(n => {
        n.onclick = () => { const id = n.getAttribute('data-owl-no'); this.M.owlSuggestions = this.M.owlSuggestions.filter(o => o.id !== id); this.toast('Подсказка отклонена', 'info'); this.render(); };
      });
      el.querySelectorAll('[data-cardtab]').forEach(n => {
        n.onclick = () => this.setCardTab(n.getAttribute('data-cardtab'));
      });
      // 6.3: проводник артефактов
      el.querySelectorAll('[data-art-go]').forEach(n => n.onclick = () => this.artNav(n.getAttribute('data-art-go') || null));
      el.querySelectorAll('[data-art-open-folder]').forEach(n => n.onclick = () => this.artNav(n.getAttribute('data-art-open-folder')));
      el.querySelectorAll('[data-art-open-file]').forEach(n => n.onclick = () => this.artOpenFile(n.getAttribute('data-art-open-file')));
      const aup = el.querySelector('[data-art-up]'); if (aup && !aup.disabled) aup.onclick = () => this.artUp();
      const anf = el.querySelector('[data-art-newfolder]'); if (anf) anf.onclick = () => this.artNewFolder();
      el.querySelectorAll('[data-art-gen]').forEach(n => n.onclick = () => this.artGenModal(n.getAttribute('data-art-gen')));
      // 6.5: упаковки (Этап 2)
      const pn = el.querySelector('[data-pkg-new]'); if (pn) pn.onclick = () => this.pkgFromDealModal();
      el.querySelectorAll('[data-pkg-ready]').forEach(n => n.onclick = () => this.pkgSetReady(n.getAttribute('data-pkg-ready'), n.getAttribute('data-pkg-to')));
      // 6.11: настройки
      el.querySelectorAll('[data-set-grade]').forEach(n => n.onclick = () => this.settingsSetGrade(n.getAttribute('data-set-grade'), n.getAttribute('data-grade-val')));
      const tp = el.querySelector('[data-toggle-privacy]'); if (tp) tp.onclick = () => this.settingsTogglePrivacy();
      // 6.10: граф объектов
      el.querySelectorAll('[data-graph-node]').forEach(n => n.onclick = () => this.graphSelect(n.getAttribute('data-graph-node')));
      el.querySelectorAll('[data-graph-type]').forEach(n => n.onclick = () => this.graphToggleType(n.getAttribute('data-graph-type')));
      // 6.9: входящие
      el.querySelectorAll('[data-inbox-filter]').forEach(n => n.onclick = () => this.inboxSetFilter(n.getAttribute('data-inbox-filter')));
      el.querySelectorAll('[data-inbox-create]').forEach(n => n.onclick = () => this.inboxCreate(n.getAttribute('data-inbox-create')));
      el.querySelectorAll('[data-inbox-dismiss]').forEach(n => n.onclick = () => this.inboxDismiss(n.getAttribute('data-inbox-dismiss')));
      // 6.8: команда
      el.querySelectorAll('[data-team-toggle]').forEach(n => n.onclick = () => this.teamToggle(n.getAttribute('data-team-toggle')));
      el.querySelectorAll('[data-team-reassign]').forEach(n => n.onclick = (e) => { e.stopPropagation(); this.teamReassignModal(n.getAttribute('data-team-reassign')); });
      // 6.7: цели (Стратегия → Цели)
      el.querySelectorAll('[data-goal-toggle]').forEach(n => n.onclick = () => this.goalToggle(n.getAttribute('data-goal-toggle')));
      el.querySelectorAll('[data-goal-pin]').forEach(n => n.onclick = (e) => { e.stopPropagation(); this.goalPinModal(n.getAttribute('data-goal-pin')); });
      // 6.13: проекты
      el.querySelectorAll('[data-proj-toggle]').forEach(n => n.onclick = () => this.projToggle(n.getAttribute('data-proj-toggle')));
      el.querySelectorAll('[data-proj-pin]').forEach(n => n.onclick = (e) => { e.stopPropagation(); this.projPinModal(n.getAttribute('data-proj-pin')); });
      // 6.6: контент и соцсети (SSM)
      el.querySelectorAll('[data-post-sel]').forEach(n => n.onclick = () => this.postSelect(n.getAttribute('data-post-sel')));
      el.querySelectorAll('[data-post-act]').forEach(n => n.onclick = () => this.postAct(n.getAttribute('data-post-id'), n.getAttribute('data-post-act')));
      el.querySelectorAll('[data-post-field]').forEach(n => {
        n.oninput = (e) => this.postField(n.getAttribute('data-post-id'), n.getAttribute('data-post-field'), e.target.value);
      });
      // чанк 2.3: мониторинг
      const add = el.querySelector('[data-src-add]'); if (add) add.onclick = () => this.srcAddModal();
      el.querySelectorAll('[data-src-scan]').forEach(n => n.onclick = () => this.srcScan(n.getAttribute('data-src-scan')));
      el.querySelectorAll('[data-signal-act]').forEach(n => n.onclick = (e) => { e.stopPropagation(); this.signalAction(n.getAttribute('data-signal-act')); });
      el.querySelectorAll('[data-src-toggle]').forEach(n => n.onclick = () => this.srcToggle(n.getAttribute('data-src-toggle')));
      // чанк 2.4: клиенты
      const ca = el.querySelector('[data-cli-add]'); if (ca) ca.onclick = () => this.cliAddModal();
      const ci = el.querySelector('[data-cli-import]'); if (ci) ci.onclick = () => this.cliImportModal();
      // чанк 2.5: сделки
      el.querySelectorAll('[data-deal-add]').forEach(n => n.onclick = () => this.dealAddModal(n.getAttribute('data-deal-add') || null));
      // чанк 3.1: поиск + сортировка клиентов
      const cs = el.querySelector('#cliSearch');
      if (cs) {
        cs.oninput = (e) => { this.cliQuery = e.target.value; const pos = e.target.selectionStart; this.render(); this.$nextTick(() => { const f = document.getElementById('cliSearch'); if (f) { f.focus(); try { f.setSelectionRange(pos, pos); } catch (_) {} } }); };
      }
      el.querySelectorAll('[data-cli-sort]').forEach(n => n.onclick = () => { this.cliSort = n.getAttribute('data-cli-sort'); this.render(); });
      // чанк 3.4: фильтр воронки по ответственному (сброс выбора при смене фильтра)
      el.querySelectorAll('[data-deal-owner]').forEach(n => n.onclick = () => { this.dealOwner = n.getAttribute('data-deal-owner'); this.selClearAll(); this.render(); });
      // 6.23: bulk — чекбоксы и тулбар
      el.querySelectorAll('[data-deal-sel]').forEach(n => {
        n.addEventListener('click', (e) => { e.stopPropagation(); e.preventDefault(); this.selToggle('deals', n.getAttribute('data-deal-sel')); }, true);
      });
      const dsa = el.querySelector('[data-deal-selall]');
      if (dsa) dsa.onclick = (e) => { e.stopPropagation(); const flt = this.dealOwner === 'all' ? this.M.deals : this.M.deals.filter(d => d.owner === this.dealOwner); this.selAll('deals', flt.map(d => d.id)); };
      el.querySelectorAll('[data-task-sel]').forEach(n => {
        n.addEventListener('click', (e) => { e.stopPropagation(); e.preventDefault(); this.selToggle('tasks', n.getAttribute('data-task-sel')); }, true);
      });
      const tsa = el.querySelector('[data-task-selall]');
      if (tsa) tsa.onclick = (e) => { e.stopPropagation(); this.selAll('tasks', this.M.tasks.map(t => t.id)); };
      el.querySelectorAll('[data-bulk]').forEach(n => {
        n.onclick = (e) => {
          e.stopPropagation();
          const act = n.getAttribute('data-bulk');
          if (act === 'deal-stage') this.bulkDealStageModal();
          else if (act === 'deal-owner') this.bulkDealOwnerModal();
          else if (act === 'deal-project') this.bulkDealProjectModal();
          else if (act === 'task-complete') this.bulkTaskComplete();
          else if (act === 'task-owner') this.bulkTaskOwnerModal();
          else if (act === 'task-date') this.bulkTaskDateModal();
          else if (act === 'task-deal') this.bulkTaskDealModal();
          else if (act === 'clear-deals') this.selClear('deals');
          else if (act === 'clear-tasks') this.selClear('tasks');
        };
      });
      // 5.1: сворачивание колонок воронки
      el.querySelectorAll('[data-stage-toggle]').forEach(n => n.onclick = (e) => { e.stopPropagation(); this.toggleStage(n.getAttribute('data-stage-toggle')); });
      // И12: drag-and-drop карточек воронки
      let dragged = false;
      el.querySelectorAll('[data-deal-drag]').forEach(n => {
        n.addEventListener('dragstart', (e) => { dragged = true; this.dragDealId = n.getAttribute('data-deal-drag'); n.style.opacity = '0.4'; if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'; });
        n.addEventListener('dragend', () => { n.style.opacity = ''; this.dragDealId = null; setTimeout(() => { dragged = false; }, 50); });
        n.addEventListener('click', (e) => { if (dragged) { e.stopPropagation(); e.preventDefault(); } }, true);
      });
      el.querySelectorAll('[data-stage-drop]').forEach(col => {
        col.addEventListener('dragover', (e) => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'; col.style.background = 'var(--accent-soft)'; });
        col.addEventListener('dragleave', () => { col.style.background = ''; });
        col.addEventListener('drop', (e) => { e.preventDefault(); col.style.background = ''; const id = this.dragDealId; const st = col.getAttribute('data-stage-drop'); if (id && st) this.moveDeal(id, st); });
      });
      // 6.16: Канбан — drag-and-drop (тот же паттерн, что и воронка) + фильтры
      el.querySelectorAll('[data-kb-drag]').forEach(n => {
        n.addEventListener('dragstart', (e) => { dragged = true; this.dragDealId = n.getAttribute('data-kb-drag'); n.style.opacity = '0.4'; if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'; });
        n.addEventListener('dragend', () => { n.style.opacity = ''; this.dragDealId = null; setTimeout(() => { dragged = false; }, 50); });
        n.addEventListener('click', (e) => { if (dragged) { e.stopPropagation(); e.preventDefault(); } }, true);
      });
      el.querySelectorAll('[data-kb-drop]').forEach(col => {
        col.addEventListener('dragover', (e) => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'; col.style.background = 'var(--accent-soft)'; });
        col.addEventListener('dragleave', () => { col.style.background = ''; });
        col.addEventListener('drop', (e) => { e.preventDefault(); col.style.background = ''; const id = this.dragDealId; const st = col.getAttribute('data-kb-drop'); if (id && st) this.moveDeal(id, st); });
      });
      const kbO = document.getElementById('kbOwner'); if (kbO) kbO.onchange = (e) => { this.kanbanFilter.owner = e.target.value; this.render(); };
      const kbN = document.getElementById('kbNeed'); if (kbN) kbN.onchange = (e) => { this.kanbanFilter.need = e.target.value; this.render(); };
      const kbG = document.getElementById('kbGoal'); if (kbG) kbG.onchange = (e) => { this.kanbanFilter.goal = e.target.value; this.render(); };
      const kbR = document.getElementById('kbReset'); if (kbR) kbR.onclick = () => this.kanbanFilterReset();
    },
  };
}
