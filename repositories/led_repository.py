from __future__ import annotations

# 本文件属于仓储层，负责 LED 配置、设备、灯带和盒子映射的 SQLite 读写，不包含 HTTP 或页面逻辑。

import sqlite3
from pathlib import Path
from typing import Any

from models import InventoryError, clean_color, clean_int, clean_optional_int, clean_text
from repositories.base import BaseRepository


DEFAULT_LED_COLOR = "#00ff00"


class LedRepository(BaseRepository):
    """封装 LED 定位相关 SQL，并保证写入前完成业务约束校验。"""

    def __init__(self, db_path: Path, file_logger: Any) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger

    def get_led_config(self) -> dict[str, Any]:
        with self.connect() as conn:
            self._ensure_config(conn)
            row = self._fetchone(conn, "SELECT * FROM led_config WHERE id = 1")
            return dict(row) if row else {}

    def update_led_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        enabled = 1 if payload.get("enabled") in (True, 1, "1", "true", "on") else 0
        blink_interval_ms = max(100, clean_int(payload.get("blink_interval_ms"), 500))
        blink_duration_ms = max(0, clean_int(payload.get("blink_duration_ms"), 10000))
        with self.connect() as conn:
            self._ensure_config(conn)
            conn.execute(
                """
                UPDATE led_config
                SET enabled = ?, blink_interval_ms = ?, blink_duration_ms = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (enabled, blink_interval_ms, blink_duration_ms),
            )
        self.file_logger.write_backend("LED", f"更新 LED 配置: enabled={enabled}, duration={blink_duration_ms}ms")
        return self.get_led_config()

    def list_led_devices(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT d.*, COUNT(s.id) AS strip_count
                FROM led_devices d
                LEFT JOIN led_strips s ON s.device_id = d.id
                GROUP BY d.id
                ORDER BY d.id DESC
                """,
            )
            return [dict(row) for row in rows]

    def get_led_device(self, device_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM led_devices WHERE id = ?", (device_id,))
            return dict(row) if row else None

    def create_led_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        name, host, port, enabled = self._device_payload(payload)
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO led_devices (name, host, port, enabled)
                    VALUES (?, ?, ?, ?)
                    """,
                    (name, host, port, enabled),
                )
            except sqlite3.IntegrityError as exc:
                raise InventoryError("LED 设备名称已存在") from exc
            device_id = cur.lastrowid
        self.file_logger.write_backend("LED", f"新增 LED 设备: {name} {host}:{port}")
        device = self.get_led_device(device_id)
        if not device:
            raise InventoryError("LED 设备创建失败")
        return device

    def update_led_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM led_devices WHERE id = ?", (device_id,))
            if not existing:
                raise InventoryError("LED 设备不存在")
            merged = {**dict(existing), **payload}
            name, host, port, enabled = self._device_payload(merged)
            try:
                conn.execute(
                    """
                    UPDATE led_devices
                    SET name = ?, host = ?, port = ?, enabled = ?
                    WHERE id = ?
                    """,
                    (name, host, port, enabled, device_id),
                )
            except sqlite3.IntegrityError as exc:
                raise InventoryError("LED 设备名称已存在") from exc
        self.file_logger.write_backend("LED", f"更新 LED 设备: ID={device_id}, {name} {host}:{port}")
        device = self.get_led_device(device_id)
        if not device:
            raise InventoryError("LED 设备不存在")
        return device

    def delete_led_device(self, device_id: int) -> None:
        with self.connect() as conn:
            device = self._fetchone(conn, "SELECT * FROM led_devices WHERE id = ?", (device_id,))
            if not device:
                raise InventoryError("LED 设备不存在")
            conn.execute("DELETE FROM led_devices WHERE id = ?", (device_id,))
        self.file_logger.write_backend("LED", f"删除 LED 设备: ID={device_id}, 名称={device['name']}")

    def list_led_strips(self, device_id: int | None = None) -> list[dict[str, Any]]:
        params: tuple[Any, ...] = ()
        where = ""
        if device_id is not None:
            where = "WHERE s.device_id = ?"
            params = (device_id,)
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                f"""
                SELECT s.*, d.name AS device_name, d.host, d.port, d.enabled AS device_enabled
                FROM led_strips s
                JOIN led_devices d ON d.id = s.device_id
                {where}
                ORDER BY d.id DESC, s.id DESC
                """,
                params,
            )
            return [dict(row) for row in rows]

    def create_led_strip(self, payload: dict[str, Any]) -> dict[str, Any]:
        device_id, name, gpio_num, led_count = self._strip_payload(payload)
        with self.connect() as conn:
            self._ensure_device(conn, device_id)
            try:
                cur = conn.execute(
                    """
                    INSERT INTO led_strips (device_id, name, gpio_num, led_count)
                    VALUES (?, ?, ?, ?)
                    """,
                    (device_id, name, gpio_num, led_count),
                )
            except sqlite3.IntegrityError as exc:
                raise InventoryError("同一 LED 设备下 GPIO 不能重复") from exc
            strip_id = cur.lastrowid
        self.file_logger.write_backend("LED", f"新增 LED 灯带: device={device_id}, gpio={gpio_num}, count={led_count}")
        return self._get_strip(strip_id)

    def update_led_strip(self, strip_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM led_strips WHERE id = ?", (strip_id,))
            if not existing:
                raise InventoryError("LED 灯带不存在")
            merged = {**dict(existing), **payload}
            device_id, name, gpio_num, led_count = self._strip_payload(merged)
            self._ensure_device(conn, device_id)
            self._ensure_existing_mappings_fit(conn, strip_id, led_count)
            try:
                conn.execute(
                    """
                    UPDATE led_strips
                    SET device_id = ?, name = ?, gpio_num = ?, led_count = ?
                    WHERE id = ?
                    """,
                    (device_id, name, gpio_num, led_count, strip_id),
                )
            except sqlite3.IntegrityError as exc:
                raise InventoryError("同一 LED 设备下 GPIO 不能重复") from exc
        self.file_logger.write_backend("LED", f"更新 LED 灯带: ID={strip_id}, device={device_id}, gpio={gpio_num}")
        return self._get_strip(strip_id)

    def delete_led_strip(self, strip_id: int) -> None:
        with self.connect() as conn:
            strip = self._fetchone(conn, "SELECT * FROM led_strips WHERE id = ?", (strip_id,))
            if not strip:
                raise InventoryError("LED 灯带不存在")
            conn.execute("DELETE FROM led_strips WHERE id = ?", (strip_id,))
        self.file_logger.write_backend("LED", f"删除 LED 灯带: ID={strip_id}, GPIO={strip['gpio_num']}")

    def get_led_mappings(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(conn, self._mapping_sql() + " ORDER BY b.name, m.id")
            return [dict(row) for row in rows]

    def save_led_mappings(self, mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(mappings, list):
            raise InventoryError("LED 映射必须是列表")
        with self.connect() as conn:
            prepared = [self._mapping_payload(conn, mapping) for mapping in mappings]
            self._ensure_mapping_unique(prepared)
            conn.execute("DELETE FROM led_box_mapping")
            for item in prepared:
                conn.execute(
                    """
                    INSERT INTO led_box_mapping (box_id, strip_id, led_index, color)
                    VALUES (?, ?, ?, ?)
                    """,
                    (item["box_id"], item["strip_id"], item["led_index"], item["color"]),
                )
        self.file_logger.write_backend("LED", f"保存 LED 映射: count={len(mappings)}")
        return self.get_led_mappings()

    def find_led_by_box(self, box_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = self._fetchone(
                conn,
                self._mapping_sql()
                + """
                WHERE m.box_id = ?
                """,
                (box_id,),
            )
            return dict(row) if row else None

    def _ensure_config(self, conn: sqlite3.Connection) -> None:
        """保证全局 LED 配置单行存在，兼容测试或旧库跳过初始化的场景。"""
        existing = self._fetchone(conn, "SELECT id FROM led_config WHERE id = 1")
        if not existing:
            conn.execute("INSERT INTO led_config (id, enabled) VALUES (1, 0)")

    def _device_payload(self, payload: dict[str, Any]) -> tuple[str, str, int, int]:
        name = clean_text(payload.get("name"))
        host = clean_text(payload.get("host"))
        port = clean_int(payload.get("port"), 80)
        enabled = 0 if payload.get("enabled") in (False, 0, "0", "false", "off") else 1
        if not name:
            raise InventoryError("LED 设备名称不能为空")
        if not host:
            raise InventoryError("LED 设备地址不能为空")
        if port < 1 or port > 65535:
            raise InventoryError("LED 设备端口必须在 1-65535 之间")
        return name, host, port, enabled

    def _strip_payload(self, payload: dict[str, Any]) -> tuple[int, str, int, int]:
        device_id = clean_int(payload.get("device_id"), 0)
        name = clean_text(payload.get("name"))
        gpio_num = clean_int(payload.get("gpio_num"), -1)
        led_count = clean_int(payload.get("led_count"), 0)
        if device_id < 1:
            raise InventoryError("LED 设备不能为空")
        if not name:
            raise InventoryError("LED 灯带名称不能为空")
        if gpio_num < 0:
            raise InventoryError("GPIO 必须大于等于 0")
        if led_count < 0:
            raise InventoryError("LED 数量不能小于 0")
        return device_id, name, gpio_num, led_count

    def _mapping_payload(self, conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
        box_id = clean_int(payload.get("box_id"), 0)
        strip_id = clean_int(payload.get("strip_id"), 0)
        led_index = clean_int(payload.get("led_index"), -1)
        color = clean_color(payload.get("color"), DEFAULT_LED_COLOR)
        if box_id < 1:
            raise InventoryError("收纳盒不能为空")
        if strip_id < 1:
            raise InventoryError("LED 灯带不能为空")
        if led_index < 0:
            raise InventoryError("LED 索引必须大于等于 0")
        if not self._fetchone(conn, "SELECT id FROM boxes WHERE id = ?", (box_id,)):
            raise InventoryError("收纳盒不存在")
        strip = self._fetchone(conn, "SELECT * FROM led_strips WHERE id = ?", (strip_id,))
        if not strip:
            raise InventoryError("LED 灯带不存在")
        if strip["led_count"] > 0 and led_index >= strip["led_count"]:
            raise InventoryError("LED 索引超出灯带数量")
        return {"box_id": box_id, "strip_id": strip_id, "led_index": led_index, "color": color}

    def _ensure_mapping_unique(self, mappings: list[dict[str, Any]]) -> None:
        boxes: set[int] = set()
        leds: set[tuple[int, int]] = set()
        for item in mappings:
            if item["box_id"] in boxes:
                raise InventoryError("同一个收纳盒只能配置一条 LED 映射")
            boxes.add(item["box_id"])
            led_key = (item["strip_id"], item["led_index"])
            if led_key in leds:
                raise InventoryError("同一灯带上的同一 LED 索引不能重复")
            leds.add(led_key)

    def _ensure_device(self, conn: sqlite3.Connection, device_id: int) -> None:
        if not self._fetchone(conn, "SELECT id FROM led_devices WHERE id = ?", (device_id,)):
            raise InventoryError("LED 设备不存在")

    def _ensure_existing_mappings_fit(self, conn: sqlite3.Connection, strip_id: int, led_count: int) -> None:
        if led_count <= 0:
            return
        row = self._fetchone(
            conn,
            "SELECT led_index FROM led_box_mapping WHERE strip_id = ? AND led_index >= ? LIMIT 1",
            (strip_id, led_count),
        )
        if row:
            raise InventoryError("已有映射超出新的 LED 数量")

    def _get_strip(self, strip_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(
                conn,
                """
                SELECT s.*, d.name AS device_name, d.host, d.port, d.enabled AS device_enabled
                FROM led_strips s
                JOIN led_devices d ON d.id = s.device_id
                WHERE s.id = ?
                """,
                (strip_id,),
            )
            if not row:
                raise InventoryError("LED 灯带不存在")
            return dict(row)

    def _mapping_sql(self) -> str:
        return """
            SELECT
                m.id,
                m.box_id,
                b.name AS box_name,
                m.strip_id,
                s.name AS strip_name,
                s.gpio_num,
                s.led_count,
                d.id AS device_id,
                d.name AS device_name,
                d.host,
                d.port,
                d.enabled AS device_enabled,
                m.led_index,
                m.color
            FROM led_box_mapping m
            JOIN boxes b ON b.id = m.box_id
            JOIN led_strips s ON s.id = m.strip_id
            JOIN led_devices d ON d.id = s.device_id
        """
