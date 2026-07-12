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
    calendar_events: [],     // M7: загружаются через _loadCalendarLayer()
    calFilter: 'all',        // M7: фильтр по kind (all/meeting/call/deadline/other)
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
          // M6-a: AI-слой после основных данных (non-fatal)
await this._loadAiLayer();
          // M7: Calendar-слой — только при CALENDAR_READY (предохранитель CONTRACTS.md §5)
          if (window.AGL && window.AGL.CALENDAR_READY) await this._loadCalendarLayer();

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
        esc(s) { return String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); },
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
      this.sel = { ...this.sel }; // trigger Alpine reactivity
    },
    selClearAll() { this.sel = { deals: new Set(), tasks: new Set() }; this.selMode = false; },
    selAll(kind, ids) { this.sel[kind] = new Set(ids); this.sel = { ...this.sel }; },

    // ======== render + bindView ========
    render() {
      let html = '';
      if      (this.route === 'myday')      html = this.vMyDay();
      else if (this.route === 'dashboard')  html = this.vDashboard();
      else if (this.route === 'inbox')      html = this.vInbox();
      else if (this.route === 'goals')      html = this.vGoals();
      else if (this.route === 'projects')   html = this.vProjects();
      else if (this.route === 'clients')    html = this.vClients();
      else if (this.route === 'client')     html = this.vClient();
      else if (this.route === 'deals')      html = this.vDeals();
      else if (this.route === 'deal')       html = this.vDeal();
      else if (this.route === 'kanban')     html = this.vKanban();
      else if (this.route === 'tasks')      html = this.vTasks();
      else if (this.route === 'packages')   html = this.vPackages();
      else if (this.route === 'artifacts')  html = this.vArtifacts();
      else if (this.route === 'team')       html = this.vTeam();
      else if (this.route === 'skills')     html = this.vSkills();
      else if (this.route === 'calendar')   html = this.vCalendar();
      else if (this.route === 'graph')      html = this.vGraph();
      else if (this.route === 'monitoring') html = this.vMonitoring();
      else if (this.route === 'content')    html = this.vContent();
      else if (this.route === 'settings')   html = this.vSettings();
      else html = `<div class="p-6 text-muted">Раздел в разработке: ${this.esc(this.route)}</div>`;
      const el = document.getElementById('view');
      if (el) { el.innerHTML = html; this.bindView(el); }
    },

    bindView(el) {
      if (!el) return;
      // universal back
      el.querySelectorAll('[data-back]').forEach(n => { n.onclick = () => history.back(); });
      // nav links
      el.querySelectorAll('[data-go]').forEach(n => { n.onclick = () => this.go(n.getAttribute('data-go'), n.getAttribute('data-arg') || null); });
      // deal stage
      el.querySelectorAll('[data-stage]').forEach(n => { n.onclick = () => this.setStage(n.getAttribute('data-deal'), n.getAttribute('data-stage')); });
      // task done
      el.querySelectorAll('[data-task-done]').forEach(n => { n.onclick = () => this.taskDone(n.getAttribute('data-task-done')); });
      // task delete
      el.querySelectorAll('[data-task-del]').forEach(n => { n.onclick = () => this.taskDel(n.getAttribute('data-task-del')); });
      // new task
      const ntf = el.querySelector('[data-new-task-form]');
      if (ntf) ntf.onsubmit = (e) => { e.preventDefault(); this.taskAdd(ntf); };
      // owl suggestion ok
      el.querySelectorAll('[data-owl-ok]').forEach(n => { n.onclick = () => this.owlOk(n.getAttribute('data-owl-ok')); });
      // owl suggestion dismiss
      el.querySelectorAll('[data-owl-dis]').forEach(n => { n.onclick = () => this.owlDismiss(n.getAttribute('data-owl-dis')); });
      // inbox item actions
      el.querySelectorAll('[data-inbox-done]').forEach(n => { n.onclick = () => this.inboxDone(n.getAttribute('data-inbox-done')); });
      el.querySelectorAll('[data-inbox-create]').forEach(n => { n.onclick = () => this.inboxCreate(n.getAttribute('data-inbox-create')); });
      // client filters
      const clf = el.querySelector('[data-cli-filter]');
      if (clf) clf.oninput = () => { this.cliQuery = clf.value; this.render(); };
      const cls = el.querySelector('[data-cli-sort]');
      if (cls) cls.onchange = () => { this.cliSort = cls.value; this.render(); };
      // deal owner filter
      const dof = el.querySelector('[data-deal-owner]');
      if (dof) dof.onchange = (e) => { this.dealOwner = e.target.value; this.render(); };
      // kanban filters
      const kbO = document.getElementById('kbOwner'); if (kbO) kbO.onchange = (e) => { this.kanbanFilter.owner = e.target.value; this.render(); };
      const kbN = document.getElementById('kbNeed');  if (kbN) kbN.onchange  = (e) => { this.kanbanFilter.need  = e.target.value; this.render(); };
      const kbG = document.getElementById('kbGoal');  if (kbG) kbG.onchange  = (e) => { this.kanbanFilter.goal  = e.target.value; this.render(); };
      const kbR = document.getElementById('kbReset'); if (kbR) kbR.onclick   = () => this.kanbanFilterReset();
      // M7: Calendar
      el.querySelectorAll('[data-cal-filter]').forEach(n => {
        n.onclick = () => { this.calFilter = n.getAttribute('data-cal-filter'); this.render(); };
      });
      el.querySelectorAll('[data-create-event]').forEach(n => {
        n.onclick = () => this.createEventModal();
      });
    },

    empty() { return '<div class="p-6 text-center" style="color:var(--text-mute)">Нет данных</div>'; },
  };
}
