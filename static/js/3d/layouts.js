// 本文件负责 3D 地图预设布局计算；只返回需要保存的位置更新，不直接操作 DOM、THREE 或 API。
(function register3DLayouts(global) {
    'use strict';

    var modules = global.InventoryModules || (global.InventoryModules = {});

    var GAP_X = 180;
    var GAP_Y = 250;
    var BOX_GAP = 90;
    var OFFSET_X = 100;
    var OFFSET_Y = 100;

    /** 按稳定 ID 排序，保证同一批数据多次应用预设时结果可预测。 */
    function sortById(items) {
        return (items || []).slice().sort(function compareById(left, right) {
            return Number(left.id || 0) - Number(right.id || 0);
        });
    }

    /** 只给独立收纳盒生成位置；柜内盒的位置由柜子和槽位共同决定。 */
    function standaloneBoxes(boxes) {
        return sortById((boxes || []).filter(function isStandalone(box) {
            return !box.cabinet_id;
        }));
    }

    function addCabinet(updates, cabinet, x, y) {
        updates.push({
            type: 'cabinet',
            id: cabinet.id,
            position_x: Math.round(x),
            position_y: Math.round(y)
        });
    }

    function addBox(updates, box, x, y) {
        updates.push({
            type: 'box',
            id: box.id,
            position_x: Math.round(x),
            position_y: Math.round(y)
        });
    }

    /** 单面墙：柜子沿一面墙排开，独立盒放在下方工具区。 */
    function wallLayout(cabinets, boxes) {
        var updates = [];
        var sortedCabinets = sortById(cabinets);
        var sortedBoxes = standaloneBoxes(boxes);

        sortedCabinets.forEach(function placeCabinet(cabinet, index) {
            addCabinet(updates, cabinet, OFFSET_X + index * GAP_X, OFFSET_Y);
        });
        sortedBoxes.forEach(function placeBox(box, index) {
            addBox(updates, box, OFFSET_X + index * BOX_GAP, OFFSET_Y + GAP_Y);
        });

        return updates;
    }

    /** L 型：前半段沿 X 轴，后半段沿 Y 轴，适合角落或墙角收纳。 */
    function lShapeLayout(cabinets, boxes) {
        var updates = [];
        var sortedCabinets = sortById(cabinets);
        var sortedBoxes = standaloneBoxes(boxes);
        var turnIndex = Math.ceil(sortedCabinets.length / 2);

        sortedCabinets.forEach(function placeCabinet(cabinet, index) {
            if (index < turnIndex) {
                addCabinet(updates, cabinet, OFFSET_X + index * GAP_X, OFFSET_Y);
            } else {
                addCabinet(updates, cabinet, OFFSET_X, OFFSET_Y + (index - turnIndex + 1) * GAP_Y);
            }
        });
        sortedBoxes.forEach(function placeBox(box, index) {
            addBox(updates, box, OFFSET_X + GAP_X * 1.5, OFFSET_Y + index * BOX_GAP);
        });

        return updates;
    }

    /** 工作台：柜子围出上下两侧，中间留出独立盒或取料操作区域。 */
    function workbenchLayout(cabinets, boxes) {
        var updates = [];
        var sortedCabinets = sortById(cabinets);
        var sortedBoxes = standaloneBoxes(boxes);
        var topCount;
        var i;

        if (sortedCabinets.length <= 2) {
            return wallLayout(cabinets, boxes);
        }

        topCount = Math.ceil(sortedCabinets.length / 2);
        for (i = 0; i < sortedCabinets.length; i += 1) {
            if (i < topCount) {
                addCabinet(updates, sortedCabinets[i], OFFSET_X + i * GAP_X, OFFSET_Y);
            } else {
                addCabinet(updates, sortedCabinets[i], OFFSET_X + (i - topCount) * GAP_X, OFFSET_Y + GAP_Y * 2);
            }
        }
        sortedBoxes.forEach(function placeBox(box, index) {
            addBox(updates, box, OFFSET_X + index * BOX_GAP, OFFSET_Y + GAP_Y);
        });

        return updates;
    }

    /** 面对面：两排柜子隔出走道，独立盒放在两排之间。 */
    function faceToFaceLayout(cabinets, boxes) {
        var updates = [];
        var sortedCabinets = sortById(cabinets);
        var sortedBoxes = standaloneBoxes(boxes);
        var frontCount = Math.ceil(sortedCabinets.length / 2);

        sortedCabinets.forEach(function placeCabinet(cabinet, index) {
            if (index < frontCount) {
                addCabinet(updates, cabinet, OFFSET_X + index * GAP_X, OFFSET_Y);
            } else {
                addCabinet(updates, cabinet, OFFSET_X + (index - frontCount) * GAP_X, OFFSET_Y + GAP_Y);
            }
        });
        sortedBoxes.forEach(function placeBox(box, index) {
            var row = Math.floor(index / 4);
            var col = index % 4;
            addBox(updates, box, OFFSET_X + col * BOX_GAP, OFFSET_Y + GAP_Y / 2 + row * BOX_GAP);
        });

        return updates;
    }

    modules._3DLayouts = {
        wall: wallLayout,
        'l-shape': lShapeLayout,
        workbench: workbenchLayout,
        'face-to-face': faceToFaceLayout
    };
})(window);
