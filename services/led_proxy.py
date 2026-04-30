from __future__ import annotations

# 本文件属于服务层边界，负责把 ESP32 HTTP 通信封装成可测试的代理能力，不接触 Flask 请求对象。

import json
import time
from typing import Any
from urllib import error, request

from models import InventoryError


class LedProxy:
    """向 ESP32 LED 控制接口发送 HTTP 请求，并统一转换网络错误。"""

    def __init__(self, timeout: float = 3.0) -> None:
        self.timeout = timeout

    def health(self, device: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        data = self._request_json(device, "GET", "/api/health")
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {"connected": True, "latency_ms": latency_ms, "strips": data.get("strips") or []}

    def set_leds(self, device: dict[str, Any], leds: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request_json(device, "POST", "/api/led/set", {"leds": leds})

    def clear(self, device: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(device, "POST", "/api/led/clear", {})

    def get_config(self, device: dict[str, Any]) -> dict[str, Any]:
        """读取 ESP32 当前灯带配置。"""
        return self._request_json(device, "GET", "/api/config")

    def push_strip(self, device: dict[str, Any], gpio: int, led_count: int) -> dict[str, Any]:
        """向 ESP32 添加/更新单条灯带，立即热重载。"""
        return self._request_json(device, "POST", "/api/config/strip", {"gpio": gpio, "led_count": led_count})

    def remove_strip(self, device: dict[str, Any], gpio: int) -> dict[str, Any]:
        """向 ESP32 删除单条灯带，立即热重载。"""
        return self._request_json(device, "POST", "/api/config/strip/remove", {"gpio": gpio})

    def push_full_config(
        self,
        device: dict[str, Any],
        strips: list[dict[str, Any]],
        http_port: int = 80,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """向 ESP32 推送完整灯带配置，立即热重载（用于批量同步）。"""
        payload = {"strips": strips, "http_port": http_port}
        if extra_config:
            payload.update(extra_config)
        return self._request_json(device, "POST", "/api/config", payload)

    def _request_json(
        self,
        device: dict[str, Any],
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行请求并解析 JSON；ESP32 返回空 body 时按成功空对象处理。"""
        url = f"http://{device.get('host')}:{device.get('port') or 80}{path}"
        body = json.dumps(payload or {}).encode("utf-8") if method != "GET" else None
        req = request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                try:
                    decoded = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise InventoryError(f"设备 {device.get('name')} 返回数据格式异常") from exc
                return decoded if isinstance(decoded, dict) else {"data": decoded}
        except error.HTTPError as exc:
            raise InventoryError(f"设备 {device.get('name')} 返回错误: {exc.code}") from exc
        except TimeoutError as exc:
            raise InventoryError(f"设备 {device.get('name')} 响应超时") from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError):
                raise InventoryError(f"设备 {device.get('name')} 响应超时") from exc
            raise InventoryError(f"设备 {device.get('name')} 连接失败，请检查地址和端口") from exc
        except OSError as exc:
            raise InventoryError(f"设备 {device.get('name')} 连接失败，请检查地址和端口") from exc
