// Loom App — Alpine.js Application

// Format UTC timestamp to Asia/Bangkok timezone
function formatBangkok(utcStr) {
    if (!utcStr) return '—';
    // Append Z if no timezone info so JS parses as UTC
    const d = new Date(utcStr.endsWith('Z') || utcStr.includes('+') ? utcStr : utcStr + 'Z');
    return d.toLocaleString('en-GB', { timeZone: 'Asia/Bangkok', hour12: false });
}

// Format cron schedule string to human-readable times
function formatSchedule(schedule) {
    if (!schedule) return 'Manual only';
    const slots = schedule.split(',').map(c => c.trim()).filter(Boolean).map(cron => {
        const parts = cron.split(' ');
        if (parts.length !== 5) return null;
        let h = parseInt(parts[1], 10);
        const m = parts[0].padStart(2, '0');
        let amPm = 'AM';
        if (h >= 12) { amPm = 'PM'; if (h > 12) h -= 12; }
        if (h === 0) h = 12;
        return `${h}:${m} ${amPm}`;
    }).filter(Boolean);
    return slots.length > 0 ? slots.join(', ') : 'Manual only';
}

document.addEventListener('alpine:init', () => {

    // Global store for navigation and state
    Alpine.store('app', {
        view: 'dashboard',
        selectedPage: null,
        selectedWorkflow: null,
        selectedExecution: null,
        sourceWorkflowId: null,
        selectedDataTable: null,
        toast: null,
        toastType: 'success',

        navigate(view, data = {}) {
            this.view = view;
            Object.assign(this, data);
        },

        showToast(msg, type = 'success') {
            this.toast = msg;
            this.toastType = type;
            setTimeout(() => this.toast = null, 4000);
        },
    });

    // Pages list component
    // Groups stored in localStorage — key per niche/global
    const GROUPS_KEY = 'loom_page_groups';
    function loadGroups() {
        try { return JSON.parse(localStorage.getItem(GROUPS_KEY) || '[]'); } catch(e) { return []; }
    }
    function saveGroups(list) {
        localStorage.setItem(GROUPS_KEY, JSON.stringify(list));
    }

        // IMPORTANT: When using SortableJS with Alpine.js, NEVER call recompute() or 
    // trigger Alpine re-renders immediately after Sortable's onEnd callback.
    // Sortable has already moved the DOM; letting Alpine re-render will cause
    // a race condition where Alpine restores the old DOM order from its internal state.
    // Solution: let Sortable's DOM change stand, update state silently, save to API in background.
    // See: https://github.com/SortableJS/Sortable/issues/XXX (known pattern issue)
Alpine.data('pagesList', () => ({
        pages: [],
        loading: true,
        ungrouped: [],
        groups: [],

        // Create page modal
        showCreateModal: false,
        newPageName: '',

        // Create group modal
        showCreateGroupModal: false,
        newGroupName: '',

        // Move to group modal
        showMoveModal: false,
        movingPage: null,

        // Rename page modal
        showRenamePageModal: false,
        renamingPage: null,
        renamePageId: '',
        renamePageValue: '',
        renameCascade: false,

        // Rename group modal
        showRenameGroupModal: false,
        renamingGroupName: '',
        renameGroupValue: '',

        sortables: [],

        async init() {
            await this.load();
        },

        async load() {
            this.loading = true;
            this.destroySortables();
            try {
                this.pages = await API.listPages();
                this.recompute();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
            await this.$nextTick();
            this.initSortables();
        },

        destroySortables() {
            this.sortables.forEach(s => { try { s.destroy(); } catch(e) {} });
            this.sortables = [];
        },

        initSortables() {
            const self = this;
            // All containers: ungrouped list + each group list
            const containers = document.querySelectorAll('[data-page-list]');
            containers.forEach(el => {
                const s = Sortable.create(el, {
                    group: 'pages',
                    animation: 150,
                    ghostClass: 'opacity-30',
                    handle: '.drag-handle',
                    onEnd(evt) {
                        const pageId = evt.item.getAttribute('data-page-id');
                        const rawDest = evt.to.getAttribute('data-page-list');
                        const destGroup = (rawDest === '') ? null : rawDest;

                        if (!pageId) return;

                        // Update group_name on moved page
                        const page = self.pages.find(p => p.id === pageId);
                        if (page && page.group_name !== destGroup) {
                            page.group_name = destGroup;
                        }

                        const updates = [];
                        const updatesData = [];

                        // Helper: read DOM order and update both self.pages and API
                        function syncContainer(container, groupName) {
                            const ids = Array.from(container.querySelectorAll(':scope > [data-page-id]'))
                                            .map(c => c.getAttribute('data-page-id'));
                            ids.forEach((id, idx) => {
                                const p = self.pages.find(x => x.id === id);
                                if (p) {
                                    p.sort_order = idx;
                                    p.group_name = groupName;
                                }
                                updates.push(API.updatePage(id, { sort_order: idx, group_name: groupName }));
                            });
                        }

                        syncContainer(evt.to, destGroup);
                        if (evt.from !== evt.to) {
                            const srcGroup = evt.from.getAttribute('data-page-list');
                            syncContainer(evt.from, srcGroup === '' ? null : srcGroup);
                        }

                        // Don't reload - manually sync local state to match what we just did
                        // This is instant and avoids race conditions
                        self.pages = self.pages.map(p => {
                            const updated = updatesData.find(u => u.id === p.id);
                            if (updated) {
                                return { ...p, sort_order: updated.sort_order, group_name: updated.group_name };
                            }
                            return p;
                        });
                        // Don't recompute - let Sortable's DOM change stand as-is
                        // self.recompute();

                        // Also save in background (already saved, but this is for confirmation)
                        Promise.all(updates)
                            .then(() => Alpine.store('app').showToast('Saved'))
                            .catch(err => {
                                Alpine.store('app').showToast('Failed: ' + err.message, 'error');
                                self.load();
                            });
                    },
                });
                self.sortables.push(s);
            });
        },

        recompute() {
            // Build group map from server data
            const byGroup = {};
            this.pages.filter(p => p.group_name).forEach(p => {
                if (!byGroup[p.group_name]) byGroup[p.group_name] = [];
                byGroup[p.group_name].push(p);
            });
            // Merge with localStorage group list (preserves empty groups)
            let gList = loadGroups();
            Object.keys(byGroup).forEach(name => {
                if (!gList.find(g => g.name === name)) gList.push({ name });
            });
            saveGroups(gList);
            this.groups = gList.map(g => ({ name: g.name, pages: (byGroup[g.name] || []).slice().sort((a,b) => a.sort_order - b.sort_order) }));
            this.ungrouped = this.pages.filter(p => !p.group_name).slice().sort((a,b) => a.sort_order - b.sort_order);
        },

        slugify(text) {
            return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        },

        // --- Create page ---
        async create() {
            if (!this.newPageName.trim()) return Alpine.store('app').showToast('Page name is required', 'error');
            try {
                await API.createPage({
                    id: this.slugify(this.newPageName),
                    name: this.newPageName.trim(),
                    niche_id: 'general',
                    language: 'English',
                });
                Alpine.store('app').showToast('Page created');
                this.showCreateModal = false;
                this.newPageName = '';
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        // --- Delete / duplicate page ---
        async deletePage(page) {
            if (!confirm(`Delete "${page.name}" and all its workflows? This cannot be undone.`)) return;
            try {
                await API.deletePage(page.id);
                Alpine.store('app').showToast('Page deleted');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async duplicatePage(page) {
            if (!confirm(`Duplicate "${page.name}"?`)) return;
            try {
                await API.clonePage(page.id);
                Alpine.store('app').showToast('Page duplicated');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        openPage(page) {
            Alpine.store('app').navigate('page-detail', { selectedPage: page.id });
        },

        // --- Rename page ---
        openRenamePage(page) {
            this.renamingPage = page;
            this.renamePageId = page.id;
            this.renamePageValue = page.name;
            this.renameCascade = false;
            this.showRenamePageModal = true;
        },

        async saveRenamePage() {
            const newName = this.renamePageValue.trim();
            const newId = this.renamePageId.trim();
            if (!newName && !newId) return;
            try {
                if (newId && newId !== this.renamingPage.id) {
                    await API.renamePage(this.renamingPage.id, {
                        new_id: newId,
                        new_name: newName,
                        cascade: this.renameCascade,
                    });
                } else {
                    await API.updatePage(this.renamingPage.id, { name: newName });
                }
                Alpine.store('app').showToast('Page renamed');
                this.showRenamePageModal = false;
                this.renamingPage = null;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        // --- Create group ---
        createGroup() {
            const name = this.newGroupName.trim();
            if (!name) return Alpine.store('app').showToast('Group name is required', 'error');
            const list = loadGroups();
            if (list.find(g => g.name === name)) return Alpine.store('app').showToast('Group already exists', 'error');
            list.push({ name });
            saveGroups(list);
            this.recompute();
            this.showCreateGroupModal = false;
            this.newGroupName = '';
            Alpine.store('app').showToast(`Group "${name}" created`);
        },

        // --- Rename group ---
        openRenameGroup(groupName) {
            this.renamingGroupName = groupName;
            this.renameGroupValue = groupName;
            this.showRenameGroupModal = true;
        },

        async saveRenameGroup() {
            const newName = this.renameGroupValue.trim();
            const oldName = this.renamingGroupName;
            if (!newName || newName === oldName) { this.showRenameGroupModal = false; return; }
            // Update localStorage
            const list = loadGroups();
            const g = list.find(g => g.name === oldName);
            if (g) g.name = newName;
            saveGroups(list);
            // Update pages on server
            const affected = this.pages.filter(p => p.group_name === oldName);
            try {
                await Promise.all(affected.map(p => API.updatePage(p.id, { group_name: newName })));
                Alpine.store('app').showToast('Group renamed');
                this.showRenameGroupModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        // --- Delete group ---
        async deleteGroup(groupName) {
            if (!confirm(`Remove group "${groupName}"? Pages will become ungrouped.`)) return;
            const list = loadGroups().filter(g => g.name !== groupName);
            saveGroups(list);
            const affected = this.pages.filter(p => p.group_name === groupName);
            try {
                await Promise.all(affected.map(p => API.updatePage(p.id, { group_name: null })));
                Alpine.store('app').showToast('Group removed');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        // --- Move page to group ---
        openMoveToGroup(page) {
            this.movingPage = page;
            this.showMoveModal = true;
        },

        async assignGroup(groupName) {
            const page = this.movingPage;
            this.showMoveModal = false;
            this.movingPage = null;
            if (page.group_name === groupName) return;
            try {
                await API.updatePage(page.id, { group_name: groupName });
                Alpine.store('app').showToast(groupName ? `Moved to "${groupName}"` : 'Removed from group');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },
    }));

    // Page detail component


    // Page detail component
    Alpine.data('pageDetail', () => ({
        page: null,
        workflows: [],
        loading: true,
        showCreateWfModal: false,
        wfName: '',
        wfHour: '9',
        wfMinute: '00',
        wfAmPm: 'AM',

        // Schedule editor
        showScheduleModal: false,
        scheduleWorkflow: null,
        scheduleSlots: [],  // [{hour, minute, amPm}]

        // Rename workflow
        showRenameWfModal: false,
        renameWfOldId: '',
        renameWfNewId: '',
        renameWfNewName: '',

        // Duplicate workflow
        showDuplicateWfModal: false,
        dupWfSourceId: '',
        dupWfNewId: '',
        dupWfNewName: '',
        dupWfPageId: '',
        allPages: [],

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'page-detail') await this.load();
            });
            if (Alpine.store('app').view === 'page-detail') await this.load();
        },

        async load() {
            const pageId = Alpine.store('app').selectedPage;
            if (!pageId) { this.loading = false; return; }
            this.loading = true;
            try {
                this.page = await API.getPage(pageId);
                this.workflows = await API.listWorkflows(pageId);
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
        },

        _slugify(text) {
            return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        },

        _buildCron() {
            let h = parseInt(this.wfHour, 10);
            const m = parseInt(this.wfMinute, 10);
            if (this.wfAmPm === 'PM' && h < 12) h += 12;
            if (this.wfAmPm === 'AM' && h === 12) h = 0;
            return `${m} ${h} * * *`;
        },

        async createWorkflow() {
            if (!this.wfName.trim()) return Alpine.store('app').showToast('Workflow name is required', 'error');
            try {
                const slug = this._slugify(this.wfName);
                await API.createWorkflow({
                    id: slug,
                    page_id: this.page.id,
                    name: this.wfName.trim(),
                    language: 'English',
                    schedule: this._buildCron(),
                    active: true,
                });
                Alpine.store('app').showToast('Workflow created');
                this.showCreateWfModal = false;
                this.wfName = '';
                this.wfHour = '9';
                this.wfMinute = '00';
                this.wfAmPm = 'AM';
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async deleteWorkflow(wf) {
            if (!confirm(`Delete workflow "${wf.name}"?`)) return;
            try {
                await API.deleteWorkflow(wf.id);
                Alpine.store('app').showToast('Workflow deleted');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async toggleWorkflow(wf) {
            try {
                await API.updateWorkflow(wf.id, { active: !wf.active });
                Alpine.store('app').showToast(`Workflow ${wf.active ? 'deactivated' : 'activated'}`);
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        openWorkflow(wf) {
            Alpine.store('app').navigate('workflow-detail', { selectedWorkflow: wf.id });
        },

        openAssets() {
            Alpine.store('app').navigate('page-assets', { selectedPage: this.page.id });
        },

        // --- Rename workflow ---
        openRenameWorkflow(wf) {
            this.renameWfOldId = wf.id;
            this.renameWfNewId = wf.id;
            this.renameWfNewName = wf.name;
            this.showRenameWfModal = true;
        },

        async saveRenameWorkflow() {
            try {
                await API.renameWorkflow(this.renameWfOldId, {
                    new_id: this.renameWfNewId.trim(),
                    new_name: this.renameWfNewName.trim(),
                });
                Alpine.store('app').showToast('Workflow renamed');
                this.showRenameWfModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        // --- Duplicate workflow ---
        async openDuplicateWorkflow(wf) {
            this.dupWfSourceId = wf.id;
            this.dupWfNewId = wf.id + '-copy';
            this.dupWfNewName = wf.name + ' (copy)';
            this.dupWfPageId = this.page.id;
            try {
                this.allPages = await API.listPages();
            } catch (e) { /* keep empty */ }
            this.showDuplicateWfModal = true;
        },

        async saveDuplicateWorkflow() {
            if (!this.dupWfNewId.trim()) return Alpine.store('app').showToast('ID is required', 'error');
            try {
                const targetPageId = this.dupWfPageId !== this.page.id ? this.dupWfPageId : null;
                await API.duplicateWorkflow(this.dupWfSourceId, this.dupWfNewId.trim(), this.dupWfNewName.trim(), targetPageId);
                Alpine.store('app').showToast('Workflow duplicated');
                this.showDuplicateWfModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        // --- Schedule editor ---
        _parseCronToSlots(schedule) {
            if (!schedule) return [];
            return schedule.split(',').map(c => c.trim()).filter(Boolean).map(cron => {
                const parts = cron.split(' ');
                if (parts.length !== 5) return null;
                let h = parseInt(parts[1], 10);
                const m = parts[0].padStart(2, '0');
                let amPm = 'AM';
                if (h >= 12) { amPm = 'PM'; if (h > 12) h -= 12; }
                if (h === 0) h = 12;
                return { hour: String(h), minute: m, amPm };
            }).filter(Boolean);
        },

        _slotsToCron(slots) {
            return slots.map(s => {
                let h = parseInt(s.hour, 10);
                const m = parseInt(s.minute, 10);
                if (s.amPm === 'PM' && h < 12) h += 12;
                if (s.amPm === 'AM' && h === 12) h = 0;
                return `${m} ${h} * * *`;
            }).join(',');
        },

        openScheduleEditor(wf) {
            this.scheduleWorkflow = wf;
            const slots = this._parseCronToSlots(wf.schedule);
            if (slots.length === 0) {
                slots.push({ hour: '9', minute: '00', amPm: 'AM' });
            }
            // Set placeholder slots with same count so x-for renders the right number of rows
            this.scheduleSlots = slots.map(() => ({ hour: '1', minute: '00', amPm: 'AM' }));
            this.showScheduleModal = true;
            // After modal + nested x-for options are rendered, set actual values
            this.$nextTick(() => { this.scheduleSlots = slots; });
        },

        addScheduleSlot() {
            this.scheduleSlots.push({ hour: '9', minute: '00', amPm: 'AM' });
        },

        removeScheduleSlot(idx) {
            this.scheduleSlots.splice(idx, 1);
        },

        async saveSchedule() {
            if (!this.scheduleWorkflow) return;
            const cron = this.scheduleSlots.length > 0 ? this._slotsToCron(this.scheduleSlots) : null;
            try {
                await API.updateWorkflow(this.scheduleWorkflow.id, { schedule: cron || '' });
                Alpine.store('app').showToast('Schedule updated');
                this.showScheduleModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async clearSchedule() {
            if (!this.scheduleWorkflow) return;
            try {
                await API.updateWorkflow(this.scheduleWorkflow.id, { schedule: '' });
                Alpine.store('app').showToast('Schedule cleared');
                this.showScheduleModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        formatScheduleDisplay(schedule) {
            return formatSchedule(schedule);
        },
    }));

    // Workflow detail component
    Alpine.data('workflowDetail', () => ({
        workflow: null,
        steps: [],  // top-level reactive array — avoids deep-proxy issues
        loading: true,
        triggerResult: null,
        triggering: false,
        recentExecs: [],
        recentExecsLoading: true,

        // Inline prompt editor
        expandedStepId: null,
        inlinePrompt: { system_prompt: '', user_prompt: '' },

        // Step builder modal state
        showStepModal: false,
        stepModalMode: 'add', // 'add' or 'edit'
        editingStepId: null,
        stepFormId: '',
        stepFormName: '',
        stepFormType: 'llm',
        stepFormOutputVar: '',
        // Config fields (flat — avoids nested reactivity issues)
        cfgProvider: 'openai',
        cfgModel: 'gpt-4o-mini',
        _modelOptions: {
            openai: [
                { id: 'gpt-4o-mini', label: 'GPT-4o Mini' },
                { id: 'gpt-4o', label: 'GPT-4o' },
                { id: 'gpt-4.1-nano', label: 'GPT-4.1 Nano (fastest)' },
                { id: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
                { id: 'gpt-4.1', label: 'GPT-4.1' },
                { id: 'gpt-5-nano', label: 'GPT-5 Nano' },
                { id: 'gpt-5-mini', label: 'GPT-5 Mini' },
                { id: 'gpt-5', label: 'GPT-5' },
                { id: 'gpt-5.2', label: 'GPT-5.2 (latest)' },
                { id: 'o3-mini', label: 'o3-mini (reasoning)' },
                { id: 'o3', label: 'o3 (reasoning)' },
                { id: 'o4-mini', label: 'o4-mini (reasoning)' },
            ],
            gemini: [
                { id: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite (fastest)' },
                { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
                { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
                { id: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview' },
                { id: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro Preview (latest)' },
            ],
            anthropic: [
                { id: 'claude-haiku-4-5', label: 'Claude Haiku 4.5 (fast)' },
                { id: 'claude-sonnet-4-0', label: 'Claude Sonnet 4' },
                { id: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
                { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
                { id: 'claude-opus-4-0', label: 'Claude Opus 4' },
                { id: 'claude-opus-4-1', label: 'Claude Opus 4.1' },
                { id: 'claude-opus-4-5', label: 'Claude Opus 4.5' },
                { id: 'claude-opus-4-6', label: 'Claude Opus 4.6 (most capable)' },
            ],
        },
        getModelOptions() { return this._modelOptions[this.cfgProvider] || []; },
        _activeConfigType() {
            return this.stepFormType;
        },
        getCredentialOptions() {
            const t = this._activeConfigType();
            if (t === 'llm') {
                // Filter by selected LLM provider
                return this.availableCredentials.filter(c => c.type === this.cfgProvider);
            }
            const typeMap = { fb_post: 'facebook', fb_comment: 'facebook', nova_voice: 'nova_astra', nova_video: 'nova_astra', http_request: null };
            const needed = typeMap[t];
            if (needed === undefined || needed === null) return this.availableCredentials;
            return this.availableCredentials.filter(c => c.type === needed);
        },
        needsCredential() {
            return ['llm', 'fb_post', 'fb_comment', 'nova_voice', 'nova_video', 'http_request'].includes(this._activeConfigType());
        },
        _autoSelectCredential() {
            const opts = this.getCredentialOptions();
            const t = this._activeConfigType();
            const credType = t === 'llm' ? this.cfgProvider
                : { fb_post: 'facebook', fb_comment: 'facebook', nova_voice: 'nova_astra', nova_video: 'nova_astra' }[t];
            if (credType === 'facebook') return; // keep manual for multi-page
            // Clear if current selection is not in the filtered options
            if (this.cfgCredentialId && !opts.find(c => c.id === this.cfgCredentialId)) {
                this.cfgCredentialId = '';
            }
            if (!this.cfgCredentialId && opts.length === 1) {
                this.cfgCredentialId = opts[0].id;
            }
        },
        _populateFormFromConfig(type, config) {
            this._resetFormFields();
            const cfg = config || {};
            if (type === 'llm') {
                this.cfgProvider = cfg.provider || 'openai';
                this.cfgModel = cfg.model || 'gpt-4o-mini';
                this.cfgSystemPrompt = cfg.system_prompt || '';
                this.cfgUserPrompt = cfg.user_prompt || '';
                this.cfgLookupTableId = cfg.lookup_table_id || '';
                this.cfgLookupColumns = cfg.lookup_columns || '';
                this.cfgLookupLimit = cfg.lookup_limit || '';
                this.cfgThinkingLevel = cfg.thinking_level || 'minimal';
            } else if (type === 'datatable_insert') {
                this.cfgTableId = cfg.table_id || '';
                this.cfgColumnsJson = cfg.columns_json ? (typeof cfg.columns_json === 'string' ? cfg.columns_json : JSON.stringify(cfg.columns_json, null, 2)) : '';
            } else if (type === 'datatable_update') {
                this.cfgTableId = cfg.table_id || '';
                this.cfgRowId = cfg.row_id || '';
                this.cfgColumnsJson = cfg.columns_json ? (typeof cfg.columns_json === 'string' ? cfg.columns_json : JSON.stringify(cfg.columns_json, null, 2)) : '';
            } else if (type === 'nova_voice') {
                this.cfgInputText = cfg.input_text || '';
                this.cfgVoice = cfg.voice || 'Algieba';
                this.cfgStyle = cfg.style || 'auto';
            } else if (type === 'nova_video') {
                this.cfgAudioUrl = cfg.audio_url || '';
                this.cfgVideoScript = cfg.video_script || '';
                this.cfgImageStyle = cfg.image_style || 'photorealistic';
                this.cfgImageModel = cfg.image_model || 'flux';
            } else if (type === 'fb_post') {
                this.cfgMediaType = cfg.media_type || 'photo';
                this.cfgMediaUrl = cfg.media_url || '';
                this.cfgMessage = cfg.message || '';
            } else if (type === 'fb_comment') {
                this.cfgPostId = cfg.post_id || '';
                this.cfgMessage = cfg.message || '';
            } else if (type === 'datatable_read') {
                this.cfgTableId = cfg.table_id || '';
                this.cfgFilterColumn = cfg.filter_column || '';
                this.cfgFilterMode = cfg.filter_mode || 'empty';
                this.cfgFilterValue = cfg.filter_value || '';
                this.cfgReadLimit = cfg.limit || 1;
            } else if (type === 'gen_image') {
                this.cfgImagePrompt = cfg.prompt || '';
            } else if (type === 'http_download') {
                this.cfgDownloadUrl = cfg.url || '';
            } else if (type === 'http_request') {
                this.cfgHttpMethod = cfg.method || 'GET';
                this.cfgHttpUrl = cfg.url || '';
                this.cfgHttpHeaders = cfg.headers || '';
                this.cfgHttpBody = cfg.body || '';
                this.cfgHttpBodyType = cfg.body_type || 'json';
            } else if (type === 'code') {
                this.cfgCode = cfg.code || '';
            } else if (type === 'loop') {
                this.cfgLoopSourceVar = cfg.source_var || '';
                this.cfgLoopItemVar = cfg.item_var || 'item';
                this.cfgLoopSteps = (cfg.substeps || []).map(s => ({
                    name: s.name || '',
                    type: s.type || 'llm',
                    config: s.config || {},
                    output_var: s.output_var || '',
                    _configJson: JSON.stringify(s.config || {}, null, 2),
                }));
            }
            this.cfgCredentialId = cfg.credential_id || '';
            if (this.cfgTableId && ['datatable_insert', 'datatable_update', 'datatable_read'].includes(type)) {
                this.onTableSelected();
            }
        },
        cfgColumnValues: {},
        selectedTableColumns: [],
        async onTableSelected() {
            if (!this.cfgTableId) { this.selectedTableColumns = []; this.cfgColumnValues = {}; return; }
            try {
                const dt = await API.getDatatable(this.cfgTableId, 1, 0);
                this.selectedTableColumns = dt.columns || [];
                const existing = {};
                try { Object.assign(existing, typeof this.cfgColumnsJson === 'string' ? JSON.parse(this.cfgColumnsJson) : this.cfgColumnsJson || {}); } catch {}
                this.cfgColumnValues = {};
                this.selectedTableColumns.forEach(col => this.cfgColumnValues[col] = existing[col] || '');
            } catch { this.selectedTableColumns = []; this.cfgColumnValues = {}; }
        },
        syncColumnsJson() {
            const data = {};
            this.selectedTableColumns.forEach(col => { if (this.cfgColumnValues[col]) data[col] = this.cfgColumnValues[col]; });
            this.cfgColumnsJson = JSON.stringify(data);
        },
        cfgSystemPrompt: '',
        cfgUserPrompt: '',
        cfgLookupTableId: '',
        cfgLookupColumns: '',
        cfgLookupLimit: '',
        cfgThinkingLevel: 'minimal',
        availableDatatables: [],
        cfgCredentialId: '',
        availableCredentials: [],
        // Datatable fields
        cfgTableId: '',
        cfgColumnsJson: '',
        cfgRowId: '',
        // Nova fields
        cfgInputText: '',
        cfgVoice: 'Algieba',
        cfgStyle: 'auto',
        cfgAudioUrl: '',
        cfgVideoScript: '',
        cfgImageStyle: 'photorealistic',
        cfgImageModel: 'flux',
        // FB fields
        cfgMediaType: 'photo',
        cfgMediaUrl: '',
        cfgMessage: '',
        cfgPostId: '',
        // Gen Image
        cfgImagePrompt: '',
        // Datatable Read
        cfgFilterColumn: '',
        cfgFilterMode: 'empty',
        cfgFilterValue: '',
        cfgReadLimit: 1,
        // HTTP Download
        cfgDownloadUrl: '',
        // HTTP Request
        cfgHttpMethod: 'GET',
        cfgHttpUrl: '',
        cfgHttpHeaders: '',
        cfgHttpBody: '',
        cfgHttpBodyType: 'json',
        // Code
        cfgCode: '',
        // Loop
        cfgLoopSourceVar: '',
        cfgLoopItemVar: 'item',
        cfgLoopSteps: [], // [{name, type, config, output_var}]
        _loopSubstepTypes: [
            { value: 'llm', label: 'LLM' },
            { value: 'code', label: 'Code' },
            { value: 'http_request', label: 'HTTP Request' },
            { value: 'fb_post', label: 'FB: Post' },
            { value: 'fb_comment', label: 'FB: Comment' },
            { value: 'datatable_insert', label: 'Datatable: Insert' },
            { value: 'datatable_update', label: 'Datatable: Update' },
            { value: 'datatable_read', label: 'Datatable: Read' },
            { value: 'http_download', label: 'HTTP: Download' },
            { value: 'gen_image', label: 'Gen Image' },
            { value: 'nova_voice', label: 'Nova: Voice' },
            { value: 'nova_video', label: 'Nova: Video' },
        ],
        addLoopSubstep() {
            this.cfgLoopSteps.push({ name: '', type: 'llm', config: {}, output_var: '' });
        },
        removeLoopSubstep(idx) {
            this.cfgLoopSteps.splice(idx, 1);
        },
        updateLoopSubstepConfig(idx) {
            // Parse JSON config if it's a string
            const step = this.cfgLoopSteps[idx];
            if (typeof step._configJson === 'string') {
                try { step.config = JSON.parse(step._configJson); } catch {}
            }
        },
        // Test step
        testingStepId: null,
        testOutput: null,
        testError: null,
        testLoading: false,
        showTestOutput: false,

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'workflow-detail') await this.load();
            });
            if (Alpine.store('app').view === 'workflow-detail') await this.load();
        },

        async load() {
            const wfId = Alpine.store('app').selectedWorkflow;
            if (!wfId) { this.loading = false; return; }
            this.loading = true;
            try {
                const data = await API.getWorkflow(wfId);
                this.workflow = data;
                this.steps = data.steps || [];
            } catch (e) {
                try { Alpine.store('app').showToast(e.message || String(e), 'error'); } catch {}
            } finally {
                this.loading = false;
            }
            this.loadRecentExecs();
        },

        async loadRecentExecs() {
            if (!this.workflow?.id) return;
            this.recentExecsLoading = true;
            try {
                this.recentExecs = await API.listExecutions(this.workflow.id, 10);
            } catch { this.recentExecs = []; }
            this.recentExecsLoading = false;
        },

        // --- Step type helpers ---
        stepTypeIcon(type) {
            const icons = { llm: '\u{1F9E0}', datatable_insert: '\u{1F4E5}', datatable_update: '\u{1F4DD}', datatable_read: '\u{1F50D}', nova_voice: '\u{1F399}\uFE0F', nova_video: '\u{1F3AC}', fb_post: '\u{1F4D8}', fb_comment: '\u{1F4AC}', gen_image: '\u{1F5BC}\uFE0F', http_download: '\u{2B07}\uFE0F', http_request: '\u{1F310}', code: '\u{1F4BB}', loop: '\u{1F501}' };
            return icons[type] || '\u{2699}\uFE0F';
        },

        stepTypeColor(type) {
            const colors = { llm: 'bg-purple-500/20 text-purple-300', datatable_insert: 'bg-green-500/20 text-green-300', datatable_update: 'bg-green-500/20 text-green-300', datatable_read: 'bg-emerald-500/20 text-emerald-300', nova_voice: 'bg-orange-500/20 text-orange-300', nova_video: 'bg-orange-500/20 text-orange-300', fb_post: 'bg-blue-500/20 text-blue-300', fb_comment: 'bg-blue-500/20 text-blue-300', gen_image: 'bg-pink-500/20 text-pink-300', http_download: 'bg-cyan-500/20 text-cyan-300', http_request: 'bg-teal-500/20 text-teal-300', code: 'bg-yellow-500/20 text-yellow-300', loop: 'bg-indigo-500/20 text-indigo-300' };
            return colors[type] || 'bg-gray-500/20 text-gray-300';
        },

        // --- Inline prompt editor (LLM quick-edit) ---
        toggleInlinePrompt(step) {
            if (this.expandedStepId === step.id) {
                this.expandedStepId = null;
                return;
            }
            this.expandedStepId = step.id;
            const cfg = step.config || {};
            this.inlinePrompt = {
                system_prompt: cfg.system_prompt || '',
                user_prompt: cfg.user_prompt || '',
            };
        },

        async saveInlinePrompt(step) {
            try {
                await API.updatePrompt(this.workflow.id, step.id, this.inlinePrompt);
                // Update local state directly to avoid full reload
                const idx = this.steps.findIndex(s => s.id === step.id);
                if (idx !== -1) {
                    this.steps[idx] = { ...this.steps[idx], config: { ...this.steps[idx].config, system_prompt: this.inlinePrompt.system_prompt, user_prompt: this.inlinePrompt.user_prompt } };
                }
                Alpine.store('app').showToast('Prompt saved');
                this.expandedStepId = null;
            } catch (e) {
                Alpine.store('app').showToast(e.message || String(e), 'error');
            }
        },

        // --- Step modal CRUD ---
        _resetFormFields() {
            this.cfgProvider = 'openai';
            this.cfgModel = 'gpt-4o-mini';
            this.cfgSystemPrompt = '';
            this.cfgUserPrompt = '';
            this.cfgLookupTableId = '';
            this.cfgLookupColumns = '';
            this.cfgLookupLimit = '';
            this.cfgThinkingLevel = 'minimal';
            this.cfgCredentialId = '';
            this.cfgTableId = '';
            this.cfgColumnsJson = '';
            this.cfgRowId = '';
            this.cfgInputText = '';
            this.cfgVoice = 'Algieba';
            this.cfgStyle = 'auto';
            this.cfgAudioUrl = '';
            this.cfgVideoScript = '';
            this.cfgImageStyle = 'photorealistic';
            this.cfgImageModel = 'flux';
            this.cfgMediaType = 'photo';
            this.cfgMediaUrl = '';
            this.cfgMessage = '';
            this.cfgPostId = '';
            this.cfgImagePrompt = '';
            this.cfgFilterColumn = '';
            this.cfgFilterMode = 'empty';
            this.cfgFilterValue = '';
            this.cfgReadLimit = 1;
            this.cfgDownloadUrl = '';
            this.cfgHttpMethod = 'GET';
            this.cfgHttpUrl = '';
            this.cfgHttpHeaders = '';
            this.cfgHttpBody = '';
            this.cfgHttpBodyType = 'json';
            this.cfgCode = '';
            this.cfgLoopSourceVar = '';
            this.cfgLoopItemVar = 'item';
            this.cfgLoopSteps = [];
            this.cfgRetryOnError = false;
            this.cfgColumnValues = {};
            this.selectedTableColumns = [];
        },

        async openAddStep() {
            this.stepModalMode = 'add';
            this.editingStepId = null;
            this.stepFormId = '';
            this.stepFormName = '';
            this.stepFormType = 'llm';
            this.stepFormOutputVar = '';
            this._resetFormFields();
            try { this.availableDatatables = await API.listDatatables(); } catch { this.availableDatatables = []; }
            try { this.availableCredentials = await API.listCredentials(); } catch { this.availableCredentials = []; }
            this._autoSelectCredential();
            this.$nextTick(() => { this.showStepModal = true; });
        },

        async openEditStep(step) {
            this.stepModalMode = 'edit';
            this.editingStepId = step.id;
            this.stepFormId = step.id;
            this.stepFormName = step.name;
            this.stepFormType = step.type;
            this.stepFormOutputVar = step.output_var || '';
            this._resetFormFields();

            // Load async data FIRST so dropdown options are available before setting values
            try { this.availableDatatables = await API.listDatatables(); } catch { this.availableDatatables = []; }
            try { this.availableCredentials = await API.listCredentials(); } catch { this.availableCredentials = []; }

            const cfg = step.config || {};
            // LLM — infer provider from model for legacy configs, validate model belongs to provider
            if (cfg.provider) {
                this.cfgProvider = cfg.provider;
            } else {
                const m = cfg.model || '';
                this.cfgProvider = m.startsWith('gemini') ? 'gemini' : m.startsWith('claude') ? 'anthropic' : 'openai';
            }
            const providerModels = this._modelOptions[this.cfgProvider] || [];
            const savedModel = cfg.model || 'gpt-4o-mini';
            this.cfgModel = providerModels.find(m => m.id === savedModel) ? savedModel : (providerModels[0]?.id || savedModel);
            this.cfgSystemPrompt = cfg.system_prompt || '';
            this.cfgUserPrompt = cfg.user_prompt || '';
            this.cfgLookupTableId = cfg.lookup_table_id || '';
            this.cfgLookupColumns = cfg.lookup_columns || '';
            this.cfgLookupLimit = cfg.lookup_limit || '';
            this.cfgThinkingLevel = cfg.thinking_level || 'minimal';
            // Datatable
            this.cfgTableId = cfg.table_id || '';
            this.cfgColumnsJson = cfg.columns_json ? (typeof cfg.columns_json === 'string' ? cfg.columns_json : JSON.stringify(cfg.columns_json, null, 2)) : '';
            this.cfgRowId = cfg.row_id || '';
            // Nova
            this.cfgInputText = cfg.input_text || '';
            this.cfgVoice = cfg.voice || 'Algieba';
            this.cfgStyle = cfg.style || 'auto';
            this.cfgAudioUrl = cfg.audio_url || '';
            this.cfgVideoScript = cfg.video_script || '';
            this.cfgImageStyle = cfg.image_style || 'photorealistic';
            this.cfgImageModel = cfg.image_model || 'flux';
            // FB
            this.cfgMediaType = cfg.media_type || 'photo';
            this.cfgMediaUrl = cfg.media_url || '';
            this.cfgMessage = cfg.message || '';
            this.cfgPostId = cfg.post_id || '';
            // Gen Image
            this.cfgImagePrompt = cfg.prompt || '';
            // Datatable Read
            this.cfgFilterColumn = cfg.filter_column || '';
            this.cfgFilterMode = cfg.filter_mode || 'empty';
            this.cfgFilterValue = cfg.filter_value || '';
            this.cfgReadLimit = cfg.limit || 1;
            // HTTP Download
            this.cfgDownloadUrl = cfg.url || '';
            // HTTP Request
            this.cfgHttpMethod = cfg.method || 'GET';
            this.cfgHttpUrl = cfg.url || '';
            this.cfgHttpHeaders = cfg.headers || '';
            this.cfgHttpBody = cfg.body || '';
            this.cfgHttpBodyType = cfg.body_type || 'json';
            // Code
            this.cfgCode = cfg.code || '';
            // Loop
            this.cfgLoopSourceVar = cfg.source_var || '';
            this.cfgLoopItemVar = cfg.item_var || 'item';
            this.cfgLoopSteps = (cfg.substeps || []).map(s => ({
                name: s.name || '',
                type: s.type || 'llm',
                config: s.config || {},
                output_var: s.output_var || '',
                _configJson: JSON.stringify(s.config || {}, null, 2),
            }));
            // Retry on error
            this.cfgRetryOnError = !!cfg.retry_on_error;
            // Credential — set AFTER options are loaded
            this.cfgCredentialId = cfg.credential_id || '';
            if (!this.cfgCredentialId) this._autoSelectCredential();
            if (this.cfgTableId) await this.onTableSelected();
            // Wait for Alpine to render options, then show modal
            this.$nextTick(() => { this.showStepModal = true; });
        },

        _buildConfig() {
            const t = this.stepFormType;
            let cfg = {};
            if (t === 'llm') {
                cfg = { provider: this.cfgProvider, model: this.cfgModel, system_prompt: this.cfgSystemPrompt, user_prompt: this.cfgUserPrompt };
                if (this.cfgLookupTableId) {
                    cfg.lookup_table_id = this.cfgLookupTableId;
                    if (this.cfgLookupColumns.trim()) cfg.lookup_columns = this.cfgLookupColumns.trim();
                    if (this.cfgLookupLimit && parseInt(this.cfgLookupLimit) > 0) cfg.lookup_limit = parseInt(this.cfgLookupLimit);
                }
                if (this.cfgProvider === 'gemini' && this.cfgModel.startsWith('gemini-3')) {
                    cfg.thinking_level = this.cfgThinkingLevel;
                }
            } else if (t === 'datatable_insert') {
                this.syncColumnsJson();
                cfg = { table_id: this.cfgTableId, columns_json: this.cfgColumnsJson };
            } else if (t === 'datatable_update') {
                this.syncColumnsJson();
                cfg = { table_id: this.cfgTableId, row_id: this.cfgRowId, columns_json: this.cfgColumnsJson };
            }
            else if (t === 'nova_voice') { cfg = { input_text: this.cfgInputText, voice: this.cfgVoice, style: this.cfgStyle }; }
            else if (t === 'nova_video') { cfg = { audio_url: this.cfgAudioUrl, video_script: this.cfgVideoScript, image_style: this.cfgImageStyle, image_model: this.cfgImageModel }; }
            else if (t === 'fb_post') { cfg = { media_type: this.cfgMediaType, media_url: this.cfgMediaUrl, message: this.cfgMessage }; }
            else if (t === 'fb_comment') { cfg = { post_id: this.cfgPostId, message: this.cfgMessage }; }
            else if (t === 'datatable_read') {
                cfg = { table_id: this.cfgTableId, filter_column: this.cfgFilterColumn, filter_mode: this.cfgFilterMode, limit: parseInt(this.cfgReadLimit) || 1 };
                if (['equals', 'not_equals'].includes(this.cfgFilterMode)) cfg.filter_value = this.cfgFilterValue;
            }
            else if (t === 'gen_image') { cfg = { prompt: this.cfgImagePrompt }; }
            else if (t === 'http_download') { cfg = { url: this.cfgDownloadUrl }; }
            else if (t === 'http_request') { cfg = { method: this.cfgHttpMethod, url: this.cfgHttpUrl, headers: this.cfgHttpHeaders, body: this.cfgHttpBody, body_type: this.cfgHttpBodyType }; }
            else if (t === 'code') { cfg = { code: this.cfgCode }; }
            else if (t === 'loop') {
                cfg = {
                    source_var: this.cfgLoopSourceVar,
                    item_var: this.cfgLoopItemVar || 'item',
                    substeps: this.cfgLoopSteps.map(s => {
                        let config = s.config;
                        if (typeof s._configJson === 'string' && s._configJson.trim()) {
                            try { config = JSON.parse(s._configJson); } catch {}
                        }
                        return { name: s.name, type: s.type, config, output_var: s.output_var };
                    }),
                };
            }
            if (this.cfgCredentialId) cfg.credential_id = this.cfgCredentialId;
            if (this.cfgRetryOnError) cfg.retry_on_error = true;
            return cfg;
        },

        _slugify(text) {
            return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        },

        async saveStep() {
            if (!this.stepFormName) return Alpine.store('app').showToast('Step name is required', 'error');

            const config = this._buildConfig();
            try {
                if (this.stepModalMode === 'add') {
                    const stepSlug = this._slugify(this.stepFormName);
                    const stepId = this.workflow.id + '-' + stepSlug;
                    const newStep = await API.createStep(this.workflow.id, {
                        id: stepId,
                        name: this.stepFormName,
                        type: this.stepFormType,
                        sort_order: this.steps.length,
                        config,
                        output_var: this.stepFormName,
                    });
                    this.steps.push(newStep);
                    Alpine.store('app').showToast('Step added');
                } else {
                    const updated = await API.updateStep(this.workflow.id, this.editingStepId, {
                        name: this.stepFormName,
                        config,
                        output_var: this.stepFormName,
                    });
                    const idx = this.steps.findIndex(s => s.id === this.editingStepId);
                    if (idx !== -1) this.steps[idx] = updated;
                    Alpine.store('app').showToast('Step updated');
                }
                this.showStepModal = false;
            } catch (e) {
                Alpine.store('app').showToast(e.message || String(e), 'error');
            }
        },

        async testStep(step) {
            this.testingStepId = step.id;
            this.testOutput = null;
            this.testError = null;
            this.testLoading = true;
            this.showTestOutput = true;
            try {
                const result = await API.testStep(this.workflow.id, step.id, {});
                if (result.status === 'success') {
                    this.testOutput = result.output;
                    // Try to parse as JSON for pretty display
                    try { this.testOutput = JSON.parse(result.output); } catch {}
                } else {
                    this.testError = result.error;
                }
            } catch (e) {
                this.testError = e.message;
            }
            this.testLoading = false;
        },

        getOutputKeys(output) {
            if (output && typeof output === 'object' && !Array.isArray(output)) {
                return Object.keys(output);
            }
            return [];
        },

        insertVariable(stepName, key) {
            const varText = key ? `{{${stepName}.${key}}}` : `{{${stepName}}}`;
            navigator.clipboard.writeText(varText).then(() => {
                Alpine.store('app').showToast(`Copied: ${varText}`);
            });
        },

        async removeStep(step) {
            if (!confirm(`Delete step "${step.name}"?`)) return;
            try {
                await API.deleteStep(this.workflow.id, step.id);
                this.steps = this.steps.filter(s => s.id !== step.id);
                Alpine.store('app').showToast('Step deleted');
            } catch (e) {
                Alpine.store('app').showToast(e.message || String(e), 'error');
            }
        },

        async moveStep(fromIdx, toIdx) {
            const arr = [...this.steps];
            const [moved] = arr.splice(fromIdx, 1);
            arr.splice(toIdx, 0, moved);
            this.steps = arr;
            try {
                await API.reorderSteps(this.workflow.id, arr.map(s => s.id));
            } catch (e) {
                Alpine.store('app').showToast(e.message || String(e), 'error');
                await this.load(); // revert on error
            }
        },

        // --- Trigger ---
        async trigger() {
            this.triggering = true;
            this.triggerResult = null;
            try {
                const result = await API.triggerWorkflow(this.workflow.id);
                this.triggerResult = result;
                Alpine.store('app').showToast('Workflow triggered');
                // Refresh recent executions after a short delay to let the execution record be created
                setTimeout(() => this.loadRecentExecs(), 500);
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.triggering = false;
        },

        async runUntilStep(step) {
            this.triggering = true;
            this.triggerResult = null;
            try {
                const result = await API.triggerUntilStep(this.workflow.id, step.id);
                this.triggerResult = result;
                Alpine.store('app').showToast(`Running up to "${step.name}"...`);
                Alpine.store('app').navigate('execution-detail', { selectedExecution: result.execution_id, sourceWorkflowId: this.workflow.id });
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.triggering = false;
        },

        viewExecution(execId) {
            Alpine.store('app').navigate('execution-detail', { selectedExecution: execId, sourceWorkflowId: this.workflow.id });
        },
    }));

    // Schedules overview component
    Alpine.data('schedulesView', () => ({
        pages: [],
        workflows: [],
        loading: true,
        showInactive: false,
        showScheduleModal: false,
        scheduleWorkflow: null,
        scheduleSlots: [],
        _sortables: [],

        async init() {
            this.$watch('$store.app.view', (v) => { if (v === 'schedules') this.load(); });
            if (this.$store.app.view === 'schedules') await this.load();
        },

        async load() {
            this.loading = true;
            this._destroySortables();
            try {
                const [pages, workflows] = await Promise.all([
                    API.listPages(),
                    API.listWorkflows(),
                ]);
                this.pages = pages;
                this.workflows = workflows;
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
            await this.$nextTick();
            this._initSortables();
        },

        _destroySortables() {
            this._sortables.forEach(s => { try { s.destroy(); } catch(e) {} });
            this._sortables = [];
        },

        _initSortables() {
            const self = this;

            // Page-level sortable
            const pagesContainer = this.$el.querySelector('[data-schedule-pages]');
            if (pagesContainer) {
                this._sortables.push(Sortable.create(pagesContainer, {
                    animation: 150,
                    ghostClass: 'opacity-30',
                    handle: '.page-drag-handle',
                    onEnd(evt) {
                        const ids = Array.from(pagesContainer.querySelectorAll(':scope > [data-page-id]'))
                            .map(el => el.getAttribute('data-page-id'));
                        const updates = [];
                        ids.forEach((id, idx) => {
                            const p = self.pages.find(x => x.id === id);
                            if (p) p.sort_order = idx;
                            updates.push(API.updatePage(id, { sort_order: idx }));
                        });
                        Promise.all(updates).catch(e => Alpine.store('app').showToast(e.message, 'error'));
                    },
                }));
            }

            // Workflow-level sortables (one per page)
            const wfContainers = this.$el.querySelectorAll('[data-schedule-workflows]');
            wfContainers.forEach(el => {
                this._sortables.push(Sortable.create(el, {
                    animation: 150,
                    ghostClass: 'opacity-30',
                    handle: '.wf-drag-handle',
                    group: 'schedule-workflows',
                    onEnd(evt) {
                        // Sync sort_order for the destination container
                        const destPageId = evt.to.getAttribute('data-page-id');
                        const ids = Array.from(evt.to.querySelectorAll(':scope > [data-wf-id]'))
                            .map(el => el.getAttribute('data-wf-id'));
                        const updates = [];
                        ids.forEach((id, idx) => {
                            const w = self.workflows.find(x => x.id === id);
                            if (w) {
                                w.sort_order = idx;
                                w.page_id = destPageId;
                            }
                            updates.push(API.updateWorkflow(id, { sort_order: idx }));
                        });
                        // If moved between pages, also sync source
                        if (evt.from !== evt.to) {
                            const srcIds = Array.from(evt.from.querySelectorAll(':scope > [data-wf-id]'))
                                .map(el => el.getAttribute('data-wf-id'));
                            srcIds.forEach((id, idx) => {
                                const w = self.workflows.find(x => x.id === id);
                                if (w) w.sort_order = idx;
                                updates.push(API.updateWorkflow(id, { sort_order: idx }));
                            });
                        }
                        Promise.all(updates).catch(e => Alpine.store('app').showToast(e.message, 'error'));
                    },
                }));
            });
        },

        get filteredPages() {
            return this.pages.map(pg => {
                const wfs = this.workflows
                    .filter(w => w.page_id === pg.id)
                    .filter(w => this.showInactive || w.active)
                    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
                return { ...pg, workflows: wfs };
            }).filter(pg => pg.workflows.length > 0 || this.showInactive);
        },

        _parseCronToSlots(schedule) {
            if (!schedule) return [];
            return schedule.split(',').map(c => c.trim()).filter(Boolean).map(cron => {
                const parts = cron.split(' ');
                if (parts.length !== 5) return null;
                let h = parseInt(parts[1], 10);
                const m = parts[0].padStart(2, '0');
                let amPm = 'AM';
                if (h >= 12) { amPm = 'PM'; if (h > 12) h -= 12; }
                if (h === 0) h = 12;
                return { hour: String(h), minute: m, amPm };
            }).filter(Boolean);
        },

        _slotsToCron(slots) {
            return slots.map(s => {
                let h = parseInt(s.hour, 10);
                const m = parseInt(s.minute, 10);
                if (s.amPm === 'PM' && h < 12) h += 12;
                if (s.amPm === 'AM' && h === 12) h = 0;
                return `${m} ${h} * * *`;
            }).join(',');
        },

        openScheduleModal(wf) {
            this.scheduleWorkflow = wf;
            const slots = this._parseCronToSlots(wf.schedule);
            if (slots.length === 0) slots.push({ hour: '9', minute: '00', amPm: 'AM' });
            this.scheduleSlots = slots.map(() => ({ hour: '1', minute: '00', amPm: 'AM' }));
            this.showScheduleModal = true;
            this.$nextTick(() => { this.scheduleSlots = slots; });
        },

        addScheduleSlot() {
            this.scheduleSlots.push({ hour: '9', minute: '00', amPm: 'AM' });
        },

        removeScheduleSlot(idx) {
            this.scheduleSlots.splice(idx, 1);
        },

        async saveSchedule() {
            if (!this.scheduleWorkflow) return;
            const cron = this.scheduleSlots.length > 0 ? this._slotsToCron(this.scheduleSlots) : null;
            try {
                await API.updateWorkflow(this.scheduleWorkflow.id, { schedule: cron || '' });
                Alpine.store('app').showToast('Schedule updated');
                this.showScheduleModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async clearSchedule() {
            if (!this.scheduleWorkflow) return;
            try {
                await API.updateWorkflow(this.scheduleWorkflow.id, { schedule: '' });
                Alpine.store('app').showToast('Schedule cleared');
                this.showScheduleModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async toggleActive(wf) {
            try {
                await API.updateWorkflow(wf.id, { active: !wf.active });
                wf.active = !wf.active;
                Alpine.store('app').showToast(wf.active ? 'Workflow activated' : 'Workflow deactivated');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

    }));

    // Execution detail component
    Alpine.data('executionDetail', () => ({
        execution: null,
        loading: true,
        _eventSource: null,
        _liveStepOutputs: [],

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'execution-detail') {
                    await this.load();
                } else {
                    this._closeSSE();
                }
            });
            if (Alpine.store('app').view === 'execution-detail') await this.load();
        },

        destroy() {
            this._closeSSE();
        },

        _closeSSE() {
            if (this._eventSource) {
                this._eventSource.close();
                this._eventSource = null;
            }
        },

        async load() {
            const execId = Alpine.store('app').selectedExecution;
            if (!execId) { this.loading = false; return; }
            this.loading = true;
            this._closeSSE();
            this._liveStepOutputs = [];
            try {
                this.execution = await API.getExecution(execId);
            } catch (e) {
                // Execution might not be in DB yet if just triggered — start SSE to wait
                this.execution = {
                    id: execId,
                    status: 'running',
                    step_outputs: [],
                    error_message: null,
                    started_at: new Date().toISOString(),
                    finished_at: null,
                    trigger_type: 'manual',
                    duration_ms: null,
                    variables: {},
                };
            }
            this.loading = false;

            // If execution is still running, connect SSE for live updates
            if (this.execution?.status === 'running') {
                this._connectSSE(execId);
            }
        },

        _connectSSE(execId) {
            this._closeSSE();
            const es = API.streamExecution(execId);
            this._eventSource = es;

            es.addEventListener('execution_started', (e) => {
                const data = JSON.parse(e.data);
                if (this.execution) {
                    this.execution = { ...this.execution, status: 'running' };
                }
            });

            es.addEventListener('step_started', (e) => {
                const data = JSON.parse(e.data);
                const newOutput = {
                    id: data.step_id + '-live',
                    step_id: data.step_id,
                    step_name: data.step_name,
                    step_type: data.step_type,
                    status: 'running',
                    output: null,
                    error_message: null,
                    duration_ms: null,
                    started_at: new Date().toISOString(),
                    finished_at: null,
                };
                this._liveStepOutputs = [...this._liveStepOutputs, newOutput];
                if (this.execution) {
                    this.execution = { ...this.execution, step_outputs: [...this._liveStepOutputs] };
                }
            });

            es.addEventListener('step_completed', (e) => {
                const data = JSON.parse(e.data);
                this._liveStepOutputs = this._liveStepOutputs.map(o =>
                    o.step_id === data.step_id ? {
                        ...o,
                        status: 'success',
                        output: data.output_preview || null,
                        duration_ms: data.duration_ms,
                        finished_at: new Date().toISOString(),
                    } : o
                );
                if (this.execution) {
                    this.execution = { ...this.execution, step_outputs: [...this._liveStepOutputs] };
                }
            });

            es.addEventListener('step_failed', (e) => {
                const data = JSON.parse(e.data);
                this._liveStepOutputs = this._liveStepOutputs.map(o =>
                    o.step_id === data.step_id ? {
                        ...o,
                        status: 'failed',
                        error_message: data.error,
                        duration_ms: data.duration_ms,
                        finished_at: new Date().toISOString(),
                    } : o
                );
                if (this.execution) {
                    this.execution = { ...this.execution, step_outputs: [...this._liveStepOutputs] };
                }
            });

            es.addEventListener('execution_completed', async (e) => {
                this._closeSSE();
                // Fetch final state from API for complete data
                try {
                    this.execution = await API.getExecution(execId);
                } catch {}
            });

            es.addEventListener('execution_failed', async (e) => {
                const data = JSON.parse(e.data);
                this._closeSSE();
                // Fetch final state from API for complete data
                try {
                    this.execution = await API.getExecution(execId);
                } catch {
                    if (this.execution) {
                        this.execution = { ...this.execution, status: 'failed', error_message: data.error };
                    }
                }
            });

            es.onerror = () => {
                // SSE connection lost — try fetching final state
                this._closeSSE();
                setTimeout(async () => {
                    try {
                        this.execution = await API.getExecution(execId);
                    } catch {}
                }, 1000);
            };
        },

        statusColor(status) {
            const colors = { success: 'text-green-600', failed: 'text-red-600', running: 'text-yellow-600', pending: 'text-gray-400' };
            return colors[status] || 'text-gray-500';
        },

        statusIcon(status) {
            const icons = { success: '\u2705', failed: '\u274C', running: '\u{1F504}', pending: '\u23F3' };
            return icons[status] || '\u2754';
        },
    }));

    // Executions list component
    Alpine.data('executionsList', () => ({
        executions: [],
        loading: true,
        filterWorkflow: '',

        async init() {
            await this.load();
        },

        async load() {
            this.loading = true;
            try {
                this.executions = await API.listExecutions(this.filterWorkflow || null);
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
        },

        viewExecution(id) {
            Alpine.store('app').navigate('execution-detail', { selectedExecution: id });
        },

        statusColor(status) {
            const colors = { success: 'text-green-600', failed: 'text-red-600', running: 'text-yellow-600' };
            return colors[status] || 'text-gray-500';
        },
    }));

    // Datatables list component
    Alpine.data('datatablesList', () => ({
        datatables: [],
        loading: true,
        showCreateModal: false,
        newTableName: '',
        showRenameModal: false,
        renameOldId: '',
        renameNewId: '',
        renameNewName: '',

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'datatables') await this.load();
            });
            if (Alpine.store('app').view === 'datatables') await this.load();
        },

        async load() {
            this.loading = true;
            try {
                this.datatables = await API.listDatatables();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
        },

        async createTable() {
            if (!this.newTableName.trim()) return Alpine.store('app').showToast('Name is required', 'error');
            const id = this.newTableName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
            if (!id) return Alpine.store('app').showToast('Name must contain at least one letter or number', 'error');
            try {
                await API.createDatatable({ id, name: this.newTableName.trim() });
                Alpine.store('app').showToast('Data table created');
                this.showCreateModal = false;
                this.newTableName = '';
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async deleteTable(dt) {
            if (!confirm(`Delete "${dt.name}" and all its rows? This cannot be undone.`)) return;
            try {
                await API.deleteDatatable(dt.id);
                Alpine.store('app').showToast('Data table deleted');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        viewTable(dt) {
            Alpine.store('app').navigate('datatable-detail', { selectedDataTable: dt.id });
        },

        openRename(dt) {
            this.renameOldId = dt.id;
            this.renameNewId = dt.id;
            this.renameNewName = dt.name;
            this.showRenameModal = true;
        },

        async saveRename() {
            try {
                await API.renameDatatable(this.renameOldId, {
                    new_id: this.renameNewId.trim(),
                    new_name: this.renameNewName.trim(),
                });
                Alpine.store('app').showToast('Data table renamed');
                this.showRenameModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },
    }));

    // Datatable detail component
    Alpine.data('datatableDetail', () => ({
        table: null,
        rows: [],
        columns: [],
        loading: true,
        showAddRowModal: false,
        showAddColumnModal: false,
        newColumnName: '',
        newRowData: {},
        pageSize: 50,
        pageOffset: 0,
        selectedRows: [],

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'datatable-detail') await this.load();
            });
            if (Alpine.store('app').view === 'datatable-detail') await this.load();
        },

        async load() {
            const tableId = Alpine.store('app').selectedDataTable;
            if (!tableId) { this.loading = false; return; }
            this.loading = true;
            this.selectedRows = [];
            try {
                const data = await API.getDatatable(tableId, this.pageSize, this.pageOffset);
                this.table = data;
                this.rows = data.rows || [];
                this.columns = data.columns || [];
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
        },

        async addColumn() {
            const name = this.newColumnName.trim();
            if (!name) return Alpine.store('app').showToast('Column name is required', 'error');
            if (this.columns.includes(name)) return Alpine.store('app').showToast('Column already exists', 'error');
            try {
                const updated = [...this.columns, name];
                await API.updateDatatable(this.table.id, { columns: updated });
                this.columns = updated;
                this.table.columns = updated;
                this.newColumnName = '';
                this.showAddColumnModal = false;
                Alpine.store('app').showToast('Column added');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async removeColumn(col) {
            if (!confirm(`Remove column "${col}"? Existing row data won't be deleted.`)) return;
            try {
                const updated = this.columns.filter(c => c !== col);
                await API.updateDatatable(this.table.id, { columns: updated });
                this.columns = updated;
                this.table.columns = updated;
                Alpine.store('app').showToast('Column removed');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        openAddRow() {
            this.newRowData = {};
            this.columns.forEach(c => this.newRowData[c] = '');
            this.showAddRowModal = true;
        },

        async addRow() {
            try {
                const data = {};
                this.columns.forEach(c => { if (this.newRowData[c] !== undefined) data[c] = this.newRowData[c]; });
                await API.addDatatableRow(this.table.id, { data });
                Alpine.store('app').showToast('Row added');
                this.showAddRowModal = false;
                this.newRowData = {};
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        toggleAll() {
            if (this.selectedRows.length === this.rows.length) {
                this.selectedRows = [];
            } else {
                this.selectedRows = this.rows.map(r => r.id);
            }
        },

        async bulkDelete() {
            const ids = [...this.selectedRows];
            if (!ids.length) return;
            if (!confirm(`Delete ${ids.length} selected row${ids.length > 1 ? 's' : ''}?`)) return;
            try {
                await API.bulkDeleteDatatableRows(this.table.id, ids);
                Alpine.store('app').showToast(`${ids.length} row${ids.length > 1 ? 's' : ''} deleted`);
                this.selectedRows = [];
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async deleteRow(row) {
            if (!confirm('Delete this row?')) return;
            try {
                await API.deleteDatatableRow(this.table.id, row.id);
                Alpine.store('app').showToast('Row deleted');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async clearAll() {
            if (!confirm(`Clear ALL rows from "${this.table.name}"? This cannot be undone.`)) return;
            try {
                await API.clearDatatableRows(this.table.id);
                Alpine.store('app').showToast('All rows cleared');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        // Cell editing
        editingRow: null,
        editingCol: null,
        editingValue: '',
        showEditCellModal: false,

        openEditCell(row, col) {
            this.editingRow = row;
            this.editingCol = col;
            this.editingValue = row.data[col] ?? '';
            this.showEditCellModal = true;
        },

        async saveCell() {
            if (!this.editingRow) return;
            try {
                const updatedData = { ...this.editingRow.data, [this.editingCol]: this.editingValue };
                await API.updateDatatableRow(this.table.id, this.editingRow.id, { data: updatedData });
                this.editingRow.data[this.editingCol] = this.editingValue;
                this.showEditCellModal = false;
                Alpine.store('app').showToast('Cell updated');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        nextPage() {
            this.pageOffset += this.pageSize;
            this.load();
        },

        prevPage() {
            this.pageOffset = Math.max(0, this.pageOffset - this.pageSize);
            this.load();
        },
    }));

    // Credentials component
    Alpine.data('credentialsList', () => ({
        credentials: [],
        loading: true,
        showCreateModal: false,
        showEditModal: false,
        editId: null,
        editName: '',
        editType: '',
        editValue: '',
        editPageId: null,
        allPages: [],
        showRenameModal: false,
        renameOldId: '',
        renameNewId: '',
        renameNewName: '',
        credService: 'openai',
        credName: '',
        credApiKey: '',

        async init() {
            await this.load();
        },

        async load() {
            this.loading = true;
            try {
                const all = await API.listCredentials();
                this.credentials = all.filter(c => c.type !== 'facebook_user');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
        },

        _serviceConfig(service) {
            const configs = {
                facebook: { id: 'fb', name: 'Facebook Access Token', type: 'facebook', transform: v => v },
                openai: { id: 'openai', name: 'OpenAI API Key', type: 'openai', transform: v => v },
                gemini: { id: 'gemini', name: 'Gemini API Key', type: 'gemini', transform: v => v },
                anthropic: { id: 'anthropic', name: 'Anthropic API Key', type: 'anthropic', transform: v => v },
                nova: { id: 'nova', name: 'Authorization', type: 'nova_astra', transform: v => `Bearer ${v}` },
            };
            return configs[service];
        },

        async create() {
            if (!this.credName.trim()) return Alpine.store('app').showToast('Name is required', 'error');
            if (!this.credApiKey.trim()) return Alpine.store('app').showToast('API Key is required', 'error');
            const cfg = this._serviceConfig(this.credService);
            const id = this.credName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
            try {
                await API.createCredential({
                    id: `${id}-${Date.now()}`,
                    name: this.credName.trim(),
                    type: cfg.type,
                    value: cfg.transform(this.credApiKey.trim()),
                });
                Alpine.store('app').showToast('Credential created');
                this.showCreateModal = false;
                this.credService = 'openai';
                this.credName = '';
                this.credApiKey = '';
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async openEdit(cred) {
            this.editId = cred.id;
            this.editName = cred.name;
            this.editType = cred.type;
            this.editValue = '';
            this.editPageId = cred.page_id || '';
            try { this.allPages = await API.listPages(); } catch (_) {}
            this.showEditModal = true;
        },

        async saveEdit() {
            if (!this.editName.trim()) return Alpine.store('app').showToast('Name is required', 'error');
            const payload = { name: this.editName.trim(), type: this.editType, page_id: this.editPageId || null };
            if (this.editValue.trim()) payload.value = this.editValue.trim();
            try {
                await API.updateCredential(this.editId, payload);
                Alpine.store('app').showToast('Credential updated');
                this.showEditModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async reveal(id) {
            try {
                const data = await API.revealCredential(id);
                prompt('Credential value:', data.value);
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async deleteCred(id) {
            if (!confirm(`Delete credential "${id}"?`)) return;
            try {
                await API.deleteCredential(id);
                Alpine.store('app').showToast('Credential deleted');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        openRename(cred) {
            this.renameOldId = cred.id;
            this.renameNewId = cred.id;
            this.renameNewName = cred.name;
            this.showRenameModal = true;
        },

        async saveRename() {
            try {
                await API.renameCredential(this.renameOldId, {
                    new_id: this.renameNewId.trim(),
                    new_name: this.renameNewName.trim(),
                });
                Alpine.store('app').showToast('Credential renamed');
                this.showRenameModal = false;
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },
    }));

    // Access Tokens component (facebook_user credentials for page token sync)
    Alpine.data('accessTokensList', () => ({
        tokens: [],
        syncedPages: [],
        loading: true,
        showCreateModal: false,
        showSyncModal: false,
        syncing: false,
        syncingId: null,
        syncResult: null,
        tokenName: '',
        tokenValue: '',

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'access-tokens') await this.load();
            });
            if (Alpine.store('app').view === 'access-tokens') await this.load();
        },

        async load() {
            this.loading = true;
            try {
                const all = await API.listCredentials();
                this.tokens = all.filter(c => c.type === 'facebook_user');
                // Deduplicate by page_id — only show one entry per Loom page
                const seen = new Set();
                this.syncedPages = all.filter(c => c.type === 'facebook' && c.page_id && !seen.has(c.page_id) && seen.add(c.page_id));
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
        },

        async create() {
            if (!this.tokenName.trim()) return Alpine.store('app').showToast('Name is required', 'error');
            if (!this.tokenValue.trim()) return Alpine.store('app').showToast('Token is required', 'error');
            const id = this.tokenName.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
            try {
                await API.createCredential({
                    id: `fb-user-${id}-${Date.now()}`,
                    name: this.tokenName.trim(),
                    type: 'facebook_user',
                    value: this.tokenValue.trim(),
                });
                Alpine.store('app').showToast('Access token saved');
                this.showCreateModal = false;
                this.tokenName = '';
                this.tokenValue = '';
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async reveal(id) {
            try {
                const data = await API.revealCredential(id);
                prompt('Token value:', data.value);
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async deleteToken(id) {
            if (!confirm(`Delete access token "${id}"?`)) return;
            try {
                await API.deleteCredential(id);
                Alpine.store('app').showToast('Token deleted');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
        },

        async syncFbPages(credId) {
            if (!confirm('Sync page tokens? This will create or update Facebook credentials for all matching Loom pages.')) return;
            this.syncing = true;
            this.syncingId = credId;
            this.syncResult = null;
            try {
                this.syncResult = await API.syncFbPages(credId);
                await this.load();
                this.showSyncModal = true;
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.syncing = false;
            this.syncingId = null;
        },
    }));

    // Page assets component
    Alpine.data('pageAssets', () => ({
        page: null,
        loading: false,
        generating: false,
        generatingType: '',
        profileStyle: '',
        coverStyle: '',
        bioNiche: '',
        generatedProfile: null,
        generatedCover: null,
        generatedBio: null,

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'page-assets') await this.load();
            });
            if (Alpine.store('app').view === 'page-assets') await this.load();
        },

        async load() {
            const pageId = Alpine.store('app').selectedPage;
            if (!pageId) { this.loading = false; return; }
            this.loading = true;
            try {
                this.page = await API.getPage(pageId);
                if (this.page.bio) this.generatedBio = this.page.bio;
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.loading = false;
        },

        async generateProfile() {
            if (!this.profileStyle) return Alpine.store('app').showToast('Enter a style description', 'error');
            this.generating = true;
            this.generatingType = 'profile';
            try {
                const result = await API.generateProfileImage(this.page.id, {
                    theme: this.profileStyle,
                });
                this.generatedProfile = `data:image/png;base64,${result.image_base64}`;
                Alpine.store('app').showToast('Profile image generated');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.generating = false;
            this.generatingType = '';
        },

        async generateCover() {
            if (!this.coverStyle) return Alpine.store('app').showToast('Enter a style description', 'error');
            this.generating = true;
            this.generatingType = 'cover';
            try {
                const result = await API.generateCoverPhoto(this.page.id, {
                    theme: this.coverStyle,
                });
                this.generatedCover = `data:image/png;base64,${result.image_base64}`;
                Alpine.store('app').showToast('Cover photo generated');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.generating = false;
            this.generatingType = '';
        },

        async generateBioText() {
            this.generating = true;
            this.generatingType = 'bio';
            try {
                const result = await API.generateBio(this.page.id, {
                    niche_description: this.bioNiche || this.page.niche_id || '',
                });
                this.generatedBio = result.bio;
                Alpine.store('app').showToast('Bio generated');
            } catch (e) {
                Alpine.store('app').showToast(e.message, 'error');
            }
            this.generating = false;
            this.generatingType = '';
        },

        downloadImage(dataUrl, filename) {
            const a = document.createElement('a');
            a.href = dataUrl;
            a.download = filename;
            a.click();
        },

        copyBio() {
            navigator.clipboard.writeText(this.generatedBio);
            Alpine.store('app').showToast('Bio copied to clipboard');
        },
    }));
});
