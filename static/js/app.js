// 本文件负责主界面的 Alpine 状态、API 编排和用户交互，不直接包含后端业务规则。
function app() {
    const emptyComponentForm = () => ({
        id: null,
        name: '',
        category_id: '',
        model: '',
        package: '',
        nominal_value: '',
        voltage_rating: '',
        current_rating: '',
        power_rating: '',
        tolerance: '',
        material_type: '',
        manufacturer: '',
        quantity: 0,
        min_stock: 0,
        box_id: '',
        cell_row: '',
        cell_col: '',
        description: '',
        tagsInput: '',
        images: [],
        documents: []
    });

    const emptyBoxForm = () => ({
        id: null,
        name: '',
        rows: 4,
        cols: 6,
        color: '#84b59b',
        cabinet_id: '',
        cabinet_slot: 0,
        description: ''
    });

    const emptyCabinetForm = () => ({
        id: null,
        name: '',
        color: '#8b9aae',
        description: ''
    });

    const emptyLedDeviceForm = () => ({
        id: null,
        name: '',
        host: '',
        port: 80,
        enabled: true
    });

    const emptyLedStripForm = () => ({
        id: null,
        device_id: '',
        name: '',
        gpio_num: 0,
        led_count: 0
    });

    return {
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

        categories: [],
        boxes: [],
        cabinets: [],
        stats: {},
        lowStockList: [],
        recentLogs: [],

        searchKeyword: '',
        filterCategory: '',
        filterBox: '',
        filterStock: '',
        componentList: [],
        componentPagination: { page: 1, page_size: 20, total: 0 },
        componentForm: emptyComponentForm(),
        availableCells: [],
        currentComponent: null,
        stockForm: { type: 'in', quantity: 1, reason: '' },

        boxForm: emptyBoxForm(),
        cabinetForm: emptyCabinetForm(),
        currentBox: null,
        boxGrid: [],

        mapBoxes: [],
        mapCabinets: [],
        expandedCabinets: [],
        mapHighlights: [],
        mapState: { panX: 48, panY: 48, scale: 1 },
        mapDirty: false,
        draggingBox: null,
        draggingCabinet: null,
        dragState: null,
        mapBackground: localStorage.getItem('inventory-map-bg') || 'grid',
        mapBackgroundUrl: '',

        bomFile: null,
        bomData: null,
        bomStats: { total: 0, matched: 0, shortage: 0, unmatched: 0 },
        bomSelectedRows: [],
        bomManualRowIndex: null,
        bomManualKeyword: '',
        bomManualResults: [],
        bomManualLoading: false,

        nfcBoxId: '',
        nfcStatus: null,
        nfcSupported: 'NDEFReader' in window || 'NDEFWriter' in window,

        scannerManualText: '',
        scannerError: '',
        brandClickCount: 0,
        brandClickStartedAt: 0,
        tokenForm: { name: '' },
        apiTokens: [],
        generatedToken: '',
        settingsTab: 'token',
        ledConfig: { enabled: false, blink_interval_ms: 500, blink_duration_ms: 10000 },
        ledDevices: [],
        ledStrips: [],
        ledMappings: [],
        ledDeviceForm: null,
        ledStripForm: null,
        ledTestResults: {},
        ledTestLoading: {},
        ledClearLoading: false,
        ledClearMessage: '',
        ledPowerOffLoading: false,
        ledPowerOffMessage: '',

        async initApp() {
            await Promise.all([this.loadCategories(), this.loadCabinets(), this.loadBoxes(), this.loadLedConfig()]);
            await this.loadDashboard();
            await this.openComponentFromUrl();
        },

        async navigate(pageId) {
            this.page = pageId;
            if (pageId === 'dashboard') await this.loadDashboard();
            if (pageId === 'components') await this.loadComponents();
            if (pageId === 'boxes') await Promise.all([this.loadCabinets(), this.loadBoxes()]);
            if (pageId === 'map') await this.loadMapData();
            if (pageId === 'nfc') await this.loadBoxes();
        },

        async handleBrandMarkClick() {
            const now = Date.now();
            if (!this.brandClickStartedAt || now - this.brandClickStartedAt > 1800) {
                this.brandClickStartedAt = now;
                this.brandClickCount = 0;
            }
            this.brandClickCount += 1;
            if (this.brandClickCount >= 5) {
                this.brandClickCount = 0;
                this.brandClickStartedAt = 0;
                await this.openSettings();
            }
        },

        async openSettings() {
            this.modal = 'settings';
            this.generatedToken = '';
            this.tokenForm = { name: '' };
            this.settingsTab = 'token';
            await Promise.all([this.loadApiTokens(), this.loadLedConfig()]);
        },

        async loadApiTokens() {
            try {
                this.apiTokens = await api.get('/api/settings/tokens');
            } catch (err) {
                this.toast('加载 Token 失败：' + err.message, 'error');
            }
        },

        async generateApiToken() {
            const name = (this.tokenForm.name || '').trim();
            if (!name) {
                this.toast('请先填写 Token 名称', 'warn');
                return;
            }
            try {
                const result = await api.post('/api/settings/tokens', { name });
                this.generatedToken = result.token;
                this.tokenForm.name = '';
                await this.loadApiTokens();
                this.toast('Token 已生成，请立即保存', 'success');
            } catch (err) {
                this.toast('生成 Token 失败：' + err.message, 'error');
            }
        },

        async copyGeneratedToken() {
            if (!this.generatedToken) return;
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(this.generatedToken);
                } else {
                    this.copyTextFallback(this.generatedToken);
                }
                this.toast('Token 已复制', 'success');
            } catch (err) {
                try {
                    this.copyTextFallback(this.generatedToken);
                    this.toast('Token 已复制', 'success');
                } catch (fallbackErr) {
                    this.toast('复制失败，请手动选择 Token', 'error');
                }
            }
        },

        copyTextFallback(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.setAttribute('readonly', '');
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            textarea.style.top = '0';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            const ok = document.execCommand('copy');
            textarea.remove();
            if (!ok) throw new Error('copy command failed');
        },

        async deleteApiToken(token) {
            if (!token || !token.id) return;
            if (!confirm(`删除 Token "${token.name}"？删除后使用它的设备会立即失效。`)) return;
            try {
                await api.del(`/api/settings/tokens/${token.id}`);
                await this.loadApiTokens();
                this.toast('Token 已删除', 'success');
            } catch (err) {
                this.toast('删除 Token 失败：' + err.message, 'error');
            }
        },

        normalizeLedConfig(config = {}) {
            return {
                id: config.id || 1,
                enabled: config.enabled === true || Number(config.enabled || 0) === 1,
                blink_interval_ms: Number(config.blink_interval_ms || 500),
                blink_duration_ms: Number(config.blink_duration_ms || 10000)
            };
        },

        normalizeLedColor(color) {
            const value = String(color || '').trim();
            return /^#[0-9a-fA-F]{6}$/.test(value) ? value.toLowerCase() : '#00ff00';
        },

        normalizeLedMappings(mappings = []) {
            return (mappings || []).map((item) => ({
                ...item,
                box_id: Number(item.box_id || 0),
                strip_id: Number(item.strip_id || 0),
                led_index: Math.max(0, Number(item.led_index || 0)),
                color: this.normalizeLedColor(item.color)
            }));
        },

        async loadLedConfig() {
            try {
                const data = await api.get('/api/settings/led');
                this.ledConfig = this.normalizeLedConfig(data?.config || {});
                this.ledDevices = data?.devices || [];
                this.ledStrips = data?.strips || [];
                this.ledMappings = this.normalizeLedMappings(data?.mappings || []);
            } catch (err) {
                this.toast('加载 LED 配置失败：' + err.message, 'error');
            }
        },

        ledStripLabel(strip) {
            if (!strip) return '请选择灯带';
            return `${strip.device_name || '未命名设备'} / ${strip.name || '灯带'} / GPIO ${strip.gpio_num}`;
        },

        nextLedIndex(stripId) {
            const id = Number(stripId || 0);
            const used = new Set(this.ledMappings.filter((item) => Number(item.strip_id) === id).map((item) => Number(item.led_index || 0)));
            const strip = this.ledStrips.find((item) => Number(item.id) === id);
            const limit = Number(strip?.led_count || 0);
            for (let index = 0; limit <= 0 || index < limit; index += 1) {
                if (!used.has(index)) return index;
            }
            return Math.max(0, limit);
        },

        prepareLedMapping(mapping) {
            mapping.box_id = Number(mapping.box_id || 0);
            mapping.strip_id = Number(mapping.strip_id || 0);
            mapping.led_index = Math.max(0, Number(mapping.led_index || 0));
            mapping.color = this.normalizeLedColor(mapping.color);
            return mapping;
        },

        async saveLedConfig() {
            try {
                this.ledConfig = this.normalizeLedConfig(await api.put('/api/settings/led', this.ledConfig));
                this.toast('LED 配置已保存', 'success');
            } catch (err) {
                this.toast('保存 LED 配置失败：' + err.message, 'error');
            }
        },

        async powerOffLed() {
            const enabledDevices = this.ledDevices.filter((device) => device.enabled === true || Number(device.enabled || 0) === 1);
            if (!enabledDevices.length) {
                this.ledPowerOffMessage = '没有启用的 LED 设备';
                this.toast(this.ledPowerOffMessage, 'warning');
                return;
            }
            try {
                this.ledPowerOffLoading = true;
                this.ledPowerOffMessage = '';
                const result = await api.post('/api/led/clear', {});
                const errors = result?.errors?.length ? `，失败 ${result.errors.length} 台` : '';
                const detail = result?.errors?.length ? `：${result.errors.join('；')}` : '';
                this.ledPowerOffMessage = `已向 ${result?.cleared_devices?.length || 0} 台设备发送关灯${errors}${detail}`;
                this.toast(this.ledPowerOffMessage, result?.errors?.length ? 'warning' : 'success');
            } catch (err) {
                this.ledPowerOffMessage = err.message;
                this.toast('一键关灯失败：' + err.message, 'error');
            } finally {
                this.ledPowerOffLoading = false;
            }
        },

        async clearLed() {
            const mappingCount = this.ledMappings.length;
            if (!mappingCount) {
                this.ledClearMessage = '没有可清空的 LED 映射';
                this.toast(this.ledClearMessage, 'warning');
                return;
            }
            if (mappingCount && !confirm(`确定清空全部 ${mappingCount} 条 LED 映射配置吗？此操作不会删除设备和灯带。`)) return;
            try {
                this.ledClearLoading = true;
                this.ledClearMessage = '';
                this.ledMappings = this.normalizeLedMappings(await api.put('/api/settings/led/mappings', { mappings: [] }));
                this.ledClearMessage = `已清空 ${mappingCount} 条 LED 映射`;
                this.toast(this.ledClearMessage, 'success');
            } catch (err) {
                this.ledClearMessage = err.message;
                this.toast('清空 LED 映射失败：' + err.message, 'error');
            } finally {
                this.ledClearLoading = false;
            }
        },

        createLedDevice() {
            this.ledDeviceForm = emptyLedDeviceForm();
        },

        editLedDevice(device) {
            this.ledDeviceForm = { ...emptyLedDeviceForm(), ...device, enabled: Number(device.enabled || 0) === 1 };
        },

        cancelLedDeviceForm() {
            this.ledDeviceForm = null;
        },

        async saveLedDevice() {
            const form = { ...this.ledDeviceForm };
            if (!String(form.name || '').trim() || !String(form.host || '').trim()) {
                this.toast('请填写设备名称和地址', 'warning');
                return;
            }
            try {
                const payload = { ...form, port: Number(form.port || 80), enabled: !!form.enabled };
                if (payload.id) await api.put(`/api/settings/led/devices/${payload.id}`, payload);
                else await api.post('/api/settings/led/devices', payload);
                this.ledDeviceForm = null;
                await this.loadLedConfig();
                this.toast('LED 设备已保存', 'success');
            } catch (err) {
                this.toast('保存 LED 设备失败：' + err.message, 'error');
            }
        },

        async deleteLedDevice(device) {
            if (!device?.id || !confirm(`删除 LED 设备「${device.name}」？灯带和映射会一并删除。`)) return;
            try {
                await api.del(`/api/settings/led/devices/${device.id}`);
                await this.loadLedConfig();
                this.toast('LED 设备已删除', 'success');
            } catch (err) {
                this.toast('删除 LED 设备失败：' + err.message, 'error');
            }
        },

        async testLedDevice(deviceId) {
            this.ledTestLoading[deviceId] = true;
            try {
                this.ledTestResults[deviceId] = await api.post(`/api/settings/led/devices/${deviceId}/test`, {});
            } catch (err) {
                this.ledTestResults[deviceId] = { connected: false, error: err.message };
            } finally {
                this.ledTestLoading[deviceId] = false;
            }
        },

        createLedStrip() {
            const firstDevice = this.ledDevices[0];
            this.ledStripForm = { ...emptyLedStripForm(), device_id: firstDevice?.id || '' };
        },

        editLedStrip(strip) {
            this.ledStripForm = { ...emptyLedStripForm(), ...strip };
        },

        cancelLedStripForm() {
            this.ledStripForm = null;
        },

        async saveLedStrip() {
            const form = { ...this.ledStripForm };
            if (!form.device_id || !String(form.name || '').trim()) {
                this.toast('请填写灯带设备和名称', 'warning');
                return;
            }
            try {
                const payload = {
                    ...form,
                    device_id: Number(form.device_id),
                    gpio_num: Number(form.gpio_num || 0),
                    led_count: Number(form.led_count || 0)
                };
                if (payload.id) await api.put(`/api/settings/led/strips/${payload.id}`, payload);
                else await api.post('/api/settings/led/strips', payload);
                this.ledStripForm = null;
                await this.loadLedConfig();
                this.toast('LED 灯带已保存', 'success');
            } catch (err) {
                this.toast('保存 LED 灯带失败：' + err.message, 'error');
            }
        },

        async deleteLedStrip(strip) {
            if (!strip?.id || !confirm(`删除灯带「${strip.name}」？相关映射会一并删除。`)) return;
            try {
                await api.del(`/api/settings/led/strips/${strip.id}`);
                await this.loadLedConfig();
                this.toast('LED 灯带已删除', 'success');
            } catch (err) {
                this.toast('删除 LED 灯带失败：' + err.message, 'error');
            }
        },

        addLedMapping() {
            const firstBox = this.boxes[0];
            const firstStrip = this.ledStrips[0];
            if (!firstBox || !firstStrip) return;
            this.ledMappings.push({
                box_id: firstBox.id,
                strip_id: firstStrip.id,
                led_index: this.nextLedIndex(firstStrip.id),
                color: '#00ff00'
            });
        },

        removeLedMapping(index) {
            this.ledMappings.splice(index, 1);
        },

        async saveLedMappings() {
            try {
                const mappings = this.ledMappings.map((item) => this.prepareLedMapping({ ...item }));
                this.ledMappings = this.normalizeLedMappings(await api.put('/api/settings/led/mappings', { mappings }));
                this.toast('LED 映射已保存', 'success');
            } catch (err) {
                this.toast('保存 LED 映射失败：' + err.message, 'error');
            }
        },

        async locateBox(boxId) {
            if (!boxId) return;
            try {
                await api.post(`/api/led/locate/box/${boxId}`, {});
                this.toast('LED 定位指令已发送', 'success');
            } catch (err) {
                this.toast('LED 定位失败：' + err.message, 'error');
            }
        },

        async locateComponent(componentId) {
            if (!componentId) return;
            try {
                await api.post(`/api/led/locate/component/${componentId}`, {});
                this.toast('LED 定位指令已发送', 'success');
            } catch (err) {
                this.toast('LED 定位失败：' + err.message, 'error');
            }
        },

        async locateBomItems() {
            const boxIds = [...new Set((this.bomData?.items || []).map((item) => item.matched?.box_id).filter(Boolean))];
            if (!boxIds.length) {
                this.toast('当前 BOM 没有可定位的收纳盒', 'warning');
                return;
            }
            try {
                const result = await api.post('/api/led/locate/bom', { box_ids: boxIds });
                const errors = result?.errors?.length ? `，失败 ${result.errors.length} 台` : '';
                this.toast(`已发送 ${result?.led_count || 0} 个 LED 定位${errors}`, result?.errors?.length ? 'warning' : 'success');
            } catch (err) {
                this.toast('BOM LED 定位失败：' + err.message, 'error');
            }
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
        },

        async loadBoxes() {
            try {
                this.boxes = await api.get('/api/boxes');
            } catch (err) {
                this.toast('加载收纳盒失败：' + err.message, 'error');
            }
        },

        async loadCabinets() {
            try {
                this.cabinets = await api.get('/api/cabinets');
            } catch (err) {
                this.toast('加载柜子失败：' + err.message, 'error');
            }
        },

        async loadComponents() {
            try {
                this.loading = true;
                const params = {
                    page: this.componentPagination.page,
                    page_size: this.componentPagination.page_size
                };
                if (this.searchKeyword.trim()) params.keyword = this.searchKeyword.trim();
                if (this.filterCategory) params.category_id = this.filterCategory;
                if (this.filterBox) params.box_id = this.filterBox;
                if (this.filterStock === 'low') params.low_stock = 1;
                const data = await api.get('/api/components', params);
                this.componentList = data.items || [];
                this.componentPagination.total = data.total || 0;
                this.componentPagination.page = data.page || this.componentPagination.page;
                this.componentPagination.page_size = data.page_size || this.componentPagination.page_size;
            } catch (err) {
                this.toast('加载元器件失败：' + err.message, 'error');
            } finally {
                this.loading = false;
            }
        },

        onSearch() {
            this.searchKeyword = this.searchKeyword.trim();
            this.componentPagination.page = 1;
            this.loadComponents();
        },

        clearSearch() {
            this.searchKeyword = '';
            this.componentPagination.page = 1;
            this.loadComponents();
        },

        resetComponentFilters() {
            this.filterCategory = '';
            this.filterBox = '';
            this.filterStock = '';
            this.searchKeyword = '';
            this.componentPagination.page = 1;
            this.loadComponents();
        },

        changePage(delta) {
            const max = Math.max(1, Math.ceil(this.componentPagination.total / this.componentPagination.page_size));
            const next = this.componentPagination.page + delta;
            if (next < 1 || next > max) return;
            this.componentPagination.page = next;
            this.loadComponents();
        },

        openComponentForm(item = null) {
            if (item) {
                this.componentForm = {
                    ...emptyComponentForm(),
                    ...item,
                    tagsInput: (item.tags || []).join(', '),
                    images: (item.images || []).map((img) => ({ id: img.id, url: img.url || img.thumbnail_url })),
                    documents: (item.documents || []).map((doc) => ({
                        id: doc.id,
                        name: doc.name,
                        url: doc.url,
                        file_size: doc.file_size
                    }))
                };
            } else {
                this.componentForm = emptyComponentForm();
            }
            this.availableCells = [];
            this.modal = 'component-form';
            this.$nextTick(async () => {
                if (this.$refs.componentFormPanel) this.$refs.componentFormPanel.scrollTop = 0;
                if (this.componentForm.box_id) await this.onBoxChange(true);
            });
        },

        async onBoxChange(keepSaved = false) {
            const boxId = this.componentForm.box_id;
            const savedRow = this.componentForm.cell_row;
            const savedCol = this.componentForm.cell_col;
            this.availableCells = [];
            if (!keepSaved) {
                this.componentForm.cell_row = '';
                this.componentForm.cell_col = '';
            }
            if (!boxId) return;

            try {
                const grid = await api.get(`/api/boxes/${boxId}/grid`);
                const cells = [];
                for (let r = 0; r < grid.rows; r += 1) {
                    for (let c = 0; c < grid.cols; c += 1) {
                        const cell = grid.cells[r][c];
                        const isCurrent = String(cell.id || cell.row) === String(savedRow);
                        cells.push({
                            id: cell.id || cell.row,
                            row: cell.row,
                            col: cell.col,
                            grid_row: cell.grid_row,
                            grid_col: cell.grid_col,
                            label: cell.label,
                            occupied: !!cell.component && !isCurrent
                        });
                    }
                }
                this.availableCells = cells;
                if (keepSaved && savedRow) {
                    const exists = cells.find((cell) => String(cell.id) === String(savedRow));
                    if (exists) {
                        this.componentForm.cell_row = savedRow;
                        this.componentForm.cell_col = savedCol || exists.col;
                    }
                }
            } catch (err) {
                this.toast('加载格子失败：' + err.message, 'error');
            }
        },

        onCellSelect() {
            const selected = this.availableCells.find((cell) => String(cell.id) === String(this.componentForm.cell_row));
            this.componentForm.cell_col = selected ? selected.col : '';
        },

        async uploadComponentImage(file) {
            if (!file) return;
            try {
                this.loadingOverlay = true;
                const image = await uploadFile('/api/images/upload', file);
                this.componentForm.images.push({ id: image.id, url: image.url });
            } catch (err) {
                this.toast('图片上传失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        removeImage(index) {
            this.componentForm.images.splice(index, 1);
        },

        async uploadComponentDocument(file) {
            if (!file) return;
            try {
                this.loadingOverlay = true;
                const document = await uploadFile('/api/documents/upload', file);
                this.componentForm.documents.push(document);
            } catch (err) {
                this.toast('文档上传失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        removeDocument(index) {
            this.componentForm.documents.splice(index, 1);
        },

        formatFileSize(size) {
            const bytes = Number(size || 0);
            if (!bytes) return '-';
            if (bytes < 1024) return `${bytes} B`;
            if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
            return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
        },

        async saveComponent() {
            const form = { ...this.componentForm };
            if (!form.name.trim()) {
                this.toast('请填写元器件名称', 'warning');
                return;
            }

            form.tags = String(form.tagsInput || '').split(/[,，]/).map((tag) => tag.trim()).filter(Boolean);
            form.images = (form.images || []).map((img) => img.id || img.url).filter(Boolean);
            form.documents = (form.documents || []).map((doc) => doc.id || doc.url).filter(Boolean);
            form.category_id = form.category_id || null;
            form.box_id = form.box_id || null;
            form.cell_row = form.box_id ? (form.cell_row || null) : null;
            form.cell_col = form.box_id ? (form.cell_col || null) : null;
            delete form.tagsInput;

            try {
                this.loadingOverlay = true;
                if (form.id) {
                    await api.put(`/api/components/${form.id}`, form);
                    logAction('UPDATE', `更新元器件 ID=${form.id} 名称=${form.name}`);
                    this.toast('元器件已更新', 'success');
                } else {
                    const created = await api.post('/api/components', form);
                    logAction('CREATE', `新增元器件 ID=${created?.id || '-'} 名称=${form.name}`);
                    this.toast('元器件已创建', 'success');
                }
                this.closeModal();
                await Promise.all([this.loadComponents(), this.loadBoxes(), this.loadDashboard()]);
            } catch (err) {
                this.toast('保存失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async openComponentDetail(id) {
            try {
                this.loadingOverlay = true;
                this.currentComponent = await api.get(`/api/components/${id}`);
                this.modal = 'component-detail';
            } catch (err) {
                this.toast('加载详情失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async openComponentFromUrl() {
            const params = new URLSearchParams(window.location.search);
            const componentId = Number(params.get('component') || params.get('component_id') || 0);
            if (!componentId) return;
            this.page = 'components';
            await this.loadComponents();
            await this.openComponentDetail(componentId);
        },

        componentQrUrl(id) {
            return `/api/components/${id}/qr.svg`;
        },

        openComponentQrLabels(ids = null) {
            const params = new URLSearchParams();
            const componentIds = (ids && ids.length ? ids : []).filter(Boolean);
            if (componentIds.length) {
                params.set('ids', componentIds.join(','));
            } else {
                if (!this.componentPagination.total) {
                    this.toast('没有可生成二维码的元器件', 'warning');
                    return;
                }
                params.set('page', '1');
                params.set('page_size', '500');
                if (this.searchKeyword.trim()) params.set('keyword', this.searchKeyword.trim());
                if (this.filterCategory) params.set('category_id', this.filterCategory);
                if (this.filterBox) params.set('box_id', this.filterBox);
                if (this.filterStock === 'low') params.set('low_stock', '1');
            }
            if (!params.toString()) {
                this.toast('没有可生成二维码的元器件', 'warning');
                return;
            }
            window.open(`/components/qr-labels?${params.toString()}`, '_blank');
        },

        openCurrentComponentQrLabel() {
            if (!this.currentComponent) return;
            this.openComponentQrLabels([this.currentComponent.id]);
        },

        editCurrentComponent() {
            if (!this.currentComponent) return;
            const item = this.currentComponent;
            this.closeModal();
            this.openComponentForm(item);
        },

        async deleteCurrentComponent() {
            if (!this.currentComponent) return;
            if (!confirm(`确定删除「${this.currentComponent.name}」吗？`)) return;
            try {
                this.loadingOverlay = true;
                await api.del(`/api/components/${this.currentComponent.id}`);
                logAction('DELETE', `删除元器件 ID=${this.currentComponent.id} 名称=${this.currentComponent.name}`);
                this.toast('元器件已删除', 'success');
                this.closeModal();
                await Promise.all([this.loadComponents(), this.loadBoxes(), this.loadDashboard()]);
            } catch (err) {
                this.toast('删除失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        openStockModal(type) {
            this.stockForm = { type, quantity: 1, reason: '' };
            this.modal = 'stock';
        },

        async submitStock() {
            if (!this.currentComponent) return;
            const quantity = Number(this.stockForm.quantity || 0);
            if (quantity < 1) {
                this.toast('数量必须大于 0', 'warning');
                return;
            }
            try {
                this.loadingOverlay = true;
                await api.post(`/api/stock/${this.stockForm.type}`, {
                    component_id: this.currentComponent.id,
                    quantity,
                    reason: this.stockForm.reason
                });
                logAction('STOCK', `${this.stockForm.type === 'in' ? '入库' : '出库'} 元器件ID=${this.currentComponent.id} 数量=${quantity}`);
                this.currentComponent = await api.get(`/api/components/${this.currentComponent.id}`);
                this.toast('库存已更新', 'success');
                this.modal = 'component-detail';
                await Promise.all([this.loadComponents(), this.loadDashboard()]);
            } catch (err) {
                this.toast('库存操作失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        openBoxForm(box = null) {
            this.boxForm = box ? {
                id: box.id,
                name: box.name || '',
                rows: box.rows || 4,
                cols: box.cols || 6,
                color: box.color || '#84b59b',
                cabinet_id: box.cabinet_id || '',
                cabinet_slot: box.cabinet_slot || 0,
                description: box.description || ''
            } : emptyBoxForm();
            this.modal = 'box-form';
        },

        editBox(box) {
            this.openBoxForm(box);
        },

        async saveBox() {
            const { id, name, rows, cols, color, cabinet_id, cabinet_slot, description } = this.boxForm;
            if (!String(name || '').trim()) {
                this.toast('请填写收纳盒名称', 'warning');
                return;
            }
            try {
                this.loadingOverlay = true;
                const payload = {
                    name: name.trim(),
                    rows: Number(rows),
                    cols: Number(cols),
                    color,
                    cabinet_id: cabinet_id ? Number(cabinet_id) : null,
                    cabinet_slot: Number(cabinet_slot || 0),
                    description: description || null
                };
                if (id) {
                    await api.put(`/api/boxes/${id}`, payload);
                    logAction('UPDATE', `更新收纳盒 ID=${id} 名称=${payload.name}`);
                    this.toast('收纳盒已更新', 'success');
                } else {
                    const created = await api.post('/api/boxes', payload);
                    logAction('CREATE', `新增收纳盒 ID=${created?.id || '-'} 名称=${payload.name}`);
                    this.toast('收纳盒已创建', 'success');
                }
                this.closeModal();
                await Promise.all([this.loadBoxes(), this.loadCabinets(), this.loadDashboard()]);
                if (this.currentBox?.id === id) await this.viewBoxDetail(id);
                if (this.page === 'map') await this.loadMapData();
            } catch (err) {
                this.toast('保存收纳盒失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async deleteBox(box) {
            if (!box?.id) return;
            if (!confirm(`确定删除「${box.name}」吗？盒内有元器件时后端会拒绝删除。`)) return;
            try {
                this.loadingOverlay = true;
                await api.del(`/api/boxes/${box.id}`);
                logAction('DELETE', `删除收纳盒 ID=${box.id} 名称=${box.name}`);
                this.toast('收纳盒已删除', 'success');
                if (this.currentBox?.id === box.id) {
                    this.currentBox = null;
                    this.boxGrid = [];
                    this.page = 'boxes';
                }
                await Promise.all([this.loadBoxes(), this.loadDashboard()]);
            } catch (err) {
                this.toast('删除收纳盒失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        openCabinetForm(cabinet = null) {
            this.cabinetForm = cabinet ? {
                id: cabinet.id,
                name: cabinet.name || '',
                color: cabinet.color || '#8b9aae',
                description: cabinet.description || ''
            } : emptyCabinetForm();
            this.modal = 'cabinet-form';
        },

        async saveCabinet() {
            const { id, name, color, description } = this.cabinetForm;
            if (!String(name || '').trim()) {
                this.toast('请填写柜子名称', 'warning');
                return;
            }
            try {
                this.loadingOverlay = true;
                const payload = { name: name.trim(), color, description: description || null };
                if (id) {
                    await api.put(`/api/cabinets/${id}`, payload);
                    this.toast('柜子已更新', 'success');
                } else {
                    await api.post('/api/cabinets', payload);
                    this.toast('柜子已创建', 'success');
                }
                this.closeModal();
                await Promise.all([this.loadCabinets(), this.loadBoxes()]);
                if (this.page === 'map') await this.loadMapData();
            } catch (err) {
                this.toast('保存柜子失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async deleteCabinet(cabinet) {
            if (!cabinet?.id) return;
            if (!confirm(`确定删除柜子「${cabinet.name}」吗？柜子里有收纳盒时会被后端拒绝。`)) return;
            try {
                this.loadingOverlay = true;
                await api.del(`/api/cabinets/${cabinet.id}`);
                this.toast('柜子已删除', 'success');
                await Promise.all([this.loadCabinets(), this.loadBoxes()]);
                if (this.page === 'map') await this.loadMapData();
            } catch (err) {
                this.toast('删除柜子失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async viewBoxDetail(id) {
            try {
                this.loading = true;
                const [box, grid] = await Promise.all([
                    api.get(`/api/boxes/${id}`),
                    api.get(`/api/boxes/${id}/grid`)
                ]);
                this.currentBox = box;
                this.boxGrid = [];
                for (let r = 0; r < grid.rows; r += 1) {
                    for (let c = 0; c < grid.cols; c += 1) {
                        this.boxGrid.push(grid.cells[r][c]);
                    }
                }
                this.page = 'box-detail';
            } catch (err) {
                this.toast('加载收纳盒详情失败：' + err.message, 'error');
            } finally {
                this.loading = false;
            }
        },

        async importExcel() {
            this.$refs.importInput?.click();
        },

        async handleImportFile(file) {
            if (!file) return;
            try {
                this.loadingOverlay = true;
                const result = await uploadFile('/api/components/import', file);
                logAction('IMPORT', `元器件导入完成 type=${result.file_type || '-'} success=${result.success || 0} failed=${result.failed || 0}`);
                this.toast(`导入完成：成功 ${result.success || 0} 条，失败 ${result.failed || 0} 条`, result.failed ? 'warning' : 'success');
                await Promise.all([this.loadComponents(), this.loadBoxes(), this.loadDashboard()]);
            } catch (err) {
                this.toast('导入失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async exportExcel() {
            try {
                this.loadingOverlay = true;
                await downloadFile('/api/components/export', null, 'components_export.xlsx');
                logAction('EXPORT', '导出元器件清单');
                this.toast('导出已开始', 'success');
            } catch (err) {
                this.toast('导出失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async loadMapData() {
            try {
                this.loading = true;
                const data = await api.get('/api/map');
                this.mapBackgroundUrl = data.map_background || '';
                const cellSize = 22;
                const gap = 4;
                const allBoxes = (data.boxes || []).map((box, index) => ({
                    ...box,
                    position_x: Number(box.position_x ?? (index % 4) * 210),
                    position_y: Number(box.position_y ?? Math.floor(index / 4) * 170),
                    mapWidth: Math.max(126, box.cols * cellSize + (box.cols - 1) * gap + 28),
                    mapHeight: Math.max(112, box.rows * cellSize + (box.rows - 1) * gap + 54),
                    cells: Array.from({ length: box.rows * box.cols }, (_, cellIndex) => ({
                        idx: cellIndex,
                        occupied: cellIndex < Number(box.occupied_count || 0)
                    })),
                    pickLabels: []
                }));
                const boxesByCabinet = allBoxes.reduce((result, box) => {
                    if (box.cabinet_id) {
                        const key = String(box.cabinet_id);
                        if (!result[key]) result[key] = [];
                        result[key].push(box);
                    }
                    return result;
                }, {});
                this.mapBoxes = allBoxes.filter((box) => !box.cabinet_id);
                this.mapCabinets = (data.cabinets || []).map((cabinet, index) => ({
                    ...cabinet,
                    position_x: Number(cabinet.position_x ?? (index % 3) * 260),
                    position_y: Number(cabinet.position_y ?? Math.floor(index / 3) * 210),
                    mapWidth: 220,
                    mapHeight: 168,
                    boxes: (boxesByCabinet[String(cabinet.id)] || [])
                        .sort((a, b) => Number(a.cabinet_slot || 0) - Number(b.cabinet_slot || 0) || String(a.name).localeCompare(String(b.name)))
                }));
                this.updateMapPickLabels();
            } catch (err) {
                this.toast('加载地图失败：' + err.message, 'error');
            } finally {
                this.loading = false;
            }
        },

        async uploadMapBackground(event) {
            const file = event.target.files?.[0];
            if (!file) return;
            try {
                this.loadingOverlay = true;
                const result = await uploadFile('/api/map/background', file);
                this.mapBackgroundUrl = result?.url || '';
                this.toast('背景图已上传', 'success');
            } catch (err) {
                this.toast('上传背景图失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
                event.target.value = '';
            }
        },

        async clearMapBackground() {
            if (!this.mapBackgroundUrl) return;
            if (!confirm('确定清除自定义背景图吗？')) return;
            try {
                this.loadingOverlay = true;
                await api.del('/api/map/background');
                this.mapBackgroundUrl = '';
                this.toast('背景图已清除', 'success');
            } catch (err) {
                this.toast('清除背景图失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        mapViewportStyle() {
            return `transform: translate(${this.mapState.panX}px, ${this.mapState.panY}px) scale(${this.mapState.scale});`;
        },

        resetMapView() {
            this.mapState = { panX: 48, panY: 48, scale: 1 };
        },

        zoomMap(delta) {
            this.mapState.scale = Math.max(0.35, Math.min(2.8, Number((this.mapState.scale + delta).toFixed(2))));
        },

        panMapStart(event) {
            if (event.target.closest('.map-box') || event.target.closest('.map-cabinet')) return;
            if (event.touches && event.touches.length === 2) {
                if (event.cancelable) event.preventDefault();
                const center = this.touchCenter(event);
                this.dragState = {
                    type: 'pinch',
                    distance: this.touchDistance(event),
                    scale: this.mapState.scale,
                    centerX: center.x,
                    centerY: center.y
                };
                this._panMapMove = this.panMapMove.bind(this);
                this._endPointerWork = this.endPointerWork.bind(this);
                window.addEventListener('touchmove', this._panMapMove, { passive: false });
                window.addEventListener('touchend', this._endPointerWork);
                window.addEventListener('touchcancel', this._endPointerWork);
                return;
            }
            const point = this.eventPoint(event);
            this.dragState = { type: 'pan', x: point.x, y: point.y };
            this._panMapMove = this.panMapMove.bind(this);
            this._endPointerWork = this.endPointerWork.bind(this);
            window.addEventListener('mousemove', this._panMapMove);
            window.addEventListener('mouseup', this._endPointerWork);
            window.addEventListener('touchmove', this._panMapMove, { passive: false });
            window.addEventListener('touchend', this._endPointerWork);
        },

        panMapMove(event) {
            if (!this.dragState) return;
            if (this.dragState.type === 'pinch' && event.touches && event.touches.length === 2) {
                if (event.cancelable) event.preventDefault();
                const nextDistance = this.touchDistance(event);
                if (!this.dragState.distance) return;
                const nextScale = Math.max(0.35, Math.min(2.8, this.dragState.scale * (nextDistance / this.dragState.distance)));
                const ratio = nextScale / this.mapState.scale;
                this.mapState.panX = this.dragState.centerX - (this.dragState.centerX - this.mapState.panX) * ratio;
                this.mapState.panY = this.dragState.centerY - (this.dragState.centerY - this.mapState.panY) * ratio;
                this.mapState.scale = nextScale;
                return;
            }
            if (this.dragState.type !== 'pan') return;
            if (event.cancelable) event.preventDefault();
            const point = this.eventPoint(event);
            this.mapState.panX += point.x - this.dragState.x;
            this.mapState.panY += point.y - this.dragState.y;
            this.dragState.x = point.x;
            this.dragState.y = point.y;
        },

        startDragBox(box, event) {
            if (event.touches && event.touches.length > 1) return;
            event.stopPropagation();
            const point = this.eventPoint(event);
            this.draggingBox = box;
            this.dragState = {
                type: 'box',
                id: box.id,
                x: point.x,
                y: point.y,
                startX: point.x,
                startY: point.y,
                moved: false
            };
            this._dragBoxMove = this.dragBoxMove.bind(this);
            this._endPointerWork = this.endPointerWork.bind(this);
            window.addEventListener('mousemove', this._dragBoxMove);
            window.addEventListener('mouseup', this._endPointerWork);
            window.addEventListener('touchmove', this._dragBoxMove, { passive: false });
            window.addEventListener('touchend', this._endPointerWork);
        },

        dragBoxMove(event) {
            if (!this.dragState || this.dragState.type !== 'box' || !this.draggingBox) return;
            if (event.cancelable) event.preventDefault();
            const point = this.eventPoint(event);
            const dx = (point.x - this.dragState.x) / this.mapState.scale;
            const dy = (point.y - this.dragState.y) / this.mapState.scale;
            if (Math.abs(point.x - this.dragState.startX) > 4 || Math.abs(point.y - this.dragState.startY) > 4) {
                this.dragState.moved = true;
            }
            this.draggingBox.position_x = Number(this.draggingBox.position_x || 0) + dx;
            this.draggingBox.position_y = Number(this.draggingBox.position_y || 0) + dy;
            this.dragState.x = point.x;
            this.dragState.y = point.y;
            this.mapDirty = true;
        },

        startDragCabinet(cabinet, event) {
            if (event.touches && event.touches.length > 1) return;
            // 如果点击的是柜子内部的可交互元素（收纳盒、编辑/删除按钮、把手、查看按钮），不启动柜子拖拽
            const target = event.target;
            if (target.closest('.cabinet-box-model, .cabinet-edit, .cabinet-delete, .cabinet-handle, .cabinet-box-open')) {
                return;
            }
            event.stopPropagation();
            const point = this.eventPoint(event);
            this.draggingCabinet = cabinet;
            this.dragState = {
                type: 'cabinet',
                id: cabinet.id,
                x: point.x,
                y: point.y,
                startX: point.x,
                startY: point.y,
                moved: false
            };
            this._dragCabinetMove = this.dragCabinetMove.bind(this);
            this._endPointerWork = this.endPointerWork.bind(this);
            window.addEventListener('mousemove', this._dragCabinetMove);
            window.addEventListener('mouseup', this._endPointerWork);
            window.addEventListener('touchmove', this._dragCabinetMove, { passive: false });
            window.addEventListener('touchend', this._endPointerWork);
        },

        dragCabinetMove(event) {
            if (!this.dragState || this.dragState.type !== 'cabinet' || !this.draggingCabinet) return;
            if (event.cancelable) event.preventDefault();
            const point = this.eventPoint(event);
            const dx = (point.x - this.dragState.x) / this.mapState.scale;
            const dy = (point.y - this.dragState.y) / this.mapState.scale;
            if (Math.abs(point.x - this.dragState.startX) > 4 || Math.abs(point.y - this.dragState.startY) > 4) {
                this.dragState.moved = true;
            }
            this.draggingCabinet.position_x = Number(this.draggingCabinet.position_x || 0) + dx;
            this.draggingCabinet.position_y = Number(this.draggingCabinet.position_y || 0) + dy;
            this.dragState.x = point.x;
            this.dragState.y = point.y;
            this.mapDirty = true;
        },

        toggleCabinet(cabinet) {
            const id = cabinet?.id;
            if (!id) return;
            if (this.expandedCabinets.includes(id)) {
                this.expandedCabinets = this.expandedCabinets.filter((item) => item !== id);
            } else {
                this.expandedCabinets = [...this.expandedCabinets, id];
            }
        },

        isCabinetExpanded(cabinet) {
            return this.expandedCabinets.includes(cabinet?.id);
        },

        endPointerWork() {
            if (this.dragState?.type === 'box' && this.draggingBox && !this.dragState.moved) {
                this.viewBoxDetail(this.draggingBox.id);
            }
            this.draggingBox = null;
            this.draggingCabinet = null;
            this.dragState = null;
            if (this._panMapMove) {
                window.removeEventListener('mousemove', this._panMapMove);
                window.removeEventListener('touchmove', this._panMapMove);
            }
            if (this._dragBoxMove) {
                window.removeEventListener('mousemove', this._dragBoxMove);
                window.removeEventListener('touchmove', this._dragBoxMove);
            }
            if (this._dragCabinetMove) {
                window.removeEventListener('mousemove', this._dragCabinetMove);
                window.removeEventListener('touchmove', this._dragCabinetMove);
            }
            if (this._endPointerWork) {
                window.removeEventListener('mouseup', this._endPointerWork);
                window.removeEventListener('touchend', this._endPointerWork);
                window.removeEventListener('touchcancel', this._endPointerWork);
            }
            this._panMapMove = null;
            this._dragBoxMove = null;
            this._dragCabinetMove = null;
            this._endPointerWork = null;
        },

        eventPoint(event) {
            const source = event.touches?.[0] || event.changedTouches?.[0] || event;
            return { x: source.clientX, y: source.clientY };
        },

        touchDistance(event) {
            const [a, b] = event.touches;
            return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
        },

        touchCenter(event) {
            const [a, b] = event.touches;
            return {
                x: (a.clientX + b.clientX) / 2,
                y: (a.clientY + b.clientY) / 2
            };
        },

        async saveMapLayout() {
            try {
                this.loadingOverlay = true;
                await Promise.all([
                    ...this.mapBoxes.map((box) => api.put(`/api/boxes/${box.id}/layout`, {
                        position_x: Math.round(Number(box.position_x || 0)),
                        position_y: Math.round(Number(box.position_y || 0))
                    })),
                    ...this.mapCabinets.map((cabinet) => api.put(`/api/cabinets/${cabinet.id}/layout`, {
                        position_x: Math.round(Number(cabinet.position_x || 0)),
                        position_y: Math.round(Number(cabinet.position_y || 0))
                    }))
                ]);
                this.mapDirty = false;
                logAction('UPDATE', '保存地图布局');
                this.toast('地图布局已保存', 'success');
            } catch (err) {
                this.toast('保存布局失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async importBom(file) {
            if (!file) return;
            try {
                this.loadingOverlay = true;
                const data = await uploadFile('/api/bom/import', file);
                this.bomData = data;
                this.bomSelectedRows = [];
                this.computeBomStats();
                logAction('BOM', `导入 BOM ${data.project_name || file.name}`);
                this.toast('BOM 已解析', 'success');
            } catch (err) {
                this.toast('BOM 导入失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async openBomMatcher(index) {
            if (!this.bomData?.items?.[index]) return;
            const item = this.bomData.items[index];
            this.bomManualRowIndex = index;
            this.bomManualKeyword = [item.comment, item.footprint].filter(Boolean).join(' ').trim();
            this.bomManualResults = [];
            this.modal = 'bom-match';
            await this.searchBomComponents();
        },

        async searchBomComponents() {
            try {
                this.bomManualLoading = true;
                const data = await api.get('/api/components', {
                    keyword: this.bomManualKeyword || '',
                    page: 1,
                    page_size: 30
                });
                this.bomManualResults = data?.items || [];
            } catch (err) {
                this.toast('搜索元器件失败：' + err.message, 'error');
            } finally {
                this.bomManualLoading = false;
            }
        },

        manualMatchPayload(component) {
            if (!component) return null;
            return {
                id: component.id,
                name: component.name,
                model: component.model,
                package: component.package,
                quantity: component.quantity,
                box_id: component.box_id,
                box_name: component.box_name,
                cell_label: component.cell_label,
                row: component.grid_row,
                col: component.grid_col
            };
        },

        assignBomComponent(component) {
            if (this.bomManualRowIndex === null || !this.bomData?.items?.[this.bomManualRowIndex]) return;
            this.bomData.items[this.bomManualRowIndex].matched = this.manualMatchPayload(component);
            this.bomData.items[this.bomManualRowIndex].match_level = 'manual';
            this.computeBomStats();
            this.updateMapPickLabels();
            this.toast('已手动指定元器件', 'success');
            this.closeModal();
        },

        clearBomMatch(index = this.bomManualRowIndex) {
            if (index === null || !this.bomData?.items?.[index]) return;
            this.bomData.items[index].matched = null;
            this.bomData.items[index].match_level = null;
            this.computeBomStats();
            this.updateMapPickLabels();
            this.toast('已清除该行匹配', 'success');
            if (this.modal === 'bom-match') this.closeModal();
        },

        bomMatchLabel(item) {
            if (!item?.match_level) return '';
            return item.match_level === 'manual' ? '手动' : '自动';
        },

        removeBomItem(index) {
            if (!this.bomData?.items?.[index]) return;
            const item = this.bomData.items[index];
            const label = item.designator || item.comment || `第 ${index + 1} 行`;
            if (!confirm(`确定从当前 BOM 中删除「${label}」吗？`)) return;
            this.bomData.items.splice(index, 1);
            this.bomSelectedRows = this.bomSelectedRows
                .filter((rowIndex) => rowIndex !== index)
                .map((rowIndex) => rowIndex > index ? rowIndex - 1 : rowIndex);
            this.bomData.total_types = this.bomData.items.length;
            this.computeBomStats();
            this.updateMapPickLabels();
            this.toast('已从 BOM 中删除该行', 'success');
        },

        toggleBomRowSelection(index, checked) {
            if (checked) {
                if (!this.bomSelectedRows.includes(index)) {
                    this.bomSelectedRows = [...this.bomSelectedRows, index].sort((a, b) => a - b);
                }
                return;
            }
            this.bomSelectedRows = this.bomSelectedRows.filter((rowIndex) => rowIndex !== index);
        },

        toggleAllBomRows(checked) {
            const total = this.bomData?.items?.length || 0;
            this.bomSelectedRows = checked ? Array.from({ length: total }, (_, index) => index) : [];
        },

        allBomRowsSelected() {
            const total = this.bomData?.items?.length || 0;
            return total > 0 && this.bomSelectedRows.length === total;
        },

        removeSelectedBomItems() {
            if (!this.bomSelectedRows.length) {
                this.toast('请先选择要删除的 BOM 行', 'warning');
                return;
            }
            if (!confirm(`确定从当前 BOM 中删除选中的 ${this.bomSelectedRows.length} 行吗？`)) return;
            const selected = new Set(this.bomSelectedRows);
            this.bomData.items = this.bomData.items.filter((_, index) => !selected.has(index));
            this.bomSelectedRows = [];
            this.bomData.total_types = this.bomData.items.length;
            this.computeBomStats();
            this.updateMapPickLabels();
            this.toast('已删除选中的 BOM 行', 'success');
        },

        computeBomStats() {
            const items = this.bomData?.items || [];
            const matched = items.filter((item) => item.matched).length;
            const shortage = items.filter((item) => item.matched && Number(item.matched.quantity || 0) < Number(item.quantity_needed || 0)).length;
            this.bomStats = {
                total: items.length,
                matched,
                shortage,
                unmatched: items.length - matched
            };
        },

        async consumeBom() {
            if (!this.bomData?.items?.length) return;
            if (!confirm('确定按当前 BOM 匹配结果扣减库存吗？')) return;
            try {
                this.loadingOverlay = true;
                const result = await api.post('/api/bom/consume', { items: this.bomData.items });
                logAction('BOM', `BOM 扣库存完成 processed=${result.processed || 0}`);
                this.toast(`已扣减 ${result.processed || 0} 条库存`, 'success');
                await Promise.all([this.loadComponents(), this.loadDashboard()]);
            } catch (err) {
                this.toast('BOM 扣库存失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async exportBom() {
            if (!this.bomData?.items?.length) return;
            try {
                this.loadingOverlay = true;
                await downloadPostFile('/api/bom/export', { items: this.bomData.items }, 'bom_picklist.xlsx');
                logAction('EXPORT', '导出 BOM 取料清单');
                this.toast('BOM 清单已导出', 'success');
            } catch (err) {
                this.toast('BOM 导出失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
        },

        async gotoBomMap() {
            if (!this.bomData?.items?.length) return;
            await this.loadMapData();
            const ids = (this.bomData.items || [])
                .filter((item) => item.matched?.box_id)
                .map((item) => item.matched.box_id);
            this.mapHighlights = [...new Set(ids)];
            this.updateMapPickLabels();
            this.page = 'map';
        },

        async gotoMapHighlight(boxId) {
            await this.loadMapData();
            this.mapHighlights = [boxId];
            this.updateMapPickLabels();
            this.page = 'map';
        },

        updateMapPickLabels() {
            const items = (this.bomData?.items || []).filter((item) => item.matched?.box_id);
            const order = [];
            items.forEach((item) => {
                if (!order.includes(item.matched.box_id)) order.push(item.matched.box_id);
            });
            this.mapBoxes = this.mapBoxes.map((box) => ({
                ...box,
                pickLabels: order.includes(box.id) ? [{ num: order.indexOf(box.id) + 1 }] : []
            }));
            this.mapCabinets = this.mapCabinets.map((cabinet) => ({
                ...cabinet,
                boxes: (cabinet.boxes || []).map((box) => ({
                    ...box,
                    pickLabels: order.includes(box.id) ? [{ num: order.indexOf(box.id) + 1 }] : []
                }))
            }));
        },

        hexToRgb(color) {
            const value = String(color || '').replace('#', '');
            if (!/^[0-9a-fA-F]{6}$/.test(value)) return { r: 132, g: 181, b: 155 };
            return {
                r: parseInt(value.slice(0, 2), 16),
                g: parseInt(value.slice(2, 4), 16),
                b: parseInt(value.slice(4, 6), 16)
            };
        },

        rgba(color, alpha) {
            const { r, g, b } = this.hexToRgb(color);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        },

        shadeColor(color, amount = 0) {
            const { r, g, b } = this.hexToRgb(color);
            const mix = (channel) => {
                const target = amount >= 0 ? 255 : 0;
                return Math.round(channel + (target - channel) * Math.abs(amount));
            };
            return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
        },

        getMapBoxStyle(box) {
            const color = box.color || '#84b59b';
            return [
                `left:${box.position_x || 0}px`,
                `top:${box.position_y || 0}px`,
                `width:${box.mapWidth}px`,
                `height:${box.mapHeight}px`,
                `--box-accent:${color}`,
                `--box-accent-light:${this.shadeColor(color, 0.24)}`,
                `--box-accent-deep:${this.shadeColor(color, -0.28)}`,
                `--box-accent-soft:${this.rgba(color, 0.22)}`,
                `--box-accent-pale:${this.rgba(color, 0.10)}`,
                `--box-shadow-color:${this.rgba(color, 0.26)}`,
                `--box-accent-border:${this.rgba(color, 0.55)}`
            ].join(';');
        },

        getMapCabinetStyle(cabinet) {
            const color = cabinet.color || '#8b9aae';
            const open = this.isCabinetExpanded(cabinet);
            return [
                `left:${cabinet.position_x || 0}px`,
                `top:${cabinet.position_y || 0}px`,
                `width:${cabinet.mapWidth || 220}px`,
                `height:${open ? 292 : (cabinet.mapHeight || 168)}px`,
                `--cabinet-accent:${color}`,
                `--cabinet-accent-light:${this.shadeColor(color, 0.22)}`,
                `--cabinet-accent-deep:${this.shadeColor(color, -0.25)}`,
                `--cabinet-accent-soft:${this.rgba(color, 0.18)}`,
                `--cabinet-shadow-color:${this.rgba(color, 0.24)}`
            ].join(';');
        },

        isScannerAvailable() {
            return !!window.Html5Qrcode;
        },

        openScanner() {
            this.scannerManualText = '';
            this.scannerError = '';
            this.modal = 'scanner';
            this.$nextTick(() => {
                if (!this.isScannerAvailable()) {
                    this.scannerError = window.__scannerLibLoadErrorMessage || '扫码库未加载，可使用手动输入。';
                    this.toast(this.scannerError, 'warning');
                    return;
                }
                startScanner((text) => {
                    this.closeScanner();
                    this.toast('已识别：' + text, 'success');
                    logAction('SCAN', '扫码识别：' + text);
                    this.autoFillFromScan(text);
                }, (err) => {
                    this.scannerError = this.friendlyScannerError(err);
                    this.toast(this.scannerError, 'warning');
                });
            });
        },

        friendlyScannerError(err) {
            const message = String(err || '').trim();
            const lower = message.toLowerCase();
            if (
                lower.includes('camera streaming not supported') ||
                lower.includes('not supported') ||
                lower.includes('getusermedia') ||
                lower.includes('notreadable') ||
                lower.includes('notallowed')
            ) {
                return '当前浏览器不支持实时摄像头扫码，请使用“从图片识别”或手动输入。';
            }
            if (!message) {
                return '当前浏览器无法开启摄像头，请使用图片识别或手动输入。';
            }
            return `摄像头扫码不可用：${message}。可以继续使用图片识别或手动输入。`;
        },

        closeScanner() {
            this.modal = null;
            this.scannerError = '';
            stopScanner().catch(() => {});
        },

        submitManualScan() {
            const text = this.scannerManualText.trim();
            if (!text) {
                this.toast('请输入扫码内容', 'warning');
                return;
            }
            logAction('SCAN', '手动录入扫码内容：' + text);
            this.closeScanner();
            this.autoFillFromScan(text);
        },

        handleScannerImage(file) {
            if (!file) return;
            this.scannerError = '';
            scanImageFile(file, (text) => {
                this.toast('图片识别成功：' + text, 'success');
                logAction('SCAN', '图片识别：' + text);
                this.closeScanner();
                this.autoFillFromScan(text);
            }, (err) => {
                this.toast('图片识别失败：' + err, 'error');
            });
        },

        autoFillFromScan(text) {
            const componentId = this.componentIdFromScan(text);
            if (componentId) {
                this.page = 'components';
                this.loadComponents();
                this.openComponentDetail(componentId);
                return;
            }
            this.openComponentForm();
            const parts = String(text || '').split(',').map((part) => part.trim()).filter(Boolean);
            if (parts.length > 1) {
                this.componentForm.name = parts[0] || '';
                this.componentForm.package = parts[1] || '';
                this.componentForm.model = parts[2] || '';
            } else {
                this.componentForm.name = String(text || '').trim();
            }
        },

        componentIdFromScan(text) {
            const raw = String(text || '').trim();
            if (!raw) return 0;
            try {
                const url = new URL(raw, window.location.origin);
                const id = Number(url.searchParams.get('component') || url.searchParams.get('component_id') || 0);
                if (id > 0) return id;
                const match = url.pathname.match(/^\/components?\/(\d+)$/);
                return match ? Number(match[1]) : 0;
            } catch (_) {
                const match = raw.match(/(?:component|component_id)\s*[:=]\s*(\d+)/i);
                return match ? Number(match[1]) : 0;
            }
        },

        async nfcBind() {
            if (!this.nfcBoxId) {
                this.toast('请先选择收纳盒', 'warning');
                return;
            }
            if (!('NDEFReader' in window)) {
                this.toast('当前浏览器不支持 Web NFC 读取', 'error');
                return;
            }
            this.nfcStatus = { type: 'pending', title: '等待 NFC 标签', message: '请将手机靠近标签。' };
            try {
                const result = await readNFCTag();
                await api.post('/api/nfc/bind', { box_id: Number(this.nfcBoxId), uid: result.uid });
                this.nfcStatus = { type: 'success', title: '绑定成功', message: result.uid };
                logAction('NFC', `绑定收纳盒 ID=${this.nfcBoxId} UID=${result.uid}`);
                this.toast('NFC 标签已绑定', 'success');
            } catch (err) {
                this.nfcStatus = { type: 'error', title: '绑定失败', message: err.message };
                logAction('NFC', '绑定失败：' + err.message);
            }
        },

        async nfcWrite() {
            if (!this.nfcBoxId) {
                this.toast('请先选择收纳盒', 'warning');
                return;
            }
            if (!('NDEFWriter' in window)) {
                this.toast('当前浏览器不支持 Web NFC 写入', 'error');
                return;
            }
            this.nfcStatus = { type: 'pending', title: '准备写入', message: '请将手机靠近标签。' };
            try {
                const payload = await api.post('/api/nfc/write', { box_id: Number(this.nfcBoxId) });
                await writeNFCTag([
                    { recordType: 'url', data: payload.url },
                    { recordType: 'text', data: payload.text }
                ]);
                this.nfcStatus = { type: 'success', title: '写入成功', message: payload.url };
                logAction('NFC', `写入 NDEF 收纳盒 ID=${this.nfcBoxId}`);
                this.toast('NDEF 已写入', 'success');
            } catch (err) {
                this.nfcStatus = { type: 'error', title: '写入失败', message: err.message };
                logAction('NFC', '写入失败：' + err.message);
            }
        }
    };
}
