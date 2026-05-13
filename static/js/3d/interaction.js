// 本文件集中管理 3D 场景交互：拾取、抽屉抽拉、格子点击和对象拖拽保存。
(function registerInteractionManager(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});

    /**
     * InteractionManager 管理 3D 场景的所有用户交互。
     * @param {SceneManager} sceneManager 场景管理器实例。
     * @param {Object} alpineContext Alpine 组件上下文。
     */
    function InteractionManager(sceneManager, alpineContext) {
        this.sm = sceneManager;
        this.ctx = alpineContext;
        this.raycaster = null;
        this.pointer = new global.THREE.Vector2();
        this.groundPlane = new global.THREE.Plane(new global.THREE.Vector3(0, 1, 0), 0);
        this.hoveredHandle = null;
        this.hoveredCell = null;
        this.dragState = null;
        this.pointerDown = null;
        this.drawerTopViewIndex = -1;
        this._boundPointerDown = null;
        this._boundPointerMove = null;
        this._boundPointerUp = null;
        this._boundPointerCancel = null;
        this._boundWheel = null;
        this._boundControlStart = null;
        this._boundSuppressBrowserGesture = null;
    }

    /** 绑定 pointer 事件；交互统一挂在 WebGL canvas 上，避免 CSS2D 标签层截获事件。 */
    InteractionManager.prototype.bind = function bind() {
        var canvas = this.getCanvas();

        if (!canvas || this._boundPointerDown) return;

        this.raycaster = new global.THREE.Raycaster();
        this._boundPointerDown = this.onPointerDown.bind(this);
        this._boundPointerMove = this.onPointerMove.bind(this);
        this._boundPointerUp = this.onPointerUp.bind(this);
        this._boundPointerCancel = this.onPointerCancel.bind(this);
        this._boundWheel = this.cancelCameraFly.bind(this);
        this._boundControlStart = this.cancelCameraFly.bind(this);
        this._boundSuppressBrowserGesture = this.suppressBrowserGesture.bind(this);

        canvas.addEventListener('pointerdown', this._boundPointerDown, true);
        canvas.addEventListener('pointermove', this._boundPointerMove);
        canvas.addEventListener('pointerup', this._boundPointerUp);
        canvas.addEventListener('pointercancel', this._boundPointerCancel);
        canvas.addEventListener('pointerleave', this._boundPointerCancel);
        canvas.addEventListener('wheel', this._boundWheel, true);
        canvas.addEventListener('contextmenu', this._boundSuppressBrowserGesture);
        canvas.addEventListener('auxclick', this._boundSuppressBrowserGesture);
        if (this.sm && this.sm.controls && typeof this.sm.controls.addEventListener === 'function') {
            this.sm.controls.addEventListener('start', this._boundControlStart);
        }
    };

    /** 解绑事件，并恢复悬停与拖拽状态，供场景销毁时清理。 */
    InteractionManager.prototype.unbind = function unbind() {
        var canvas = this.getCanvas();

        if (!canvas || !this._boundPointerDown) return;

        canvas.removeEventListener('pointerdown', this._boundPointerDown, true);
        canvas.removeEventListener('pointermove', this._boundPointerMove);
        canvas.removeEventListener('pointerup', this._boundPointerUp);
        canvas.removeEventListener('pointercancel', this._boundPointerCancel);
        canvas.removeEventListener('pointerleave', this._boundPointerCancel);
        if (this._boundWheel) canvas.removeEventListener('wheel', this._boundWheel, true);
        canvas.removeEventListener('contextmenu', this._boundSuppressBrowserGesture);
        canvas.removeEventListener('auxclick', this._boundSuppressBrowserGesture);
        if (this.sm && this.sm.controls && this._boundControlStart && typeof this.sm.controls.removeEventListener === 'function') {
            this.sm.controls.removeEventListener('start', this._boundControlStart);
        }
        this.restoreHoveredHandle();
        this.restoreHoveredCell();
        this.resetCursor();
        this._boundPointerDown = null;
        this._boundPointerMove = null;
        this._boundPointerUp = null;
        this._boundPointerCancel = null;
        this._boundWheel = null;
        this._boundControlStart = null;
        this._boundSuppressBrowserGesture = null;
        this.pointerDown = null;
        this.dragState = null;
    };

    /** 记录按下目标；柜子和独立收纳盒进入可拖拽状态。 */
    InteractionManager.prototype.onPointerDown = function onPointerDown(event) {
        var hit = this.pickObject(event);
        var target = hit ? hit.object : null;
        var type = target && target.userData ? target.userData.type : null;
        var draggable;

        if (this.isSecondaryAction(event)) {
            this.cancelCameraFly();
            this.pointerDown = {
                x: event.clientX,
                y: event.clientY,
                hit: hit,
                moved: false,
                dragStarted: false,
                secondary: true
            };
            return;
        }

        if (!this.isPrimaryAction(event)) {
            // 右键/中键交给 OrbitControls，但阻止浏览器手势菜单和中键自动滚动。
            event.preventDefault();
            this.pointerDown = null;
            this.cancelCameraFly();
            return;
        }

        this.cancelCameraFly();
        this.pointerDown = {
            x: event.clientX,
            y: event.clientY,
            hit: hit,
            moved: false,
            dragStarted: false
        };

        if (type === 'handle' || type === 'box-cells' || type === 'box-cell') {
            event.preventDefault();
            return;
        }

        draggable = this.findParentByType(target, 'cabinet') || this.findParentByType(target, 'standalone-box');
        if (draggable) {
            if (this.isLayoutLocked()) {
                return;
            }
            event.preventDefault();
            this.startDrag(draggable, event);
            this.pointerDown.dragStarted = !!this.dragState;
        }
    };

    /**
     * 只让鼠标左键触发业务交互；右键/中键保留给浏览器和 OrbitControls 的默认导航语义。
     * 触摸和触控笔通常只有主按钮，仍按原有移动端交互处理。
     */
    InteractionManager.prototype.isPrimaryAction = function isPrimaryAction(event) {
        if (!event || event.pointerType !== 'mouse') return true;
        return event.button === 0;
    };

    /** 鼠标右键单击用于轮换抽屉俯视图；右键拖动仍交给 OrbitControls 调整视角。 */
    InteractionManager.prototype.isSecondaryAction = function isSecondaryAction(event) {
        return !!(event && event.pointerType === 'mouse' && event.button === 2);
    };

    /** 阻止浏览器在 3D 画布上弹出右键菜单或触发中键自动滚动。 */
    InteractionManager.prototype.suppressBrowserGesture = function suppressBrowserGesture(event) {
        if (event) {
            event.preventDefault();
        }
    };

    InteractionManager.prototype.cancelCameraFly = function cancelCameraFly() {
        if (modules._3D && typeof modules._3D.cancelFly === 'function') {
            modules._3D.cancelFly();
        }
    };

    /** 布局锁定时仅禁止位置拖拽，不影响抽屉开关、格子点击和相机控制。 */
    InteractionManager.prototype.isLayoutLocked = function isLayoutLocked() {
        return !!(this.ctx && this.ctx.mapLayoutLocked);
    };

    /** 拖拽时更新位置；非拖拽时更新悬停反馈。 */
    InteractionManager.prototype.onPointerMove = function onPointerMove(event) {
        if (event && event.pointerType === 'mouse' && event.buttons && (event.buttons & 1) === 0 && this.pointerDown && !this.pointerDown.secondary && !this.dragState) {
            this.pointerDown = null;
        }

        if (this.pointerDown) {
            var dx = event.clientX - this.pointerDown.x;
            var dy = event.clientY - this.pointerDown.y;
            this.pointerDown.moved = Math.sqrt(dx * dx + dy * dy) > 5;
            if (this.pointerDown.secondary && this.pointerDown.moved) {
                // 右键拖动代表用户正在接管相机，必须中断自动飞入，避免下一帧把视角拉回柜内。
                this.cancelCameraFly();
            }
        }

        if (this.dragState) {
            event.preventDefault();
            this.onDrag(event);
            return;
        }

        this.updateHover(event);
    };

    /** 根据按下目标和移动距离决定触发点击还是结束拖拽保存。 */
    InteractionManager.prototype.onPointerUp = function onPointerUp(event) {
        var down = this.pointerDown;
        var hit;
        var clickedObject;
        var drawer;

        if (!this.isPrimaryAction(event)) {
            if (this.isSecondaryAction(event) && down && down.secondary && !down.moved) {
                event.preventDefault();
                this.focusNextOpenDrawerTopView();
            }
            if (down && down.secondary) this.pointerDown = null;
            return;
        }

        if (this.dragState) {
            event.preventDefault();
            this.endDrag();
            this.pointerDown = null;
            return;
        }

        if (!down || down.moved) {
            this.pointerDown = null;
            return;
        }

        hit = down.hit || this.pickObject(event);
        clickedObject = hit ? hit.object : null;

        if (clickedObject && clickedObject.userData.type === 'handle') {
            drawer = this.findDrawerByHandle(clickedObject.userData);
            if (drawer) this.toggleDrawer(drawer);
        } else if (clickedObject && (clickedObject.userData.type === 'box-cells' || clickedObject.userData.type === 'box-cell')) {
            this.openCellComponent(clickedObject, hit.instanceId);
        }

        this.pointerDown = null;
    };

    /** 触摸取消或离开 canvas 时，确保控制器和光标恢复到稳定状态。 */
    InteractionManager.prototype.onPointerCancel = function onPointerCancel() {
        if (this.dragState) {
            this.cancelDrag();
        }
        this.pointerDown = null;
        this.restoreHoveredHandle();
        this.restoreHoveredCell();
        this.resetCursor();
    };

    /**
     * 射线拾取，返回第一个带有效 userData.type 的命中项。
     * @param {PointerEvent} event 指针事件。
     * @returns {THREE.Intersection|null} 命中结果。
     */
    InteractionManager.prototype.pickObject = function pickObject(event) {
        var rect;
        var intersections;
        var i;

        if (!this.sm || !this.sm.mapGroup || !this.sm.camera || !this.raycaster) return null;

        rect = this.getCanvasRect();
        if (!rect || rect.width <= 0 || rect.height <= 0) return null;

        this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        this.raycaster.setFromCamera(this.pointer, this.sm.camera);

        intersections = this.raycaster.intersectObjects(this.sm.mapGroup.children, true);
        for (i = 0; i < intersections.length; i += 1) {
            if (this.isVisualLabel(intersections[i].object)) continue;
            if (intersections[i].object && intersections[i].object.userData && (
                intersections[i].object.userData.type === 'handle' ||
                intersections[i].object.userData.type === 'box-cells' ||
                intersections[i].object.userData.type === 'box-cell'
            )) {
                return intersections[i];
            }
        }
        for (i = 0; i < intersections.length; i += 1) {
            if (this.isVisualLabel(intersections[i].object)) continue;
            var parent = this.findParentByType(intersections[i].object, 'cabinet') ||
                this.findParentByType(intersections[i].object, 'standalone-box');
            if (parent) {
                intersections[i].object = parent;
                return intersections[i];
            }
        }
        return null;
    };

    /** 铭牌和贴纸只承担视觉表达，射线拾取应继续落到其下方的抽屉或格子模型。 */
    InteractionManager.prototype.isVisualLabel = function isVisualLabel(object) {
        var current = object;
        var type;
        while (current) {
            type = current.userData && current.userData.type;
            if (type && String(type).indexOf('label-') === 0) return true;
            current = current.parent;
        }
        return false;
    };

    /** 切换抽屉开关；同一柜子同时只允许一个抽屉打开，降低遮挡和拖拽复杂度。 */
    InteractionManager.prototype.toggleDrawer = function toggleDrawer(drawerGroup) {
        if (!drawerGroup) return;
        if (drawerGroup.userData.open) {
            this.closeDrawer(drawerGroup);
        } else {
            this.openDrawer(drawerGroup);
        }
    };

    /** 打开抽屉并懒加载格子数据，用后端占用状态更新 InstancedMesh 颜色。 */
    InteractionManager.prototype.openDrawer = async function openDrawer(drawerGroup) {
        var self = this;
        var constants = modules._3D || {};
        var boxId = drawerGroup.userData.boxId;

        Object.keys(this.sm.drawerMap || {}).forEach(function closeSibling(key) {
            var drawer = self.sm.drawerMap[key];
            if (drawer && drawer !== drawerGroup && drawer.userData.cabinetId === drawerGroup.userData.cabinetId) {
                self.closeDrawer(drawer);
            }
        });

        drawerGroup.userData.open = true;
        drawerGroup.userData.targetProgress = 1;
        drawerGroup.userData.targetDistance = drawerGroup.userData.pullVector ? 0 : (drawerGroup.userData.pullDistance || constants.PULL_OUT_DISTANCE || 0.7);

        if (!boxId || !this.ctx || typeof this.ctx.loadBoxGrid !== 'function') return;

        try {
            var gridData = this.normalizeGridData(await this.ctx.loadBoxGrid(boxId), drawerGroup);
            var cellMesh = this.findChildByType(drawerGroup, 'box-cells');
            if (cellMesh && modules._3D && typeof modules._3D.updateCellColors === 'function') {
                modules._3D.updateCellColors(cellMesh, gridData);
            }
            this.callOptionalLabelHook('showCellLabels', drawerGroup, gridData);
        } catch (err) {
            this.showToast('加载格子数据失败', 'error');
        }
    };

    /** 关闭抽屉并通知可选标签模块清理标签，避免标签残留在关闭抽屉上。 */
    InteractionManager.prototype.closeDrawer = function closeDrawer(drawerGroup) {
        if (!drawerGroup) return;
        drawerGroup.userData.open = false;
        drawerGroup.userData.targetZ = 0;
        drawerGroup.userData.targetDistance = 0;
        drawerGroup.userData.targetProgress = 0;
        this.callOptionalLabelHook('clearCellLabels', drawerGroup);
    };

    /** 渲染循环调用，缓动更新所有抽屉位置。 */
    /** 右键轮换所有已打开抽屉的俯视取景，便于直接查看抽屉里的元器件。 */
    InteractionManager.prototype.focusNextOpenDrawerTopView = function focusNextOpenDrawerTopView() {
        var drawers = this.getOpenDrawers();

        if (!drawers.length) {
            this.drawerTopViewIndex = -1;
            this.showToast('请先打开一个柜子抽屉', 'info');
            return;
        }

        this.drawerTopViewIndex = (this.drawerTopViewIndex + 1) % drawers.length;
        this.focusDrawerTopView(drawers[this.drawerTopViewIndex]);
    };

    /** 获取打开的抽屉并按柜子和槽位排序，让连续右键切换顺序稳定可预期。 */
    InteractionManager.prototype.getOpenDrawers = function getOpenDrawers() {
        return Object.keys(this.sm.drawerMap || {})
            .map(function mapDrawer(key) {
                return this.sm.drawerMap[key];
            }, this)
            .filter(function isOpenDrawer(drawer) {
                return !!(drawer && drawer.userData && drawer.userData.open);
            })
            .sort(function sortByCabinetAndSlot(left, right) {
                return Number(left.userData.cabinetId || 0) - Number(right.userData.cabinetId || 0) ||
                    Number(left.userData.slotIndex || 0) - Number(right.userData.slotIndex || 0);
            });
    };

    /** 将相机移动到抽屉上方偏前的位置，并按抽屉包围盒自适应距离。 */
    InteractionManager.prototype.focusDrawerTopView = function focusDrawerTopView(drawerGroup) {
        var THREE = global.THREE;
        var box;
        var size;
        var center;
        var aspect;
        var fovRad;
        var distance;
        var target;
        var cameraPos;

        if (!THREE || !drawerGroup || !this.sm || !this.sm.camera) return;

        drawerGroup.updateMatrixWorld(true);
        box = new THREE.Box3().setFromObject(drawerGroup);
        if (box.isEmpty()) return;

        size = new THREE.Vector3();
        center = new THREE.Vector3();
        box.getSize(size);
        box.getCenter(center);

        aspect = Math.max(0.1, this.sm.camera.aspect || 1);
        fovRad = THREE.MathUtils.degToRad(this.sm.camera.fov || 45);
        // 俯视时以抽屉宽深为主要取景范围，留出少量边距给外框和标签。
        distance = Math.max(size.x / aspect, size.z) / (2 * Math.tan(fovRad / 2));
        distance = Math.max(0.7, distance * 1.32);
        target = new THREE.Vector3(center.x, box.min.y + size.y * 0.22, center.z);
        cameraPos = new THREE.Vector3(center.x, box.max.y + distance, box.max.z + distance * 0.22);

        if (modules._3D && typeof modules._3D.flyToTarget === 'function') {
            modules._3D.flyToTarget(this.sm, cameraPos, target);
        } else {
            this.sm.camera.position.copy(cameraPos);
            this.sm.camera.lookAt(target);
            if (this.sm.controls) {
                this.sm.controls.target.copy(target);
                this.sm.controls.update();
            }
        }
    };

    InteractionManager.prototype.animateDrawers = function animateDrawers() {
        var self = this;
        Object.keys(this.sm.drawerMap || {}).forEach(function animateDrawer(key) {
            var drawer = self.sm.drawerMap[key];
            var target;
            var diff;
            var axis;
            var sign;
            var base;
            var vector;
            var progress;
            var targetPosition;

            if (!drawer) return;
            vector = drawer.userData.pullVector;
            if (vector) {
                base = drawer.userData.closedPosition || { x: 0, y: 0, z: 0 };
                progress = drawer.userData.targetProgress || 0;
                targetPosition = {
                    x: base.x + vector.x * progress,
                    y: base.y + vector.y * progress,
                    z: base.z + vector.z * progress
                };
                drawer.position.x += (targetPosition.x - drawer.position.x) * 0.12;
                drawer.position.y += (targetPosition.y - drawer.position.y) * 0.12;
                drawer.position.z += (targetPosition.z - drawer.position.z) * 0.12;
                if (Math.abs(targetPosition.x - drawer.position.x) < 0.001) drawer.position.x = targetPosition.x;
                if (Math.abs(targetPosition.y - drawer.position.y) < 0.001) drawer.position.y = targetPosition.y;
                if (Math.abs(targetPosition.z - drawer.position.z) < 0.001) drawer.position.z = targetPosition.z;
                return;
            }
            target = drawer.userData.targetDistance;
            if (target === undefined) target = drawer.userData.targetZ || 0;
            axis = String(drawer.userData.pullAxis || 'z');
            sign = axis.charAt(0) === '-' ? -1 : 1;
            axis = axis.replace('-', '') || 'z';
            target *= sign;
            diff = target - drawer.position[axis];
            if (Math.abs(diff) > 0.001) {
                drawer.position[axis] += diff * 0.12;
            } else {
                drawer.position[axis] = target;
            }
        });
    };

    /** 开始拖拽前关闭抽屉并记录世界坐标偏移，保证对象不会跳到鼠标射线落点。 */
    InteractionManager.prototype.startDrag = function startDrag(object, event) {
        var intersection = this.intersectGround(event);
        var objectWorld = new global.THREE.Vector3();
        var self = this;

        if (!object || !intersection) return;

        Object.keys(this.sm.drawerMap || {}).forEach(function closeDrawer(key) {
            self.closeDrawer(self.sm.drawerMap[key]);
        });

        object.getWorldPosition(objectWorld);
        this.dragState = {
            object: object,
            startPosition: object.position.clone(),
            offset: intersection.clone().sub(objectWorld),
            saved: false
        };

        if (this.sm.controls) {
            this.sm.controls.enabled = false;
        }
        this.setCursor('grabbing');
    };

    /** 拖拽中把 Y=0 平面的世界坐标转换回父节点局部坐标。 */
    InteractionManager.prototype.onDrag = function onDrag(event) {
        var intersection = this.intersectGround(event);
        var desiredWorld;
        var desiredLocal;
        var parent;

        if (!this.dragState || !intersection) return;

        desiredWorld = intersection.clone().sub(this.dragState.offset);
        parent = this.dragState.object.parent;
        desiredLocal = parent ? parent.worldToLocal(desiredWorld.clone()) : desiredWorld;
        this.dragState.object.position.x = desiredLocal.x;
        this.dragState.object.position.z = desiredLocal.z;
    };

    /** 结束拖拽并通过现有 layout API 保存位置；失败时回滚，避免前后端状态分裂。 */
    InteractionManager.prototype.endDrag = async function endDrag() {
        var state = this.dragState;
        var object;
        var worldPosition;
        var constants = modules._3D || {};
        var scaleFactor = constants.SCALE_FACTOR || 0.01;
        var endpoint;
        var payload;

        this.dragState = null;
        if (this.sm.controls) {
            this.sm.controls.enabled = true;
        }
        this.setCursor('grab');

        if (!state || !state.object) return;

        object = state.object;
        if (this.pointerDown && !this.pointerDown.moved) {
            object.position.copy(state.startPosition);
            this.resetCursor();
            return;
        }

        worldPosition = new global.THREE.Vector3();
        object.getWorldPosition(worldPosition);

        if (object.userData.type === 'cabinet') {
            endpoint = '/api/cabinets/' + object.userData.id + '/layout';
        } else if (object.userData.type === 'standalone-box') {
            endpoint = '/api/boxes/' + object.userData.id + '/layout';
        } else {
            return;
        }

        payload = {
            position_x: Math.round(worldPosition.x / scaleFactor),
            position_y: Math.round(worldPosition.z / scaleFactor)
        };

        try {
            await this.ctx.api.put(endpoint, payload);
            this.updateLocalMapData(object, payload);
            this.showToast('位置已保存', 'success');
        } catch (err) {
            object.position.copy(state.startPosition);
            this.showToast('保存位置失败：' + err.message, 'error');
        }
    };

    /** 取消拖拽时只回滚本次交互，不向后端保存。 */
    InteractionManager.prototype.cancelDrag = function cancelDrag() {
        if (this.dragState && this.dragState.object && this.dragState.startPosition) {
            this.dragState.object.position.copy(this.dragState.startPosition);
        }
        this.dragState = null;
        if (this.sm.controls) {
            this.sm.controls.enabled = true;
        }
        this.resetCursor();
    };

    /** 更新把手发光和格子轻微抬起反馈，帮助用户判断当前可点击对象。 */
    InteractionManager.prototype.updateHover = function updateHover(event) {
        var hit = this.pickObject(event);
        var object = hit ? hit.object : null;
        var cursor = '';

        this.updateHandleHover(object && object.userData.type === 'handle' ? object : null);
        this.updateCellHover(object && (object.userData.type === 'box-cells' || object.userData.type === 'box-cell') ? object : null, hit ? hit.instanceId : null);

        if (object && object.userData.type === 'handle') {
            cursor = 'pointer';
        } else if (object && (object.userData.type === 'box-cells' || object.userData.type === 'box-cell')) {
            cursor = 'pointer';
        } else if (!this.isLayoutLocked() && (this.findParentByType(object, 'cabinet') || this.findParentByType(object, 'standalone-box'))) {
            cursor = 'grab';
        }
        this.setCursor(cursor);
    };

    /** 从 handle userData 查找 DrawerGroup。 */
    InteractionManager.prototype.findDrawerByHandle = function findDrawerByHandle(handleData) {
        if (!handleData) return null;
        return (this.sm.drawerMap || {})[handleData.cabinetId + '-' + handleData.slotIndex] || null;
    };

    /** 向上查找指定 userData.type 的父级。 */
    InteractionManager.prototype.findParentByType = function findParentByType(object, type) {
        var current = object;
        while (current) {
            if (current.userData && current.userData.type === type) return current;
            current = current.parent;
        }
        return null;
    };

    /** 点击格子时查找后端格子数据，有元器件则打开详情，否则给出空格提示。 */
    InteractionManager.prototype.openCellComponent = async function openCellComponent(cellMesh, instanceId) {
        var data = cellMesh.userData || {};
        var cols = Math.max(1, Number(data.cols || 1));
        var row = data.type === 'box-cell' ? Number(data.gridRow || 0) : Math.floor(Number(instanceId || 0) / cols);
        var col = data.type === 'box-cell' ? Number(data.gridCol || 0) : Number(instanceId || 0) % cols;
        var gridData;
        var cell;
        var component;

        if (!data.boxId) return;

        gridData = this.ctx.lazyGrids && this.ctx.lazyGrids[data.boxId]
            ? this.ctx.lazyGrids[data.boxId]
            : await this.ctx.loadBoxGrid(data.boxId);
        gridData = this.normalizeGridData(gridData, null);
        cell = this.getGridCell(gridData, row, col);
        component = cell && cell.component;

        if (component && component.id && typeof this.ctx.openComponentDetail === 'function') {
            this.ctx.openComponentDetail(component.id);
        } else {
            this.showToast('该格子为空', 'info');
        }
    };

    InteractionManager.prototype.updateHandleHover = function updateHandleHover(newHandle) {
        if (this.hoveredHandle === newHandle) return;
        this.restoreHoveredHandle();
        this.hoveredHandle = newHandle;
        if (newHandle && newHandle.material && newHandle.material.emissive) {
            newHandle.material.emissive.setHex(0x333333);
        }
    };

    InteractionManager.prototype.restoreHoveredHandle = function restoreHoveredHandle() {
        if (this.hoveredHandle && this.hoveredHandle.material && this.hoveredHandle.material.emissive) {
            this.hoveredHandle.material.emissive.setHex(0x000000);
        }
        this.hoveredHandle = null;
    };

    InteractionManager.prototype.updateCellHover = function updateCellHover(cellMesh, instanceId) {
        if (this.hoveredCell && (this.hoveredCell.mesh !== cellMesh || this.hoveredCell.instanceId !== instanceId)) {
            this.restoreHoveredCell();
        }
        if (!cellMesh || instanceId === null || instanceId === undefined || (this.hoveredCell && this.hoveredCell.mesh === cellMesh && this.hoveredCell.instanceId === instanceId)) {
            return;
        }

        // 元器件标签已贴在格子顶面；hover 不再抬高格子，避免格子盖住自己的标签。
        this.hoveredCell = {
            mesh: cellMesh,
            instanceId: instanceId
        };
    };

    InteractionManager.prototype.restoreHoveredCell = function restoreHoveredCell() {
        this.hoveredCell = null;
    };

    InteractionManager.prototype.intersectGround = function intersectGround(event) {
        var intersection = new global.THREE.Vector3();
        this.pickObject(event);
        if (this.raycaster && this.raycaster.ray.intersectPlane(this.groundPlane, intersection)) {
            return intersection;
        }
        return null;
    };

    InteractionManager.prototype.findChildByType = function findChildByType(root, type) {
        var found = null;
        if (!root) return null;
        root.traverse(function visit(child) {
            if (!found && child.userData && child.userData.type === type) {
                found = child;
            }
        });
        return found;
    };

    InteractionManager.prototype.normalizeGridData = function normalizeGridData(gridData, drawerGroup) {
        var cells = gridData && gridData.cells ? gridData.cells : [];
        var rows = Number(gridData && gridData.rows) || cells.length || Number(drawerGroup && drawerGroup.userData.boxData && drawerGroup.userData.boxData.rows) || 1;
        var cols = Number(gridData && gridData.cols) || this.getMaxCols(cells) || Number(drawerGroup && drawerGroup.userData.boxData && drawerGroup.userData.boxData.cols) || 1;

        return Object.assign({}, gridData || {}, {
            rows: rows,
            cols: cols,
            cells: cells
        });
    };

    InteractionManager.prototype.getMaxCols = function getMaxCols(cells) {
        var maxCols = 0;
        (cells || []).forEach(function measure(row) {
            maxCols = Math.max(maxCols, row ? row.length : 0);
        });
        return maxCols;
    };

    InteractionManager.prototype.getGridCell = function getGridCell(gridData, rowIndex, colIndex) {
        var cells = gridData && gridData.cells ? gridData.cells : [];
        var row = cells[rowIndex] || [];
        var cell = row[colIndex] || null;
        var i;
        var j;

        if (cell) return cell;

        // 后端若返回稀疏或按 1 基行列标记的数据，按 row/col 字段兜底查找。
        for (i = 0; i < cells.length; i += 1) {
            for (j = 0; j < (cells[i] || []).length; j += 1) {
                cell = cells[i][j];
                if (cell && Number(cell.row) === rowIndex + 1 && Number(cell.col) === colIndex + 1) {
                    return cell;
                }
            }
        }
        return null;
    };

    InteractionManager.prototype.updateLocalMapData = function updateLocalMapData(object, payload) {
        var listName = object.userData.type === 'cabinet' ? 'mapCabinets' : 'mapBoxes';
        var items = this.ctx[listName] || [];

        items.forEach(function updateItem(item) {
            if (Number(item.id) === Number(object.userData.id)) {
                item.position_x = payload.position_x;
                item.position_y = payload.position_y;
            }
        });
    };

    InteractionManager.prototype.callOptionalLabelHook = function callOptionalLabelHook(methodName) {
        var labels = modules._3DLabels;
        var args;
        if (!labels || typeof labels[methodName] !== 'function') return;
        args = Array.prototype.slice.call(arguments, 1);
        labels[methodName].apply(labels, args);
    };

    InteractionManager.prototype.showToast = function showToast(message, type) {
        if (this.ctx && typeof this.ctx.toast === 'function') {
            this.ctx.toast(message, type || 'info');
        }
    };

    InteractionManager.prototype.getCanvas = function getCanvas() {
        return this.sm && this.sm.renderer ? this.sm.renderer.domElement : null;
    };

    InteractionManager.prototype.getCanvasRect = function getCanvasRect() {
        var canvas = this.getCanvas();
        return canvas ? canvas.getBoundingClientRect() : null;
    };

    InteractionManager.prototype.setCursor = function setCursor(cursor) {
        var canvas = this.getCanvas();
        if (canvas) {
            canvas.style.cursor = cursor || '';
        }
    };

    InteractionManager.prototype.resetCursor = function resetCursor() {
        this.setCursor('');
    };

    modules.InteractionManager = InteractionManager;
})(window);
