// 本文件负责 /box/<id> 独立查看页的前端渲染，属于 static/js/features 领域层；只读取盒子数据并安全渲染 DOM。
(function initBoxPage(global) {
    /**
     * 读取当前 URL 中的收纳盒 ID。
     * @returns {string|null} 合法 ID 字符串，缺失时返回 null。
     */
    function getBoxIdFromPath() {
        const pathMatch = global.location.pathname.match(/\/box\/(\d+)/);
        return pathMatch ? pathMatch[1] : null;
    }

    /**
     * 切换页面错误状态，保持独立页原有加载/失败语义。
     * @param {string} message 用户可见错误信息。
     */
    function showError(message) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
        document.getElementById('error-msg').textContent = message;
    }

    /**
     * 创建单个格子的 DOM 节点。
     * @param {object} cell 后端网格单元数据。
     * @returns {HTMLElement} 已完成安全文本填充的格子节点。
     */
    function createCellElement(cell) {
        const el = document.createElement('div');
        el.className = 'box-cell ' + (cell.component ? (cell.component.quantity <= cell.component.min_stock ? 'box-cell-low' : 'box-cell-ok') : 'box-cell-empty');
        if (cell.component) {
            const nameEl = document.createElement('div');
            nameEl.className = 'box-cell-name';
            nameEl.textContent = cell.component.name;
            const qtyEl = document.createElement('div');
            qtyEl.className = 'box-cell-qty';
            qtyEl.textContent = cell.component.quantity;
            el.append(nameEl, qtyEl);
        } else {
            el.textContent = cell.label;
        }
        return el;
    }

    /**
     * 渲染收纳盒基础信息和网格。
     * @param {object} box 收纳盒详情。
     * @param {object} grid 收纳盒网格数据。
     */
    function renderBoxGrid(box, grid) {
        document.getElementById('box-name').textContent = box.name;
        document.getElementById('box-meta').textContent = `${box.rows}\u00d7${box.cols} \u00b7 \u5360\u7528 ${box.occupied_count || 0}/${box.rows * box.cols}`;
        document.documentElement.style.setProperty('--box-accent', box.color || '#84b59b');

        const gridEl = document.getElementById('grid');
        gridEl.style.display = 'grid';
        gridEl.style.gridTemplateColumns = `repeat(${grid.cols}, minmax(0, 1fr))`;

        for (let r = 0; r < grid.rows; r += 1) {
            for (let c = 0; c < grid.cols; c += 1) {
                gridEl.appendChild(createCellElement(grid.cells[r][c]));
            }
        }
        document.getElementById('loading').style.display = 'none';
    }

    /**
     * 初始化独立收纳盒查看页。
     */
    async function init() {
        const boxId = getBoxIdFromPath();
        if (!boxId) {
            showError('无效的收纳盒 ID');
            return;
        }
        try {
            const [box, grid] = await Promise.all([
                global.api.get(`/api/boxes/${boxId}`),
                global.api.get(`/api/boxes/${boxId}/grid`)
            ]);
            renderBoxGrid(box, grid);
        } catch (e) {
            showError(e.message);
        }
    }

    init();
})(window);
