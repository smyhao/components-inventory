// 本文件负责 Token、LED、NFC 与扫码自动化领域的前端状态和交互编排，位于 static/js/features 领域层；只依赖注入的 API、日志、确认框和外设辅助函数，不承载后端业务规则。
(function registerAutomationFeature(global) {
    const modules = global.InventoryModules = global.InventoryModules || {};

    /**
     * 生成 LED 设备表单默认值。
     * 字段名保持与现有模板绑定一致，避免重构影响设置弹窗行为。
     */
    function emptyLedDeviceForm() {
        return {
            id: null,
            name: '',
            host: '',
            port: 80,
            enabled: true
        };
    }

    /**
     * 生成 LED 灯带表单默认值。
     * device_id 在创建时由当前设备列表补齐，这里只提供稳定形状。
     */
    function emptyLedStripForm() {
        return {
            id: null,
            device_id: '',
            name: '',
            gpio_num: 0,
            led_count: 0
        };
    }

    /**
     * 标准化 LED 全局配置。
     * 该函数保持纯输入输出，便于设置页、初始化和保存结果复用。
     */
    function normalizeLedConfig(config = {}) {
        return {
            id: config.id || 1,
            enabled: config.enabled === true || Number(config.enabled || 0) === 1,
            blink_interval_ms: Number(config.blink_interval_ms || 500),
            blink_duration_ms: Number(config.blink_duration_ms || 10000)
        };
    }

    /**
     * 标准化 LED 颜色值。
     * 前端只做格式兜底，颜色含义仍由用户配置和后端定位服务决定。
     */
    function normalizeLedColor(color) {
        const value = String(color || '').trim();
        return /^#[0-9a-fA-F]{6}$/.test(value) ? value.toLowerCase() : '#00ff00';
    }

    /**
     * 标准化 LED 映射列表。
     * 返回新对象数组，避免保存前直接污染接口返回对象。
     */
    function normalizeLedMappings(mappings = []) {
        return (mappings || []).map((item) => ({
            ...item,
            box_id: Number(item.box_id || 0),
            strip_id: Number(item.strip_id || 0),
            led_index: Math.max(0, Number(item.led_index || 0)),
            color: normalizeLedColor(item.color)
        }));
    }

    /**
     * 构建自动化领域 feature。
     * deps 只接收跨领域基础能力；元器件详情和表单入口通过注入函数触发，不直接耦合其他领域内部实现。
     */
    modules.createAutomationFeature = function createAutomationFeature(deps = {}) {
        const apiClient = deps.api;
        const logActionFn = deps.logAction || function noopLogAction() {};
        const confirmFn = deps.confirm || global.confirm.bind(global);
        const startScannerFn = deps.startScanner || global.startScanner;
        const stopScannerFn = deps.stopScanner || global.stopScanner;
        const scanImageFileFn = deps.scanImageFile || global.scanImageFile;
        const readNFCTagFn = deps.readNFCTag || global.readNFCTag;
        const writeNFCTagFn = deps.writeNFCTag || global.writeNFCTag;

        /**
         * 统一发送领域提示，保留调用方现有 toast 渲染。
         */
        function notify(context, message, type = 'info') {
            if (context && typeof context.toast === 'function') {
                context.toast(message, type);
            }
        }

        /**
         * 从扫码文本中解析元器件 ID。
         * 支持现有 URL、query 和 key=value 文本格式，不引入新的业务语义。
         */
        function componentIdFromScan(text) {
            const raw = String(text || '').trim();
            if (!raw) return 0;
            try {
                const url = new URL(raw, global.location.origin);
                const id = Number(url.searchParams.get('component') || url.searchParams.get('component_id') || 0);
                if (id > 0) return id;
                const match = url.pathname.match(/^\/components?\/(\d+)$/);
                return match ? Number(match[1]) : 0;
            } catch (_) {
                const match = raw.match(/(?:component|component_id)\s*[:=]\s*(\d+)/i);
                return match ? Number(match[1]) : 0;
            }
        }

        /**
         * 将扫码结果转给元器件领域入口。
         * 优先使用依赖注入，未注入时回落到当前 Alpine 实例的兼容方法名。
         */
        function openComponentByScan(context, text) {
            const componentId = componentIdFromScan(text);
            if (componentId) {
                if (typeof deps.openComponentById === 'function') {
                    deps.openComponentById.call(context, componentId);
                } else if (typeof context.openComponentDetail === 'function') {
                    context.page = 'components';
                    context.loadComponents();
                    context.openComponentDetail(componentId);
                }
                return;
            }
            if (typeof deps.openComponentFormWithScan === 'function') {
                deps.openComponentFormWithScan.call(context, text);
                return;
            }
            if (typeof context.openComponentForm === 'function') {
                context.openComponentForm();
            }
            const parts = String(text || '').split(',').map((part) => part.trim()).filter(Boolean);
            if (parts.length > 1) {
                context.componentForm.name = parts[0] || '';
                context.componentForm.package = parts[1] || '';
                context.componentForm.model = parts[2] || '';
            } else {
                context.componentForm.name = String(text || '').trim();
            }
        }

        return {
            state: {
                nfcBoxId: '',
                nfcStatus: null,
                nfcSupported: 'NDEFReader' in global || 'NDEFWriter' in global,
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
                ledDeviceForm: emptyLedDeviceForm(),
                ledStripForm: emptyLedStripForm(),
                ledTestResults: {},
                ledTestLoading: {},
                ledSyncLoading: {},
                ledClearLoading: false,
                ledClearMessage: '',
                ledPowerOffLoading: false,
                ledPowerOffMessage: ''
            },

            methods: {
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
                        this.apiTokens = await apiClient.get('/api/settings/tokens');
                    } catch (err) {
                        notify(this, '加载 Token 失败：' + err.message, 'error');
                    }
                },

                async generateApiToken() {
                    const name = (this.tokenForm.name || '').trim();
                    if (!name) {
                        notify(this, '请先填写 Token 名称', 'warn');
                        return;
                    }
                    try {
                        const result = await apiClient.post('/api/settings/tokens', { name });
                        this.generatedToken = result.token;
                        this.tokenForm.name = '';
                        await this.loadApiTokens();
                        notify(this, 'Token 已生成，请立即保存', 'success');
                    } catch (err) {
                        notify(this, '生成 Token 失败：' + err.message, 'error');
                    }
                },

                async copyGeneratedToken() {
                    if (!this.generatedToken) return;
                    try {
                        if (navigator.clipboard && global.isSecureContext) {
                            await navigator.clipboard.writeText(this.generatedToken);
                        } else {
                            this.copyTextFallback(this.generatedToken);
                        }
                        notify(this, 'Token 已复制', 'success');
                    } catch (err) {
                        try {
                            this.copyTextFallback(this.generatedToken);
                            notify(this, 'Token 已复制', 'success');
                        } catch (fallbackErr) {
                            notify(this, '复制失败，请手动选择 Token', 'error');
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
                    if (!confirmFn(`删除 Token "${token.name}"？删除后使用它的设备会立即失效。`)) return;
                    try {
                        await apiClient.del(`/api/settings/tokens/${token.id}`);
                        await this.loadApiTokens();
                        notify(this, 'Token 已删除', 'success');
                    } catch (err) {
                        notify(this, '删除 Token 失败：' + err.message, 'error');
                    }
                },

                normalizeLedConfig,
                normalizeLedColor,
                normalizeLedMappings,

                async loadLedConfig() {
                    try {
                        const data = await apiClient.get('/api/settings/led');
                        this.ledConfig = normalizeLedConfig(data?.config || {});
                        this.ledDevices = data?.devices || [];
                        this.ledStrips = data?.strips || [];
                        this.ledMappings = normalizeLedMappings(data?.mappings || []);
                    } catch (err) {
                        notify(this, '加载 LED 配置失败：' + err.message, 'error');
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
                    mapping.color = normalizeLedColor(mapping.color);
                    return mapping;
                },

                async saveLedConfig() {
                    try {
                        this.ledConfig = normalizeLedConfig(await apiClient.put('/api/settings/led', this.ledConfig));
                        notify(this, 'LED 配置已保存', 'success');
                    } catch (err) {
                        notify(this, '保存 LED 配置失败：' + err.message, 'error');
                    }
                },

                async powerOffLed() {
                    const enabledDevices = this.ledDevices.filter((device) => device.enabled === true || Number(device.enabled || 0) === 1);
                    if (!enabledDevices.length) {
                        this.ledPowerOffMessage = '没有启用的 LED 设备';
                        notify(this, this.ledPowerOffMessage, 'warning');
                        return;
                    }
                    try {
                        this.ledPowerOffLoading = true;
                        this.ledPowerOffMessage = '';
                        const result = await apiClient.post('/api/led/clear', {});
                        const errors = result?.errors?.length ? `，失败 ${result.errors.length} 台` : '';
                        const detail = result?.errors?.length ? `：${result.errors.join('；')}` : '';
                        this.ledPowerOffMessage = `已向 ${result?.cleared_devices?.length || 0} 台设备发送关灯${errors}${detail}`;
                        notify(this, this.ledPowerOffMessage, result?.errors?.length ? 'warning' : 'success');
                    } catch (err) {
                        this.ledPowerOffMessage = err.message;
                        notify(this, '一键关灯失败：' + err.message, 'error');
                    } finally {
                        this.ledPowerOffLoading = false;
                    }
                },

                async clearLed() {
                    const mappingCount = this.ledMappings.length;
                    if (!mappingCount) {
                        this.ledClearMessage = '没有可清空的 LED 映射';
                        notify(this, this.ledClearMessage, 'warning');
                        return;
                    }
                    if (mappingCount && !confirmFn(`确定清空全部 ${mappingCount} 条 LED 映射配置吗？此操作不会删除设备和灯带。`)) return;
                    try {
                        this.ledClearLoading = true;
                        this.ledClearMessage = '';
                        this.ledMappings = normalizeLedMappings(await apiClient.put('/api/settings/led/mappings', { mappings: [] }));
                        this.ledClearMessage = `已清空 ${mappingCount} 条 LED 映射`;
                        notify(this, this.ledClearMessage, 'success');
                    } catch (err) {
                        this.ledClearMessage = err.message;
                        notify(this, '清空 LED 映射失败：' + err.message, 'error');
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
                    this.ledDeviceForm = emptyLedDeviceForm();
                },

                async saveLedDevice() {
                    const form = { ...this.ledDeviceForm };
                    if (!String(form.name || '').trim() || !String(form.host || '').trim()) {
                        notify(this, '请填写设备名称和地址', 'warning');
                        return;
                    }
                    try {
                        const payload = { ...form, port: Number(form.port || 80), enabled: !!form.enabled };
                        if (payload.id) await apiClient.put(`/api/settings/led/devices/${payload.id}`, payload);
                        else await apiClient.post('/api/settings/led/devices', payload);
                        this.ledDeviceForm = emptyLedDeviceForm();
                        await this.loadLedConfig();
                        notify(this, 'LED 设备已保存', 'success');
                    } catch (err) {
                        notify(this, '保存 LED 设备失败：' + err.message, 'error');
                    }
                },

                async deleteLedDevice(device) {
                    if (!device?.id || !confirmFn(`删除 LED 设备「${device.name}」？灯带和映射会一并删除。`)) return;
                    try {
                        await apiClient.del(`/api/settings/led/devices/${device.id}`);
                        await this.loadLedConfig();
                        notify(this, 'LED 设备已删除', 'success');
                    } catch (err) {
                        notify(this, '删除 LED 设备失败：' + err.message, 'error');
                    }
                },

                async testLedDevice(deviceId) {
                    this.ledTestLoading[deviceId] = true;
                    try {
                        this.ledTestResults[deviceId] = await apiClient.post(`/api/settings/led/devices/${deviceId}/test`, {});
                    } catch (err) {
                        this.ledTestResults[deviceId] = { connected: false, error: err.message };
                    } finally {
                        this.ledTestLoading[deviceId] = false;
                    }
                },

                async syncDeviceStrips(deviceId) {
                    this.ledSyncLoading[deviceId] = true;
                    try {
                        const result = await apiClient.post(`/api/settings/led/devices/${deviceId}/sync`, {});
                        if (result?.sync_error) {
                            notify(this, '全量同步失败：' + result.sync_error, 'error');
                        } else {
                            notify(this, `已同步 ${result?.synced_strips || 0} 条灯带到设备`, 'success');
                        }
                    } catch (err) {
                        notify(this, '全量同步失败：' + err.message, 'error');
                    } finally {
                        this.ledSyncLoading[deviceId] = false;
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
                    this.ledStripForm = emptyLedStripForm();
                },

                async saveLedStrip() {
                    const form = { ...this.ledStripForm };
                    if (!form.device_id || !String(form.name || '').trim()) {
                        notify(this, '请填写灯带设备和名称', 'warning');
                        return;
                    }
                    try {
                        const payload = {
                            ...form,
                            device_id: Number(form.device_id),
                            gpio_num: Number(form.gpio_num || 0),
                            led_count: Number(form.led_count || 0)
                        };
                        let result;
                        if (payload.id) result = await apiClient.put(`/api/settings/led/strips/${payload.id}`, payload);
                        else result = await apiClient.post('/api/settings/led/strips', payload);
                        this.ledStripForm = emptyLedStripForm();
                        await this.loadLedConfig();
                        if (result?.sync_warning) {
                            notify(this, '灯带已保存但硬件同步失败：' + result.sync_warning, 'warning');
                        } else {
                            notify(this, 'LED 灯带已保存', 'success');
                        }
                    } catch (err) {
                        notify(this, '保存 LED 灯带失败：' + err.message, 'error');
                    }
                },

                async deleteLedStrip(strip) {
                    if (!strip?.id || !confirmFn(`删除灯带「${strip.name}」？相关映射会一并删除。`)) return;
                    try {
                        const result = await apiClient.del(`/api/settings/led/strips/${strip.id}`);
                        await this.loadLedConfig();
                        if (result?.sync_warning) {
                            notify(this, '灯带已删除但硬件同步失败：' + result.sync_warning, 'warning');
                        } else {
                            notify(this, 'LED 灯带已删除', 'success');
                        }
                    } catch (err) {
                        notify(this, '删除 LED 灯带失败：' + err.message, 'error');
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
                        this.ledMappings = normalizeLedMappings(await apiClient.put('/api/settings/led/mappings', { mappings }));
                        notify(this, 'LED 映射已保存', 'success');
                    } catch (err) {
                        notify(this, '保存 LED 映射失败：' + err.message, 'error');
                    }
                },

                async locateBox(boxId) {
                    if (!boxId) return;
                    try {
                        await apiClient.post(`/api/led/locate/box/${boxId}`, {});
                        notify(this, 'LED 定位指令已发送', 'success');
                    } catch (err) {
                        notify(this, 'LED 定位失败：' + err.message, 'error');
                    }
                },

                async locateComponent(componentId) {
                    if (!componentId) return;
                    try {
                        await apiClient.post(`/api/led/locate/component/${componentId}`, {});
                        notify(this, 'LED 定位指令已发送', 'success');
                    } catch (err) {
                        notify(this, 'LED 定位失败：' + err.message, 'error');
                    }
                },

                async locateBomItems() {
                    const boxIds = [...new Set((this.bomData?.items || []).map((item) => item.matched?.box_id).filter(Boolean))];
                    if (!boxIds.length) {
                        notify(this, '当前 BOM 没有可定位的收纳盒', 'warning');
                        return;
                    }
                    try {
                        const result = await apiClient.post('/api/led/locate/bom', { box_ids: boxIds });
                        const errors = result?.errors?.length ? `，失败 ${result.errors.length} 台` : '';
                        notify(this, `已发送 ${result?.led_count || 0} 个 LED 定位${errors}`, result?.errors?.length ? 'warning' : 'success');
                    } catch (err) {
                        notify(this, 'BOM LED 定位失败：' + err.message, 'error');
                    }
                },

                isScannerAvailable() {
                    return !!global.Html5Qrcode;
                },

                openScanner() {
                    this.scannerManualText = '';
                    this.scannerError = '';
                    this.modal = 'scanner';
                    this.$nextTick(() => {
                        if (!this.isScannerAvailable()) {
                            this.scannerError = global.__scannerLibLoadErrorMessage || '扫码库未加载，可使用手动输入。';
                            notify(this, this.scannerError, 'warning');
                            return;
                        }
                        startScannerFn((text) => {
                            this.closeScanner();
                            notify(this, '已识别：' + text, 'success');
                            logActionFn('SCAN', '扫码识别：' + text);
                            this.autoFillFromScan(text);
                        }, (err) => {
                            this.scannerError = this.friendlyScannerError(err);
                            notify(this, this.scannerError, 'warning');
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
                    if (typeof stopScannerFn === 'function') {
                        stopScannerFn().catch(() => {});
                    }
                },

                submitManualScan() {
                    const text = this.scannerManualText.trim();
                    if (!text) {
                        notify(this, '请输入扫码内容', 'warning');
                        return;
                    }
                    logActionFn('SCAN', '手动录入扫码内容：' + text);
                    this.closeScanner();
                    this.autoFillFromScan(text);
                },

                handleScannerImage(file) {
                    if (!file) return;
                    this.scannerError = '';
                    scanImageFileFn(file, (text) => {
                        notify(this, '图片识别成功：' + text, 'success');
                        logActionFn('SCAN', '图片识别：' + text);
                        this.closeScanner();
                        this.autoFillFromScan(text);
                    }, (err) => {
                        notify(this, '图片识别失败：' + err, 'error');
                    });
                },

                autoFillFromScan(text) {
                    openComponentByScan(this, text);
                },

                componentIdFromScan,

                async nfcBind() {
                    if (!this.nfcBoxId) {
                        notify(this, '请先选择收纳盒', 'warning');
                        return;
                    }
                    if (!('NDEFReader' in global)) {
                        notify(this, '当前浏览器不支持 Web NFC 读取', 'error');
                        return;
                    }
                    this.nfcStatus = { type: 'pending', title: '等待 NFC 标签', message: '请将手机靠近标签。' };
                    try {
                        const result = await readNFCTagFn();
                        await apiClient.post('/api/nfc/bind', { box_id: Number(this.nfcBoxId), uid: result.uid });
                        this.nfcStatus = { type: 'success', title: '绑定成功', message: result.uid };
                        logActionFn('NFC', `绑定收纳盒 ID=${this.nfcBoxId} UID=${result.uid}`);
                        notify(this, 'NFC 标签已绑定', 'success');
                    } catch (err) {
                        this.nfcStatus = { type: 'error', title: '绑定失败', message: err.message };
                        logActionFn('NFC', '绑定失败：' + err.message);
                    }
                },

                async nfcWrite() {
                    if (!this.nfcBoxId) {
                        notify(this, '请先选择收纳盒', 'warning');
                        return;
                    }
                    if (!('NDEFWriter' in global)) {
                        notify(this, '当前浏览器不支持 Web NFC 写入', 'error');
                        return;
                    }
                    this.nfcStatus = { type: 'pending', title: '准备写入', message: '请将手机靠近标签。' };
                    try {
                        const payload = await apiClient.post('/api/nfc/write', { box_id: Number(this.nfcBoxId) });
                        await writeNFCTagFn([
                            { recordType: 'url', data: payload.url },
                            { recordType: 'text', data: payload.text }
                        ]);
                        this.nfcStatus = { type: 'success', title: '写入成功', message: payload.url };
                        logActionFn('NFC', `写入 NDEF 收纳盒 ID=${this.nfcBoxId}`);
                        notify(this, 'NDEF 已写入', 'success');
                    } catch (err) {
                        this.nfcStatus = { type: 'error', title: '写入失败', message: err.message };
                        logActionFn('NFC', '写入失败：' + err.message);
                    }
                }
            }
        };
    };
})(window);
