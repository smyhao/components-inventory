// 本文件负责 BOM 领域前端交互，属于 static/js/features 领域层；只编排导入、匹配、选择、领料、导出和地图跳转，不复制后端 BOM 匹配算法。
(function registerBomFeature(global) {
    const modules = global.InventoryModules = global.InventoryModules || {};

    /**
     * 创建 BOM 领域默认状态，字段名保持与现有 Alpine 模板绑定兼容。
     * @returns {object} BOM 导入结果、统计、批量选择和手动匹配弹窗状态。
     */
    function createBomState() {
        return {
            bomFile: null,
            bomData: null,
            bomStats: { total: 0, matched: 0, shortage: 0, unmatched: 0 },
            bomSelectedRows: [],
            bomManualRowIndex: null,
            bomManualKeyword: '',
            bomManualResults: [],
            bomManualLoading: false
        };
    }

    /**
     * 计算 BOM 前端展示统计，只依赖导入后的行数据，便于独立单元测试。
     * @param {Array<object>} items BOM 行数组。
     * @returns {{total: number, matched: number, shortage: number, unmatched: number}} 统计结果。
     */
    function computeBomStatsFromItems(items = []) {
        const rows = Array.isArray(items) ? items : [];
        const matched = rows.filter((item) => item.matched).length;
        const shortage = rows.filter((item) => item.matched && Number(item.matched.quantity || 0) < Number(item.quantity_needed || 0)).length;
        return {
            total: rows.length,
            matched,
            shortage,
            unmatched: rows.length - matched
        };
    }

    /**
     * 将元器件搜索结果压缩为 BOM 行的手动匹配快照，避免把整条详情对象塞入 BOM 请求。
     * @param {object|null} component 元器件列表项。
     * @returns {object|null} 后端 BOM consume/export 接口沿用的 matched 结构。
     */
    function createManualMatchPayload(component) {
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
    }

    /**
     * 纯函数切换单行选中状态，返回新的有序索引数组，避免直接修改 Alpine 数组。
     * @param {Array<number>} selectedRows 当前选中行索引。
     * @param {number} index 目标行索引。
     * @param {boolean} checked 是否选中。
     * @returns {Array<number>} 新的选中行索引。
     */
    function toggleSelectedRow(selectedRows, index, checked) {
        const current = Array.isArray(selectedRows) ? selectedRows : [];
        if (checked) {
            return current.includes(index) ? current : [...current, index].sort((a, b) => a - b);
        }
        return current.filter((rowIndex) => rowIndex !== index);
    }

    /**
     * 纯函数生成全选或全不选结果，输入只来自当前 BOM 行数。
     * @param {number} total BOM 行数。
     * @param {boolean} checked 是否全选。
     * @returns {Array<number>} 新的选中行索引。
     */
    function toggleAllRows(total, checked) {
        const count = Math.max(0, Number(total || 0));
        return checked ? Array.from({ length: count }, (_, index) => index) : [];
    }

    /**
     * 删除单行并重新映射选中索引，保持删除后的批量选择状态一致。
     * @param {Array<object>} items 当前 BOM 行。
     * @param {Array<number>} selectedRows 当前选中行索引。
     * @param {number} index 删除目标索引。
     * @returns {{items: Array<object>, selectedRows: Array<number>}} 删除后的行和选择状态。
     */
    function removeRowAt(items, selectedRows, index) {
        const nextItems = Array.isArray(items) ? items.filter((_, rowIndex) => rowIndex !== index) : [];
        const nextSelectedRows = (Array.isArray(selectedRows) ? selectedRows : [])
            .filter((rowIndex) => rowIndex !== index)
            .map((rowIndex) => rowIndex > index ? rowIndex - 1 : rowIndex);
        return { items: nextItems, selectedRows: nextSelectedRows };
    }

    /**
     * 按选中索引批量删除 BOM 行，返回新数组供 Alpine 替换，避免原地遍历删除导致错位。
     * @param {Array<object>} items 当前 BOM 行。
     * @param {Array<number>} selectedRows 要删除的行索引。
     * @returns {Array<object>} 删除后的 BOM 行。
     */
    function removeRowsBySelection(items, selectedRows) {
        const selected = new Set(Array.isArray(selectedRows) ? selectedRows : []);
        return (Array.isArray(items) ? items : []).filter((_, index) => !selected.has(index));
    }

    /**
     * 创建 BOM 领域特性模块。
     * @param {object} deps 外部依赖，仅接收 API、上传下载、日志、确认弹窗和地图桥接能力。
     * @returns {{state: object, methods: object}} 可由 InventoryModules.mergeFeature 合并进 app()。
     */
    modules.createBomFeature = function createBomFeature(deps = {}) {
        const api = deps.api;
        const uploadFile = deps.uploadFile;
        const downloadPostFile = deps.downloadPostFile;
        const logAction = deps.logAction || function noopLogAction() {};
        const confirmAction = deps.confirm || ((message) => global.confirm ? global.confirm(message) : true);
        const gotoMapWithBoxes = deps.gotoMapWithBoxes;
        const refreshMapPickLabels = deps.refreshMapPickLabels;

        return {
            state: createBomState(),
            methods: {
                // 文件导入：只负责上传和接收后端匹配结果，匹配算法仍由后端服务层处理。
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

                // 手动匹配弹窗：以 BOM 行内容初始化搜索词，后续搜索仍走元器件列表 API。
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
                    return createManualMatchPayload(component);
                },

                assignBomComponent(component) {
                    if (this.bomManualRowIndex === null || !this.bomData?.items?.[this.bomManualRowIndex]) return;
                    this.bomData.items[this.bomManualRowIndex].matched = this.manualMatchPayload(component);
                    this.bomData.items[this.bomManualRowIndex].match_level = 'manual';
                    this.computeBomStats();
                    this.refreshBomMapLabels();
                    this.toast('已手动指定元器件', 'success');
                    this.closeModal();
                },

                clearBomMatch(index = this.bomManualRowIndex) {
                    if (index === null || !this.bomData?.items?.[index]) return;
                    this.bomData.items[index].matched = null;
                    this.bomData.items[index].match_level = null;
                    this.computeBomStats();
                    this.refreshBomMapLabels();
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
                    if (!confirmAction(`确定从当前 BOM 中删除「${label}」吗？`)) return;
                    const result = removeRowAt(this.bomData.items, this.bomSelectedRows, index);
                    this.bomData.items = result.items;
                    this.bomSelectedRows = result.selectedRows;
                    this.bomData.total_types = this.bomData.items.length;
                    this.computeBomStats();
                    this.refreshBomMapLabels();
                    this.toast('已从 BOM 中删除该行', 'success');
                },

                toggleBomRowSelection(index, checked) {
                    this.bomSelectedRows = toggleSelectedRow(this.bomSelectedRows, index, checked);
                },

                toggleAllBomRows(checked) {
                    const total = this.bomData?.items?.length || 0;
                    this.bomSelectedRows = toggleAllRows(total, checked);
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
                    if (!confirmAction(`确定从当前 BOM 中删除选中的 ${this.bomSelectedRows.length} 行吗？`)) return;
                    this.bomData.items = removeRowsBySelection(this.bomData.items, this.bomSelectedRows);
                    this.bomSelectedRows = [];
                    this.bomData.total_types = this.bomData.items.length;
                    this.computeBomStats();
                    this.refreshBomMapLabels();
                    this.toast('已删除选中的 BOM 行', 'success');
                },

                computeBomStats() {
                    this.bomStats = computeBomStatsFromItems(this.bomData?.items || []);
                },

                async consumeBom() {
                    if (!this.bomData?.items?.length) return;
                    if (!confirmAction('确定按当前 BOM 匹配结果扣减库存吗？')) return;
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

                // 地图跳转通过注入桥接实现，BOM 模块只提供 boxId 列表，不直接操作地图内部数据结构。
                async gotoBomMap() {
                    if (!this.bomData?.items?.length) return;
                    const boxIds = (this.bomData.items || [])
                        .filter((item) => item.matched?.box_id)
                        .map((item) => item.matched.box_id);
                    if (typeof gotoMapWithBoxes === 'function') {
                        await gotoMapWithBoxes.call(this, [...new Set(boxIds)]);
                        return;
                    }
                    this.page = 'map';
                },

                refreshBomMapLabels() {
                    if (typeof refreshMapPickLabels === 'function') {
                        refreshMapPickLabels.call(this);
                    }
                }
            }
        };
    };

    modules.bomPure = {
        createBomState,
        computeBomStatsFromItems,
        createManualMatchPayload,
        toggleSelectedRow,
        toggleAllRows,
        removeRowAt,
        removeRowsBySelection
    };
})(window);
