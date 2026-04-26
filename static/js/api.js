const API_BASE = '';

async function request(method, path, data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }
    const url = API_BASE + path + (method === 'GET' && data ? '?' + new URLSearchParams(data) : '');
    try {
        const res = await fetch(url, options);
        const json = await res.json();
        if (json.code !== 0) {
            if (typeof logAction === 'function') {
                logAction('ERROR', `API ${method} ${path} 失败: ${json.message}`);
            }
            throw new Error(json.message);
        }
        return json.data;
    } catch (err) {
        if (typeof logAction === 'function') {
            logAction('ERROR', `网络请求 ${method} ${path} 异常: ${err.message}`);
        }
        throw err;
    }
}

const api = {
    get: (path, params) => request('GET', path, params),
    post: (path, data) => request('POST', path, data),
    put: (path, data) => request('PUT', path, data),
    del: (path) => request('DELETE', path),
};

async function uploadFile(path, file, extraFields = {}) {
    const formData = new FormData();
    formData.append('file', file);
    Object.entries(extraFields).forEach(([k, v]) => formData.append(k, v));
    try {
        const res = await fetch(API_BASE + path, { method: 'POST', body: formData });
        const json = await res.json();
        if (json.code !== 0) {
            if (typeof logAction === 'function') {
                logAction('ERROR', `上传 ${path} 失败: ${json.message}`);
            }
            throw new Error(json.message);
        }
        return json.data;
    } catch (err) {
        if (typeof logAction === 'function') {
            logAction('ERROR', `上传 ${path} 异常: ${err.message}`);
        }
        throw err;
    }
}

async function downloadFile(path, data = null, filename = 'download') {
    const url = data ? path + '?' + new URLSearchParams(data) : path;
    try {
        const res = await fetch(API_BASE + url);
        if (!res.ok) throw new Error('下载失败');
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    } catch (err) {
        if (typeof logAction === 'function') {
            logAction('ERROR', `下载 ${path} 异常: ${err.message}`);
        }
        throw err;
    }
}

async function downloadPostFile(path, data = {}, filename = 'download') {
    try {
        const res = await fetch(API_BASE + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error('下载失败');
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    } catch (err) {
        if (typeof logAction === 'function') {
            logAction('ERROR', `下载 ${path} 异常: ${err.message}`);
        }
        throw err;
    }
}
