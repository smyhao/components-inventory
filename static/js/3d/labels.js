// 本文件负责 3D 场景标签系统：名称牌和抽屉格子元器件标签；只处理标签生命周期，不承担交互判断。
(function registerLabels(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});
    modules._3D = modules._3D || {};

    /** 获取 CSS2DObject 构造器；它来自 Three.js addon，不属于 THREE 默认命名空间。 */
    function getCSS2DObject() {
        var CSS2DObject = global.CSS2DObjectModule || (global.THREE && global.THREE.CSS2DObject);
        if (!CSS2DObject) {
            throw new Error('CSS2DObject 未加载，无法创建 3D 标签。');
        }
        return CSS2DObject;
    }

    /** 创建安全文本节点，避免名称或封装字段中的特殊字符破坏标签 DOM。 */
    function appendText(parent, className, text) {
        var span = global.document.createElement('span');
        if (className) span.className = className;
        span.textContent = text || '';
        parent.appendChild(span);
        return span;
    }

    /**
     * 创建柜子或收纳盒名称牌。
     * @param {string} name 名称文本。
     * @param {string} color 颜色值。
     * @returns {CSS2DObject} 标签对象。
     */
    function createNameplate(name, color) {
        var CSS2DObject = getCSS2DObject();
        var div = global.document.createElement('div');
        var dot = global.document.createElement('span');
        var label = new CSS2DObject(div);

        div.className = 'nameplate-3d';
        dot.className = 'color-dot';
        dot.style.background = color || '#999999';
        div.appendChild(dot);
        appendText(div, '', name || '未命名');

        label.userData = { type: 'label-nameplate' };
        return label;
    }

    /** 创建带文字纹理的实体铭牌 Mesh，用于柜体和抽屉门板，避免名称像 UI 浮层一样漂在场景里。 */
    function createPhysicalNameplate(name, options) {
        var THREE = global.THREE;
        var canvas = global.document.createElement('canvas');
        var ctx = canvas.getContext('2d');
        var width = options.width || 0.46;
        var height = options.height || 0.09;
        var accent = options.accent || '#8b9aae';
        var texture;
        var material;
        var backingMaterial;
        var backing;
        var plate;
        var group;
        var text = String(name || '未命名');
        var fontSize = options.fontSize || 38;
        var textMaxWidth;

        canvas.width = 512;
        canvas.height = 128;
        textMaxWidth = options.textMaxWidth || canvas.width - 74;

        ctx.fillStyle = '#f9f5ec';
        roundRect(ctx, 8, 8, canvas.width - 16, canvas.height - 16, 18);
        ctx.fill();
        ctx.strokeStyle = accent;
        ctx.lineWidth = 6;
        roundRect(ctx, 12, 12, canvas.width - 24, canvas.height - 24, 14);
        ctx.stroke();

        ctx.fillStyle = '#27342f';
        ctx.font = '800 ' + fontSize + 'px "Microsoft YaHei", "PingFang SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        drawFittedText(ctx, text, canvas.width / 2, canvas.height / 2 + 2, textMaxWidth);

        texture = new THREE.CanvasTexture(canvas);
        texture.anisotropy = 4;
        material = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: false,
            toneMapped: false
        });
        backingMaterial = new THREE.MeshStandardMaterial({
            color: '#efe7d7',
            roughness: 0.48,
            metalness: 0.05
        });
        backing = new THREE.Mesh(new THREE.BoxGeometry(width + 0.018, height + 0.014, 0.01), backingMaterial);
        plate = new THREE.Mesh(new THREE.PlaneGeometry(width, height), material);
        plate.position.z = 0.0065;
        group = new THREE.Group();
        group.add(backing);
        group.add(plate);
        group.userData = { type: options.type || 'label-physical-nameplate' };
        return group;
    }

    function roundRect(ctx, x, y, width, height, radius) {
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
    }

    function drawFittedText(ctx, text, x, y, maxWidth) {
        var current = text;
        while (current.length > 1 && ctx.measureText(current).width > maxWidth) {
            current = current.slice(0, -2) + '…';
        }
        ctx.fillText(current, x, y);
    }

    /** 创建贴在格子顶面的实体元器件标签，避免标签像屏幕 UI 一样漂浮。 */
    function createComponentSurfaceLabel(component, options) {
        var THREE = global.THREE;
        var canvas = global.document.createElement('canvas');
        var ctx = canvas.getContext('2d');
        var width = options.width || 0.11;
        var depth = options.depth || 0.045;
        var texture;
        var plate;
        var backing;
        var group;
        var title = String(component.name || '未命名');
        var detail = component.package ? String(component.package) : '';

        canvas.width = 384;
        canvas.height = 160;
        ctx.fillStyle = '#fffaf0';
        roundRect(ctx, 10, 10, canvas.width - 20, canvas.height - 20, 18);
        ctx.fill();
        ctx.strokeStyle = '#5a8a6a';
        ctx.lineWidth = 6;
        roundRect(ctx, 16, 16, canvas.width - 32, canvas.height - 32, 14);
        ctx.stroke();

        ctx.fillStyle = '#20312b';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.font = '700 38px "Microsoft YaHei", "PingFang SC", sans-serif';
        drawFittedText(ctx, title, canvas.width / 2, detail ? 65 : 80, canvas.width - 58);
        if (detail) {
            ctx.fillStyle = '#65756d';
            ctx.font = '500 26px "Microsoft YaHei", "PingFang SC", sans-serif';
            drawFittedText(ctx, detail, canvas.width / 2, 112, canvas.width - 72);
        }

        texture = new THREE.CanvasTexture(canvas);
        texture.anisotropy = 4;
        backing = new THREE.Mesh(
            new THREE.BoxGeometry(width + 0.01, 0.004, depth + 0.008),
            new THREE.MeshStandardMaterial({
                color: '#eee4d1',
                roughness: 0.58,
                metalness: 0.02
            })
        );
        plate = new THREE.Mesh(
            new THREE.PlaneGeometry(width, depth),
            new THREE.MeshBasicMaterial({
                map: texture,
                toneMapped: false
            })
        );
        plate.rotation.x = -Math.PI / 2;
        plate.position.y = 0.003;

        group = new THREE.Group();
        group.add(backing);
        group.add(plate);
        group.userData = {
            type: 'label-compartment',
            physical: true
        };
        return group;
    }

    function anchorDirection(root, fromName, toName) {
        var THREE = global.THREE;
        var from = findChildByNormalizedName(root, fromName);
        var to = findChildByNormalizedName(root, toName);
        var fromWorld;
        var toWorld;
        var direction;

        if (!from || !to) return null;
        fromWorld = new THREE.Vector3();
        toWorld = new THREE.Vector3();
        from.getWorldPosition(fromWorld);
        to.getWorldPosition(toWorld);
        direction = toWorld.sub(fromWorld);
        if (direction.lengthSq() < 0.000001) return null;
        return direction.normalize();
    }

    function orientNameplateToNormal(label, parent, normal, normalIsWorld) {
        var THREE = global.THREE;
        var zAxis;
        var yAxis = new THREE.Vector3(0, 1, 0);
        var xAxis;
        var matrix;
        var worldQuat;
        var parentQuat;

        if (!label || !normal) return false;
        zAxis = normal.clone();
        if (!normalIsWorld && parent) {
            parentQuat = new THREE.Quaternion();
            parent.getWorldQuaternion(parentQuat);
            zAxis.applyQuaternion(parentQuat);
        }
        if (zAxis.lengthSq() < 0.000001) return false;
        zAxis.normalize();
        yAxis.sub(zAxis.clone().multiplyScalar(yAxis.dot(zAxis)));
        if (yAxis.lengthSq() < 0.000001) {
            yAxis.set(0, 0, 1).sub(zAxis.clone().multiplyScalar(zAxis.z));
        }
        if (yAxis.lengthSq() < 0.000001) return false;
        yAxis.normalize();
        xAxis = yAxis.clone().cross(zAxis).normalize();
        yAxis = zAxis.clone().cross(xAxis).normalize();

        matrix = new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis);
        worldQuat = new THREE.Quaternion().setFromRotationMatrix(matrix);
        if (parent) {
            parentQuat = new THREE.Quaternion();
            parent.getWorldQuaternion(parentQuat);
            label.quaternion.copy(parentQuat.invert().multiply(worldQuat));
        } else {
            label.quaternion.copy(worldQuat);
        }
        return true;
    }

    /** 为柜子底部柜腿中间添加实体铭牌。 */
    function addCabinetNameplate(cabinetGroup, cabinetData) {
        var THREE = global.THREE;
        var C = modules._3D || {};
        var modelTools = modules._3DModels || {};
        var depth;
        var legHeight;
        var label;
        var anchor;
        var target;
        var normal;
        var anchorQuat;
        var parentQuat;
        var modelBox;
        var modelSize;
        var labelWidth = 0.82;
        var labelHeight = 0.115;
        var fontSize = 64;

        if (!cabinetGroup || !cabinetData) return;
        removeLabelsByType(cabinetGroup, 'label-cabinet-nameplate');

        depth = C.CABINET_DEPTH || 0.8;
        legHeight = C.CABINET_LEG_HEIGHT || 0.16;
        if (cabinetData.template && typeof modelTools.getRenderableBox === 'function') {
            modelBox = modelTools.getRenderableBox(cabinetGroup);
            modelSize = new THREE.Vector3();
            if (!modelBox.isEmpty()) {
                modelBox.getSize(modelSize);
                labelWidth = clamp(modelSize.x * 0.58, 0.12, 0.48);
                labelHeight = clamp(modelSize.y * 0.10, 0.028, 0.075);
                fontSize = Math.round(clamp(labelHeight / 0.075 * 44, 22, 48));
            }
        }
        label = createPhysicalNameplate(cabinetData.name, {
            width: labelWidth,
            height: labelHeight,
            fontSize: fontSize,
            textMaxWidth: 486,
            accent: cabinetData.color,
            type: 'label-cabinet-nameplate'
        });
        if (cabinetData.template) {
            anchor = findChildByNormalizedName(cabinetGroup, 'NAMEPLATE_ANCHOR');
            if (anchor) {
                target = new THREE.Vector3();
                anchorQuat = new THREE.Quaternion();
                parentQuat = new THREE.Quaternion();
                anchor.getWorldPosition(target);
                anchor.getWorldQuaternion(anchorQuat);
                cabinetGroup.getWorldQuaternion(parentQuat);
                label.position.copy(cabinetGroup.worldToLocal(target));
                normal = anchorDirection(cabinetGroup, 'DRAWER_CLOSED_ANCHOR', 'DRAWER_OPEN_ANCHOR');
                if (!orientNameplateToNormal(label, cabinetGroup, normal, true)) {
                    label.quaternion.copy(parentQuat.invert().multiply(anchorQuat));
                }
            } else {
                label.position.copy(cabinetNameplateFallbackPosition(cabinetGroup));
            }
        } else {
            label.position.set(0, legHeight * 0.60, depth / 2 + 0.032);
        }
        label.userData.type = 'label-cabinet-nameplate';
        cabinetGroup.add(label);
    }

    function cabinetNameplateFallbackPosition(cabinetGroup) {
        var THREE = global.THREE;
        var modelTools = modules._3DModels || {};
        var box = typeof modelTools.getRenderableBox === 'function'
            ? modelTools.getRenderableBox(cabinetGroup)
            : new THREE.Box3().setFromObject(cabinetGroup);
        var center = new THREE.Vector3();
        var target;

        if (box.isEmpty()) return new THREE.Vector3(0, 0.09, 0.43);
        box.getCenter(center);
        target = new THREE.Vector3(center.x, box.min.y + 0.08, box.max.z + 0.032);
        return cabinetGroup.worldToLocal(target);
    }

    /** 为抽屉门板添加实体收纳盒铭牌；它挂在 drawerGroup 下，会随抽屉一起抽拉。 */
    function addDrawerNameplate(drawerGroup, boxData) {
        var C = modules._3D || {};
        var modelTools = modules._3DModels || {};
        var layerHeight = C.LAYER_HEIGHT || 0.35;
        var thickness = C.WALL_THICKNESS || 0.03;
        var depth = C.CABINET_DEPTH || 0.8;
        var panelHeight = layerHeight - thickness - 0.02;
        var label;
        var box;
        var size;
        var center;
        var labelWidth = 0.74;
        var labelHeight = 0.105;
        var fontSize = 66;

        if (!drawerGroup) return;
        removeDrawerNameplate(drawerGroup);
        if (!boxData) return;

        if (drawerGroup.userData && drawerGroup.userData.customModel && typeof modelTools.getRenderableBox === 'function') {
            box = modelTools.getRenderableBox(drawerGroup);
            size = new global.THREE.Vector3();
            if (!box.isEmpty()) {
                box.getSize(size);
                labelWidth = clamp(size.x * 0.72, 0.08, 0.38);
                labelHeight = clamp(size.y * 0.34, 0.022, 0.07);
                fontSize = Math.round(clamp(labelHeight / 0.07 * 42, 20, 46));
            }
        }

        label = createPhysicalNameplate(boxData.name, {
            width: labelWidth,
            height: labelHeight,
            fontSize: fontSize,
            textMaxWidth: 488,
            accent: boxData.color,
            type: 'label-drawer-nameplate'
        });
        if (drawerGroup.userData && drawerGroup.userData.customModel) {
            if (drawerGroup.userData.nameplatePosition) {
                label.position.copy(drawerGroup.userData.nameplatePosition);
                if (drawerGroup.userData.nameplateNormal) {
                    orientNameplateToNormal(label, drawerGroup, drawerGroup.userData.nameplateNormal, false);
                } else if (drawerGroup.userData.nameplateQuaternion) {
                    label.quaternion.copy(drawerGroup.userData.nameplateQuaternion);
                }
            } else if (box && !box.isEmpty()) {
                center = new global.THREE.Vector3();
                box.getCenter(center);
                label.position.copy(drawerGroup.worldToLocal(new global.THREE.Vector3(center.x, center.y, box.max.z + 0.012)));
            } else {
                label.position.set(0, 0.04, 0.05);
            }
        } else {
            label.position.set(0, panelHeight * 0.73 + thickness / 2, depth / 2 + 0.021);
        }
        label.userData.type = 'label-drawer-nameplate';
        drawerGroup.add(label);
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, Number(value) || min));
    }

    /** 移除单个抽屉名称牌。 */
    function removeDrawerNameplate(drawerGroup) {
        removeLabelsByType(drawerGroup, 'label-drawer-nameplate');
    }

    /**
     * 为抽屉内有元器件的格子创建标签。
     * 标签挂在 drawerGroup 下，位置用 InstancedMesh 矩阵推导，避免与格子布局公式重复后产生偏差。
     */
    function addCompartmentLabels(drawerGroup, gridData) {
        var cellMesh;
        var rows;
        var cols;
        var instanceId;
        var row;
        var col;
        var cell;
        var component;
        var matrix;
        var position;

        if (!drawerGroup || !gridData || !gridData.cells) return;

        cellMesh = findChildByType(drawerGroup, 'box-cells');
        if (!cellMesh) return;

        removeCompartmentLabels(drawerGroup);
        rows = Math.max(1, Number(gridData.rows || cellMesh.userData.rows || 1));
        cols = Math.max(1, Number(gridData.cols || cellMesh.userData.cols || 1));
        matrix = new global.THREE.Matrix4();
        position = new global.THREE.Vector3();

        for (row = 0; row < rows; row += 1) {
            for (col = 0; col < cols; col += 1) {
                cell = getGridCell(gridData, row, col);
                component = cell && cell.component;
                if (!component) continue;

                instanceId = row * cols + col;
                if (instanceId >= cellMesh.count) continue;

                cellMesh.getMatrixAt(instanceId, matrix);
                position.setFromMatrixPosition(matrix);
                addCompartmentLabel(drawerGroup, {
                    component: component,
                    row: row,
                    col: col,
                    x: cellMesh.position.x + position.x,
                    y: cellMesh.position.y + position.y + 0.018,
                    z: cellMesh.position.z + position.z
                });
            }
        }
    }

    /** 创建单个格子标签，标签实体贴在占用格子顶面，远距离时整体隐藏。 */
    function addCompartmentLabel(drawerGroup, options) {
        var label;
        var comp = options.component || {};

        label = createComponentSurfaceLabel(comp, {
            width: 0.14,
            depth: 0.056
        });
        label.position.set(options.x, options.y, options.z);
        label.userData = {
            type: 'label-compartment',
            physical: true,
            row: options.row,
            col: options.col,
            componentId: comp.id || null
        };
        drawerGroup.add(label);
    }

    /** 移除抽屉内所有格子元器件标签。 */
    function removeCompartmentLabels(drawerGroup) {
        removeLabelsByType(drawerGroup, 'label-compartment');
    }

    /** 根据相机距离更新格子标签 LOD：近看完整，中距仅名称，远距隐藏。 */
    function updateLabelVisibility(camera, mapGroup) {
        var tempVec;

        if (!camera || !mapGroup || !global.THREE) return;
        tempVec = new global.THREE.Vector3();

        mapGroup.traverse(function updateLabel(child) {
            var distance;
            var detail;

            if (!child.userData || child.userData.type !== 'label-compartment') return;

            child.getWorldPosition(tempVec);
            distance = camera.position.distanceTo(tempVec);
            if (child.userData.physical) {
                child.visible = distance <= 10;
                return;
            }
            if (!child.element) return;
            detail = child.element.querySelector('.label-detail');

            if (distance > 15) {
                child.element.style.display = 'none';
            } else if (distance > 5) {
                child.element.style.display = '';
                if (detail) detail.style.display = 'none';
            } else {
                child.element.style.display = '';
                if (detail && detail.textContent) detail.style.display = '';
            }
        });
    }

    /** 为独立收纳盒添加名称牌。 */
    function addBoxNameplate(boxGroup, boxData) {
        var label;
        if (!boxGroup || !boxData) return;
        removeLabelsByType(boxGroup, 'label-box-nameplate');
        label = createNameplate(boxData.name, boxData.color);
        label.position.set(0, 0.17, 0.23);
        label.userData.type = 'label-box-nameplate';
        boxGroup.add(label);
    }

    /** 根据 type 从某个父节点移除标签，同时清理 CSS2DObject 持有的 DOM 元素。 */
    function removeLabelsByType(parent, type) {
        var toRemove = [];
        if (!parent || !parent.children) return;

        parent.children.forEach(function collect(child) {
            if (child.userData && child.userData.type === type) {
                toRemove.push(child);
            }
        });
        toRemove.forEach(function remove(child) {
            parent.remove(child);
            disposeLabelObject(child);
        });
    }

    /** 标签可能是 CSS2DObject，也可能是实体 Mesh/Group；移除时统一清理 DOM、几何体和纹理。 */
    function disposeLabelObject(label) {
        if (!label) return;
        if (label.children && label.children.length) {
            while (label.children.length) {
                disposeLabelObject(label.children.pop());
            }
        }
        disposeLabelElement(label);
        if (label.geometry && typeof label.geometry.dispose === 'function') {
            label.geometry.dispose();
        }
        disposeMaterial(label.material);
    }

    function disposeMaterial(material) {
        if (!material) return;
        if (Array.isArray(material)) {
            material.forEach(disposeMaterial);
            return;
        }
        Object.keys(material).forEach(function disposeTexture(key) {
            var value = material[key];
            if (value && typeof value.dispose === 'function') {
                value.dispose();
            }
        });
        if (typeof material.dispose === 'function') {
            material.dispose();
        }
    }

    /** 清理 CSS2DObject 的 DOM 节点；Three.js dispose 不会自动处理 HTML 元素。 */
    function disposeLabelElement(label) {
        if (label && label.element && label.element.parentNode) {
            label.element.parentNode.removeChild(label.element);
        }
    }

    function findChildByType(root, type) {
        var found = null;
        if (!root) return null;
        root.traverse(function visit(child) {
            if (!found && child.userData && child.userData.type === type) {
                found = child;
            }
        });
        return found;
    }

    function findChildByNormalizedName(root, normalizedName) {
        var found = null;
        if (!root) return null;
        root.traverse(function visit(child) {
            if (!found && child.userData && child.userData.normalizedName === normalizedName) {
                found = child;
            }
        });
        return found;
    }

    /** 支持二维数组直接索引，也兼容按 row/col 字段返回的稀疏格子数据。 */
    function getGridCell(gridData, rowIndex, colIndex) {
        var cells = gridData && gridData.cells ? gridData.cells : [];
        var row = cells[rowIndex] || [];
        var cell = row[colIndex] || null;
        var i;
        var j;

        if (cell) return cell;
        for (i = 0; i < cells.length; i += 1) {
            for (j = 0; j < (cells[i] || []).length; j += 1) {
                cell = cells[i][j];
                if (cell && Number(cell.row) === rowIndex + 1 && Number(cell.col) === colIndex + 1) {
                    return cell;
                }
            }
        }
        return null;
    }

    modules._3D.createNameplate = createNameplate;
    modules._3D.addCabinetNameplate = addCabinetNameplate;
    modules._3D.addDrawerNameplate = addDrawerNameplate;
    modules._3D.removeDrawerNameplate = removeDrawerNameplate;
    modules._3D.addCompartmentLabels = addCompartmentLabels;
    modules._3D.removeCompartmentLabels = removeCompartmentLabels;
    modules._3D.updateLabelVisibility = updateLabelVisibility;
    modules._3D.addBoxNameplate = addBoxNameplate;
    modules._3D.disposeLabelElement = disposeLabelElement;

    // interaction.js 已预留 _3DLabels 钩子；这里桥接成稳定的小接口。
    modules._3DLabels = {
        showCellLabels: addCompartmentLabels,
        clearCellLabels: removeCompartmentLabels
    };
})(window);
