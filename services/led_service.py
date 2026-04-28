from __future__ import annotations

# 本文件属于服务层，负责 LED 定位业务编排和 ESP32 指令构造，不直接依赖 Flask 请求对象。

from typing import Any

from models import InventoryError, clean_color, clean_int
from services.led_proxy import LedProxy


DEFAULT_LED_COLOR = "#00ff00"


class LedService:
    """把仓储中的 LED 映射转换为 ESP32 可执行的控制指令。"""

    def __init__(self, repo: Any, file_logger: Any, proxy: LedProxy | None = None) -> None:
        self.repo = repo
        self.file_logger = file_logger
        self.proxy = proxy or LedProxy()

    def settings(self) -> dict[str, Any]:
        return {
            "config": self.repo.get_led_config(),
            "devices": self.repo.list_led_devices(),
            "strips": self.repo.list_led_strips(),
            "mappings": self.repo.get_led_mappings(),
        }

    def test_device(self, device_id: int) -> dict[str, Any]:
        device = self._require_device(device_id)
        try:
            result = self.proxy.health(device)
            self.file_logger.write_backend("LED", f"测试 LED 设备成功: ID={device_id}, latency={result.get('latency_ms')}ms")
            return result
        except InventoryError as exc:
            self.file_logger.write_backend("LED", f"测试 LED 设备失败: ID={device_id}, error={exc}")
            return {"connected": False, "error": str(exc)}

    def locate_box(self, box_id: int) -> dict[str, Any]:
        mapping = self.repo.find_led_by_box(box_id)
        if not mapping:
            raise InventoryError("该盒子未配置 LED 映射")
        device = self._device_from_mapping(mapping)
        led = self._led_payload(mapping)
        self.proxy.set_leds(device, [led])
        self.file_logger.write_backend("LED", f"定位收纳盒: box={box_id}, device={device.get('id')}, gpio={led['gpio']}, index={led['index']}")
        return {"led_count": 1, "box_ids": [box_id]}

    def locate_component(self, component_id: int) -> dict[str, Any]:
        component = self.repo.get_component(component_id)
        box_id = clean_int(component.get("box_id"), 0)
        if box_id < 1:
            raise InventoryError("该元器件未关联收纳盒")
        return self.locate_box(box_id)

    def locate_bom(self, box_ids: list[Any]) -> dict[str, Any]:
        unique_box_ids = self._unique_ids(box_ids)
        grouped: dict[int, dict[str, Any]] = {}
        located_box_ids: list[int] = []
        for box_id in unique_box_ids:
            mapping = self.repo.find_led_by_box(box_id)
            if not mapping or not mapping.get("device_enabled"):
                continue
            device_id = int(mapping["device_id"])
            grouped.setdefault(device_id, {"device": self._device_from_mapping(mapping), "leds": []})
            grouped[device_id]["leds"].append(self._led_payload(mapping))
            located_box_ids.append(box_id)

        errors: list[str] = []
        sent_count = 0
        for group in grouped.values():
            try:
                self.proxy.set_leds(group["device"], group["leds"])
                sent_count += len(group["leds"])
            except InventoryError as exc:
                errors.append(str(exc))

        result: dict[str, Any] = {"led_count": sent_count, "box_ids": located_box_ids}
        if errors:
            result["errors"] = errors
        self.file_logger.write_backend("LED", f"BOM LED 批量定位: boxes={len(located_box_ids)}, leds={sent_count}, errors={len(errors)}")
        return result

    def clear_all(self) -> dict[str, Any]:
        devices = [device for device in self.repo.list_led_devices() if device.get("enabled")]
        cleared: list[int] = []
        errors: list[str] = []
        for device in devices:
            try:
                self.proxy.clear(device)
                cleared.append(int(device["id"]))
            except InventoryError as exc:
                errors.append(str(exc))
        result: dict[str, Any] = {"cleared_devices": cleared}
        if errors:
            result["errors"] = errors
        self.file_logger.write_backend("LED", f"清除全部 LED: devices={len(cleared)}, errors={len(errors)}")
        return result

    def clear_device(self, device_id: int) -> dict[str, Any]:
        device = self._require_device(device_id)
        if not device.get("enabled"):
            raise InventoryError("LED 设备未启用")
        self.proxy.clear(device)
        self.file_logger.write_backend("LED", f"清除 LED 设备: ID={device_id}")
        return {"cleared_devices": [device_id]}

    def _require_device(self, device_id: int) -> dict[str, Any]:
        device = self.repo.get_led_device(device_id)
        if not device:
            raise InventoryError("LED 设备不存在")
        return device

    def _device_from_mapping(self, mapping: dict[str, Any]) -> dict[str, Any]:
        if not mapping.get("device_enabled"):
            raise InventoryError("LED 设备未启用")
        return {
            "id": mapping.get("device_id"),
            "name": mapping.get("device_name"),
            "host": mapping.get("host"),
            "port": mapping.get("port"),
            "enabled": mapping.get("device_enabled"),
        }

    def _led_payload(self, mapping: dict[str, Any]) -> dict[str, Any]:
        config = self.repo.get_led_config()
        return {
            "gpio": clean_int(mapping.get("gpio_num"), 0),
            "index": clean_int(mapping.get("led_index"), 0),
            "mode": "blink",
            "color": clean_color(mapping.get("color"), DEFAULT_LED_COLOR),
            "duration_ms": clean_int(config.get("blink_duration_ms"), 10000),
        }

    def _unique_ids(self, values: list[Any]) -> list[int]:
        result: list[int] = []
        seen: set[int] = set()
        for value in values or []:
            item_id = clean_int(value, 0)
            if item_id < 1 or item_id in seen:
                continue
            seen.add(item_id)
            result.append(item_id)
        return result
