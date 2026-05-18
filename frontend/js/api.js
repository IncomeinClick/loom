// Loom API Client
const API = {
    baseUrl: '',
    token: localStorage.getItem('loom_token') || '',
    _authPromise: null,

    setToken(key) {
        this.token = key;
        localStorage.setItem('loom_token', key);
    },

    async ensureToken() {
        if (this.token) return;
        if (!this._authPromise) {
            this._authPromise = new Promise(async (resolve) => {
                const status = await fetch(`${this.baseUrl}/api/setup-status`)
                    .then(r => r.json())
                    .catch(() => ({ needs_setup: true, has_login: false }));
                const overlay = document.getElementById('authOverlay');
                overlay.dataset.mode = status.needs_setup ? 'setup' : 'login';
                overlay.style.display = 'flex';
                const btn = document.getElementById('authBtn');
                const title = document.getElementById('authTitle');
                const subtitle = document.getElementById('authSubtitle');
                if (status.needs_setup) {
                    title.textContent = 'Welcome to Loom';
                    subtitle.textContent = 'First-time setup — create your login';
                    btn.textContent = 'Create account';
                } else {
                    title.textContent = 'Loom';
                    subtitle.textContent = 'Workflow automation';
                    btn.textContent = 'Sign in';
                }
                const onSubmit = async () => {
                    const email = document.getElementById('authEmail').value.trim();
                    const password = document.getElementById('authPass').value;
                    const errEl = document.getElementById('authError');
                    errEl.textContent = '';
                    if (!email || !password) { errEl.textContent = 'Email and password required.'; return; }
                    try {
                        const endpoint = overlay.dataset.mode === 'setup' ? '/api/setup' : '/api/login';
                        const res = await fetch(`${this.baseUrl}${endpoint}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ email, password }),
                        });
                        if (!res.ok) {
                            const data = await res.json().catch(() => ({}));
                            errEl.textContent = data.detail || `Error ${res.status}`;
                            return;
                        }
                        const data = await res.json();
                        if (data.token) {
                            this.setToken(data.token);
                            overlay.style.display = 'none';
                            btn.removeEventListener('click', onSubmit);
                            resolve();
                            this._authPromise = null;
                        }
                    } catch (e) {
                        errEl.textContent = e.message;
                    }
                };
                btn.addEventListener('click', onSubmit);
            });
        }
        await this._authPromise;
    },

    async request(method, path, body = null) {
        // Skip auth for health endpoint
        if (!path.includes('/health')) {
            await this.ensureToken();
        }

        const opts = {
            method,
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json',
            },
        };
        if (body) opts.body = JSON.stringify(body);
        const resp = await fetch(`${this.baseUrl}${path}`, opts);
        if (resp.status === 401) {
            // Token invalid — clear and re-prompt
            this.token = '';
            localStorage.removeItem('loom_token');
            this._authPromise = null;
            await this.ensureToken();
            if (this.token) {
                return this.request(method, path, body);
            }
            throw new Error('Authentication required');
        }
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        if (resp.status === 204) return null;
        const text = await resp.text();
        return text ? JSON.parse(text) : null;
    },

    // Health
    health() { return this.request('GET', '/api/health'); },

    // Pages
    listPages() { return this.request('GET', '/api/pages'); },
    getPage(id) { return this.request('GET', `/api/pages/${id}`); },
    createPage(data) { return this.request('POST', '/api/pages', data); },
    updatePage(id, data) { return this.request('PUT', `/api/pages/${id}`, data); },
    deletePage(id) { return this.request('DELETE', `/api/pages/${id}`); },
    renamePage(id, data) { return this.request('POST', `/api/pages/${id}/rename`, data); },
    clonePage(id, data) { return this.request('POST', `/api/pages/${id}/clone`, data); },
    reorderPages(pages) { return this.request('POST', '/api/pages/reorder', { pages }); },

    // Workflows
    listWorkflows(pageId = null) {
        const q = pageId ? `?page_id=${pageId}` : '';
        return this.request('GET', `/api/workflows${q}`);
    },
    getWorkflow(id) { return this.request('GET', `/api/workflows/${id}`); },
    createWorkflow(data) { return this.request('POST', '/api/workflows', data); },
    updateWorkflow(id, data) { return this.request('PUT', `/api/workflows/${id}`, data); },
    deleteWorkflow(id) { return this.request('DELETE', `/api/workflows/${id}`); },
    renameWorkflow(id, data) { return this.request('POST', `/api/workflows/${id}/rename`, data); },
    duplicateWorkflow(id, newId, newName, pageId) {
        const data = { new_id: newId, new_name: newName || '' };
        if (pageId) data.page_id = pageId;
        return this.request('POST', `/api/workflows/${id}/duplicate`, data);
    },
    updatePrompt(wfId, stepId, data) {
        return this.request('PUT', `/api/workflows/${wfId}/steps/${stepId}/prompt`, data);
    },
    triggerWorkflow(id) { return this.request('POST', `/api/workflows/${id}/trigger`); },
    triggerUntilStep(workflowId, stepId) { return this.request('POST', `/api/workflows/${workflowId}/trigger-until/${stepId}`); },

    // Credentials
    listCredentials() { return this.request('GET', '/api/credentials'); },
    createCredential(data) { return this.request('POST', '/api/credentials', data); },
    updateCredential(id, data) { return this.request('PUT', `/api/credentials/${id}`, data); },
    deleteCredential(id) { return this.request('DELETE', `/api/credentials/${id}`); },
    renameCredential(id, data) { return this.request('POST', `/api/credentials/${id}/rename`, data); },
    revealCredential(id) { return this.request('POST', `/api/credentials/${id}/reveal`); },
    syncFbPages(id) { return this.request('POST', `/api/credentials/${id}/sync-fb-pages`); },

    // Executions
    listExecutions(workflowId = null, limit = 50) {
        const params = new URLSearchParams();
        if (workflowId) params.set('workflow_id', workflowId);
        params.set('limit', limit);
        return this.request('GET', `/api/executions?${params}`);
    },
    getExecution(id) { return this.request('GET', `/api/executions/${id}`); },
    streamExecution(id) {
        return new EventSource(`${this.baseUrl}/api/executions/${id}/stream?token=${encodeURIComponent(this.token)}`);
    },

    // Assets
    generateProfileImage(pageId, data) {
        return this.request('POST', `/api/pages/${pageId}/assets/profile`, data);
    },
    generateCoverPhoto(pageId, data) {
        return this.request('POST', `/api/pages/${pageId}/assets/cover`, data);
    },
    generateBio(pageId, data) {
        return this.request('POST', `/api/pages/${pageId}/assets/bio`, data);
    },

    // Steps
    listSteps(workflowId) { return this.request('GET', `/api/workflows/${workflowId}/steps`); },
    createStep(workflowId, data) { return this.request('POST', `/api/workflows/${workflowId}/steps`, data); },
    updateStep(workflowId, stepId, data) { return this.request('PUT', `/api/workflows/${workflowId}/steps/${stepId}`, data); },
    deleteStep(workflowId, stepId) { return this.request('DELETE', `/api/workflows/${workflowId}/steps/${stepId}`); },
    reorderSteps(workflowId, stepIds) { return this.request('PUT', `/api/workflows/${workflowId}/steps/reorder`, { step_ids: stepIds }); },
    testStep(workflowId, stepId, variables = {}) { return this.request('POST', `/api/workflows/${workflowId}/steps/${stepId}/test`, { variables }); },

    // Datatables
    listDatatables() { return this.request('GET', '/api/datatables'); },
    createDatatable(data) { return this.request('POST', '/api/datatables', data); },
    getDatatable(id, limit = 50, offset = 0) {
        return this.request('GET', `/api/datatables/${id}?limit=${limit}&offset=${offset}`);
    },
    updateDatatable(id, data) { return this.request('PUT', `/api/datatables/${id}`, data); },
    renameDatatable(id, data) { return this.request('POST', `/api/datatables/${id}/rename`, data); },
    deleteDatatable(id) { return this.request('DELETE', `/api/datatables/${id}`); },
    addDatatableRow(tableId, data) { return this.request('POST', `/api/datatables/${tableId}/rows`, data); },
    updateDatatableRow(tableId, rowId, data) { return this.request('PUT', `/api/datatables/${tableId}/rows/${rowId}`, data); },
    deleteDatatableRow(tableId, rowId) { return this.request('DELETE', `/api/datatables/${tableId}/rows/${rowId}`); },
    bulkDeleteDatatableRows(tableId, rowIds) { return this.request('POST', `/api/datatables/${tableId}/rows/bulk-delete`, { row_ids: rowIds }); },
    clearDatatableRows(tableId) { return this.request('DELETE', `/api/datatables/${tableId}/rows`); },

    // Niches
    listNiches() { return this.request('GET', '/api/niches'); },
    createNiche(data) { return this.request('POST', '/api/niches', data); },
    updateNiche(id, data) { return this.request('PUT', `/api/niches/${id}`, data); },
    deleteNiche(id) { return this.request('DELETE', `/api/niches/${id}`); },

    // Ads
    getAdAccount() { return this.request('GET', '/api/ads/account'); },
    getPageVideos(pageId, limit = 10) { return this.request('GET', `/api/ads/pages/${pageId}/videos?limit=${limit}`); },
    listCampaigns(pageId = null) {
        const q = pageId ? `?page_id=${pageId}` : '';
        return this.request('GET', `/api/ads/campaigns${q}`);
    },
    createCampaign(data) { return this.request('POST', '/api/ads/campaigns', data); },
    getCampaign(id) { return this.request('GET', `/api/ads/campaigns/${id}`); },
    updateCampaign(id, data) { return this.request('PUT', `/api/ads/campaigns/${id}`, data); },
    pauseCampaign(id) { return this.request('POST', `/api/ads/campaigns/${id}/pause`); },
    resumeCampaign(id) { return this.request('POST', `/api/ads/campaigns/${id}/resume`); },
    deleteCampaign(id) { return this.request('DELETE', `/api/ads/campaigns/${id}`); },
    syncCampaignInsights(id) { return this.request('POST', `/api/ads/campaigns/${id}/sync-insights`); },
    syncAllInsights() { return this.request('POST', '/api/ads/campaigns/sync-all'); },
    listFbCampaigns() { return this.request('GET', '/api/ads/fb/campaigns'); },
    listFbAdsets(campaignId) { return this.request('GET', `/api/ads/fb/campaigns/${campaignId}/adsets`); },
    listFbAds(campaignId, adsetId) { return this.request('GET', `/api/ads/fb/campaigns/${campaignId}/adsets/${adsetId}/ads`); },
};
