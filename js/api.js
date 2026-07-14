/**
 * AgroPILOT — REST API client for BFF :5555
 * Loads real data from backend, maps to mock format used by Alpine.js UI.
 */

const API_BASE = '/agropilot/api';

// Token helpers
function getToken() {
  try { return localStorage.getItem('agropilot_token') || ''; } catch(e) { return ''; }
}
function setToken(t) {
  try { localStorage.setItem('agropilot_token', t); } catch(e) {}
}

// Store for auth token
function apiHeaders() {
  const h = { 'Content-Type': 'application/json' };
  if (AGL.token) h['Authorization'] = 'Bearer ' + AGL.token;
  return h;
}

async function apiFetch(path, opts = {}) {
  const r = await fetch(API_BASE + path, {
    method: opts.method || 'GET',
    headers: { ...apiHeaders(), ...(opts.headers || {}) },
    body: opts.data ? JSON.stringify(opts.data) : undefined,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status} ${path}`);
  const d = await r.json();
  if (d.ok === false) throw new Error(d.error?.message || 'API error');
  return d.data;
}

/**
 * safeLoad — wraps apiFetch for endpoints that may not be implemented yet.
 * Returns fallback (default []) instead of throwing on HTTP 404/5xx.
 * Lets deals/tasks/calendar fail loudly (real errors), but goals/packages/etc.
 * degrade silently so _loadAllData (Promise.all) does not abort the whole load.
 */
async function safeLoad(path, fallback = []) {
  try {
    return await apiFetch(path);
  } catch(e) {
    // Only swallow "not implemented" errors; re-throw auth errors
    if (e.message && (e.message.includes('401') || e.message.includes('403'))) throw e;
    console.warn('[AGL safeLoad] endpoint unavailable, using fallback:', path, e.message);
    return fallback;
  }
}

const AGL = {
  token: getToken(),

  // ─── Auth ───
  async login(login, password) {
    const r = await fetch(API_BASE + '/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password }),
    });
    const d = await r.json();
    if (d.ok) {
      this._saveToken(d.data);
      return d.data;
    }
    throw new Error(d.error?.message || 'Login failed');
  },

  async refresh() {
    const refresh = localStorage.getItem('agropilot_refresh') || '';
    if (!refresh) return false;
    const r = await fetch(API_BASE + '/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + refresh },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    const d = await r.json();
    if (d.ok) {
      this._saveToken(d.data);
      return true;
    }
    return false;
  },

  user: null,

  _decodeUser(token) {
    try {
      const payload = token.split('.')[1];
      if (!payload) return null;
      const json = decodeURIComponent(atob(payload.replace(/-/g, '+').replace(/_/g, '/')).split('').map(function(c){ return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2); }).join(''));
      const p = JSON.parse(json);
      const name = p.name || p.full_name || p.login || p.username || p.sub || null;
      if (!name) return null;
      return { id: p.sub || p.user_id || p.id || null, name: name };
    } catch (e) { return null; }
  },

  _saveToken(data) {
    this.token = data.access_token;
    this.user = this._decodeUser(data.access_token);
    if (data.refresh_token) {
      localStorage.setItem('agropilot_refresh', data.refresh_token);
    }
    localStorage.setItem('agropilot_token', data.access_token);
  },

  setToken(t) { this.token = t; },

  initAuth() {
    this.token = localStorage.getItem('agropilot_token') || getToken();
    this.user = this.token ? this._decodeUser(this.token) : null;
  },

  async logout() {
    try { await apiFetch('/v1/auth/logout', { method: 'POST' }); } catch(e) {}
    this.token = null;
    this.user = null;
    localStorage.removeItem('agropilot_token');
    localStorage.removeItem('agropilot_refresh');
  },

  getAuthHeaders() {
    const h = { 'Content-Type': 'application/json' };
    if (this.token) h['Authorization'] = 'Bearer ' + this.token;
    return h;
  },

  // ─── Clients (derived from deals) ───
  async loadClients() {
    const deals = await apiFetch('/v1/deals?limit=200');
    const seen = new Set();
    const clients = [];
    for (const d of deals || []) {
      if (d.client_id && !seen.has(d.client_id)) {
        seen.add(d.client_id);
        clients.push({
          id: d.client_id,
          name: d.client_name || d.client_id,
          region: d.region || '',
          industry: d.industry || '',
          need: d.need_type ? [d.need_type] : [],
          health: 'green',
          dealsCount: (deals || []).filter(x => x.client_id === d.client_id).length,
        });
      }
    }
    return clients;
  },

  // ─── Deals (implemented — hard fail on error) ───
  async loadDeals() {
    return apiFetch('/v1/deals?limit=100');
  },
  async loadDeal(id) {
    return apiFetch('/v1/deals/' + id);
  },
  async createDeal(data) {
    return apiFetch('/v1/deals', { method: 'POST', data });
  },
  async updateDeal(id, data) {
    return apiFetch('/v1/deals/' + id, { method: 'PATCH', data });
  },
  async deleteDeal(id) {
    return apiFetch('/v1/deals/' + id, { method: 'DELETE' });
  },
  async setStage(id, stage) {
    return apiFetch('/v1/deals/bulk-stage', { method: 'POST', data: { ids: [id], stage } });
  },

  // ─── Goals (safeLoad — endpoint may be absent) ───
  async loadGoals() {
    return safeLoad('/v1/goals?limit=100');
  },
  async createGoal(data) {
    return apiFetch('/v1/goals', { method: 'POST', data });
  },
  async updateGoal(id, data) {
    return apiFetch('/v1/goals/' + id, { method: 'PATCH', data });
  },

  // ─── Tasks (implemented — hard fail on error) ───
  async loadTasks() {
    return apiFetch('/v1/tasks?limit=100');
  },
  async createTask(data) {
    return apiFetch('/v1/tasks', { method: 'POST', data });
  },
  async updateTask(id, data) {
    return apiFetch('/v1/tasks/' + id, { method: 'PATCH', data });
  },
  async deleteTask(id) {
    return apiFetch('/v1/tasks/' + id, { method: 'DELETE' });
  },

  // ─── Packages (safeLoad) ───
  async loadPackages() {
    return safeLoad('/v1/packages?limit=100');
  },
  async createPackage(data) {
    return apiFetch('/v1/packages', { method: 'POST', data });
  },

  // ─── Team (safeLoad) ───
  async loadTeam() {
    return safeLoad('/v1/team?limit=100');
  },

  // ─── Sources (safeLoad) ───
  async loadSources() {
    return safeLoad('/v1/sources?limit=100');
  },
  async createSource(data) {
    return apiFetch('/v1/sources', { method: 'POST', data });
  },

  // ─── Reports (safeLoad) ───
  async loadReports() {
    return safeLoad('/v1/reports?limit=100');
  },
  async createReport(data) {
    return apiFetch('/v1/reports', { method: 'POST', data });
  },

  // ─── Content (safeLoad) ───
  async loadContent() {
    return safeLoad('/v1/content?limit=100');
  },
  async createContent(data) {
    return apiFetch('/v1/content', { method: 'POST', data });
  },

  // ─── Artifacts (safeLoad) ───
  async loadArtifacts() {
    return safeLoad('/v1/artifacts?limit=100');
  },
  async createArtifact(data) {
    return apiFetch('/v1/artifacts', { method: 'POST', data });
  },

  // ─── Search ───
  async search(q, type, limit = 20) {
    let path = `/v1/search?q=${encodeURIComponent(q)}&limit=${limit}`;
    if (type) path += `&type=${encodeURIComponent(type)}`;
    return safeLoad(path, []);
  },

  // ─── Graph ───
  async graphSync() {
    return apiFetch('/v1/graph/sync', { method: 'POST' });
  },
  async graphStats() {
    return safeLoad('/v1/graph/stats', {});
  },
  async nodeNeighbors(type, id) {
    return safeLoad(`/v1/graph/neighbors/${type}/${id}`, []);
  },

  // ─── BFF status ───
  async status() {
    const r = await fetch('/agropilot/health');
    return r.json();
  },

  // ─── LLM AI functions (safeLoad where applicable) ───
  async aiScore(dealId) {
    return apiFetch(`/v1/deals/${dealId}/ai/score`, { method: 'POST' });
  },
  async aiEnrich(dealId) {
    return apiFetch(`/v1/deals/${dealId}/ai/enrich`, { method: 'POST' });
  },
  async aiFollowup(dealId) {
    return apiFetch(`/v1/deals/${dealId}/ai/followup`, { method: 'POST' });
  },
  async aiGenerateKP(dealId) {
    return apiFetch(`/v1/deals/${dealId}/ai/generate-kp`, { method: 'POST' });
  },
  async aiContract(dealId) {
    return apiFetch(`/v1/deals/${dealId}/ai/generate-contract`, { method: 'POST' });
  },
  async aiDigest() {
    return safeLoad('/v1/orchestrator/digest', null);
  },
  async aiRecommendations() {
    return safeLoad('/v1/orchestrator/recommendations', []);
  },
  async aiFeedback(message) {
    return apiFetch('/v1/orchestrator/feedback', { method: 'POST', data: { message } });
  },
  async aiContentDraft(contentId) {
    return apiFetch(`/v1/content/${contentId}/ai/draft`, { method: 'POST' });
  },
  async orchChat(message) {
    return apiFetch('/v1/orchestrator/chat', { method: 'POST', data: { message } });
  },
  async aiContentTrends(contentId) {
    return apiFetch(`/v1/content/${contentId}/ai/trends`, { method: 'POST' });
  },

  // —— Feature flags ——
  CALENDAR_READY:  true,
  VERSIONS_READY:  false,
  SKILLS_READY:    true,
  STRATEGY_READY:  true,
  DEALS_READY:     true,   // GET/PATCH /v1/deals   ✅ backend активен
  TASKS_READY:     true,   // GET/PATCH /v1/tasks   ✅ backend активен

  // —— Calendar (M7) ——
  async loadCalendar(from, to) {
    return apiFetch('/v1/calendar?from=' + encodeURIComponent(from) + '&to=' + encodeURIComponent(to) + '&limit=200');
  },
  async createEvent(data)     { return apiFetch('/v1/calendar', { method: 'POST', data }); },
  async updateEvent(id, data) { return apiFetch('/v1/calendar/' + id, { method: 'PATCH', data }); },
  async deleteEvent(id)       { return apiFetch('/v1/calendar/' + id, { method: 'DELETE' }); },

  // —— Strategy (M4) ——
  async loadStrategy()        { return apiFetch('/v1/strategy'); },
  async updateStrategy(data)  { return apiFetch('/v1/strategy', { method: 'PUT', data }); },
};

window.AGL = AGL;
