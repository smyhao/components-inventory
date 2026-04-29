// 本文件负责 3D 场景的初始化、渲染循环、灯光、地面和对象构建/销毁，属于 3D 引擎层；不做 UI 交互和 Alpine 状态管理。
(function initSceneManager(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});

    // 三维常量：统一 2D 地图坐标与 3D 世界坐标的换算，避免后续拖拽保存时出现比例漂移。
    var SCALE_FACTOR = 0.01;
    var CABINET_WIDTH = 1.2;
    var CABINET_DEPTH = 0.8;
    var LAYER_HEIGHT = 0.35;
    var WALL_THICKNESS = 0.03;
    var CABINET_LEG_HEIGHT = 0.16;
    // 抽屉打开时必须保留足够后段在柜体内，否则近景会像整只抽屉脱离柜子。
    // 抽屉本体需要拉到柜体外，才能完整看到格子；后方延长块负责保持“仍在柜内”的视觉连续性。
    var PULL_OUT_DISTANCE = 0.52;

    /**
     * SceneManager 管理 Three.js 场景生命周期。
     * @param {HTMLElement} container 3D 视图的 DOM 容器。
     */
    function SceneManager(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.css2dRenderer = null;
        this.controls = null;
        this.mapGroup = null;
        this.animationId = null;
        this.clock = null;
        this._onResize = null;
        this._resizeObserver = null;

        this.cabinetMap = {};
        this.drawerMap = {};
        this.boxMap = {};
        this.standaloneBoxMap = {};
        this.interaction = null;
    }

    /** 初始化场景、相机、灯光、地面、控制器和渲染器。 */
    SceneManager.prototype.init = function init(THREE, OrbitControls, CSS2DRenderer) {
        THREE = THREE || global.THREE;
        OrbitControls = OrbitControls || global.OrbitControlsModule;
        CSS2DRenderer = CSS2DRenderer || global.CSS2DRendererModule;

        if (!this.container) {
            throw new Error('SceneManager 初始化失败：缺少 3D 容器。');
        }
        if (!THREE) {
            throw new Error('SceneManager 初始化失败：THREE 未加载。');
        }

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf8f3ea);
        this.clock = new THREE.Clock();

        var width = this.container.clientWidth || 1;
        var height = this.container.clientHeight || 1;
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
        this.camera.position.set(0, 8, 12);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(Math.min(global.devicePixelRatio || 1, 2));
        this.renderer.setSize(width, height);
        this.renderer.shadowMap.enabled = true;
        if (THREE.PCFSoftShadowMap) {
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        }
        this.container.appendChild(this.renderer.domElement);

        if (CSS2DRenderer) {
            this.css2dRenderer = new CSS2DRenderer();
            this.css2dRenderer.setSize(width, height);
            this.css2dRenderer.domElement.style.position = 'absolute';
            this.css2dRenderer.domElement.style.inset = '0';
            this.css2dRenderer.domElement.style.pointerEvents = 'none';
            this.container.appendChild(this.css2dRenderer.domElement);
        }

        this.addLights(THREE);
        this.addGround(THREE);

        this.mapGroup = new THREE.Group();
        this.mapGroup.name = 'inventory-map-root';
        this.scene.add(this.mapGroup);

        if (OrbitControls) {
            this.controls = new OrbitControls(this.camera, this.renderer.domElement);
            this.controls.target.set(0, 1, 0);
            this.controls.minDistance = 2;
            this.controls.maxDistance = 30;
            this.controls.minPolarAngle = 0.1;
            this.controls.maxPolarAngle = Math.PI / 2 - 0.05;
            this.controls.enableDamping = true;
            this.controls.dampingFactor = 0.08;
            // 中键按住用于平移视角；缩放保留给滚轮，避免中键按压触发浏览器自动滚动。
            this.controls.mouseButtons = {
                LEFT: THREE.MOUSE.ROTATE,
                MIDDLE: THREE.MOUSE.PAN,
                RIGHT: THREE.MOUSE.PAN
            };
            this.controls.update();
        }

        this._onResize = this.handleResize.bind(this);
        global.addEventListener('resize', this._onResize);
        if (global.ResizeObserver) {
            // 容器高度由页面剩余空间决定，工具栏换行或浏览器差异都会触发布局变化。
            this._resizeObserver = new global.ResizeObserver(this._onResize);
            this._resizeObserver.observe(this.container);
        }
        this.handleResize();
        return this;
    };

    /** 添加环境光和两盏方向光，让占位模型在浅色背景上保持清晰的体积感。 */
    SceneManager.prototype.addLights = function addLights(THREE) {
        var ambient = new THREE.AmbientLight(0xfff5e6, 0.6);
        this.scene.add(ambient);

        var mainLight = new THREE.DirectionalLight(0xffffff, 0.85);
        mainLight.position.set(6, 10, 8);
        mainLight.castShadow = true;
        mainLight.shadow.mapSize.width = 2048;
        mainLight.shadow.mapSize.height = 2048;
        mainLight.shadow.camera.left = -15;
        mainLight.shadow.camera.right = 15;
        mainLight.shadow.camera.top = 15;
        mainLight.shadow.camera.bottom = -15;
        mainLight.shadow.camera.near = 0.5;
        mainLight.shadow.camera.far = 40;
        this.scene.add(mainLight);

        var fillLight = new THREE.DirectionalLight(0xfff0dd, 0.35);
        fillLight.position.set(-6, 6, -5);
        this.scene.add(fillLight);
    };

    /** 添加网格和接收阴影的地面，给 2D 坐标映射后的对象提供空间参照。 */
    SceneManager.prototype.addGround = function addGround(THREE) {
        var grid = new THREE.GridHelper(30, 30, 0xcbb89f, 0xdbcdb8);
        grid.name = 'inventory-map-grid';
        this.scene.add(grid);

        var planeGeometry = new THREE.PlaneGeometry(30, 30);
        var planeMaterial = new THREE.ShadowMaterial({
            color: 0x71593a,
            opacity: 0.12
        });
        var plane = new THREE.Mesh(planeGeometry, planeMaterial);
        plane.name = 'inventory-map-ground-shadow';
        plane.rotation.x = -Math.PI / 2;
        plane.receiveShadow = true;
        this.scene.add(plane);
    };

    /** 从地图数据构建 3D 对象，把扁平 API 数据组合为柜子和独立收纳盒模型。 */
    SceneManager.prototype.buildFromMapData = function buildFromMapData(cabinets, boxes) {
        var self = this;
        var boxesByCabinet = {};
        var standaloneBoxes = [];
        var seenBoxIds = {};
        var builders = modules._3D || {};

        if (!this.mapGroup) return;
        if (!builders.buildCabinet || !builders.buildBox) {
            throw new Error('3D 模型构建器未加载，请确认 cabinet-model.js 和 box-model.js 已引入。');
        }
        this.clearMap();

        // 2D 地图会把柜内收纳盒挂到 cabinet.boxes；3D 优先消费这个结构，保证两种视图数量一致。
        (cabinets || []).forEach(function groupNestedCabinetBoxes(cabinet) {
            (cabinet.boxes || []).forEach(function rememberNestedBox(box) {
                if (!box || !box.id) return;
                var key = String(cabinet.id);
                if (!boxesByCabinet[key]) boxesByCabinet[key] = [];
                boxesByCabinet[key].push(box);
                seenBoxIds[box.id] = true;
            });
        });

        // 兼容旧调用方传入的扁平 boxes；已从 cabinet.boxes 读取过的收纳盒不重复加入。
        (boxes || []).forEach(function groupBoxByCabinet(box) {
            if (!box || seenBoxIds[box.id]) return;
            if (box.cabinet_id) {
                if (!boxesByCabinet[box.cabinet_id]) boxesByCabinet[box.cabinet_id] = [];
                boxesByCabinet[box.cabinet_id].push(box);
            } else {
                standaloneBoxes.push(box);
            }
        });

        (cabinets || []).forEach(function buildCabinetModel(cabinet) {
            var cabinetBoxes = boxesByCabinet[String(cabinet.id)] || boxesByCabinet[cabinet.id] || [];
            var cabinetData = Object.assign({}, cabinet, {
                boxes: cabinetBoxes
            });
            var cabinetGroup = builders.buildCabinet(cabinetData, self.drawerMap);

            if (builders.addCabinetNameplate) {
                builders.addCabinetNameplate(cabinetGroup, cabinetData);
            }
            if (builders.addDrawerNameplate) {
                cabinetGroup.traverse(function addDrawerLabel(child) {
                    if (child.userData && child.userData.type === 'drawer') {
                        builders.addDrawerNameplate(child, child.userData.boxData);
                    }
                });
            }
            self.mapGroup.add(cabinetGroup);
            self.cabinetMap[cabinet.id] = cabinetGroup;
            cabinetBoxes.forEach(function rememberCabinetBox(box) {
                self.boxMap[box.id] = cabinetGroup;
            });
        });

        standaloneBoxes.forEach(function buildStandaloneBoxModel(box) {
            var boxGroup = builders.buildBox(box);

            if (builders.addBoxNameplate) {
                builders.addBoxNameplate(boxGroup, box);
            }
            self.mapGroup.add(boxGroup);
            self.standaloneBoxMap[box.id] = boxGroup;
        });
    };

    /** 同步 2D 地图缩放比例，让 3D 物体尺寸与当前地图缩放保持一致。 */
    SceneManager.prototype.setMapScale = function setMapScale(scale) {
        var normalizedScale = Math.max(0.35, Math.min(2.8, Number(scale || 1)));

        if (!this.mapGroup) return;
        this.mapGroup.scale.set(normalizedScale, normalizedScale, normalizedScale);
    };

    /** 根据当前模型范围设置默认正视图，让 3D 打开时自动放大到刚好可见全部对象。 */
    SceneManager.prototype.fitDefaultFrontView = function fitDefaultFrontView() {
        var THREE = global.THREE;
        var box;
        var size;
        var center;
        var target;
        var aspect;
        var fovRad;
        var fitWidth;
        var fitHeight;
        var distance;
        var yLift;

        if (!THREE || !this.mapGroup || !this.camera) return;
        if (!this.mapGroup.children.length) return;

        this.mapGroup.updateMatrixWorld(true);
        box = new THREE.Box3().setFromObject(this.mapGroup);
        if (box.isEmpty()) return;

        size = new THREE.Vector3();
        center = new THREE.Vector3();
        box.getSize(size);
        box.getCenter(center);

        aspect = Math.max(0.1, this.camera.aspect || 1);
        fovRad = THREE.MathUtils.degToRad(this.camera.fov || 45);
        fitWidth = size.x / aspect;
        // 正视图主要看宽高，稍带一点深度余量，避免柜体顶部和标签贴边。
        fitHeight = size.y + size.z * 0.22;
        distance = Math.max(fitWidth, fitHeight) / (2 * Math.tan(fovRad / 2));
        distance = Math.max(2.4, distance * 1.28 + size.z * 0.45);
        yLift = Math.max(0.24, size.y * 0.16);
        target = new THREE.Vector3(center.x, box.min.y + size.y * 0.48, center.z);

        this.camera.position.set(center.x, target.y + yLift, box.max.z + distance);
        this.camera.lookAt(target);
        this.camera.updateProjectionMatrix();

        if (this.controls) {
            this.controls.target.copy(target);
            this.controls.minDistance = Math.max(1.2, distance * 0.22);
            this.controls.maxDistance = Math.max(30, distance * 4);
            this.controls.update();
        }
    };

    /** 清除地图组中所有对象，并释放几何体、材质和纹理资源。 */
    SceneManager.prototype.clearMap = function clearMap() {
        if (!this.mapGroup) return;

        while (this.mapGroup.children.length) {
            var child = this.mapGroup.children.pop();
            this.disposeObject(child);
        }

        this.cabinetMap = {};
        this.drawerMap = {};
        this.boxMap = {};
        this.standaloneBoxMap = {};
    };

    /** 递归释放对象树，避免频繁切换 2D/3D 或刷新数据时泄漏 GPU 资源。 */
    SceneManager.prototype.disposeObject = function disposeObject(object3d) {
        if (!object3d) return;

        while (object3d.children && object3d.children.length) {
            this.disposeObject(object3d.children.pop());
        }

        if (object3d.parent) {
            object3d.parent.remove(object3d);
        }
        if (object3d.geometry) {
            object3d.geometry.dispose();
        }
        if (object3d.element && modules._3D && modules._3D.disposeLabelElement) {
            modules._3D.disposeLabelElement(object3d);
        }
        this.disposeMaterial(object3d.material);
    };

    /** 释放单个或数组材质；纹理属性也一并处理，给后续真实模型预留安全出口。 */
    SceneManager.prototype.disposeMaterial = function disposeMaterial(material) {
        if (!material) return;
        if (Array.isArray(material)) {
            material.forEach(this.disposeMaterial.bind(this));
            return;
        }

        Object.keys(material).forEach(function disposeTexture(key) {
            var value = material[key];
            if (value && typeof value.dispose === 'function') {
                value.dispose();
            }
        });
        material.dispose();
    };

    /** 启动渲染循环。 */
    SceneManager.prototype.startAnimationLoop = function startAnimationLoop() {
        var self = this;

        if (this.animationId) return;

        function animate() {
            var deltaTime = self.clock ? self.clock.getDelta() : 0.016;

            self.animationId = global.requestAnimationFrame(animate);
            if (self.controls) self.controls.update();
            if (self.interaction) self.interaction.animateDrawers();
            if (modules._3D && modules._3D.updatePulse) {
                modules._3D.updatePulse(self, deltaTime);
            }
            if (modules._3D && modules._3D.updateFly) {
                modules._3D.updateFly(self);
            }
            if (modules._3D && modules._3D.updateLabelVisibility) {
                modules._3D.updateLabelVisibility(self.camera, self.mapGroup);
            }
            if (self.renderer && self.scene && self.camera) {
                self.renderer.render(self.scene, self.camera);
            }
            if (self.css2dRenderer && self.scene && self.camera) {
                self.css2dRenderer.render(self.scene, self.camera);
            }
        }

        animate();
    };

    /** 停止渲染循环。 */
    SceneManager.prototype.stopAnimationLoop = function stopAnimationLoop() {
        if (!this.animationId) return;
        global.cancelAnimationFrame(this.animationId);
        this.animationId = null;
    };

    /** 根据容器尺寸同步相机和渲染器，避免侧栏/窗口变化后画面拉伸。 */
    SceneManager.prototype.handleResize = function handleResize() {
        if (!this.container || !this.renderer || !this.camera) return;

        var width = this.container.clientWidth || 1;
        var height = this.container.clientHeight || 1;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
        if (this.css2dRenderer) {
            this.css2dRenderer.setSize(width, height);
        }
    };

    /** 销毁场景，释放所有 DOM、控制器和 GPU 资源。 */
    SceneManager.prototype.dispose = function dispose() {
        this.stopAnimationLoop();

        if (this._onResize) {
            global.removeEventListener('resize', this._onResize);
        }
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
            this._resizeObserver = null;
        }
        this._onResize = null;

        if (this.interaction) {
            this.interaction.unbind();
            this.interaction = null;
        }

        this.clearMap();

        if (this.mapGroup && this.mapGroup.parent) {
            this.mapGroup.parent.remove(this.mapGroup);
        }
        this.mapGroup = null;

        if (this.controls) {
            this.controls.dispose();
            this.controls = null;
        }

        if (this.renderer) {
            if (this.renderer.domElement && this.renderer.domElement.parentNode) {
                this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
            }
            this.renderer.dispose();
            this.renderer = null;
        }

        if (this.css2dRenderer) {
            if (this.css2dRenderer.domElement && this.css2dRenderer.domElement.parentNode) {
                this.css2dRenderer.domElement.parentNode.removeChild(this.css2dRenderer.domElement);
            }
            this.css2dRenderer = null;
        }

        this.scene = null;
        this.camera = null;
        this.clock = null;
    };

    modules.SceneManager = SceneManager;
    modules._3D = modules._3D || {};
    modules._3D.SCALE_FACTOR = SCALE_FACTOR;
    modules._3D.CABINET_WIDTH = CABINET_WIDTH;
    modules._3D.CABINET_DEPTH = CABINET_DEPTH;
    modules._3D.LAYER_HEIGHT = LAYER_HEIGHT;
    modules._3D.WALL_THICKNESS = WALL_THICKNESS;
    modules._3D.CABINET_LEG_HEIGHT = CABINET_LEG_HEIGHT;
    modules._3D.PULL_OUT_DISTANCE = PULL_OUT_DISTANCE;
})(window);
