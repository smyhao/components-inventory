// 本文件负责地图工作台前端领域交互，属于 static/js/features 领域层；只编排地图加载、拖拽、缩放、背景和 BOM 高亮联动，不复制后端地图 API 规则。
(function registerMapWorkbenchFeature(global) {
    const modules = global.InventoryModules = global.InventoryModules || {};

    /**
     * 创建地图领域默认状态，保持与现有 Alpine 模板字段完全兼容。
     * @returns {object} 地图页面、拖拽过程和高亮信息所需的前端状态。
     */
    function createMapState() {
        return {
            mapBoxes: [],
            mapCabinets: [],
            expandedCabinets: [],
            mapHighlights: [],
            mapState: { panX: 48, panY: 48, scale: 1 },
            mapDirty: false,
            draggingBox: null,
            draggingCabinet: null,
            dragState: null,
            mapBackground: global.localStorage?.getItem('inventory-map-bg') || 'grid',
            mapBackgroundUrl: ''
        };
    }

    /**
     * 创建地图工作台特性模块。
     * @param {object} deps 外部依赖，只接收 API、上传、日志和确认弹窗能力。
     * @returns {{state: object, methods: object}} 可由 InventoryModules.mergeFeature 合并进 app()。
     */
    modules.createMapFeature = function createMapFeature(deps = {}) {
        const api = deps.api;
        const uploadFile = deps.uploadFile;
        const logAction = deps.logAction || function noopLogAction() {};
        const confirmAction = deps.confirm || ((message) => global.confirm ? global.confirm(message) : true);
        const confirm = (message) => confirmAction(message);

        return {
            state: createMapState(),
            methods: {
        // 地图数据加载：只转换前端展示尺寸和柜内分组，不改变后端返回语义。
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

        // 视口交互：平移和双指缩放共享 dragState，触摸移动使用 passive=false 避免页面滚动抢占。
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

        // 布局拖拽：收纳盒和柜子都只更新前端坐标，保存时再分别调用 layout API。
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

        // BOM 联动：根据匹配到的收纳盒生成取料序号，高亮逻辑只消费当前 bomData。
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

        // 样式工具：地图卡片颜色只在前端派生 CSS 变量，不写回业务数据。
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
        }
            }
        };
    };
})(window);
