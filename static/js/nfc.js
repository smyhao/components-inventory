// NFC 相关辅助逻辑
// 主逻辑在 app.js 中，此文件保留扩展用

async function readNFCTag() {
    if (!('NDEFReader' in window)) {
        throw new Error('当前浏览器不支持 Web NFC');
    }
    const reader = new NDEFReader();
    await reader.scan();
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            reject(new Error('NFC 读取超时'));
        }, 30000);
        reader.addEventListener('reading', (event) => {
            clearTimeout(timer);
            resolve({ uid: event.serialNumber, message: event.message });
        });
        reader.addEventListener('readingerror', () => {
            clearTimeout(timer);
            reject(new Error('NFC 读取错误'));
        });
    });
}

async function writeNFCTag(records) {
    if (!('NDEFReader' in window)) {
        throw new Error('当前浏览器不支持 Web NFC');
    }
    const writer = new NDEFWriter();
    await writer.write({ records });
}
