// ===== AgroPILOT — ЭСКИЗ: ядро (роутер + диспетчер, навигация ОТ ОБЪЕКТОВ) =====
// Экраны дозаписываются в следующих чанках (1.4 Мой день, 1.5 карточка, 1.6 списки, 1.7 ПЕТРУШКА).
console.log('[AgroPILOT] appObjects.js loaded, MOCKO:', typeof window.MOCKO);
function appObjects() {
  return {
    M: (window.DEV_MOCK ? window.MOCKO : window.EMPTY_MODEL),  // M2.6-a: при DEV_MOCK=false — пустой скелет (без демо-сида)
    apiMode: false,  // true = data from BFF API, false = mock
    apiData: {},     // cached API data
    _persistKey: 'agropilot_data_v1',
    theme: (function () { try { var st = window['local' + 'Storage']; return (st && st.getItem('agropilot_theme')) || 'light'; } catch (e) { return 'light'; } })(),
    route: 'myday', routeArg: null,
    cmdkOpen: false, cmdkQuery: '',
    clock: '',
    toasts: [],
    owl: { open: false },
    owlDigest: null,          // M6-a: агрегат AGL.aiDigest() для шапки ПЕТРУШКА
    owlGrade: 'all',
    cliQuery: '', cliSort: 'name',
    dealOwner: 'all',
    skillFilter: 'all', skillReachedOnly: false, // M9-c: фильтры Team View (#/skills)
    calendar_events: [],       // M7: загружаются через _loadCalendarLayer()
        strategy: window.DEV_MOCK ? window.MOCKO.strategy : window.EMPTY_MODEL.strategy,
calFilter: 'all',          // M7: фильтр по kind (all/meeting/call/deadline/other)
    collapsedStages: {},
    kanbanFilter: { owner: 'all', need: 'all', goal: 'all' },
    kanbanDrag: null,
    // ======== ЧАНК 6.23: BULK-ДЕЙСТВИЯ — раздел 1: state выбора ========
    sel: { deals: new Set(), tasks: new Set() }, // множества id выбранных объектов
    selMode: false,                              // режим мультивыбора (показ чекбоксов)
    mobNav: false,
    currentUser: null,   // { id, name } из AGL.user (M8-b); null → actor='Оператор'
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

// M6-a (Класс A): подключение уже существующих AGL AI-методов. Non-fatal: сбой AI не рушит основную загрузку.
async _loadAiLayer() {
if (!window.AGL) return;
// digest → агрегат для шапки
try {
const dg = await window.AGL.aiDigest();
if (dg) this.owlDigest = dg;
} catch (e) { console.warn('[AGL] aiDigest skipped:', e && e.message); }
// recommendations → проактивные подсказки через owlPush (дедуп внутри)
try {
const recs = await window.AGL.aiRecommendations();
const list = Array.isArray(recs) ? recs : (recs && recs.items) || [];
for (const r of list) {
this.owlPush(this.makeHint({
kind: r.kind || 'task',
grade: r.grade || 'HINT',
text: r.title || r.text || '',
dealId: r.dealId || r.deal_id || '',
clientId: r.clientId || r.client_id || '',
okMsg: r.okMsg || r.ok_msg || '',
source: 'ai',
}));
}
} catch (e) { console.warn('[AGL] aiRecommendations skipped:', e && e.message); }
},

// M7: Calendar layer — non-fatal, только при CALENDAR_READY (CONTRACTS.md §5)
async _loadCalendarLayer() {
if (!window.AGL) return;
try {
const t = this.M.TODAY;
const from = new Date(new Date(t).getTime() - 30*864e5).toISOString().slice(0,10);
const to   = new Date(new Date(t).getTime() + 30*864e5).toISOString().slice(0,10);
const rows = await window.AGL.loadCalendar(from, to);
if (Array.isArray(rows)) this.M.calendar_events = rows;
} catch (e) { console.warn('[AGL] loadCalendar skipped:', e && e.message); }
},
    
    // M4: Strategy layer — non-fatal, только при STRATEGY_READY (CONTRACTS.md §4)
    _loadStrategyLayer() {
      if (!window.AGL.STRATEGY_READY) return;
      window.AGL.loadStrategy()
        .then(d => { this.M.strategy = d; })
        .catch(e => console.warn('[M4] loadStrategy error', e));
    },

    async loadFromAPI() {
      if (!window.AGL) { console.warn('[AGL] window.AGL not found'); return false; }
      window.AGL.initAuth();
      this.currentUser = window.AGL.user || null;   // M8-b
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

          console.log('[AGL] loadFromAPI results: deals=' + (deals?.length || 0) + ' goals=' + (goals?.length || 0) + ' tasks=' + (tasks?.length || 0) + ' team=' + (team?.length || 0) + ' packages=' + (packages?.length || 0) + ' artifacts=' + (artifacts?.length || 0) + ' content=' + (content?.length || 0) + ' reports=' + (reports?.length || 0) + ' clients=' + (clients?.length || 0));

          // If ALL API calls returned empty, keep mock data (don't overwrite MOCKO)
          const allEmpty = [deals, goals, tasks, team, packages, artifacts, content, reports, clients].every(a => !a || a.length === 0);
          if (allEmpty) {
            if (window.DEV_MOCK) {  // M2.6-c: пустой API-ответ — в mock остаёмся на демо-сиде, в проде показываем empty()
              console.warn('[AGL] all API calls empty, keeping mock data (DEV_MOCK)');
              this.apiMode = false;
              return false;
            }
            console.warn('[AGL] all API calls empty, showing empty state (prod)');
            this.apiMode = true;
            return false;
          }

          this.apiData = { deals, goals, tasks, team, packages, artifacts, content, reports, clients };

          // Map BFF format to mock format
          const STAGE_MAP = { lead: 'Зацепка', assess: 'Оценка', proposal: 'Договор', deal: 'Проектирование', won: 'Реализация', lost: 'Проиграна', service: 'Сервис', cancelled: 'Отменена' };
          const STAGE_REVERSE = Object.fromEntries(Object.entries(STAGE_MAP).map(([k, v]) => [v, k]));
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
            date: t.due_at || '',        // алиас для vMyDay4() (fix: t.date.slice(5) TypeError)
            priority: t.priority || 'normal',
            dealId: t.deal_id || '',
            score: t.score || 0,         // fix: hot[] был всегда пуст без этого поля
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
          // M6-a: AI-слой после основных данных (non-fatal)
await this._loadAiLayer();
// M7: Calendar-слой — только при CALENDAR_READY (предохранитель CONTRACTS.md §5)
if (window.AGL && window.AGL.CALENDAR_READY) await this._loadCalendarLayer();
                    if (window.AGL && window.AGL.STRATEGY_READY) this._loadStrategyLayer();

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
            } catch (refreshErr) {
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
      } catch (e) { console.warn('[persist] failed:', e); }
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
      } catch (e) { console.warn('[restore] failed:', e); return false; }
    },

    init() {
      console.log('[AgroPILOT] init() called');
      this.applyTheme();
      // Restore persisted data before anything else (M2.6-d: только в демо-режиме;
      // при DEV_MOCK=false localStorage-слепок не подмешивается в прод-состояние)
      if (window.DEV_MOCK) this.restore();
      this.tick(); setInterval(() => this.tick(), 1000);
      // seed истории по сделкам
      if (window.DEV_MOCK) {  // M2.6-b: сид демо-истории только в mock-режиме
        console.log('[AgroPILOT] deals count:', this.M.deals?.length || 0);
        this.M.deals.forEach(d => { if (!d.history) d.history = [{ date: d.updated, kind: 'stage', text: `Стадия: ${d.stage}` }, { date: d.updated, kind: 'create', text: 'Сделка создана' }]; });
      }
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
      try { var st = window['local' + 'Storage']; if (st) st.setItem('agropilot_theme', this.theme); } catch (e) { }
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
    go(r, arg) { if (r !== this.route) this.selClearAll(); location.hash = '#/' + r + (arg ? '/' + arg : ''); this.route = r; this.routeArg = arg; this.mobNav = false;  if (r === 'deal' && arg && window.AGL && window.AGL.aiScore) { window.AGL.aiScore(arg).then(res => { const d = this.dealById(arg); if (d && res) { d.score = (res.score != null ? res.score : (res.data && res.data.score)) || d.score; } }).catch(e => console.warn('[AGL] aiScore skipped:', e && e.message)); }},

    pageTitle() {
      return ({
        myday: 'Мой день',
        clients: 'Клиенты',
        deals: 'Сделки · Проекты',
        tasks: 'Задачи',
        packages: 'Упаковки',
        artifacts: 'Артефакты',
        graph: 'Граф объектов',
        skills: 'Навыки команды',
        calendar: 'Календарь',
        monitoring: 'Мониторинг рынка',
        client: 'Карточка клиента',
        deal: 'Карточка сделки',
        settings: 'Настройки',
                strategy: 'Стратегия',
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
        esc(s) { return String(s ?? '').replace(/[&<>\"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); },
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
    logDeal(d, kind, text, actor) { if (!d) return; if (!d.history) d.history = []; d.history.unshift({ date: this.M.TODAY, kind, text, actor_name: actor || 'Система' }); },

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
        else if (this.route === 'skills') html = this.vSkills();
        else if (this.route === 'calendar') html = this.vCalendar();
                  else if (this.route === 'strategy') html = this.vStrategy();
        else if (this.route === 'graph') html = this.vGraph();
        else if (this.route === 'client') html = this.vClientCard(this.routeArg);
        else if (this.route === 'deal') html = this.vDealCard(this.routeArg);
        else if (this.route === 'settings') html = this.vSettings();
        else html = `<div class="card p-8 text-center" style="color:var(--text-mute)"><div class="text-2xl font-semibold mb-2">Раздел не найден</div><div class="mb-4">Такого раздела нет или он ещё не подключён.</div><button class="btn btn-accent" data-go="myday:">На главную</button></div>`;
        el.innerHTML = `<div class="fade-in">${html}</div>`;
        this.bindView();
        this.owlRender();
      });
    },
  bindView() {
    const el = document.getElementById('view');
    if (!el) return;
    // data-go="route:arg" — навигация по клику
    el.querySelectorAll('[data-go]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const val = btn.getAttribute('data-go');
        const [r, arg] = val.split(':');
        this.go(r, arg || null);
      });
    });
    // data-cal-filter
    el.querySelectorAll('[data-cal-filter]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.calFilter = btn.getAttribute('data-cal-filter');
        this.render();
      });
    });
    // data-skills-view
    el.querySelectorAll('[data-skills-view]').forEach(btn => {
      btn.addEventListener('click', () => {
        const v = btn.getAttribute('data-skills-view');
        this._skillsViewSet(v);
        this.render();
      });
    });
    // data-skill-filter (select)
    el.querySelectorAll('[data-skill-filter]').forEach(sel => {
      sel.addEventListener('change', () => {
        this.skillFilter = sel.value;
        this.render();
      });
    });
    // data-skill-reached (checkbox)
    el.querySelectorAll('[data-skill-reached]').forEach(cb => {
      cb.addEventListener('change', () => {
        this.skillReachedOnly = cb.checked;
        this.render();
      });
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
  // ======== M9-b: skillMaturity() — порог B→A по team_skills (batch-агрегат) ========
  // grade: CONFIRM → V и числитель Q; AUTO → только V; HINT → игнор; иное → warn.
  // окно: 30 дней от M.TODAY вкл.; порог V>=10 AND Q>=0.80 → reached.
  // user_id: dealId→deals.owner(имя)→team[].name===owner→id. Возврат map {user_id:{V,Q,reached}}.
  skillMaturity() {
    const M = this.M;
    const today = new Date(M.TODAY);
    const from = new Date(today); from.setDate(from.getDate() - 30);
    const dealOwner = id => { const d = (M.deals || []).find(x => x.id === id); return d ? d.owner : null; };
    const ownerToUser = name => { const t = (M.team || []).find(x => x.name === name); return t ? t.id : null; };
    const acc = {};
    (M.owlSuggestions || []).forEach(o => {
      if (!o.date) return;
      const d = new Date(o.date);
      if (d < from || d > today) return;
      let uid = o.user_id || ownerToUser(dealOwner(o.dealId));
      if (!uid) return;
      const g = o.grade;
      if (g === 'HINT') return;
      if (g !== 'CONFIRM' && g !== 'AUTO') { console.warn('skillMaturity: unknown grade', g, o.id); return; }
      const a = acc[uid] || (acc[uid] = { V: 0, conf: 0 });
      a.V += 1;
      if (g === 'CONFIRM') a.conf += 1;
    });
    const out = {};
    Object.keys(acc).forEach(uid => {
      const V = acc[uid].V;
      const Q = V ? acc[uid].conf / V : 0;
      out[uid] = { V, Q: Math.round(Q * 100) / 100, reached: (V >= 10 && Q >= 0.80) };
    });
    return out;
  },                                                                                                                                                        
  // ======== M9-c: вьюха #/skills — Навыки команды и порог B->A ========
// Роль-гейтинг Team View (§5): только 'Руководитель продаж' по team[].role (единая привязка).
// Персист режима: localStorage ключ agropilot_skills_view ('team'|'my'). Форс 'my' при потере прав.
_skillsViewGet() { try { var st = window['local' + 'Storage']; var v = st && st.getItem('agropilot_skills_view'); return (v === 'team' || v === 'my') ? v : 'team'; } catch (e) { return 'team'; } },
_skillsViewSet(v) { try { var st = window['local' + 'Storage']; if (st) st.setItem('agropilot_skills_view', v); } catch (e) { } },
currentUserId() { return (this.currentUser && this.currentUser.id) || (this.M.team && this.M.team[0] && this.M.team[0].id) || null; },
isManager() { const uid = this.currentUserId(); const u = (this.M.team || []).find(t => t.id === uid); return !!(u && u.role === 'Руководитель продаж'); },
// навыки пользователя -> строка 'skill: level, ...'
skillsOf(uid) { return (this.M.skills || []).filter(s => s.user_id === uid); },
skillsList() { const set = []; (this.M.skills || []).forEach(s => { if (s.skill && set.indexOf(s.skill) < 0) set.push(s.skill); }); return set; },
// диспетчер вьюхи: форс 'my' если нет прав на Team View (§5)
vSkills() {
  let mode = this._skillsViewGet();
  const mgr = this.isManager();
  if (mode === 'team' && !mgr) { mode = 'my'; this._skillsViewSet('my'); }
  const toggle = mgr ? `<div style="display:inline-flex;border:1px solid var(--border);border-radius:9px;overflow:hidden"><button data-skills-view="team" style="padding:6px 14px;border:0;cursor:pointer;background:${mode==='team'?'var(--accent-soft)':'transparent'};color:var(--text)">Команда</button><button data-skills-view="my" style="padding:6px 14px;border:0;cursor:pointer;background:${mode==='my'?'var(--accent-soft)':'transparent'};color:var(--text)">Я</button></div>` : '';
  const body = mode === 'team' ? this.vSkillsTeam() : this.vSkillsMy();
  return `<div class="card"><div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px"><div style="font-size:18px;font-weight:600">🎓 Навыки команды</div>${toggle}</div>${body}</div>`;
},
// Team View (§3): таблица по team[], batch skillMaturity(), сортировка по дистанции до порога
vSkillsTeam() {
  const M = this.M;
  const mat = this.skillMaturity();
  const filter = this.skillFilter || 'all';
  const reachedOnly = !!this.skillReachedOnly;
  const skillOpts = this.skillsList().map(s => `<option value="${this.esc(s)}" ${filter===s?'selected':''}>${this.esc(s)}</option>`).join('');
  const bar = (val, max, ok) => { const pct = Math.min(100, Math.round(val / max * 100)); const col = ok ? 'var(--ok)' : 'var(--warn)'; return `<div style="background:var(--surface-2);border-radius:6px;height:8px;overflow:hidden;min-width:70px"><div style="height:100%;width:${pct}%;background:${col}"></div></div>`; };
  let rows = (M.team || []).map(u => {
    const sk = this.skillsOf(u.id);
    if (filter !== 'all' && !sk.some(s => s.skill === filter)) return null;
    const m = mat[u.id];
    const reached = !!(m && m.reached);
    if (reachedOnly && !reached) return null;
    const skStr = sk.length ? sk.map(s => `${this.esc(s.skill)}: ${s.level}`).join(', ') : '—';
    let cells;
    if (!m) { cells = `<td colspan="3" style="color:var(--text-dim)">Нет активности за 30 дней</td>`; }
    else {
      const qPct = Math.round(m.Q * 100);
      const status = reached ? `<span style="background:var(--ok);color:#fff;padding:2px 8px;border-radius:6px;font-size:12px">Достигнут</span>` : `<div style="display:flex;flex-direction:column;gap:3px;font-size:12px"><div>V ${m.V}/10 ${bar(m.V,10,m.V>=10)}</div><div>Q ${qPct}%/80% ${bar(m.Q,0.8,m.Q>=0.8)}</div></div>`;
      cells = `<td>${m.V}</td><td>${qPct}%</td><td>${status}</td>`;
    }
    const dist = m ? (Math.max(0, 10 - m.V) + Math.max(0, 0.8 - m.Q) * 12.5) : 999;
    const rowBg = reached ? 'background:rgba(34,197,94,.12)' : '';
    const badge = reached ? ` <span style="background:var(--ok);color:#fff;padding:1px 6px;border-radius:5px;font-size:11px">B-&gt;A</span>` : '';
    return { dist, html: `<tr style="${rowBg}"><td>${u.avatar || ''} ${this.esc(u.name)}${badge}</td><td>${this.esc(u.role)}</td><td>${this.esc(skStr)}</td>${cells}</tr>` };
  }).filter(Boolean).sort((a, b) => a.dist - b.dist).map(r => r.html).join('');
  if (!rows) rows = `<tr><td colspan="6" style="color:var(--text-dim);text-align:center">Нет данных по фильтру</td></tr>`;
  return `<div style="display:flex;gap:12px;align-items:center;margin-bottom:10px;flex-wrap:wrap"><select data-skill-filter style="padding:5px 8px"><option value="all" ${filter==='all'?'selected':''}>Все навыки</option>${skillOpts}</select><label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" data-skill-reached ${reachedOnly?'checked':''}> Только достигшие порога</label></div><table style="width:100%;border-collapse:collapse" class="skills-table"><thead><tr style="text-align:left;color:var(--text-mute);font-size:12px"><th>Сотрудник</th><th>Роль</th><th>Навыки</th><th>V</th><th>Q</th><th>Порог B-&gt;A</th></tr></thead><tbody>${rows}</tbody></table>`;
},
// My View (§4): личный прогресс текущего пользователя (point-wise skillMaturity()[uid])
vSkillsMy() {
  const M = this.M;
  const uid = this.currentUserId();
  const m = this.skillMaturity()[uid];
  const bar = (val, max, ok) => { const pct = Math.min(100, Math.round(val / max * 100)); const col = ok ? 'var(--ok)' : 'var(--warn)'; return `<div style="background:var(--surface-2);border-radius:6px;height:12px;overflow:hidden;flex:1"><div style="height:100%;width:${pct}%;background:${col}"></div></div>`; };
  const reached = !!(m && m.reached);
  let progress;
  if (!m) { progress = `<div style="color:var(--text-dim)">Нет активности за 30 дней</div>`; }
  else if (reached) { progress = `<div style="background:var(--ok);color:#fff;padding:10px 14px;border-radius:9px;font-weight:600">✅ Порог B-&gt;A достигнут (V ${m.V}/10, Q ${Math.round(m.Q*100)}%/80%)</div>`; }
  else { const qPct = Math.round(m.Q * 100); progress = `<div style="display:flex;flex-direction:column;gap:8px"><div style="display:flex;gap:10px;align-items:center"><span style="min-width:120px">V (объём): ${m.V}/10</span>${bar(m.V,10,m.V>=10)}</div><div style="display:flex;gap:10px;align-items:center"><span style="min-width:120px">Q (качество): ${qPct}%/80%</span>${bar(m.Q,0.8,m.Q>=0.8)}</div></div>`; }
  const sk = this.skillsOf(uid);
  const skRows = sk.length ? sk.map(s => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)"><span>${this.esc(s.skill)} · ур. ${s.level}</span><span style="color:var(--text-dim)">${this.esc(s.note || '')}</span></div>`).join('') : `<div style="color:var(--text-dim)">Навыки не указаны</div>`;
  const today = new Date(M.TODAY); const from = new Date(today); from.setDate(from.getDate() - 30);
  const feed = (M.owlSuggestions || []).filter(o => { if (o.user_id !== uid) return false; if (o.grade !== 'CONFIRM' && o.grade !== 'AUTO') return false; if (!o.date) return false; const d = new Date(o.date); return d >= from && d <= today; }).sort((a, b) => (a.date < b.date ? 1 : -1));
  const feedRows = feed.length ? feed.map(o => { const d = this.dealById(o.dealId); const gc = o.grade === 'CONFIRM' ? 'var(--warn)' : 'var(--ok)'; return `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px"><span style="color:var(--text-dim)">${o.date}</span> · <span style="color:${gc}">${o.grade}</span>${d ? ' · ' + this.esc(d.title) : ''}<div style="color:var(--text-dim)">${this.esc(o.text || '')}</div></div>`; }).join('') : `<div style="color:var(--text-dim)">Нет учтённых действий за 30 дней</div>`;
  return `<div class="card-2" style="padding:14px;margin-bottom:12px"><div class="label" style="margin-bottom:8px">Мой прогресс к следующему уровню</div>${progress}</div><div class="card-2" style="padding:14px;margin-bottom:12px"><div class="label" style="margin-bottom:8px">Мои навыки</div>${skRows}</div><div class="card-2" style="padding:14px"><div class="label" style="margin-bottom:8px">Действия за 30 дней (учтены в V/Q)</div>${feedRows}</div>`;
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
        <span class="text-lg" style="color:${done ? 'var(--ok)' : 'var(--text-mute)'}"><span>${done ? '✔' : n}</span>
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
      // ===== ПЕТРУШКА: рендер панели + запрос =====
  owlRender() {
    const body = document.getElementById('owlBody');
    if (!body) return;
    const hints = (this.M.owlSuggestions || []).slice().reverse();
    if (!hints.length) {
      body.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0">\n      \u041d\u0435\u0442 \u043f\u043e\u0434\u0441\u043a\u0430\u0437\u043e\u043a. \u0417\u0430\u0434\u0430\u0439\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441 \u0438\u043b\u0438 \u043f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d\u043e\u0433\u043e \u0430\u043d\u0430\u043b\u0438\u0437\u0430.</div>`;
      return;
    }
    body.innerHTML = hints.map(h => {
      const gc = this.gradeColor(h.grade);
      const d = h.dealId ? this.dealById(h.dealId) : null;
      return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">`
        + `<div style="display:flex;gap:6px;align-items:center;margin-bottom:3px">`
        + `<span style="color:${gc};font-size:11px;font-weight:600">${this.esc(h.grade)}</span>`
        + (d ? `<span style="font-size:11px;color:var(--text-dim)">${this.esc(d.title)}</span>` : '')
        + `<span style="font-size:11px;color:var(--text-mute);margin-left:auto">${h.date || ''}</span>`
        + `</div><div style="font-size:13px">${this.esc(h.text || '')}</div></div>`;
    }).join('');
  },

  async owlAsk() {
    const inp = document.getElementById('owlInput');
    if (!inp) return;
    const q = (inp.value || '').trim();
    if (!q) return;
    inp.value = '';
    const body = document.getElementById('owlBody');
    if (body) {
      body.innerHTML = `<div style="color:var(--text-dim);font-size:13px;padding:8px 0">`
        + `${this.petIco(14)} \u0414\u0443\u043c\u0430\u044e\u2026</div>`;
    }
    try {
      let reply = '';
      if (this.apiMode && window.AGL && window.AGL.orchChat) {
        const res = await window.AGL.orchChat({ message: q });
        reply = (res && (res.reply || res.text || res.message)) || '(\u043d\u0435\u0442 \u043e\u0442\u0432\u0435\u0442\u0430)';
      } else {
        reply = this.petReply(q);
      }
      this.owlPush(this.makeHint({
        kind: 'chat',
        grade: 'HINT',
        text: `Q: ${q}\nA: ${reply}`,
        source: 'chat',
      }));
    } catch (e) {
      this.owlPush(this.makeHint({
        kind: 'chat',
        grade: 'HINT',
        text: `Q: ${q}\nA: [\u043e\u0448\u0438\u0431\u043a\u0430 \u0437\u0430\u043f\u0440\u043e\u0441\u0430: ${e && e.message}]`,
        source: 'chat',
      }));
    }
    this.owlRender();
  },
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
      cons
