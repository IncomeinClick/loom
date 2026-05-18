// Dashboard component — Page Lifecycle Tracker

document.addEventListener('alpine:init', () => {

    Alpine.data('dashboardView', () => ({
        summary: null,
        loading: true,
        savingId: null,
        filterStage: null,

        STAGES: [
            { key: 'setup',       label: 'Setup',       icon: '🔧', desc: 'Has ≥1 workflow', auto: true },
            { key: 'fb_ready',    label: 'FB Ready',    icon: '🔑', desc: 'Has Facebook credential', auto: true },
            { key: 'video_live',  label: 'Video Live',  icon: '🎬', desc: 'Active+scheduled video workflow', auto: true },
            { key: 'image_live',  label: 'Image Live',  icon: '🖼️', desc: 'Active+scheduled image workflow', auto: true },
            { key: 'ads_running', label: 'Ads Running', icon: '📢', desc: 'Facebook ads active', auto: false },
            { key: 'monetized',   label: 'Monetized',   icon: '✅', desc: 'Manually marked as monetized', auto: false },
        ],

        STAGE_COLORS: {
            0: 'text-gray-500',
            1: 'text-blue-400',
            2: 'text-yellow-400',
            3: 'text-emerald-400',
            4: 'text-purple-400',
            5: 'text-orange-400',
            6: 'text-pink-400',
        },

        STAGE_BG: {
            0: 'bg-gray-500/10 border-gray-500/20',
            1: 'bg-blue-500/10 border-blue-500/20',
            2: 'bg-yellow-500/10 border-yellow-500/20',
            3: 'bg-emerald-500/10 border-emerald-500/20',
            4: 'bg-purple-500/10 border-purple-500/20',
            5: 'bg-orange-500/10 border-orange-500/20',
            6: 'bg-pink-500/10 border-pink-500/20',
        },

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'dashboard') await this.load();
            });
            await this.load();
        },

        async load() {
            this.loading = true;
            try {
                this.summary = await API.request('GET', '/api/dashboard');
            } catch(e) {
                Alpine.store('app').showToast('Failed to load dashboard', 'error');
            }
            this.loading = false;
        },

        filteredPages() {
            if (!this.summary?.pages) return [];
            if (this.filterStage === null) return this.summary.pages;
            return this.summary.pages.filter(p => p.current_stage === this.filterStage);
        },

        toggleFilter(stage) {
            this.filterStage = this.filterStage === stage ? null : stage;
        },

        stageLabel(stage) {
            const s = this.STAGES[stage - 1];
            return s ? s.label : 'Not Started';
        },

        stagePercent(stage) {
            return Math.round((stage / 6) * 100);
        },

        progressBarColor(stage) {
            const colors = ['', 'bg-blue-500', 'bg-yellow-500', 'bg-emerald-500', 'bg-purple-500', 'bg-orange-500', 'bg-pink-500'];
            return colors[stage] || 'bg-gray-600';
        },

        async markStage(pageId, stageKey) {
            this.savingId = pageId + stageKey;
            try {
                const updated = await API.request('POST', `/api/dashboard/${pageId}/stage/${stageKey}`);
                this._updatePage(pageId, updated);
                Alpine.store('app').showToast('Stage updated ✓');
            } catch(e) {
                Alpine.store('app').showToast('Failed to update stage', 'error');
            }
            this.savingId = null;
        },

        async clearStage(pageId, stageKey) {
            this.savingId = pageId + stageKey + 'clear';
            try {
                const updated = await API.request('POST', `/api/dashboard/${pageId}/stage/${stageKey}/clear`);
                this._updatePage(pageId, updated);
                Alpine.store('app').showToast('Stage cleared');
            } catch(e) {
                Alpine.store('app').showToast('Failed to clear stage', 'error');
            }
            this.savingId = null;
        },

        async toggleAds(page) {
            try {
                if (page.ads_running_at) {
                    const updated = await API.request('POST', `/api/dashboard/${page.page_id}/stage/ads_running/clear`);
                    this._updatePage(page.page_id, updated);
                } else {
                    const updated = await API.request('POST', `/api/dashboard/${page.page_id}/stage/ads_running`);
                    this._updatePage(page.page_id, updated);
                }
            } catch(e) {
                Alpine.store('app').showToast('Failed to toggle ads', 'error');
            }
        },

        async toggleMonetized(page) {
            try {
                if (page.monetized_at) {
                    const updated = await API.request('POST', `/api/dashboard/${page.page_id}/stage/monetized/clear`);
                    this._updatePage(page.page_id, updated);
                } else {
                    const updated = await API.request('POST', `/api/dashboard/${page.page_id}/stage/monetized`);
                    this._updatePage(page.page_id, updated);
                }
            } catch(e) {
                Alpine.store('app').showToast('Failed to toggle monetized', 'error');
            }
        },

        _updatePage(pageId, updated) {
            if (!this.summary) return;
            const idx = this.summary.pages.findIndex(p => p.page_id === pageId);
            if (idx >= 0) {
                this.summary.pages[idx] = updated;
                // Recompute by_stage
                const stageCounts = { not_started: 0, setup: 0, fb_ready: 0, video_live: 0, image_live: 0, ads_running: 0, monetized: 0 };
                const stageKeys = ['not_started', 'setup', 'fb_ready', 'video_live', 'image_live', 'ads_running', 'monetized'];
                this.summary.pages.forEach(p => {
                    stageCounts[stageKeys[p.current_stage]]++;
                });
                this.summary.by_stage = stageCounts;
            }
        },

        stageIsComplete(page, stageKey) {
            const fieldMap = {
                setup: 'setup_at',
                fb_ready: 'fb_ready_at',
                video_live: 'video_live_at',
                image_live: 'image_live_at',
                ads_running: 'ads_running_at',
                monetized: 'monetized_at',
            };
            return !!page[fieldMap[stageKey]];
        },

        formatDate(dt) {
            if (!dt) return null;
            return new Date(dt.endsWith('Z') ? dt : dt + 'Z').toLocaleDateString('en-GB', {
                timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short', year: '2-digit'
            });
        },
    }));
});
