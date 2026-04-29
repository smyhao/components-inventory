// 本文件负责 3D 地图视图的 Alpine 功能模块，包括 2D/3D 切换、场景生命周期和跨功能桥接，属于前端功能层；不做 Three.js 渲染细节。
(function registerMap3DFeature(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});

    /** 创建 3D 地图功能的默认状态。 */
    function createMap3DState(api) {
        return {
            mapViewMode: '2d',
            scene3D: null,
            lazyGrids: {},
            presetLayout: 'none',
            api: api
        };
    }

    /**
     * 创建 3D 地图功能模块。
     * @param {object} deps 外部依赖，只接收 API 和日志能力。
     * @returns {{state: object, methods: object}} 可由 InventoryModules.mergeFeature 合并进 app()。
     */
    modules.createMap3DFeature = function createMap3DFeature(deps) {
        deps = deps || {};
        var api = deps.api;
        var logAction = deps.logAction || function noopLogAction() {};

        return {
            state: createMap3DState(api),
            methods: {
                /** 切换 2D/3D 视图模式，进入 3D 前保留对未保存 2D 布局的确认。 */
                toggleMapView(mode) {
                    var newMode = mode || (this.mapViewMode === '2d' ? '3d' : '2d');
                    var self = this;

                    if (newMode === this.mapViewMode) return;
                    if (newMode !== '2d' && newMode !== '3d') return;

                    if (newMode === '3d' && this.mapDirty) {
                        if (!global.confirm('2D 地图有未保存的修改，确定切换到 3D 吗？')) return;
                    }

                    this.mapViewMode = newMode;
                    if (newMode === '3d') {
                        // Alpine 更新 DOM 可见性后再初始化，否则渲染器会拿到 0 尺寸容器。
                        global.setTimeout(function initSceneAfterDomUpdate() {
                            self.init3DScene();
                        }, 50);
                    } else {
                        this.dispose3DScene();
                    }
                },

                /** 初始化 3D 场景，并用当前地图缓存构建占位模型。 */
                init3DScene() {
                    var container = global.document.getElementById('map-3d-container');
                    var THREE = global.THREE;
                    var SceneManager = modules.SceneManager;
                    var InteractionManager = modules.InteractionManager;
                    var manager;

                    if (!container) {
                        this.toast('3D 容器未找到', 'error');
                        return;
                    }

                    if (!THREE || !SceneManager || !InteractionManager) {
                        this.toast('3D 引擎加载失败，请刷新页面重试', 'error');
                        this.mapViewMode = '2d';
                        return;
                    }

                    if (this.scene3D) {
                        this.scene3D.dispose();
                        this.scene3D = null;
                    }

                    try {
                        manager = new SceneManager(container);
                        manager.init(THREE, global.OrbitControlsModule, global.CSS2DRendererModule);
                        manager.buildFromMapData(this.mapCabinets || [], this.mapBoxes || []);
                        // 3D 使用与 2D 相同的缩放状态，避免切换视图后物体视觉尺寸跳变。
                        if (typeof manager.setMapScale === 'function') {
                            manager.setMapScale(this.mapState && this.mapState.scale);
                        }
                        if (typeof manager.fitDefaultFrontView === 'function') {
                            manager.fitDefaultFrontView();
                        }
                        // 交互层需要 Alpine 上下文来调用懒加载、详情弹窗和布局保存 API。
                        manager.interaction = new InteractionManager(manager, this);
                        manager.interaction.bind();
                        manager.startAnimationLoop();
                        this.scene3D = manager;
                        this.sync3DHighlights();

                        global.setTimeout(function resizeSceneAfterLayout() {
                            manager.handleResize();
                            if (typeof manager.fitDefaultFrontView === 'function') {
                                manager.fitDefaultFrontView();
                            }
                        }, 100);

                        logAction('VIEW', '切换到 3D 地图视图');
                    } catch (err) {
                        if (manager) manager.dispose();
                        this.scene3D = null;
                        this.mapViewMode = '2d';
                        this.toast('初始化 3D 地图失败：' + err.message, 'error');
                    }
                },

                /** 销毁 3D 场景，释放 GPU 和 DOM 资源。 */
                dispose3DScene() {
                    if (this.scene3D) {
                        this.scene3D.dispose();
                        this.scene3D = null;
                    }
                    this.lazyGrids = {};
                    logAction('VIEW', '切换到 2D 地图视图');
                },

                /**
                 * 懒加载收纳盒格子数据，供后续抽屉拉出和格子点击交互复用。
                 * @param {number|string} boxId 收纳盒 ID。
                 * @returns {Promise<object|null>} 格子数据。
                 */
                async loadBoxGrid(boxId) {
                    if (!boxId) return null;
                    if (this.lazyGrids[boxId]) return this.lazyGrids[boxId];

                    try {
                        var data = await api.get('/api/boxes/' + boxId + '/grid');
                        this.lazyGrids[boxId] = data;
                        return data;
                    } catch (err) {
                        this.toast('加载格子数据失败', 'error');
                        return null;
                    }
                },

                /** 应用 3D 预设布局，并在保存后重建当前 3D 场景。 */
                async applyPresetLayout(presetName) {
                    var layoutFn;
                    var updates;
                    var i;
                    var item;
                    var endpoint;

                    if (!presetName || presetName === 'none') return;
                    if (!this.scene3D) return;
                    if (this.mapLayoutLocked) {
                        this.toast('布局已锁定，解锁后才能应用预设布局', 'warning');
                        this.presetLayout = 'none';
                        return;
                    }

                    layoutFn = modules._3DLayouts && modules._3DLayouts[presetName];
                    if (!layoutFn) {
                        this.toast('未知布局预设', 'error');
                        return;
                    }

                    this.loadingOverlay = true;
                    try {
                        // 布局函数只计算坐标，保存仍走现有 layout API，保持后端数据入口一致。
                        updates = layoutFn(this.mapCabinets || [], this.mapBoxes || []);
                        for (i = 0; i < updates.length; i += 1) {
                            item = updates[i];
                            endpoint = item.type === 'cabinet'
                                ? '/api/cabinets/' + item.id + '/layout'
                                : '/api/boxes/' + item.id + '/layout';
                            try {
                                await api.put(endpoint, {
                                    position_x: item.position_x,
                                    position_y: item.position_y
                                });
                            } catch (err) {
                                // 单个对象保存失败不阻断其余对象，最后通过重载数据回到后端实际状态。
                            }
                        }

                        await this.loadMapData();
                        this.scene3D.buildFromMapData(this.mapCabinets || [], this.mapBoxes || []);
                        if (typeof this.scene3D.setMapScale === 'function') {
                            this.scene3D.setMapScale(this.mapState && this.mapState.scale);
                        }
                        if (typeof this.scene3D.fitDefaultFrontView === 'function') {
                            this.scene3D.fitDefaultFrontView();
                        }
                        this.sync3DHighlights();
                        this.presetLayout = presetName;
                        this.toast('已应用预设布局', 'success');
                    } catch (err) {
                        this.toast('应用布局失败：' + err.message, 'error');
                    } finally {
                        this.loadingOverlay = false;
                    }
                },

                /** 同步 2D 地图的 BOM 高亮和领料序号到当前 3D 场景。 */
                sync3DHighlights() {
                    if (!this.scene3D || !modules._3D) return;
                    if (typeof modules._3D.highlightDrawers === 'function') {
                        modules._3D.highlightDrawers(this.scene3D, this.mapHighlights || []);
                    }
                    if (typeof modules._3D.updatePickLabels === 'function') {
                        modules._3D.updatePickLabels(this.scene3D, this.get3DPickOrderMap());
                    }
                },

                /** 从当前 mapBoxes/mapCabinets 的 pickLabels 派生 3D 标签所需的 boxId -> 序号映射。 */
                get3DPickOrderMap() {
                    var result = {};
                    (this.mapBoxes || []).forEach(function collectStandalone(box) {
                        addPickLabel(result, box);
                    });
                    (this.mapCabinets || []).forEach(function collectCabinet(cabinet) {
                        (cabinet.boxes || []).forEach(function collectBox(box) {
                            addPickLabel(result, box);
                        });
                    });
                    return result;
                },

                /** 3D 模式下定位收纳盒：相机飞入，柜内盒完成后自动拉开抽屉。 */
                flyToBox3D(boxId) {
                    var self = this;
                    if (!this.scene3D || !modules._3D || typeof modules._3D.flyToBox !== 'function') return false;
                    return modules._3D.flyToBox(this.scene3D, boxId, function openDrawer(drawer) {
                        if (self.scene3D && self.scene3D.interaction && drawer) {
                            self.scene3D.interaction.openDrawer(drawer);
                        }
                    });
                },

                /** LED 定位成功后，在 3D 场景内给目标盒子一个短时脉冲。 */
                pulseBox3D(boxId, durationMs) {
                    if (!this.scene3D || !modules._3D || typeof modules._3D.startPulse !== 'function') return;
                    modules._3D.startPulse(boxId, durationMs || 5000);
                },

                /** BOM 高亮进入 3D 时自动拉出相关抽屉，帮助用户直接看到命中的盒子。 */
                reveal3DHighlights() {
                    var self = this;
                    if (!this.scene3D || !this.scene3D.interaction || !modules._3D || typeof modules._3D.findDrawerByBoxId !== 'function') return;
                    (this.mapHighlights || []).forEach(function reveal(boxId) {
                        var drawer = modules._3D.findDrawerByBoxId(self.scene3D, boxId);
                        if (drawer) {
                            self.scene3D.interaction.openDrawer(drawer);
                        }
                    });
                }
            }
        };
    };

    function addPickLabel(result, box) {
        var label;
        if (!box || !box.id || !(box.pickLabels || []).length) return;
        label = box.pickLabels[0];
        if (label && label.num) {
            result[box.id] = label.num;
        }
    }
})(window);
