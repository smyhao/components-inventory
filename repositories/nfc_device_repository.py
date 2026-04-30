from __future__ import annotations

# 本文件属于仓储层，负责 NFC 远程读写设备的本地配置持久化，不包含 ESP32 HTTP 调用。

import sqlite3
from pathlib import Path
from typing import Any

from models import InventoryError, clean_int, clean_optional_int, clean_text
from repositories.base import BaseRepository


class NfcDeviceRepository(BaseRepository):
    """管理 NFC 全局配置和 ESP32-S3 读写器设备。"""

    def __init__(self, db_path: Path, file_logger: Any) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger

    def get_nfc_config(self) -> dict[str, Any]:
        with self.connect() as conn:
            self._ensure_config(conn)
            row = self._fetchone(conn, "SELECT * FROM nfc_config WHERE id = 1")
            return dict(row) if row else {}

    def update_nfc_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        enabled = 1 if payload.get("enabled") in (True, 1, "1", "true", "on") else 0
        default_timeout_ms = self._timeout_ms(payload.get("default_timeout_ms"), 10000)
        default_device_id = clean_optional_int(payload.get("default_device_id"))
        with self.connect() as conn:
            self._ensure_config(conn)
            if default_device_id is not None:
                self._ensure_device(conn, default_device_id)
            conn.execute(
                """
                UPDATE nfc_config
                SET enabled = ?, default_device_id = ?, default_timeout_ms = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (enabled, default_device_id, default_timeout_ms),
            )
        self.file_logger.write_backend("NFC", f"更新 NFC 配置: enabled={enabled}, default_device={default_device_id}")
        return self.get_nfc_config()

    def list_nfc_devices(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(conn, "SELECT * FROM nfc_devices ORDER BY id DESC")
            return [self._public_device(dict(row)) for row in rows]

    def get_nfc_device(self, device_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM nfc_devices WHERE id = ?", (device_id,))
            return dict(row) if row else None

    def create_nfc_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        name, host, port, enabled, linked_led_device_id, module_type, device_token, default_timeout_ms, allow_erase, allow_lock = self._device_payload(payload)
        with self.connect() as conn:
            if linked_led_device_id is not None:
                self._ensure_led_device(conn, linked_led_device_id)
            try:
                cur = conn.execute(
                    """
                    INSERT INTO nfc_devices (
                        name, host, port, enabled, linked_led_device_id, module_type, device_token,
                        default_timeout_ms, allow_erase, allow_lock, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (name, host, port, enabled, linked_led_device_id, module_type, device_token, default_timeout_ms, allow_erase, allow_lock),
                )
            except sqlite3.IntegrityError as exc:
                raise InventoryError("NFC 设备名称已存在") from exc
            device_id = cur.lastrowid
        self.file_logger.write_backend("NFC", f"新增 NFC 设备: {name} {host}:{port}")
        device = self.get_nfc_device(device_id)
        if not device:
            raise InventoryError("NFC 设备创建失败")
        return self._public_device(device)

    def update_nfc_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM nfc_devices WHERE id = ?", (device_id,))
            if not existing:
                raise InventoryError("NFC 设备不存在")
            merged = {**dict(existing), **payload}
            if "device_token" not in payload:
                merged["device_token"] = existing["device_token"]
            name, host, port, enabled, linked_led_device_id, module_type, device_token, default_timeout_ms, allow_erase, allow_lock = self._device_payload(merged)
            if linked_led_device_id is not None:
                self._ensure_led_device(conn, linked_led_device_id)
            try:
                conn.execute(
                    """
                    UPDATE nfc_devices
                    SET name = ?, host = ?, port = ?, enabled = ?, linked_led_device_id = ?, module_type = ?, device_token = ?,
                        default_timeout_ms = ?, allow_erase = ?, allow_lock = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (name, host, port, enabled, linked_led_device_id, module_type, device_token, default_timeout_ms, allow_erase, allow_lock, device_id),
                )
            except sqlite3.IntegrityError as exc:
                raise InventoryError("NFC 设备名称已存在") from exc
        self.file_logger.write_backend("NFC", f"更新 NFC 设备: ID={device_id}, {name} {host}:{port}")
        device = self.get_nfc_device(device_id)
        if not device:
            raise InventoryError("NFC 设备不存在")
        return self._public_device(device)

    def delete_nfc_device(self, device_id: int) -> None:
        with self.connect() as conn:
            device = self._fetchone(conn, "SELECT * FROM nfc_devices WHERE id = ?", (device_id,))
            if not device:
                raise InventoryError("NFC 设备不存在")
            conn.execute("UPDATE nfc_config SET default_device_id = NULL WHERE default_device_id = ?", (device_id,))
            conn.execute("DELETE FROM nfc_devices WHERE id = ?", (device_id,))
        self.file_logger.write_backend("NFC", f"删除 NFC 设备: ID={device_id}, 名称={device['name']}")

    def mark_nfc_device_tested(self, device_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE nfc_devices SET last_test_at = CURRENT_TIMESTAMP WHERE id = ?", (device_id,))

    def find_nfc_device_for_led_device(self, led_device_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM nfc_devices WHERE linked_led_device_id = ? LIMIT 1", (led_device_id,))
            return dict(row) if row else None

    def find_nfc_devices_by_endpoint(self, host: str, port: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(conn, "SELECT * FROM nfc_devices WHERE host = ? AND port = ? ORDER BY id", (host, port))
            return [dict(row) for row in rows]

    def _ensure_config(self, conn: sqlite3.Connection) -> None:
        """测试库或旧库可能只跑过部分迁移，因此读取配置前先补齐单行。"""
        existing = self._fetchone(conn, "SELECT id FROM nfc_config WHERE id = 1")
        if not existing:
            conn.execute("INSERT INTO nfc_config (id, enabled, default_timeout_ms) VALUES (1, 0, 10000)")

    def _ensure_device(self, conn: sqlite3.Connection, device_id: int) -> None:
        if not self._fetchone(conn, "SELECT id FROM nfc_devices WHERE id = ?", (device_id,)):
            raise InventoryError("NFC 设备不存在")

    def _ensure_led_device(self, conn: sqlite3.Connection, device_id: int) -> None:
        if not self._fetchone(conn, "SELECT id FROM led_devices WHERE id = ?", (device_id,)):
            raise InventoryError("关联的 LED 设备不存在")

    def _device_payload(self, payload: dict[str, Any]) -> tuple[str, str, int, int, int | None, str, str, int, int, int]:
        name = clean_text(payload.get("name"))
        host = clean_text(payload.get("host"))
        port = clean_int(payload.get("port"), 80)
        enabled = 0 if payload.get("enabled") in (False, 0, "0", "false", "off") else 1
        linked_led_device_id = clean_optional_int(payload.get("linked_led_device_id"))
        module_type = clean_text(payload.get("module_type")) or "PN532"
        device_token = clean_text(payload.get("device_token"))
        default_timeout_ms = self._timeout_ms(payload.get("default_timeout_ms"), 10000)
        allow_erase = 1 if payload.get("allow_erase") in (True, 1, "1", "true", "on") else 0
        allow_lock = 1 if payload.get("allow_lock") in (True, 1, "1", "true", "on") else 0
        if not name:
            raise InventoryError("NFC 设备名称不能为空")
        if not host:
            raise InventoryError("NFC 设备地址不能为空")
        if port < 1 or port > 65535:
            raise InventoryError("NFC 设备端口必须在 1-65535 之间")
        return name, host, port, enabled, linked_led_device_id, module_type, device_token, default_timeout_ms, allow_erase, allow_lock

    def _timeout_ms(self, value: Any, default: int) -> int:
        return min(30000, max(1000, clean_int(value, default)))

    def _public_device(self, device: dict[str, Any]) -> dict[str, Any]:
        # Token 只用于后端访问 ESP32，列表接口仅暴露是否配置，避免前端无意泄露密钥。
        result = {key: value for key, value in device.items() if key != "device_token"}
        result["device_token_configured"] = bool(clean_text(device.get("device_token")))
        return result
