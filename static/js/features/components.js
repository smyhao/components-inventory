// 本文件负责元器件领域的前端状态和交互编排，位于 static/js/features 领域层；只依赖注入的 API、上传下载、日志和提示能力，不直接修改后端规则或其他领域内部实现。
(function registerComponentsFeature(global) {
    const namespace = global.InventoryModules || (global.InventoryModules = {});

    /**
     * 生成元器件表单初始值。
     * 字段名与现有模板绑定保持一致，确保最终挂载时不需要改 HTML 结构。
     */
    function emptyComponentForm() {
        return {
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
        };
    }

    /**
     * 构建元器件领域 feature。
     * deps 只接收跨领域基础能力；categories、boxes、availableCells、currentComponent 等状态仍通过 Alpine 实例 this 读取。
     */
    namespace.createComponentsFeature = function createComponentsFeature(deps = {}) {
        const apiClient = deps.api;
        const uploadFileFn = deps.uploadFile;
        const downloadFileFn = deps.downloadFile;
        const logActionFn = deps.logAction || function noopLogAction() {};
        const toastFn = deps.toast;

        /**
         * 统一发送领域提示。
         * 优先使用注入的 toast，未注入时回落到 Alpine 根对象的现有 toast 方法。
         */
        function notify(context, message, type = 'info') {
            if (typeof toastFn === 'function') {
                toastFn.call(context, message, type);
                return;
            }
            if (context && typeof context.toast === 'function') {
                context.toast(message, type);
            }
        }

        return {
            state: {
                searchKeyword: '',
                filterCategory: '',
                filterBox: '',
                filterStock: '',
                componentList: [],
                componentPagination: { page: 1, page_size: 20, total: 0 },
                componentForm: emptyComponentForm(),
                availableCells: [],
                currentComponent: null,
                stockForm: { type: 'in', quantity: 1, reason: '' }
            },

            methods: {
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
                        const data = await apiClient.get('/api/components', params);
                        this.componentList = data.items || [];
                        this.componentPagination.total = data.total || 0;
                        this.componentPagination.page = data.page || this.componentPagination.page;
                        this.componentPagination.page_size = data.page_size || this.componentPagination.page_size;
                    } catch (err) {
                        notify(this, '加载元器件失败：' + err.message, 'error');
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
                        const grid = await apiClient.get(`/api/boxes/${boxId}/grid`);
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
                        notify(this, '加载格子失败：' + err.message, 'error');
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
                        const image = await uploadFileFn('/api/images/upload', file);
                        this.componentForm.images.push({ id: image.id, url: image.url });
                    } catch (err) {
                        notify(this, '图片上传失败：' + err.message, 'error');
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
                        const document = await uploadFileFn('/api/documents/upload', file);
                        this.componentForm.documents.push(document);
                    } catch (err) {
                        notify(this, '文档上传失败：' + err.message, 'error');
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
                        notify(this, '请填写元器件名称', 'warning');
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
                            await apiClient.put(`/api/components/${form.id}`, form);
                            logActionFn('UPDATE', `更新元器件 ID=${form.id} 名称=${form.name}`);
                            notify(this, '元器件已更新', 'success');
                        } else {
                            const created = await apiClient.post('/api/components', form);
                            logActionFn('CREATE', `新增元器件 ID=${created?.id || '-'} 名称=${form.name}`);
                            notify(this, '元器件已创建', 'success');
                        }
                        this.closeModal();
                        await Promise.all([this.loadComponents(), this.loadBoxes(), this.loadDashboard()]);
                    } catch (err) {
                        notify(this, '保存失败：' + err.message, 'error');
                    } finally {
                        this.loadingOverlay = false;
                    }
                },

                async openComponentDetail(id) {
                    try {
                        this.loadingOverlay = true;
                        this.currentComponent = await apiClient.get(`/api/components/${id}`);
                        this.modal = 'component-detail';
                    } catch (err) {
                        notify(this, '加载详情失败：' + err.message, 'error');
                    } finally {
                        this.loadingOverlay = false;
                    }
                },

                async openComponentFromUrl() {
                    const params = new URLSearchParams(global.location.search);
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
                            notify(this, '没有可生成二维码的元器件', 'warning');
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
                        notify(this, '没有可生成二维码的元器件', 'warning');
                        return;
                    }
                    global.open(`/components/qr-labels?${params.toString()}`, '_blank');
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
                    if (!global.confirm(`确定删除「${this.currentComponent.name}」吗？`)) return;
                    try {
                        this.loadingOverlay = true;
                        await apiClient.del(`/api/components/${this.currentComponent.id}`);
                        logActionFn('DELETE', `删除元器件 ID=${this.currentComponent.id} 名称=${this.currentComponent.name}`);
                        notify(this, '元器件已删除', 'success');
                        this.closeModal();
                        await Promise.all([this.loadComponents(), this.loadBoxes(), this.loadDashboard()]);
                    } catch (err) {
                        notify(this, '删除失败：' + err.message, 'error');
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
                        notify(this, '数量必须大于 0', 'warning');
                        return;
                    }
                    try {
                        this.loadingOverlay = true;
                        await apiClient.post(`/api/stock/${this.stockForm.type}`, {
                            component_id: this.currentComponent.id,
                            quantity,
                            reason: this.stockForm.reason
                        });
                        logActionFn('STOCK', `${this.stockForm.type === 'in' ? '入库' : '出库'} 元器件ID=${this.currentComponent.id} 数量=${quantity}`);
                        this.currentComponent = await apiClient.get(`/api/components/${this.currentComponent.id}`);
                        notify(this, '库存已更新', 'success');
                        this.modal = 'component-detail';
                        await Promise.all([this.loadComponents(), this.loadDashboard()]);
                    } catch (err) {
                        notify(this, '库存操作失败：' + err.message, 'error');
                    } finally {
                        this.loadingOverlay = false;
                    }
                },

                async importExcel() {
                    this.$refs.importInput?.click();
                },

                async handleImportFile(file) {
                    if (!file) return;
                    try {
                        this.loadingOverlay = true;
                        const result = await uploadFileFn('/api/components/import', file);
                        logActionFn('IMPORT', `元器件导入完成 type=${result.file_type || '-'} success=${result.success || 0} failed=${result.failed || 0}`);
                        notify(this, `导入完成：成功 ${result.success || 0} 条，失败 ${result.failed || 0} 条`, result.failed ? 'warning' : 'success');
                        await Promise.all([this.loadComponents(), this.loadBoxes(), this.loadDashboard()]);
                    } catch (err) {
                        notify(this, '导入失败：' + err.message, 'error');
                    } finally {
                        this.loadingOverlay = false;
                        if (this.$refs.importInput) this.$refs.importInput.value = '';
                    }
                },

                async exportExcel() {
                    try {
                        this.loadingOverlay = true;
                        await downloadFileFn('/api/components/export', null, 'components_export.xlsx');
                        logActionFn('EXPORT', '导出元器件清单');
                        notify(this, '导出已开始', 'success');
                    } catch (err) {
                        notify(this, '导出失败：' + err.message, 'error');
                    } finally {
                        this.loadingOverlay = false;
                    }
                }
            }
        };
    };
})(window);
