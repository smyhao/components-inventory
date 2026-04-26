// 地图渲染与交互辅助函数
// 主逻辑在 app.js 中，此文件保留扩展用

function renderMapGrid(container, boxes, options = {}) {
    // 可扩展：使用 Canvas 或 SVG 替代 DOM 渲染
    // 当前使用 DOM 渲染已在 app.js / index.html 中实现
}

function optimizePickRoute(items) {
    // 简单的取料路径优化：按 box_id 聚集，再按 cell 行列排序
    const grouped = {};
    items.forEach((it, idx) => {
        if (!it.matched) return;
        const bid = it.matched.box_id;
        if (!grouped[bid]) grouped[bid] = [];
        grouped[bid].push({ ...it, _idx: idx });
    });
    const result = [];
    Object.values(grouped).forEach(group => {
        group.sort((a, b) => {
            const ma = a.matched, mb = b.matched;
            if (ma.cell_row !== mb.cell_row) return ma.cell_row - mb.cell_row;
            return ma.cell_col - mb.cell_col;
        });
        result.push(...group);
    });
    return result;
}
