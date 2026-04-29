// 本文件负责参数化柜子 3D 模型构建，包括外壳、层架、抽屉和把手，属于 3D 引擎层；不做交互和标签渲染。
(function registerCabinetModel(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});
    modules._3D = modules._3D || {};

    /**
     * 创建一块板壁 Mesh。
     * @param {number} width 宽度。
     * @param {number} height 高度。
     * @param {number} depth 深度。
     * @param {number|string} color 板壁颜色。
     * @returns {THREE.Mesh} 可投影和接收阴影的板壁。
     */
    function createBoard(width, height, depth, color, materialOptions) {
        var THREE = global.THREE;
        var geometry = new THREE.BoxGeometry(
            Math.max(0.001, width),
            Math.max(0.001, height),
            Math.max(0.001, depth)
        );
        var material = createMaterial(color, materialOptions || {});
        var mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        return mesh;
    }

    /** 创建统一的金属/烤漆材质，让柜体不再像纯色积木块。 */
    function createMaterial(color, options) {
        var THREE = global.THREE;
        var shaded = new THREE.Color(color || '#8b9aae');
        if (options.lightness || options.saturation) {
            shaded.offsetHSL(0, options.saturation || 0, options.lightness || 0);
        }
        return new THREE.MeshStandardMaterial({
            color: shaded,
            roughness: options.roughness === undefined ? 0.52 : options.roughness,
            metalness: options.metalness === undefined ? 0.18 : options.metalness
        });
    }

    function createCabinetColor(base, lightness) {
        var THREE = global.THREE;
        var color = new THREE.Color(base || '#8b9aae');
        color.offsetHSL(0, -0.08, lightness || 0);
        return color;
    }

    /**
     * 构建完整的柜子 3D 模型。
     *
     * 柜子由外壳、层架和抽屉组成；把手与抽屉面板都标记为 handle，
     * 是为了让后续射线拾取在桌面和触屏上都有足够大的点击区域。
     *
     * @param {object} cabinetData 柜子数据，需包含按 cabinet_id 注入的 boxes 数组。
     * @param {object} drawerMap SceneManager 维护的抽屉映射表，函数会向其中填充数据。
     * @returns {THREE.Group} 柜子根节点。
     */
    function buildCabinet(cabinetData, drawerMap) {
        var THREE = global.THREE;
        var constants = modules._3D || {};
        var group = new THREE.Group();
        var width = constants.CABINET_WIDTH || 1.2;
        var depth = constants.CABINET_DEPTH || 0.8;
        var layerHeight = constants.LAYER_HEIGHT || 0.35;
        var thickness = constants.WALL_THICKNESS || 0.03;
        var legHeight = constants.CABINET_LEG_HEIGHT || 0.16;
        var scaleFactor = constants.SCALE_FACTOR || 0.01;
        var bodyColor = cabinetData.color || '#8b9aae';
        var boxes = (cabinetData.boxes || []).slice().sort(function sortBySlot(left, right) {
            var leftSlot = Number(left.cabinet_slot || 0);
            var rightSlot = Number(right.cabinet_slot || 0);
            if (leftSlot !== rightSlot) return leftSlot - rightSlot;
            return String(left.name || '').localeCompare(String(right.name || ''));
        });
        // 柜子的层数表达“柜内收纳盒数量”，不能使用 total_slots；total_slots 是收纳盒内部格子总数。
        var layers = Math.max(1, boxes.length);
        var bodyHeight = layers * layerHeight + thickness * 2;
        var i;

        addCabinetLegs(group, {
            width: width,
            depth: depth,
            height: legHeight,
            thickness: thickness,
            color: bodyColor
        });
        addCabinetShell(group, {
            width: width,
            depth: depth,
            height: bodyHeight,
            thickness: thickness,
            color: bodyColor,
            yOffset: legHeight
        });

        for (i = 0; i < layers; i += 1) {
            addLayer(group, {
                cabinetData: cabinetData,
                drawerMap: drawerMap,
                boxData: boxes[i] || null,
                slotIndex: i,
                width: width,
                depth: depth,
                layerHeight: layerHeight,
                thickness: thickness,
                bodyColor: bodyColor,
                yOffset: legHeight
            });
        }

        group.position.set(
            Number(cabinetData.position_x || 0) * scaleFactor,
            0,
            Number(cabinetData.position_y || 0) * scaleFactor
        );
        group.userData = {
            type: 'cabinet',
            id: cabinetData.id,
            name: cabinetData.name,
            data: cabinetData,
            bodyHeight: bodyHeight,
            legHeight: legHeight
        };

        return group;
    }

    /** 添加柜子底部柜腿和前横梁，让柜体铭牌有实体承载面而不是悬浮在空间中。 */
    function addCabinetLegs(group, options) {
        var width = options.width;
        var depth = options.depth;
        var height = options.height;
        var thickness = options.thickness;
        var color = options.color;
        var legSize = thickness * 1.45;
        var railColor = createCabinetColor(color, -0.08);
        var frontZ = depth / 2 - legSize / 2;
        var backZ = -depth / 2 + legSize / 2;
        var leftX = -width / 2 + legSize / 2;
        var rightX = width / 2 - legSize / 2;
        var legPositions = [
            [leftX, frontZ],
            [rightX, frontZ],
            [leftX, backZ],
            [rightX, backZ]
        ];
        var frontRail = createBoard(width - legSize * 2, height * 0.55, thickness * 0.8, railColor, {
            roughness: 0.46,
            metalness: 0.28
        });

        legPositions.forEach(function addLeg(position) {
            var leg = createBoard(legSize, height, legSize, railColor, {
                roughness: 0.45,
                metalness: 0.3
            });
            leg.position.set(position[0], height / 2, position[1]);
            group.add(leg);
        });

        frontRail.position.set(0, height * 0.52, frontZ + thickness * 0.3);
        group.add(frontRail);
    }

    /** 添加柜子顶板、底板、背板和左右侧板，保持所有抽屉子节点使用柜体局部坐标。 */
    function addCabinetShell(group, options) {
        var width = options.width;
        var depth = options.depth;
        var height = options.height;
        var thickness = options.thickness;
        var color = options.color;
        var yOffset = options.yOffset || 0;
        var shellColor = createCabinetColor(color, -0.04);
        var edgeColor = createCabinetColor(color, -0.13);
        var top = createBoard(width + 0.04, thickness * 1.2, depth + 0.035, edgeColor, { roughness: 0.42, metalness: 0.32 });
        var bottom = createBoard(width, thickness, depth, edgeColor, { roughness: 0.45, metalness: 0.28 });
        var back = createBoard(width, height, thickness, shellColor, { roughness: 0.55, metalness: 0.16 });
        var left = createBoard(thickness * 1.25, height, depth, edgeColor, { roughness: 0.45, metalness: 0.3 });
        var right = createBoard(thickness * 1.25, height, depth, edgeColor, { roughness: 0.45, metalness: 0.3 });
        var frontLeft = createBoard(thickness * 1.15, height, thickness * 1.25, edgeColor, { roughness: 0.42, metalness: 0.32 });
        var frontRight = createBoard(thickness * 1.15, height, thickness * 1.25, edgeColor, { roughness: 0.42, metalness: 0.32 });

        top.position.set(0, yOffset + height - thickness / 2, 0);
        bottom.position.set(0, yOffset + thickness / 2, 0);
        back.position.set(0, yOffset + height / 2, -depth / 2 + thickness / 2);
        left.position.set(-width / 2 + thickness / 2, yOffset + height / 2, 0);
        right.position.set(width / 2 - thickness / 2, yOffset + height / 2, 0);
        frontLeft.position.set(-width / 2 + thickness / 2, yOffset + height / 2, depth / 2 - thickness / 2);
        frontRight.position.set(width / 2 - thickness / 2, yOffset + height / 2, depth / 2 - thickness / 2);

        group.add(top);
        group.add(bottom);
        group.add(back);
        group.add(left);
        group.add(right);
        group.add(frontLeft);
        group.add(frontRight);
    }

    /** 添加单层层架和抽屉组，抽屉状态放在 userData 中供后续动画模块消费。 */
    function addLayer(group, options) {
        var THREE = global.THREE;
        var slotIndex = options.slotIndex;
        var yBase = (options.yOffset || 0) + options.thickness + slotIndex * options.layerHeight;
        var drawerGroup = new THREE.Group();
        var panelWidth = options.width - options.thickness * 2 - 0.02;
        var panelHeight = options.layerHeight - options.thickness - 0.02;
        var panelColor = options.boxData ? (options.boxData.color || '#84b59b') : '#b8c4d0';
        var shelf;
        var bayFrame;
        var bayShadow;
        var frontZ = options.depth / 2 - options.thickness * 0.35;
        var frameColor = createCabinetColor(options.bodyColor, -0.12);

        if (slotIndex > 0) {
            shelf = createBoard(
                options.width - options.thickness * 2,
                options.thickness,
                options.depth - options.thickness,
                frameColor,
                { roughness: 0.46, metalness: 0.28 }
            );
            shelf.position.set(0, yBase - options.thickness / 2, options.thickness / 4);
            group.add(shelf);
        }

        bayFrame = createBoard(panelWidth + 0.035, panelHeight + 0.025, options.thickness * 0.42, frameColor, {
            roughness: 0.42,
            metalness: 0.32
        });
        bayShadow = createBoard(panelWidth - 0.02, panelHeight - 0.018, options.thickness * 0.18, '#1f2624', {
            roughness: 0.65,
            metalness: 0.1
        });
        bayFrame.position.set(0, yBase + panelHeight / 2 + options.thickness / 2, frontZ - options.thickness * 0.95);
        bayShadow.position.set(0, yBase + panelHeight / 2 + options.thickness / 2, frontZ - options.thickness * 1.12);
        group.add(bayFrame);
        group.add(bayShadow);

        drawerGroup.position.set(0, yBase, 0);
        addDrawerParts(drawerGroup, {
            cabinetData: options.cabinetData,
            boxData: options.boxData,
            slotIndex: slotIndex,
            panelWidth: panelWidth,
            panelHeight: panelHeight,
            panelColor: panelColor,
            width: options.width,
            depth: options.depth,
            thickness: options.thickness,
            bodyColor: options.bodyColor
        });

        drawerGroup.userData = {
            type: 'drawer',
            cabinetId: options.cabinetData.id,
            slotIndex: slotIndex,
            boxId: options.boxData ? options.boxData.id : null,
            open: false,
            targetZ: 0,
            boxData: options.boxData
        };
        group.add(drawerGroup);

        if (options.drawerMap) {
            options.drawerMap[options.cabinetData.id + '-' + slotIndex] = drawerGroup;
        }
    }

    /** 构建抽屉面板、把手、侧板和底板，面板也作为可拾取区域服务移动端交互。 */
    function addDrawerParts(drawerGroup, options) {
        var THREE = global.THREE;
        var panel = createBoard(options.panelWidth - 0.018, options.panelHeight - 0.018, options.thickness * 0.9, options.panelColor, {
            lightness: -0.02,
            saturation: -0.05,
            roughness: 0.56,
            metalness: 0.08
        });
        var panelLip = createBoard(options.panelWidth - 0.006, options.thickness * 0.62, options.thickness * 0.7, '#27302d', {
            roughness: 0.48,
            metalness: 0.3
        });
        var panelBottomLip = createBoard(options.panelWidth - 0.006, options.thickness * 0.52, options.thickness * 0.7, '#27302d', {
            roughness: 0.48,
            metalness: 0.3
        });
        var handleGeometry = new THREE.CylinderGeometry(0.011, 0.011, Math.max(0.001, options.panelWidth * 0.34), 12);
        var handleMaterial = new THREE.MeshStandardMaterial({
            color: '#2b2f2e',
            metalness: 0.72,
            roughness: 0.24
        });
        var handle = new THREE.Mesh(handleGeometry, handleMaterial);
        var sideHeight = options.panelHeight;
        var sideDepth = options.depth * 0.66;
        var sideInset = options.thickness * 0.2;
        var leftSide = createBoard(options.thickness * 0.7, sideHeight, sideDepth, options.bodyColor);
        var rightSide = createBoard(options.thickness * 0.7, sideHeight, sideDepth, options.bodyColor);
        var floorBoard = createBoard(options.panelWidth - sideInset * 2, options.thickness * 0.65, sideDepth, options.bodyColor);
        var backBoard = createBoard(options.panelWidth, sideHeight, options.thickness * 0.5, options.bodyColor);
        var panelFrontZ = options.depth / 2 - options.thickness * 0.12;
        var panelBackZ = panelFrontZ - options.thickness * 0.9 / 2 - options.thickness * 0.06;
        var drawerBodyZ = panelBackZ - sideDepth / 2 + options.thickness * 0.18;
        var drawerBackZ = drawerBodyZ - sideDepth / 2 + options.thickness * 0.25;
        var tailLength = options.depth * 0.36;
        var tailZ = drawerBackZ - tailLength / 2 + options.thickness * 0.18;
        var innerBridge = createBoard(options.panelWidth - 0.05, options.thickness * 1.2, options.thickness * 1.1, options.bodyColor, {
            lightness: -0.04,
            roughness: 0.5,
            metalness: 0.12
        });
        var rearLeftRail = createBoard(options.thickness * 0.62, options.thickness * 1.5, tailLength, options.bodyColor, {
            lightness: -0.08,
            roughness: 0.48,
            metalness: 0.18
        });
        var rearRightRail = createBoard(options.thickness * 0.62, options.thickness * 1.5, tailLength, options.bodyColor, {
            lightness: -0.08,
            roughness: 0.48,
            metalness: 0.18
        });
        var rearBottomRail = createBoard(options.panelWidth - sideInset * 2, options.thickness * 0.5, tailLength, options.bodyColor, {
            lightness: -0.1,
            roughness: 0.5,
            metalness: 0.14
        });
        var handleData = {
            type: 'handle',
            cabinetId: options.cabinetData.id,
            slotIndex: options.slotIndex,
            boxId: options.boxData ? options.boxData.id : null
        };

        panel.position.set(0, options.panelHeight / 2 + options.thickness / 2, panelFrontZ - options.thickness * 0.9 / 2);
        panel.userData = handleData;
        drawerGroup.add(panel);
        panelLip.position.set(0, options.panelHeight + options.thickness * 0.18, panelFrontZ - options.thickness * 0.16);
        panelBottomLip.position.set(0, options.thickness * 0.75, panelFrontZ - options.thickness * 0.16);
        panelLip.userData = handleData;
        panelBottomLip.userData = handleData;
        drawerGroup.add(panelLip);
        drawerGroup.add(panelBottomLip);

        handle.rotation.z = Math.PI / 2;
        handle.position.set(0, options.panelHeight * 0.34 + options.thickness / 2, options.depth / 2 + 0.018);
        handle.userData = handleData;
        handle.castShadow = true;
        drawerGroup.add(handle);

        // 让抽屉盒体前缘贴住面板背面，否则拉开时会出现柜门和抽屉脱节的视觉断层。
        // 让抽屉盒体前沿略微插入面板背面，近景下不会看到“门板”和盒体分家的缝。
        innerBridge.position.set(0, options.thickness * 0.72, panelBackZ - options.thickness * 0.12);
        drawerGroup.add(innerBridge);
        leftSide.position.set(-options.panelWidth / 2 + sideInset, sideHeight / 2 + options.thickness / 2, drawerBodyZ);
        rightSide.position.set(options.panelWidth / 2 - sideInset, sideHeight / 2 + options.thickness / 2, drawerBodyZ);
        floorBoard.position.set(0, options.thickness * 0.25, drawerBodyZ);
        backBoard.position.set(0, sideHeight / 2 + options.thickness / 2, drawerBackZ);
        drawerGroup.add(leftSide);
        drawerGroup.add(rightSide);
        drawerGroup.add(floorBoard);
        drawerGroup.add(backBoard);

        // 后方延长滑轨随抽屉移动，但始终向柜体内部延伸；这样抽屉可完整拉出，又不会像脱离柜子。
        rearLeftRail.position.set(-options.panelWidth / 2 + sideInset, options.thickness * 0.75, tailZ);
        rearRightRail.position.set(options.panelWidth / 2 - sideInset, options.thickness * 0.75, tailZ);
        rearBottomRail.position.set(0, options.thickness * 0.25, tailZ);
        drawerGroup.add(rearLeftRail);
        drawerGroup.add(rearRightRail);
        drawerGroup.add(rearBottomRail);

        // 抽屉内格子只在有行列数据时创建，避免空层生成无意义实例网格。
        if (options.boxData && options.boxData.rows && options.boxData.cols && modules._3D.buildDrawerCells) {
            var drawerCells = modules._3D.buildDrawerCells(options.boxData, options.panelWidth, sideDepth);
            if (drawerCells) {
                drawerCells.position.set(0, 0, drawerBodyZ);
                drawerGroup.add(drawerCells);
            }
        }
    }

    modules._3D.buildCabinet = buildCabinet;
    modules._3D.createCabinetBoard = createBoard;
})(window);
