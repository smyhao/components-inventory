from __future__ import annotations

# 本文件负责封装 ESP32-S3 NFC HTTP 协议，把设备响应信封转换为项目内部异常或纯数据。

import json
import time
from typing import Any
from urllib import error, request

from models import InventoryError, clean_text


class NfcProxy:
    """ESP32-S3 NFC 设备 HTTP 代理。"""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def health(self, device: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        data = self._request_json(device, "GET", "/api/health")
        data["connected"] = True
        data["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return data

    def get_config(self, device: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "GET", "/api/config")

    def push_config(self, device: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "POST", "/api/config", payload)

    def state(self, device: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "GET", "/api/nfc/state")

    def read(self, device: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "POST", "/api/nfc/read", payload, payload.get("timeout_ms"))

    def write(self, device: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "POST", "/api/nfc/write", payload, payload.get("timeout_ms"))

    def erase(self, device: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "POST", "/api/nfc/erase", payload, payload.get("timeout_ms"))

    def cancel(self, device: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "POST", "/api/nfc/cancel", payload)

    def _request_json(
        self,
        device: dict[str, Any],
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        operation_timeout_ms: Any = None,
    ) -> dict[str, Any]:
        """发送请求并解析设备统一信封；这里集中处理是为了避免路由层理解设备内部错误。"""
        url = f"http://{device.get('host')}:{device.get('port') or 80}{path}"
        body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if method != "GET" else None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        token = clean_text(device.get("device_token"))
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = request.Request(url, data=body, method=method, headers=headers)
        timeout = self._request_timeout(operation_timeout_ms)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                envelope = self._decode_envelope(resp.read(), device)
                return self._unwrap_envelope(envelope, device)
        except error.HTTPError as exc:
            raw = exc.read()
            envelope = self._decode_envelope(raw, device) if raw else {}
            if envelope:
                raise self._device_error(device, envelope, exc.code) from exc
            raise InventoryError(f"设备 {device.get('name')} 返回错误: HTTP {exc.code}") from exc
        except TimeoutError as exc:
            raise InventoryError(f"设备 {device.get('name')} 响应超时") from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError):
                raise InventoryError(f"设备 {device.get('name')} 响应超时") from exc
            raise InventoryError(f"设备 {device.get('name')} 连接失败，请检查地址和端口") from exc
        except OSError as exc:
            raise InventoryError(f"设备 {device.get('name')} 连接失败，请检查地址和端口") from exc

    def _decode_envelope(self, raw: bytes, device: dict[str, Any]) -> dict[str, Any]:
        if not raw:
            return {"code": 0, "message": "ok", "data": {}}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InventoryError(f"设备 {device.get('name')} 返回数据格式异常") from exc
        if not isinstance(decoded, dict):
            raise InventoryError(f"设备 {device.get('name')} 返回数据格式异常")
        return decoded

    def _unwrap_envelope(self, envelope: dict[str, Any], device: dict[str, Any]) -> dict[str, Any]:
        if int(envelope.get("code") or 0) == 0:
            data = envelope.get("data")
            return data if isinstance(data, dict) else {}
        raise self._device_error(device, envelope, None)

    def _device_error(self, device: dict[str, Any], envelope: dict[str, Any], http_status: int | None) -> InventoryError:
        error_data = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = clean_text(error_data.get("code")) or "INTERNAL_ERROR"
        message = clean_text(envelope.get("message")) or code
        suffix = f"HTTP {http_status}, " if http_status else ""
        return InventoryError(f"设备 {device.get('name')} 返回错误: {suffix}{code} - {message}")

    def _request_timeout(self, operation_timeout_ms: Any) -> float:
        try:
            timeout_ms = int(operation_timeout_ms)
        except (TypeError, ValueError):
            return self.timeout
        return max(self.timeout, timeout_ms / 1000 + 2)
