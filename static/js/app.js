// 本文件负责主界面的 Alpine 状态、API 编排和用户交互，不直接包含后端业务规则。
function app() {
    // 收纳盒/柜子、地图、BOM 和自动化领域逻辑由 feature 注入，保持 app() 入口和模板绑定兼容。
    const componentsFeature = window.InventoryModules?.createComponentsFeature?.({ api, uploadFile, downloadFile, logAction });
    const storageFeature = window.InventoryModules?.createStorageFeature?.({ api, logAction, confirm });
    const mapFeature = window.InventoryModules?.createMapFeature?.({ api, uploadFile, logAction, confirm });
    const bomFeature = window.InventoryModules?.createBomFeature?.({
        api,
        uploadFile,
        downloadPostFile,
        logAction,
        confirm,
        gotoMapWithBoxes: async function gotoMapWithBoxes(boxIds) {
            await this.loadMapData();
            this.mapHighlights = boxIds;
            this.updateMapPickLabels();
            if (this.mapViewMode === '3d' && this.scene3D) {
                if (typeof this.sync3DHighlights === 'function') this.sync3DHighlights();
                if (typeof this.reveal3DHighlights === 'function') this.reveal3DHighlights();
            }
            this.page = 'map';
        },
        refreshMapPickLabels: function refreshMapPickLabels() {
            if (typeof this.updateMapPickLabels === 'function') {
                this.updateMapPickLabels();
            }
            if (this.scene3D && typeof this.sync3DHighlights === 'function') {
                this.sync3DHighlights();
            }
        }
    });
    const automationFeature = window.InventoryModules?.createAutomationFeature?.({
        api,
        logAction,
        confirm,
        openComponentById: function openComponentById(componentId) {
            this.page = 'components';
            this.loadComponents();
            this.openComponentDetail(componentId);
        },
        openComponentFormWithScan: function openComponentFormWithScan(text) {
            this.openComponentForm();
            const parts = String(text || '').split(',').map((part) => part.trim()).filter(Boolean);
            if (parts.length > 1) {
                this.componentForm.name = parts[0] || '';
                this.componentForm.package = parts[1] || '';
                this.componentForm.model = parts[2] || '';
            } else {
                this.componentForm.name = String(text || '').trim();
            }
        }
    });
    const modelAppearanceFeature = window.InventoryModules?.createModelAppearanceFeature?.({ api, uploadFile, confirm });
    // 3D 地图功能模块：依赖 api 进行格子数据懒加载和布局 API 调用。
    const map3dFeature = window.InventoryModules?.createMap3DFeature?.({ api, logAction });

    // Alpine 根状态按领域分区排列，后续模块通过 InventoryModules.mergeFeature 进行轻量注入。
    const appState = {
        // 页面框架状态：控制导航、弹窗、加载态和图片预览。
        page: 'dashboard',
        modal: null,
        loading: false,
        loadingOverlay: false,
        previewImage: null,

        navItems: [
            { id: 'dashboard', label: '首页', icon: 'grid' },
            { id: 'components', label: '元器件', icon: 'chip' },
            { id: 'boxes', label: '收纳盒', icon: 'box' },
            { id: 'map', label: '地图', icon: 'map' },
            { id: 'bom', label: 'BOM', icon: 'list' },
            { id: 'nfc', label: 'NFC', icon: 'nfc' }
        ],

        // 基础数据缓存：供仪表盘、表单下拉和地图视图复用。
        categories: [],
        stats: {},
        lowStockList: [],
        recentLogs: [],

        // 应用生命周期：初始化只编排数据加载，不承担具体领域计算。
        async initApp() {
            await Promise.all([this.loadCategories(), this.loadCabinets(), this.loadBoxes(), this.loadLedConfig(), this.loadNfcConfig()]);
            await this.loadDashboard();
            await this.openComponentFromUrl();
        },

        async navigate(pageId) {
            this.page = pageId;
            if (pageId === 'dashboard') await this.loadDashboard();
            if (pageId === 'components') await this.loadComponents();
            if (pageId === 'boxes') await Promise.all([this.loadCabinets(), this.loadBoxes()]);
            if (pageId === 'map') await this.loadMapData();
            if (pageId === 'nfc') await Promise.all([this.loadBoxes(), this.loadNfcConfig()]);
        },

        closeAllModals() {
            if (this.modal === 'scanner') {
                this.closeScanner();
                return;
            }
            this.modal = null;
            this.previewImage = null;
        },

        closeModal() {
            if (this.modal === 'scanner') {
                this.closeScanner();
                return;
            }
            this.modal = null;
        },

        toast(message, type = 'info') {
            const container = document.getElementById('toast-container');
            if (!container) return;
            const el = document.createElement('div');
            el.className = `toast toast-${type}`;
            el.textContent = message;
            container.appendChild(el);
            setTimeout(() => el.remove(), 3200);
        },

        formatDateTime(iso) {
            if (!iso) return '-';
            const date = new Date(iso);
            if (Number.isNaN(date.getTime())) return iso;
            const pad = (n) => String(n).padStart(2, '0');
            return `${date.getMonth() + 1}/${date.getDate()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
        },

        stockState(item) {
            if (!item) return 'normal';
            return Number(item.quantity || 0) <= Number(item.min_stock || 0) ? 'low' : 'normal';
        },

        locationText(item) {
            if (!item || !item.box_name) return '未入盒';
            return `${item.box_name}${item.cell_label ? ' / ' + item.cell_label : ''}`;
        },

        async loadDashboard() {
            try {
                this.loading = true;
                const [stats, logs] = await Promise.all([
                    api.get('/api/stats'),
                    api.get('/api/stock/logs/0', { page_size: 8 })
                ]);
                this.stats = stats || {};
                this.lowStockList = this.stats.low_stock_items || [];
                this.recentLogs = logs?.items || [];
            } catch (err) {
                this.toast('加载首页失败：' + err.message, 'error');
            } finally {
                this.loading = false;
            }
        },

        async loadCategories() {
            try {
                this.categories = await api.get('/api/categories');
            } catch (err) {
                this.toast('加载分类失败：' + err.message, 'error');
            }
        }
    };

    const mergedAppState = window.InventoryModules?.mergeFeature(appState, window.InventoryModules.features?.app) || appState;
    const appWithComponents = window.InventoryModules?.mergeFeature(mergedAppState, componentsFeature) || mergedAppState;
    const appWithStorage = window.InventoryModules?.mergeFeature(appWithComponents, storageFeature) || appWithComponents;
    const appWithMap = window.InventoryModules?.mergeFeature(appWithStorage, mapFeature) || appWithStorage;
    const appWithBom = window.InventoryModules?.mergeFeature(appWithMap, bomFeature) || appWithMap;
    const appWithAppearance = window.InventoryModules?.mergeFeature(appWithBom, modelAppearanceFeature) || appWithBom;
    const appWith3D = window.InventoryModules?.mergeFeature(appWithAppearance, map3dFeature) || appWithAppearance;
    return window.InventoryModules?.mergeFeature(appWith3D, automationFeature) || appWith3D;
}
