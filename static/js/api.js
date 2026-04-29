// 本文件负责暴露兼容旧页面代码的 API 全局入口，属于 static 前端服务适配层；具体 HTTP 实现在 modules/http.js。
const InventoryHttp = window.InventoryModules?.http;
const API_BASE = InventoryHttp?.API_BASE || '';

async function request(method, path, data = null) {
    if (!InventoryHttp) throw new Error('前端 HTTP 模块未加载');
    return InventoryHttp.request(method, path, data);
}

const api = {
    get: (path, params) => request('GET', path, params),
    post: (path, data) => request('POST', path, data),
    put: (path, data) => request('PUT', path, data),
    del: (path) => request('DELETE', path),
};

async function uploadFile(path, file, extraFields = {}) {
    if (!InventoryHttp) throw new Error('前端 HTTP 模块未加载');
    return InventoryHttp.uploadFile(path, file, extraFields);
}

async function downloadFile(path, data = null, filename = 'download') {
    if (!InventoryHttp) throw new Error('前端 HTTP 模块未加载');
    return InventoryHttp.downloadFile(path, data, filename);
}

async function downloadPostFile(path, data = {}, filename = 'download') {
    if (!InventoryHttp) throw new Error('前端 HTTP 模块未加载');
    return InventoryHttp.downloadPostFile(path, data, filename);
}

// 兼容独立页面和旧脚本通过 window 读取 API 能力的用法。
window.api = api;
window.uploadFile = uploadFile;
window.downloadFile = downloadFile;
window.downloadPostFile = downloadPostFile;
