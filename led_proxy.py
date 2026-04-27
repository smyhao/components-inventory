from __future__ import annotations

import time

import requests

from models import InventoryError, InventoryRepository


class LEDProxy:
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 5

    def __init__(self, repo: InventoryRepository) -> None:
        self.repo = repo

    def _device_url(self, device: dict, path: str) -> str:
        return f"http://{device['host']}:{device['port']}{path}"

    def _request(self, device: dict, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            resp = requests.request(
                method,
                self._device_url(device, path),
                json=payload,
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise InventoryError(f"设备 {device.get('name', '?')} 连接失败，请检查地址和端口")
        except requests.exceptions.Timeout:
            raise InventoryError(f"设备 {device.get('name', '?')} 响应超时")
        except requests.exceptions.HTTPError as e:
            raise InventoryError(f"设备 {device.get('name', '?')} 返回错误: {e.response.status_code}")
        except Exception as e:
            raise InventoryError(f"设备 {device.get('name', '?')} 通信异常: {e}")

    def test_device(self, device_id: int) -> dict:
        device = self.repo.get_led_device(device_id)
        if not device:
            raise InventoryError("设备不存在")
        start = time.monotonic()
        try:
            result = self._request(device, "GET", "/api/health")
            latency = int((time.monotonic() - start) * 1000)
            return {"connected": True, "latency_ms": latency, "strips": result.get("strips", [])}
        except InventoryError as e:
            return {"connected": False, "error": str(e)}

    def locate_box(self, box_id: int) -> dict:
        cfg = self.repo.get_led_config()
        mapping = self.repo.find_led_by_box(box_id)
        if not mapping:
            raise InventoryError("该盒子未配置 LED 映射")
        device = self.repo.get_led_device(mapping["device_id"])
        if not device or not device.get("enabled"):
            raise InventoryError(f"设备 {mapping.get('device_name', '?')} 未启用")
        self._request(device, "POST", "/api/led/set", {
            "leds": [{
                "gpio": mapping["gpio_num"],
                "index": mapping["led_index"],
                "mode": "blink",
                "color": cfg["default_color"],
                "duration_ms": cfg["blink_duration_ms"],
            }]
        })
        return {
            "box_id": box_id,
            "device_name": mapping["device_name"],
            "gpio": mapping["gpio_num"],
            "led_index": mapping["led_index"],
            "mode": "blink",
        }

    def locate_component(self, component_id: int) -> dict:
        comp = self.repo.get_component(component_id)
        if not comp or not comp.get("box_id"):
            raise InventoryError("该元器件未关联收纳盒")
        result = self.locate_box(comp["box_id"])
        result["component_id"] = component_id
        return result

    def locate_bom(self, box_ids: list[int]) -> dict:
        cfg = self.repo.get_led_config()
        device_leds: dict[int, list[dict]] = {}
        devices: dict[int, dict] = {}
        resolved: list[int] = []
        for box_id in box_ids:
            mapping = self.repo.find_led_by_box(box_id)
            if not mapping:
                continue
            did = mapping["device_id"]
            device = self.repo.get_led_device(did)
            if not device or not device.get("enabled"):
                continue
            devices.setdefault(did, device)
            device_leds.setdefault(did, []).append({
                "gpio": mapping["gpio_num"],
                "index": mapping["led_index"],
                "mode": "blink",
                "color": cfg["default_color"],
                "duration_ms": cfg["blink_duration_ms"],
            })
            resolved.append(box_id)
        errors: list[str] = []
        for did, leds in device_leds.items():
            try:
                self._request(devices[did], "POST", "/api/led/set", {"leds": leds})
            except InventoryError as e:
                errors.append(str(e))
        result: dict = {
            "led_count": sum(len(v) for v in device_leds.values()),
            "box_ids": resolved,
        }
        if errors:
            result["errors"] = errors
        return result

    def clear_all(self) -> dict:
        devices = self.repo.list_led_devices()
        errors: list[str] = []
        cleared = 0
        for device in devices:
            if not device.get("enabled"):
                continue
            try:
                self._request(device, "POST", "/api/led/clear", {})
                cleared += 1
            except InventoryError as e:
                errors.append(str(e))
        result: dict = {"cleared_devices": cleared}
        if errors:
            result["errors"] = errors
        return result

    def clear_device(self, device_id: int) -> dict:
        device = self.repo.get_led_device(device_id)
        if not device:
            raise InventoryError("设备不存在")
        self._request(device, "POST", "/api/led/clear", {})
        return {"cleared": True, "device_name": device["name"]}
