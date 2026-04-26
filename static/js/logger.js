const LOG_BUFFER_KEY = 'ci_log_buffer';
const LOG_BUFFER_MAX = 30;
const IMPORTANT_FRONTEND_TYPES = new Set([
    'ERROR', 'CREATE', 'UPDATE', 'DELETE', 'STOCK',
    'IMPORT', 'EXPORT', 'BOM', 'NFC', 'SCAN'
]);

function formatTime(date) {
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function shouldLogAction(type, detail) {
    const normalizedType = String(type || '').trim().toUpperCase();
    const normalizedDetail = String(detail || '').trim();
    if (!normalizedDetail) return false;
    if (IMPORTANT_FRONTEND_TYPES.has(normalizedType)) return true;
    const lowered = normalizedDetail.toLowerCase();
    return normalizedDetail.includes('失败') || normalizedDetail.includes('异常') || lowered.includes('error') || lowered.includes('exception');
}

function logAction(type, detail) {
    if (!shouldLogAction(type, detail)) return;
    const line = `[${formatTime(new Date())}] [${type}] ${detail}`;
    console.log(line);

    // 写入 localStorage 缓冲区
    try {
        let buf = JSON.parse(localStorage.getItem(LOG_BUFFER_KEY) || '[]');
        buf.push({ type, detail, time: new Date().toISOString() });
        if (buf.length > LOG_BUFFER_MAX) buf = buf.slice(-LOG_BUFFER_MAX);
        localStorage.setItem(LOG_BUFFER_KEY, JSON.stringify(buf));
    } catch (e) {
        // localStorage 不可用则跳过
    }

    // 尝试批量同步到后端（防抖批量）
    scheduleSyncLogs();
}

let _syncTimer = null;
function scheduleSyncLogs() {
    if (_syncTimer) return;
    _syncTimer = setTimeout(() => {
        _syncTimer = null;
        syncLogs();
    }, 3000);
}

async function syncLogs() {
    try {
        const buf = JSON.parse(localStorage.getItem(LOG_BUFFER_KEY) || '[]');
        if (buf.length === 0) return;
        const res = await fetch('/api/frontend/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ logs: buf }),
        });
        const json = await res.json();
        if (json.code === 0) {
            localStorage.setItem(LOG_BUFFER_KEY, '[]');
        }
    } catch (e) {
        // 网络失败保留缓冲区，下次再试
    }
}

// 页面可见性变化时尝试同步
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
        if (_syncTimer) {
            clearTimeout(_syncTimer);
            _syncTimer = null;
        }
        syncLogs();
    }
});
