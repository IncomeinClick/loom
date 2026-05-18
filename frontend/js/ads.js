// Ads Manager component — Facebook Page Like campaigns

document.addEventListener('alpine:init', () => {

    Alpine.data('adsManager', () => ({
        campaigns: [],
        fbCampaigns: [],
        expandedFbCampaign: null,
        fbAdsets: [],
        loadingAdsets: false,
        pages: [],
        account: null,
        loading: true,
        syncing: false,
        syncingId: null,
        creating: false,
        insightsPeriod: 'maximum',  // 'today' or 'maximum'
        fbInsights: {},  // keyed by campaign ID

        // Create modal
        showCreateModal: false,
        videos: [],
        loadingVideos: false,
        countryOptions: [
            { code: 'TH', name: 'Thailand' },
            { code: 'LA', name: 'Laos' },
            { code: 'SG', name: 'Singapore' },
            { code: 'MY', name: 'Malaysia' },
            { code: 'PH', name: 'Philippines' },
            { code: 'VN', name: 'Vietnam' },
            { code: 'BN', name: 'Brunei' },
            { code: 'ID', name: 'Indonesia' },
        ],
        languageOptions: [
            { id: '1001', name: 'Thai' },
            { id: '24', name: 'Filipino' },
            { id: '1023', name: 'Indonesian' },
            { id: '1011', name: 'Malay' },
            { id: '1010', name: 'Vietnamese' },
            { id: '6', name: 'English' },
        ],
        newCampaign: {
            page_id: '',
            name: '',
            daily_budget: 100,
            countries: ['TH'],
            age_min: 18,
            age_max: 65,
            gender: 0,  // 0=all, 1=male, 2=female
            locales: [],  // array of locale ID strings
            video_ids: [],
            start_active: false,
        },

        async init() {
            this.$watch('$store.app.view', async (view) => {
                if (view === 'ads') await this.load();
            });
            if (this.$store.app.view === 'ads') await this.load();
        },

        async load() {
            this.loading = true;
            try {
                const [campaigns, pages, fbCampaigns] = await Promise.all([
                    API.listCampaigns(),
                    API.listPages(),
                    API.listFbCampaigns(),
                ]);
                this.campaigns = campaigns;
                this.pages = pages;
                // Sort: active first, then by created_time desc
                this.fbCampaigns = fbCampaigns.sort((a, b) => {
                    const aActive = a.effective_status === 'ACTIVE' ? 0 : 1;
                    const bActive = b.effective_status === 'ACTIVE' ? 0 : 1;
                    if (aActive !== bActive) return aActive - bActive;
                    return new Date(b.created_time) - new Date(a.created_time);
                });
            } catch (e) {
                Alpine.store('app').showToast('Failed to load campaigns: ' + e.message, 'error');
            }
            // Load account info in background
            try {
                this.account = await API.getAdAccount();
            } catch (e) {
                // Not critical
            }
            this.loading = false;
            // Load insights for active campaigns
            await this.loadInsights();
        },

        async loadInsights() {
            const active = this.fbCampaigns.filter(c => c.effective_status === 'ACTIVE');
            const results = await Promise.allSettled(
                active.map(c =>
                    fetch(`/api/ads/fb/campaigns/${c.id}/insights?date_preset=${this.insightsPeriod}`, {
                        headers: { 'Authorization': `Bearer ${API.token}` }
                    }).then(r => r.json()).then(data => ({ id: c.id, ...data }))
                )
            );
            const insights = {};
            for (const r of results) {
                if (r.status === 'fulfilled' && r.value.id) {
                    insights[r.value.id] = r.value;
                }
            }
            this.fbInsights = insights;
        },

        async switchPeriod(period) {
            this.insightsPeriod = period;
            await this.loadInsights();
        },

        activeFbCampaigns() {
            return this.fbCampaigns.filter(c => c.effective_status === 'ACTIVE');
        },

        fbActiveCampaigns() {
            return this.activeFbCampaigns().length;
        },

        fbTotalBudget() {
            return this.activeFbCampaigns().reduce((sum, c) => {
                const daily = parseInt(c.daily_budget || 0) / 100;
                return sum + daily;
            }, 0);
        },

        fbTotalSpend() {
            return Object.values(this.fbInsights).reduce((sum, i) => sum + (i.spend || 0), 0).toFixed(2);
        },

        fbTotalLikes() {
            return Object.values(this.fbInsights).reduce((sum, i) => sum + (i.page_likes || 0), 0).toLocaleString();
        },

        getInsights(campaignId) {
            return this.fbInsights[campaignId] || null;
        },

        async toggleFbCampaign(campaignId) {
            if (this.expandedFbCampaign === campaignId) {
                this.expandedFbCampaign = null;
                this.fbAdsets = [];
                return;
            }
            this.expandedFbCampaign = campaignId;
            this.loadingAdsets = true;
            this.fbAdsets = [];
            try {
                this.fbAdsets = await API.listFbAdsets(campaignId);
            } catch (e) {
                Alpine.store('app').showToast('Failed to load ad sets: ' + e.message, 'error');
            }
            this.loadingAdsets = false;
        },

        async loadVideos() {
            if (!this.newCampaign.page_id) return;
            this.loadingVideos = true;
            this.videos = [];
            this.newCampaign.video_ids = [];
            try {
                this.videos = await API.getPageVideos(this.newCampaign.page_id, 10);
            } catch (e) {
                Alpine.store('app').showToast('Failed to load videos: ' + e.message, 'error');
            }
            this.loadingVideos = false;
        },

        async create() {
            if (!this.newCampaign.page_id) {
                Alpine.store('app').showToast('Please select a page', 'error');
                return;
            }
            if (!this.newCampaign.name) {
                Alpine.store('app').showToast('Please enter a campaign name', 'error');
                return;
            }
            if (this.newCampaign.countries.length === 0) {
                Alpine.store('app').showToast('Please select at least one country', 'error');
                return;
            }
            if (this.newCampaign.video_ids.length === 0) {
                Alpine.store('app').showToast('Please select at least one video', 'error');
                return;
            }

            this.creating = true;
            try {
                const genders = this.newCampaign.gender > 0 ? [this.newCampaign.gender] : [];
                const locales = this.newCampaign.locales.map(l => parseInt(l)).filter(l => !isNaN(l));

                const data = {
                    name: this.newCampaign.name,
                    page_id: this.newCampaign.page_id,
                    daily_budget: this.newCampaign.daily_budget || null,
                    targeting: {
                        countries: this.newCampaign.countries,
                        age_min: this.newCampaign.age_min || 18,
                        age_max: this.newCampaign.age_max || 65,
                        genders: genders,
                        locales: locales,
                    },
                    video_ids: this.newCampaign.video_ids,
                    start_active: this.newCampaign.start_active,
                };

                const campaign = await API.createCampaign(data);
                this.campaigns.unshift(campaign);
                this.showCreateModal = false;
                this.resetForm();
                Alpine.store('app').showToast('Campaign created successfully');
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast('Failed to create campaign: ' + e.message, 'error');
            }
            this.creating = false;
        },

        resetForm() {
            this.newCampaign = {
                page_id: '',
                name: '',
                daily_budget: 100,
                countries: ['TH'],
                age_min: 18,
                age_max: 65,
                gender: 0,
                locales: [],
                video_ids: [],
                start_active: false,
            };
            this.videos = [];
        },

        async pause(id) {
            try {
                const updated = await API.pauseCampaign(id);
                this._updateCampaign(id, updated);
                Alpine.store('app').showToast('Campaign paused');
            } catch (e) {
                Alpine.store('app').showToast('Failed to pause: ' + e.message, 'error');
            }
        },

        async resume(id) {
            try {
                const updated = await API.resumeCampaign(id);
                this._updateCampaign(id, updated);
                Alpine.store('app').showToast('Campaign resumed');
            } catch (e) {
                Alpine.store('app').showToast('Failed to resume: ' + e.message, 'error');
            }
        },

        async deleteCampaign(id, name) {
            if (!confirm(`Delete campaign "${name}"? This will also delete it from Facebook Ads Manager.`)) return;
            try {
                await API.deleteCampaign(id);
                this.campaigns = this.campaigns.filter(c => c.id !== id);
                Alpine.store('app').showToast('Campaign deleted');
            } catch (e) {
                Alpine.store('app').showToast('Failed to delete: ' + e.message, 'error');
            }
        },

        async syncInsights(id) {
            this.syncingId = id;
            try {
                const updated = await API.syncCampaignInsights(id);
                this._updateCampaign(id, updated);
                Alpine.store('app').showToast('Insights synced');
            } catch (e) {
                Alpine.store('app').showToast('Failed to sync: ' + e.message, 'error');
            }
            this.syncingId = null;
        },

        async syncAll() {
            this.syncing = true;
            try {
                const result = await API.syncAllInsights();
                Alpine.store('app').showToast(`Synced ${result.synced} campaign(s)`);
                await this.load();
            } catch (e) {
                Alpine.store('app').showToast('Failed to sync: ' + e.message, 'error');
            }
            this.syncing = false;
        },

        totalSpend() {
            const sum = this.campaigns.reduce((acc, c) => acc + (c.spend || 0), 0);
            return sum.toFixed(2);
        },

        totalLikes() {
            return this.campaigns.reduce((acc, c) => acc + (c.page_likes || 0), 0).toLocaleString();
        },

        _updateCampaign(id, updated) {
            const idx = this.campaigns.findIndex(c => c.id === id);
            if (idx >= 0) this.campaigns[idx] = updated;
        },
    }));
});
