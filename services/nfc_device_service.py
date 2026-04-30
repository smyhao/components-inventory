from __future__ import annotations

# 本文件属于服务层，负责把库存业务、NDEF 生成和 ESP32-S3 NFC 设备动作编排在一起。

import re
from typing import Any
from uuid import uuid4

from config import SERVER_URL
from models import InventoryError, clean_int, clean_text
from services.nfc_proxy import NfcProxy


UID_RE = re.compile(r"^[0-9A-F]+$")
NDEF_TYPES = {"uri", "text", "mime"}


def normalize_uid(value: Any, *, strict: bool = True) -> str:
    """规范化 UID；远程设备返回的 UID 必须严格校验，旧手动接口可选择兼容历史文本。"""
    text = clean_text(value).upper()
    if text.startswith("0X"):
        text = text[2:]
    text = re.sub(r"[\s:\-]", "", text)
    if not text:
        raise InventoryError("UID 不能为空")
    if strict and (len(text) % 2 != 0 or not UID_RE.fullmatch(text)):
        raise InventoryError("UID 格式不正确")
    return text


class NfcDeviceService:
    """按协议编排 NFC 设备管理、远程读卡、写卡和擦除。"""

    def __init__(self, repo: Any, file_logger: Any, proxy: NfcProxy | None = None) -> None:
        self.repo = repo
        self.file_logger = file_logger
        self.proxy = proxy or NfcProxy()

    def settings(self) -> dict[str, Any]:
        return {
            "config": self.repo.get_nfc_config(),
            "devices": self.repo.list_nfc_devices(),
        }

    def test_device(self, device_id: int) -> dict[str, Any]:
        device = self._require_device(device_id, require_enabled=False)
        try:
            result = self.proxy.health(device)
            self.repo.mark_nfc_device_tested(device_id)
            self.file_logger.write_backend(
                "NFC",
                f"测试 NFC 设备成功: ID={device_id}, latency={result.get('latency_ms')}ms, ready={result.get('nfc', {}).get('ready')}",
            )
            return result
        except InventoryError as exc:
            self.file_logger.write_backend("NFC", f"测试 NFC 设备失败: ID={device_id}, error={exc}")
            return {"connected": False, "error": str(exc)}

    def sync_device(self, device_id: int) -> dict[str, Any]:
        device = self._require_device(device_id)
        payload = self._device_config_payload(device)
        result = self.proxy.push_config(device, payload)
        self.file_logger.write_backend("NFC", f"同步 NFC 设备配置: ID={device_id}, name={device.get('name')}")
        return {"device_id": device_id, "synced": True, "device_result": result}

    def read_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        device = self._require_device(device_id)
        request_payload = {
            "request_id": self._request_id("read"),
            "timeout_ms": self._operation_timeout_ms(payload.get("timeout_ms")),
            "mode": self._read_mode(payload.get("mode")),
            "include_raw": payload.get("include_raw") in (True, 1, "1", "true", "on"),
        }
        data = self.proxy.read(device, request_payload)
        tag = data.get("tag") if isinstance(data.get("tag"), dict) else {}
        uid = normalize_uid(tag.get("uid"), strict=True)
        lookup = self.repo.lookup_nfc_summary(uid)
        self.file_logger.write_backend("NFC", f"远程读卡: device={device_id}, uid={uid}, bound={lookup.get('bound')}")
        return {
            "device_id": device_id,
            "uid": uid,
            "tag": tag,
            "lookup": lookup,
            "device_result": data,
        }

    def write_box(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        device = self._require_device(device_id)
        box_id = clean_int(payload.get("box_id"), 0)
        if box_id < 1:
            raise InventoryError("收纳盒不能为空")
        ndef_payload = self.repo.get_nfc_payload(box_id, SERVER_URL)
        request_payload = {
            "request_id": self._request_id("write"),
            "timeout_ms": self._operation_timeout_ms(payload.get("timeout_ms")),
            "overwrite": payload.get("overwrite") not in (False, 0, "0", "false", "off"),
            "verify_after_write": True,
            "lock_after_write": False,
            "ndef": {
                "records": [
                    {"type": "uri", "value": ndef_payload["url"]},
                    {"type": "text", "language": "zh-CN", "encoding": "utf-8", "value": ndef_payload["text"]},
                ]
            },
        }
        data = self.proxy.write(device, request_payload)
        uid = normalize_uid((data.get("tag") or {}).get("uid"), strict=True)
        binding = self.repo.bind_nfc(box_id, uid)
        box = self.repo.get_box(box_id)
        written = data.get("written") if isinstance(data.get("written"), dict) else {}
        self.file_logger.write_backend(
            "NFC",
            f"远程写卡并绑定: device={device_id}, box={box_id}, uid={uid}, bytes={written.get('payload_bytes')}, verified={written.get('verified')}",
        )
        return {
            "device_id": device_id,
            "box_id": box_id,
            "box": {"id": box.get("id"), "name": box.get("name")},
            "uid": uid,
            "url": ndef_payload["url"],
            "text": ndef_payload["text"],
            "written": written,
            "binding": binding,
            "device_result": data,
        }

    def write_custom(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        device = self._require_device(device_id)
        records = self._validate_ndef_records((payload.get("ndef") or {}).get("records"))
        request_payload = {
            "request_id": self._request_id("write"),
            "timeout_ms": self._operation_timeout_ms(payload.get("timeout_ms")),
            "overwrite": payload.get("overwrite") not in (False, 0, "0", "false", "off"),
            "verify_after_write": payload.get("verify_after_write") not in (False, 0, "0", "false", "off"),
            "lock_after_write": self._lock_after_write(device, payload),
            "ndef": {"records": records},
        }
        data = self.proxy.write(device, request_payload)
        uid = normalize_uid((data.get("tag") or {}).get("uid"), strict=True)
        self.file_logger.write_backend("NFC", f"远程自定义写卡: device={device_id}, uid={uid}, records={len(records)}")
        return {"device_id": device_id, "uid": uid, "written": data.get("written") or {}, "device_result": data}

    def erase_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        device = self._require_device(device_id)
        if not device.get("allow_erase"):
            raise InventoryError("NFC 设备未启用擦除能力")
        request_payload = {
            "request_id": self._request_id("erase"),
            "timeout_ms": self._operation_timeout_ms(payload.get("timeout_ms")),
            "verify_after_erase": payload.get("verify_after_erase") not in (False, 0, "0", "false", "off"),
        }
        data = self.proxy.erase(device, request_payload)
        uid = normalize_uid((data.get("tag") or {}).get("uid"), strict=True)
        self.file_logger.write_backend("NFC", f"远程擦除标签: device={device_id}, uid={uid}")
        return {"device_id": device_id, "uid": uid, "erased": data.get("erased"), "verified": data.get("verified"), "device_result": data}

    def cancel_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        device = self._require_device(device_id)
        request_id = clean_text(payload.get("request_id"))
        if not request_id:
            raise InventoryError("request_id 不能为空")
        result = self.proxy.cancel(device, {"request_id": request_id})
        self.file_logger.write_backend("NFC", f"取消 NFC 操作: device={device_id}, request_id={request_id}, cancelled={result.get('cancelled')}")
        return {"device_id": device_id, **result}

    def _require_device(self, device_id: int, *, require_enabled: bool = True) -> dict[str, Any]:
        device = self.repo.get_nfc_device(device_id)
        if not device:
            raise InventoryError("NFC 设备不存在")
        if require_enabled and not device.get("enabled"):
            raise InventoryError("NFC 设备未启用")
        return device

    def _device_config_payload(self, device: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "device_name": device.get("name"),
            "http_port": int(device.get("port") or 80),
            "module": {"type": device.get("module_type") or "PN532", "bus": "i2c", "sda": 8, "scl": 9, "irq": None, "reset": None},
            "operation": {
                "default_timeout_ms": self._operation_timeout_ms(None),
                "allow_erase": bool(device.get("allow_erase")),
                "allow_lock": bool(device.get("allow_lock")),
            },
        }
        led_device_id = clean_int(device.get("linked_led_device_id"), 0)
        if led_device_id > 0:
            strips = self.repo.list_led_strips(device_id=led_device_id)
            esp_strips = [{"gpio": int(s["gpio_num"]), "led_count": int(s["led_count"])} for s in strips]
            # 同一 ESP32 同时承载 NFC 与 LED 时，同步 NFC 配置也带上灯带配置，避免固件端整表保存时丢失另一类能力。
            payload["strips"] = esp_strips
            payload["led"] = {"strips": esp_strips}
        return payload

    def _validate_ndef_records(self, records: Any) -> list[dict[str, Any]]:
        if not isinstance(records, list) or not records:
            raise InventoryError("NDEF 记录不能为空")
        if len(records) > 4:
            raise InventoryError("NDEF 记录最多 4 条")
        normalized: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                raise InventoryError("NDEF 记录格式不正确")
            record_type = clean_text(record.get("type")).lower()
            value = clean_text(record.get("value"))
            if record_type not in NDEF_TYPES:
                raise InventoryError("NDEF 记录类型不支持")
            if not value:
                raise InventoryError("NDEF 记录内容不能为空")
            if len(value.encode("utf-8")) > 512:
                raise InventoryError("NDEF 记录内容过长")
            normalized_record = {"type": record_type, "value": value}
            if record_type == "text":
                normalized_record["language"] = clean_text(record.get("language")) or "zh-CN"
                normalized_record["encoding"] = clean_text(record.get("encoding")) or "utf-8"
            if record_type == "mime":
                normalized_record["mime_type"] = clean_text(record.get("mime_type")) or "application/octet-stream"
            normalized.append(normalized_record)
        return normalized

    def _lock_after_write(self, device: dict[str, Any], payload: dict[str, Any]) -> bool:
        requested = payload.get("lock_after_write") in (True, 1, "1", "true", "on")
        if requested and not device.get("allow_lock"):
            raise InventoryError("NFC 设备未启用锁定能力")
        return requested

    def _timeout_ms(self, value: Any, default: Any) -> int:
        return min(30000, max(1000, clean_int(value, clean_int(default, 10000))))

    def _operation_timeout_ms(self, value: Any) -> int:
        # 默认超时在全局配置中统一维护，避免同一读写器页面和设备表单出现两套容易分叉的设置。
        config = self.repo.get_nfc_config()
        return self._timeout_ms(value, config.get("default_timeout_ms"))

    def _read_mode(self, value: Any) -> str:
        mode = clean_text(value) or "ndef"
        if mode not in {"uid", "ndef", "raw"}:
            raise InventoryError("读卡模式不支持")
        return mode

    def _request_id(self, operation: str) -> str:
        return f"nfc-{operation}-{uuid4().hex[:12]}"
