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
        images: []
    });

    const emptyBoxForm = () => ({
        id: null,
        name: '',
        rows: 4,
        cols: 6,
        color: '#84b59b'
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
        currentBox: null,
        boxGrid: [],

        mapBoxes: [],
        mapHighlights: [],
        mapState: { panX: 48, panY: 48, scale: 1 },
        mapDirty: false,
        draggingBox: null,
        dragState: null,

        bomFile: null,
        bomData: null,
        bomStats: { total: 0, matched: 0, shortage: 0, unmatched: 0 },

        nfcBoxId: '',
        nfcStatus: null,
        nfcSupported: 'NDEFReader' in window || 'NDEFWriter' in window,

        scannerManualText: '',
        scannerError: '',

        async initApp() {
            await Promise.all([this.loadCategories(), this.loadBoxes()]);
            await this.loadDashboard();
        },

        async navigate(pageId) {
            this.page = pageId;
            if (pageId === 'dashboard') await this.loadDashboard();
            if (pageId === 'components') await this.loadComponents();
            if (pageId === 'boxes') await this.loadBoxes();
            if (pageId === 'map') await this.loadMapData();
            if (pageId === 'nfc') await this.loadBoxes();
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
                    images: (item.images || []).map((img) => ({ id: img.id, url: img.url || img.thumbnail_url }))
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

        async saveComponent() {
            const form = { ...this.componentForm };
            if (!form.name.trim()) {
                this.toast('请填写元器件名称', 'warning');
                return;
            }

            form.tags = String(form.tagsInput || '').split(/[,，]/).map((tag) => tag.trim()).filter(Boolean);
            form.images = (form.images || []).map((img) => img.id || img.url).filter(Boolean);
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
                color: box.color || '#84b59b'
            } : emptyBoxForm();
            this.modal = 'box-form';
        },

        editBox(box) {
            this.openBoxForm(box);
        },

        async saveBox() {
            const { id, name, rows, cols, color } = this.boxForm;
            if (!String(name || '').trim()) {
                this.toast('请填写收纳盒名称', 'warning');
                return;
            }
            try {
                this.loadingOverlay = true;
                const payload = { name: name.trim(), rows: Number(rows), cols: Number(cols), color };
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
                await Promise.all([this.loadBoxes(), this.loadDashboard()]);
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
                logAction('IMPORT', `Excel 导入完成 success=${result.success || 0} failed=${result.failed || 0}`);
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
                const cellSize = 22;
                const gap = 4;
                this.mapBoxes = (data.boxes || []).map((box, index) => ({
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
                this.updateMapPickLabels();
            } catch (err) {
                this.toast('加载地图失败：' + err.message, 'error');
            } finally {
                this.loading = false;
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
            if (event.target.closest('.map-box')) return;
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

        endPointerWork() {
            if (this.dragState?.type === 'box' && this.draggingBox && !this.dragState.moved) {
                this.viewBoxDetail(this.draggingBox.id);
            }
            this.draggingBox = null;
            this.dragState = null;
            if (this._panMapMove) {
                window.removeEventListener('mousemove', this._panMapMove);
                window.removeEventListener('touchmove', this._panMapMove);
            }
            if (this._dragBoxMove) {
                window.removeEventListener('mousemove', this._dragBoxMove);
                window.removeEventListener('touchmove', this._dragBoxMove);
            }
            if (this._endPointerWork) {
                window.removeEventListener('mouseup', this._endPointerWork);
                window.removeEventListener('touchend', this._endPointerWork);
                window.removeEventListener('touchcancel', this._endPointerWork);
            }
            this._panMapMove = null;
            this._dragBoxMove = null;
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
                await Promise.all(this.mapBoxes.map((box) => api.put(`/api/boxes/${box.id}/layout`, {
                    position_x: Math.round(Number(box.position_x || 0)),
                    position_y: Math.round(Number(box.position_y || 0))
                })));
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
                this.computeBomStats();
                logAction('BOM', `导入 BOM ${data.project_name || file.name}`);
                this.toast('BOM 已解析', 'success');
            } catch (err) {
                this.toast('BOM 导入失败：' + err.message, 'error');
            } finally {
                this.loadingOverlay = false;
            }
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
