// 本文件负责独立收纳盒 3D 模型构建，包括托盘和 InstancedMesh 格子网格，属于 3D 引擎层；不做交互逻辑。
(function registerBoxModel(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});
    modules._3D = modules._3D || {};

    var COLOR_OCCUPIED = 0x5a8a6a;
    var COLOR_EMPTY = 0xd4ddd6;

    /**
     * 构建独立收纳盒 3D 模型，未归属柜子的收纳盒直接放置在地面坐标上。
     * @param {object} boxData 收纳盒数据。
     * @returns {THREE.Group} 收纳盒根节点。
     */
    function buildBox(boxData) {
        var THREE = global.THREE;
        var constants = modules._3D || {};
        var group = new THREE.Group();
        var rows = Math.max(1, Number(boxData.rows || 1));
        var cols = Math.max(1, Number(boxData.cols || 1));
        var boxColor = boxData.color || '#84b59b';
        var trayWidth = 0.6;
        var trayDepth = 0.4;
        var trayHeight = 0.08;
        var trayGeometry = new THREE.BoxGeometry(trayWidth, trayHeight, trayDepth);
        var trayMaterial = new THREE.MeshStandardMaterial({
            color: boxColor,
            roughness: 0.5,
            metalness: 0.1
        });
        var tray = new THREE.Mesh(trayGeometry, trayMaterial);
        var cellMesh;

        tray.position.y = trayHeight / 2;
        tray.castShadow = true;
        tray.receiveShadow = true;
        group.add(tray);

        cellMesh = buildCellGrid({
            boxData: boxData,
            rows: rows,
            cols: cols,
            width: trayWidth,
            depth: trayDepth,
            y: trayHeight + 0.015,
            padding: 0.02,
            cellHeight: 0.03,
            meta: {
                trayW: trayWidth,
                trayD: trayDepth
            }
        });
        if (cellMesh) {
            group.add(cellMesh);
        }

        group.position.set(
            Number(boxData.position_x || 0) * (constants.SCALE_FACTOR || 0.01),
            0,
            Number(boxData.position_y || 0) * (constants.SCALE_FACTOR || 0.01)
        );
        group.userData = {
            type: 'standalone-box',
            id: boxData.id,
            name: boxData.name,
            data: boxData
        };

        return group;
    }

    /**
     * 根据格子数据更新 InstancedMesh 的颜色；已放元器件的格子显示为占用色。
     * @param {THREE.InstancedMesh} cellMesh 格子实例网格。
     * @param {object} gridData 后端格子数据。
     */
    function updateCellColors(cellMesh, gridData) {
        var THREE = global.THREE;
        var occupiedColor = new THREE.Color(COLOR_OCCUPIED);
        var emptyColor = new THREE.Color(COLOR_EMPTY);
        var rows;
        var cols;
        var cells;
        var row;
        var col;
        var index = 0;
        var cell;

        if (!cellMesh || !gridData || !gridData.cells) return;

        rows = Math.max(1, Number(gridData.rows || 1));
        cols = Math.max(1, Number(gridData.cols || 1));
        cells = gridData.cells;

        for (row = 0; row < rows; row += 1) {
            for (col = 0; col < cols; col += 1) {
                cell = (cells[row] && cells[row][col]) || null;
                cellMesh.setColorAt(index, cell && cell.component ? occupiedColor : emptyColor);
                index += 1;
            }
        }

        if (cellMesh.instanceColor) {
            cellMesh.instanceColor.needsUpdate = true;
        }
    }

    /**
     * 在柜子抽屉内创建格子网格。它只负责格子本体，托盘由抽屉底板承担。
     * @param {object} boxData 收纳盒数据。
     * @param {number} panelWidth 抽屉可用宽度。
     * @param {number} sideDepth 抽屉可用深度。
     * @returns {THREE.InstancedMesh|null} 格子实例网格。
     */
    function buildDrawerCells(boxData, panelWidth, sideDepth) {
        if (!boxData) return null;

        return buildCellGrid({
            boxData: boxData,
            rows: Math.max(1, Number(boxData.rows || 1)),
            cols: Math.max(1, Number(boxData.cols || 1)),
            width: panelWidth,
            depth: sideDepth,
            y: 0.0325,
            padding: 0.01,
            cellHeight: 0.025,
            meta: {
                panelW: panelWidth,
                sideD: sideDepth
            }
        });
    }

    /**
     * 创建共享的格子 InstancedMesh。独立盒和抽屉内盒都走这里，保证矩阵和颜色规则一致。
     * @param {object} options 格子网格参数。
     * @returns {THREE.InstancedMesh|null} 格子实例网格。
     */
    function buildCellGrid(options) {
        var THREE = global.THREE;
        var totalCells = options.rows * options.cols;
        var cellWidth;
        var cellDepth;
        var cellGeometry;
        var cellMaterial;
        var cellMesh;
        var matrix;
        var emptyColor;
        var row;
        var col;
        var index = 0;
        var x;
        var z;

        if (totalCells <= 0) return null;

        cellWidth = (options.width - options.padding) / options.cols;
        cellDepth = (options.depth - options.padding) / options.rows;
        cellGeometry = new THREE.BoxGeometry(
            Math.max(0.001, cellWidth * 0.92),
            Math.max(0.001, options.cellHeight),
            Math.max(0.001, cellDepth * 0.92)
        );
        // 不固定材质颜色，让 instanceColor 成为格子占用状态的唯一视觉来源。
        cellMaterial = new THREE.MeshStandardMaterial({
            roughness: 0.5,
            metalness: 0.05
        });
        cellMesh = new THREE.InstancedMesh(cellGeometry, cellMaterial, totalCells);
        matrix = new THREE.Matrix4();
        emptyColor = new THREE.Color(COLOR_EMPTY);

        for (row = 0; row < options.rows; row += 1) {
            for (col = 0; col < options.cols; col += 1) {
                x = -options.width / 2 + cellWidth / 2 + col * cellWidth + options.padding / 2;
                z = -options.depth / 2 + cellDepth / 2 + row * cellDepth + options.padding / 2;
                matrix.setPosition(x, options.y, z);
                cellMesh.setMatrixAt(index, matrix);
                cellMesh.setColorAt(index, emptyColor);
                index += 1;
            }
        }

        cellMesh.instanceMatrix.needsUpdate = true;
        if (cellMesh.instanceColor) {
            cellMesh.instanceColor.needsUpdate = true;
        }
        cellMesh.userData = Object.assign({
            type: 'box-cells',
            boxId: options.boxData.id,
            rows: options.rows,
            cols: options.cols
        }, options.meta || {});
        cellMesh.castShadow = true;

        return cellMesh;
    }

    modules._3D.buildBox = buildBox;
    modules._3D.updateCellColors = updateCellColors;
    modules._3D.buildDrawerCells = buildDrawerCells;
    modules._3D.COLOR_OCCUPIED = COLOR_OCCUPIED;
    modules._3D.COLOR_EMPTY = COLOR_EMPTY;
})(window);
