// 本文件负责收纳盒与柜子前端领域交互，属于 static/js/features 领域层；只编排 API、表单状态和页面刷新，不复制后端业务规则。
(function registerStorageFeature(global) {
    const modules = global.InventoryModules = global.InventoryModules || {};

    /**
     * 生成收纳盒表单默认值。
     * @returns {object} 与主页面现有 boxForm 绑定兼容的表单对象。
     */
    function emptyBoxForm() {
        return {
            id: null,
            name: '',
            rows: 4,
            cols: 6,
            color: '#84b59b',
            template_id: '',
            cabinet_id: '',
            cabinet_slot: 0,
            description: ''
        };
    }

    /**
     * 将 API 返回的收纳盒转换为表单值，避免模板直接依赖后端缺省字段。
     * @param {object|null} box 收纳盒数据。
     * @returns {object} 可编辑的收纳盒表单对象。
     */
    function boxToForm(box) {
        return box ? {
            id: box.id,
            name: box.name || '',
            rows: box.rows || 4,
            cols: box.cols || 6,
            color: box.color || '#84b59b',
            template_id: box.template_id || '',
            cabinet_id: box.cabinet_id || '',
            cabinet_slot: box.cabinet_slot || 0,
            description: box.description || ''
        } : emptyBoxForm();
    }

    /**
     * 生成柜子表单默认值。
     * @returns {object} 与主页面现有 cabinetForm 绑定兼容的表单对象。
     */
    function emptyCabinetForm() {
        return {
            id: null,
            name: '',
            color: '#8b9aae',
            template_id: '',
            layer_count: 1,
            description: ''
        };
    }

    /**
     * 生成收纳盒详情占位对象。
     * Alpine 会求值隐藏区块中的绑定，保持稳定形状可避免初始渲染读取 null 字段。
     */
    function emptyCurrentBox() {
        return {
            id: null,
            name: '',
            rows: 0,
            cols: 0,
            occupied_count: 0,
            description: ''
        };
    }

    /**
     * 将 API 返回的柜子转换为表单值。
     * @param {object|null} cabinet 柜子数据。
     * @returns {object} 可编辑的柜子表单对象。
     */
    function cabinetToForm(cabinet) {
        return cabinet ? {
            id: cabinet.id,
            name: cabinet.name || '',
            color: cabinet.color || '#8b9aae',
            template_id: cabinet.template_id || '',
            layer_count: cabinet.layer_count || 1,
            description: cabinet.description || ''
        } : emptyCabinetForm();
    }

    /**
     * 创建收纳盒/柜子领域模块。
     * @param {object} deps 外部依赖，包含 api、logAction 和 confirm，便于模块独立测试与最终集成。
     * @returns {{state: object, methods: object}} 可由 InventoryModules.mergeFeature 合并进 app()。
     */
    modules.createStorageFeature = function createStorageFeature(deps) {
        const api = deps.api;
        const logAction = deps.logAction || function noop() {};
        const confirmAction = deps.confirm || global.confirm.bind(global);

        return {
            state: {
                boxes: [],
                cabinets: [],
                boxForm: emptyBoxForm(),
                cabinetForm: emptyCabinetForm(),
                currentBox: emptyCurrentBox(),
                boxGrid: []
            },
            methods: {
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

                openBoxForm(box = null) {
                    this.boxForm = boxToForm(box);
                    if (typeof this.load3DAppearance === 'function') this.load3DAppearance();
                    this.modal = 'box-form';
                },

                editBox(box) {
                    this.openBoxForm(box);
                },

                async saveBox() {
                    const { id, name, rows, cols, color, template_id, cabinet_id, cabinet_slot, description } = this.boxForm;
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
                            template_id: template_id ? Number(template_id) : null,
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
                    if (!confirmAction(`确定删除「${box.name}」吗？盒内有元器件时后端会拒绝删除。`)) return;
                    try {
                        this.loadingOverlay = true;
                        await api.del(`/api/boxes/${box.id}`);
                        logAction('DELETE', `删除收纳盒 ID=${box.id} 名称=${box.name}`);
                        this.toast('收纳盒已删除', 'success');
                        if (this.currentBox?.id === box.id) {
                            this.currentBox = emptyCurrentBox();
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
                    this.cabinetForm = cabinetToForm(cabinet);
                    if (typeof this.load3DAppearance === 'function') this.load3DAppearance();
                    this.modal = 'cabinet-form';
                },

                async saveCabinet() {
                    const { id, name, color, template_id, layer_count, description } = this.cabinetForm;
                    if (!String(name || '').trim()) {
                        this.toast('请填写柜子名称', 'warning');
                        return;
                    }
                    try {
                        this.loadingOverlay = true;
                        const payload = {
                            name: name.trim(),
                            color,
                            template_id: template_id ? Number(template_id) : null,
                            layer_count: Number(layer_count || 1),
                            description: description || null
                        };
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
                    if (!confirmAction(`确定删除柜子「${cabinet.name}」吗？柜子里有收纳盒时会被后端拒绝。`)) return;
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
                }
            }
        };
    };
})(window);
