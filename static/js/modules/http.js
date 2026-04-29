// 本文件负责前端 HTTP 基础服务，属于 static 前端服务层；封装请求、响应解析、错误日志和文件下载，不绑定页面状态。
(function initInventoryHttp(global) {
    const API_BASE = '';
    const modules = global.InventoryModules || (global.InventoryModules = {});

    /**
     * 安全写入前端日志，避免日志模块缺失时影响主流程。
     * @param {string} message 中文错误上下文。
     */
    function logError(message) {
        if (typeof global.logAction === 'function') {
            global.logAction('ERROR', message);
        }
    }

    /**
     * 将查询参数追加到 GET URL，跳过 undefined/null 值。
     * @param {string} path API 路径。
     * @param {Object|null} params 查询参数对象。
     * @returns {string} 拼接后的相对 URL。
     */
    function buildUrl(path, params = null) {
        if (!params) return API_BASE + path;
        const query = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null) query.append(key, value);
        });
        const queryString = query.toString();
        return API_BASE + path + (queryString ? `?${queryString}` : '');
    }

    /**
     * 解析 JSON 响应并输出清晰中文错误。
     * @param {Response} response fetch 响应对象。
     * @param {string} context 日志和错误上下文。
     * @returns {Promise<Object>} 后端 JSON 响应。
     */
    async function parseJsonResponse(response, context) {
        const text = await response.text();
        let json = null;
        try {
            json = text ? JSON.parse(text) : null;
        } catch (_) {
            throw new Error(`${context} 返回的不是有效 JSON`);
        }
        if (!response.ok) {
            throw new Error(json?.message || `${context} HTTP ${response.status}`);
        }
        if (!json || json.code !== 0) {
            throw new Error(json?.message || `${context} 失败`);
        }
        return json;
    }

    /**
     * 执行 JSON API 请求，保持旧版 api.get/post/put/del 的 data 返回约定。
     * @param {string} method HTTP 方法。
     * @param {string} path API 路径。
     * @param {Object|null} data 请求体或 GET 查询参数。
     * @returns {Promise<*>} 后端 data 字段。
     */
    async function request(method, path, data = null) {
        const options = { method, headers: { 'Content-Type': 'application/json' } };
        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }
        const url = method === 'GET' ? buildUrl(path, data) : API_BASE + path;
        try {
            const json = await parseJsonResponse(await fetch(url, options), `API ${method} ${path}`);
            return json.data;
        } catch (err) {
            logError(`网络请求 ${method} ${path} 异常: ${err.message}`);
            throw err;
        }
    }

    /**
     * 上传单个文件并合并额外表单字段。
     * @param {string} path 上传 API 路径。
     * @param {File} file 浏览器文件对象。
     * @param {Object} extraFields 附加表单字段。
     * @returns {Promise<*>} 后端 data 字段。
     */
    async function uploadFile(path, file, extraFields = {}) {
        const formData = new FormData();
        formData.append('file', file);
        Object.entries(extraFields).forEach(([key, value]) => formData.append(key, value));
        try {
            const json = await parseJsonResponse(await fetch(API_BASE + path, { method: 'POST', body: formData }), `上传 ${path}`);
            return json.data;
        } catch (err) {
            logError(`上传 ${path} 异常: ${err.message}`);
            throw err;
        }
    }

    /**
     * 将 blob 响应保存为浏览器下载，供 GET/POST 导出复用。
     * @param {Response} response fetch 响应对象。
     * @param {string} filename 下载文件名。
     * @param {string} context 错误上下文。
     */
    async function saveBlobResponse(response, filename, context) {
        if (!response.ok) {
            let message = `${context} HTTP ${response.status}`;
            try {
                const text = await response.text();
                const json = text ? JSON.parse(text) : null;
                message = json?.message || message;
            } catch (_) {
                message = `${context} 失败`;
            }
            throw new Error(message);
        }
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    /**
     * 执行 GET 文件下载。
     * @param {string} path 下载 API 路径。
     * @param {Object|null} data 查询参数。
     * @param {string} filename 下载文件名。
     */
    async function downloadFile(path, data = null, filename = 'download') {
        try {
            await saveBlobResponse(await fetch(buildUrl(path, data)), filename, `下载 ${path}`);
        } catch (err) {
            logError(`下载 ${path} 异常: ${err.message}`);
            throw err;
        }
    }

    /**
     * 执行 POST 文件下载。
     * @param {string} path 下载 API 路径。
     * @param {Object} data JSON 请求体。
     * @param {string} filename 下载文件名。
     */
    async function downloadPostFile(path, data = {}, filename = 'download') {
        try {
            await saveBlobResponse(await fetch(API_BASE + path, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }), filename, `下载 ${path}`);
        } catch (err) {
            logError(`下载 ${path} 异常: ${err.message}`);
            throw err;
        }
    }

    modules.http = {
        API_BASE,
        request,
        uploadFile,
        downloadFile,
        downloadPostFile,
        buildUrl,
    };
})(window);
