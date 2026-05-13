// 本文件负责“设置 -> 3D 外观”的前端状态和交互；模型文件只在设置页入库，柜子/盒子表单只消费模板。
(function registerModelAppearanceFeature(global) {
    const modules = global.InventoryModules = global.InventoryModules || {};

    function emptyModelAssetForm() {
        return {
            name: '',
            type: 'cabinet_layer',
            width_mm: '',
            height_mm: '',
            depth_mm: ''
        };
    }

    function emptyCabinetTemplateForm() {
        return {
            id: null,
            name: '',
            structure_type: 'drawer_cabinet',
            layer_model_asset_id: '',
            base_model_asset_id: '',
            top_model_asset_id: '',
            layer_height_mm: 80,
            pull_axis: 'z',
            pull_distance_mm: 160,
            slot_offset_x_mm: 0,
            slot_offset_y_mm: 0,
            slot_offset_z_mm: 0
        };
    }

    function emptyBoxTemplateForm() {
        return {
            id: null,
            name: '',
            cell_model_asset_id: '',
            frame_model_asset_id: '',
            cell_width_mm: 28,
            cell_depth_mm: 28,
            cell_height_mm: 12,
            gap_x_mm: 2,
            gap_z_mm: 2,
            padding_x_mm: 4,
            padding_z_mm: 4
        };
    }

    function numberOrNull(value) {
        if (value === '' || value === null || value === undefined) return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function idOrNull(value) {
        const parsed = Number(value || 0);
        return parsed > 0 ? parsed : null;
    }

    modules.createModelAppearanceFeature = function createModelAppearanceFeature(deps = {}) {
        const api = deps.api;
        const uploadFile = deps.uploadFile;
        const confirmAction = deps.confirm || global.confirm.bind(global);

        return {
            state: {
                appearanceTab: 'assets',
                modelAssets: [],
                cabinetTemplates: [],
                boxTemplates: [],
                modelAssetForm: emptyModelAssetForm(),
                cabinetTemplateForm: emptyCabinetTemplateForm(),
                boxTemplateForm: emptyBoxTemplateForm(),
                modelAssetUploading: false
            },
            methods: {
                async load3DAppearance() {
                    try {
                        const [assets, cabinetTemplates, boxTemplates] = await Promise.all([
                            api.get('/api/model-assets'),
                            api.get('/api/cabinet-templates'),
                            api.get('/api/box-templates')
                        ]);
                        this.modelAssets = assets || [];
                        this.cabinetTemplates = cabinetTemplates || [];
                        this.boxTemplates = boxTemplates || [];
                    } catch (err) {
                        this.toast('加载 3D 外观配置失败：' + err.message, 'error');
                    }
                },

                modelAssetsByType(type) {
                    return (this.modelAssets || []).filter((asset) => asset.type === type);
                },

                modelTypeLabel(type) {
                    return ({
                        cabinet_layer: '柜子标准层',
                        cabinet_base: '柜子底座',
                        cabinet_top: '柜子顶盖',
                        box_cell: '收纳盒单格',
                        box_frame: '收纳盒外框'
                    })[type] || type;
                },

                structureTypeLabel(type) {
                    return type === 'open_shelf' ? '开放架' : '抽拉柜';
                },

                nodeIssueSummary(asset) {
                    const issues = asset?.node_report?.issues || [];
                    if (!issues.length) return '节点检查通过';
                    const errors = issues.filter((issue) => issue.level === 'error').length;
                    const warnings = issues.length - errors;
                    return `${errors} 个错误 / ${warnings} 个提醒`;
                },

                async uploadModelAsset(event) {
                    const file = event?.target?.files?.[0];
                    if (!file) return;
                    if (!String(file.name || '').toLowerCase().endsWith('.glb')) {
                        this.toast('第一版模型库只支持 .glb 文件', 'warning');
                        event.target.value = '';
                        return;
                    }
                    const form = { ...this.modelAssetForm };
                    const payload = {
                        name: form.name || file.name.replace(/\.glb$/i, ''),
                        type: form.type,
                        width_mm: numberOrNull(form.width_mm) ?? '',
                        height_mm: numberOrNull(form.height_mm) ?? '',
                        depth_mm: numberOrNull(form.depth_mm) ?? ''
                    };
                    try {
                        this.modelAssetUploading = true;
                        await uploadFile('/api/model-assets/upload', file, payload);
                        this.modelAssetForm = emptyModelAssetForm();
                        await this.load3DAppearance();
                        this.toast('模型已加入模型库', 'success');
                    } catch (err) {
                        this.toast('上传模型失败：' + err.message, 'error');
                    } finally {
                        this.modelAssetUploading = false;
                        event.target.value = '';
                    }
                },

                async deleteModelAsset(asset) {
                    if (!asset?.id || !confirmAction(`删除模型「${asset.name}」？被模板引用时后端会拒绝。`)) return;
                    try {
                        await api.del(`/api/model-assets/${asset.id}`);
                        await this.load3DAppearance();
                        this.toast('模型已删除', 'success');
                    } catch (err) {
                        this.toast('删除模型失败：' + err.message, 'error');
                    }
                },

                editCabinetTemplate(template) {
                    this.cabinetTemplateForm = {
                        ...emptyCabinetTemplateForm(),
                        ...template,
                        layer_model_asset_id: template.layer_model_asset_id || '',
                        base_model_asset_id: template.base_model_asset_id || '',
                        top_model_asset_id: template.top_model_asset_id || ''
                    };
                    this.appearanceTab = 'cabinet-templates';
                },

                resetCabinetTemplateForm() {
                    this.cabinetTemplateForm = emptyCabinetTemplateForm();
                },

                async saveCabinetTemplate() {
                    const form = { ...this.cabinetTemplateForm };
                    if (!String(form.name || '').trim()) {
                        this.toast('请填写柜体模板名称', 'warning');
                        return;
                    }
                    const payload = {
                        name: form.name.trim(),
                        structure_type: form.structure_type,
                        layer_model_asset_id: idOrNull(form.layer_model_asset_id),
                        base_model_asset_id: idOrNull(form.base_model_asset_id),
                        top_model_asset_id: idOrNull(form.top_model_asset_id),
                        layer_height_mm: Number(form.layer_height_mm || 80),
                        pull_axis: form.pull_axis || 'z',
                        pull_distance_mm: Number(form.pull_distance_mm || 160),
                        slot_offset_x_mm: Number(form.slot_offset_x_mm || 0),
                        slot_offset_y_mm: Number(form.slot_offset_y_mm || 0),
                        slot_offset_z_mm: Number(form.slot_offset_z_mm || 0)
                    };
                    try {
                        if (form.id) await api.put(`/api/cabinet-templates/${form.id}`, payload);
                        else await api.post('/api/cabinet-templates', payload);
                        this.resetCabinetTemplateForm();
                        await this.load3DAppearance();
                        this.toast('柜体模板已保存', 'success');
                    } catch (err) {
                        this.toast('保存柜体模板失败：' + err.message, 'error');
                    }
                },

                async deleteCabinetTemplate(template) {
                    if (!template?.id || !confirmAction(`删除柜体模板「${template.name}」？被柜子引用时后端会拒绝。`)) return;
                    try {
                        await api.del(`/api/cabinet-templates/${template.id}`);
                        await this.load3DAppearance();
                        this.toast('柜体模板已删除', 'success');
                    } catch (err) {
                        this.toast('删除柜体模板失败：' + err.message, 'error');
                    }
                },

                editBoxTemplate(template) {
                    this.boxTemplateForm = {
                        ...emptyBoxTemplateForm(),
                        ...template,
                        cell_model_asset_id: template.cell_model_asset_id || '',
                        frame_model_asset_id: template.frame_model_asset_id || ''
                    };
                    this.appearanceTab = 'box-templates';
                },

                resetBoxTemplateForm() {
                    this.boxTemplateForm = emptyBoxTemplateForm();
                },

                async saveBoxTemplate() {
                    const form = { ...this.boxTemplateForm };
                    if (!String(form.name || '').trim()) {
                        this.toast('请填写收纳盒模板名称', 'warning');
                        return;
                    }
                    const payload = {
                        name: form.name.trim(),
                        cell_model_asset_id: idOrNull(form.cell_model_asset_id),
                        frame_model_asset_id: idOrNull(form.frame_model_asset_id),
                        cell_width_mm: Number(form.cell_width_mm || 28),
                        cell_depth_mm: Number(form.cell_depth_mm || 28),
                        cell_height_mm: Number(form.cell_height_mm || 12),
                        gap_x_mm: Number(form.gap_x_mm || 0),
                        gap_z_mm: Number(form.gap_z_mm || 0),
                        padding_x_mm: Number(form.padding_x_mm || 0),
                        padding_z_mm: Number(form.padding_z_mm || 0)
                    };
                    try {
                        if (form.id) await api.put(`/api/box-templates/${form.id}`, payload);
                        else await api.post('/api/box-templates', payload);
                        this.resetBoxTemplateForm();
                        await this.load3DAppearance();
                        this.toast('收纳盒模板已保存', 'success');
                    } catch (err) {
                        this.toast('保存收纳盒模板失败：' + err.message, 'error');
                    }
                },

                async deleteBoxTemplate(template) {
                    if (!template?.id || !confirmAction(`删除收纳盒模板「${template.name}」？被收纳盒引用时后端会拒绝。`)) return;
                    try {
                        await api.del(`/api/box-templates/${template.id}`);
                        await this.load3DAppearance();
                        this.toast('收纳盒模板已删除', 'success');
                    } catch (err) {
                        this.toast('删除收纳盒模板失败：' + err.message, 'error');
                    }
                }
            }
        };
    };
})(window);
