let _html5QrCode = null;
let _scannerStarted = false;

function startScanner(onScan, onError) {
    const containerId = 'scanner-container';
    const container = document.getElementById(containerId);
    if (!container) {
        if (onError) onError('扫码容器未找到');
        return;
    }
    container.innerHTML = '';

    if (!window.Html5Qrcode) {
        if (onError) onError('html5-qrcode 库未加载');
        return;
    }

    _scannerStarted = false;
    _html5QrCode = new Html5Qrcode(containerId);
    const config = { fps: 10, qrbox: { width: 250, height: 250 } };

    _html5QrCode.start(
        { facingMode: 'environment' },
        config,
        (decodedText) => {
            if (onScan) onScan(decodedText);
        },
        (errorMessage) => {
            // 频繁的错误可以忽略，只传严重错误
        }
    ).then(() => {
        _scannerStarted = true;
    }).catch(err => {
        _scannerStarted = false;
        if (onError) onError(err.message || String(err));
    });
}

async function scanImageFile(file, onScan, onError) {
    const containerId = 'scanner-container';
    const container = document.getElementById(containerId);
    if (!container) {
        if (onError) onError('扫码容器未找到');
        return;
    }
    if (!window.Html5Qrcode) {
        if (onError) onError('html5-qrcode 库未加载');
        return;
    }

    try {
        if (_html5QrCode) {
            try {
                if (_scannerStarted) await _html5QrCode.stop();
            } catch (_) {
                // ignore stop failures when camera never started
            }
            try {
                await _html5QrCode.clear();
            } catch (_) {
                // ignore clear failures
            }
            _html5QrCode = null;
            _scannerStarted = false;
        }

        container.innerHTML = '';
        _html5QrCode = new Html5Qrcode(containerId);
        const result = await _html5QrCode.scanFile(file, true);
        const text = typeof result === 'string' ? result : (result?.decodedText || '');
        if (!text) throw new Error('未能识别图片中的二维码/条码');
        if (onScan) onScan(text);
    } catch (err) {
        if (onError) onError(err.message || String(err));
    } finally {
        try {
            if (_html5QrCode) {
                await _html5QrCode.clear();
            }
        } catch (_) {
            // ignore clear failures
        }
        _html5QrCode = null;
        _scannerStarted = false;
    }
}

async function stopScanner() {
    if (!_html5QrCode) return;
    const scanner = _html5QrCode;
    _html5QrCode = null;
    try {
        if (_scannerStarted) {
            await scanner.stop();
        }
    } catch (_) {
        // ignore stop failures
    }
    try {
        await scanner.clear();
    } catch (_) {
        // ignore clear failures
    }
    _scannerStarted = false;
}
