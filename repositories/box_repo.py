from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from config import DEFAULT_BOX_COLOR
from models import InventoryError, clean_color, clean_int, clean_optional_int, clean_text
from repositories._utils import image_url
from repositories.base import BaseRepository


class BoxRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger

    def list_boxes(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT
                    b.*,
                    cb.name AS cabinet_name,
                    COUNT(DISTINCT c.compartment_id) AS occupied_count,
                    COUNT(c.id) AS component_count,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM boxes b
                LEFT JOIN cabinets cb ON cb.id = b.cabinet_id
                LEFT JOIN components c ON c.box_id = b.id
                GROUP BY b.id
                ORDER BY COALESCE(cb.name, ''), b.cabinet_slot, b.name
                """,
            )
            items = []
            for row in rows:
                item = dict(row)
                item["total_slots"] = item["rows"] * item["cols"]
                item["used_slots"] = item["occupied_count"]
                items.append(item)
            return items

    def get_box(self, box_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(
                conn,
                """
                SELECT
                    b.*,
                    cb.name AS cabinet_name,
                    COUNT(DISTINCT c.compartment_id) AS occupied_count,
                    COUNT(c.id) AS component_count,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM boxes b
                LEFT JOIN cabinets cb ON cb.id = b.cabinet_id
                LEFT JOIN components c ON c.box_id = b.id
                WHERE b.id = ?
                GROUP BY b.id
                """,
                (box_id,),
            )
            if not row:
                raise InventoryError("收纳盒不存在")
            item = dict(row)
            item["total_slots"] = item["rows"] * item["cols"]
            item["used_slots"] = item["occupied_count"]
            return item

    def _ensure_compartments(self, conn: sqlite3.Connection, box_id: int, rows: int, cols: int) -> None:
        for row in range(1, rows + 1):
            for col in range(1, cols + 1):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO compartments (box_id, row, col, label)
                    VALUES (?, ?, ?, ?)
                    """,
                    (box_id, row, col, f"{row}-{col}"),
                )

    def create_box(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = clean_text(payload.get("name"))
        rows = clean_int(payload.get("rows"), 1)
        cols = clean_int(payload.get("cols"), 1)
        description = clean_text(payload.get("description")) or None
        color = clean_color(payload.get("color"))
        cabinet_id = clean_optional_int(payload.get("cabinet_id"))
        cabinet_slot = clean_int(payload.get("cabinet_slot"), 0)
        if not name:
            raise InventoryError("box name is required")
        if rows < 1 or cols < 1:
            raise InventoryError("rows and cols must be greater than 0")

        with self.connect() as conn:
            if cabinet_id is not None and not self._fetchone(conn, "SELECT id FROM cabinets WHERE id = ?", (cabinet_id,)):
                raise InventoryError("cabinet not found")
            cur = conn.execute(
                """
                INSERT INTO boxes (name, rows, cols, description, color, cabinet_id, cabinet_slot, position_x, position_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (name, rows, cols, description, color, cabinet_id, cabinet_slot),
            )
            box_id = cur.lastrowid
            self._ensure_compartments(conn, box_id, rows, cols)

        self.file_logger.write_backend("BOX", f"create box: {name}, size={rows}x{cols}, color={color}")
        self.file_logger.write_backend("COMPARTMENT", f"create compartments: {name}, count={rows * cols}")
        return self.get_box(box_id)

    def update_box(self, box_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM boxes WHERE id = ?", (box_id,))
            if not existing:
                raise InventoryError("收纳盒不存在")

            name = clean_text(payload.get("name")) or existing["name"]
            description = clean_text(payload.get("description")) if "description" in payload else existing["description"]
            rows = clean_int(payload.get("rows"), existing["rows"])
            cols = clean_int(payload.get("cols"), existing["cols"])
            color = clean_color(payload.get("color"), existing["color"] or DEFAULT_BOX_COLOR)
            cabinet_id = clean_optional_int(payload.get("cabinet_id")) if "cabinet_id" in payload else existing["cabinet_id"]
            cabinet_slot = clean_int(payload.get("cabinet_slot"), existing["cabinet_slot"] or 0)
            if rows < 1 or cols < 1:
                raise InventoryError("行列数量必须大于 0")

            if cabinet_id is not None and not self._fetchone(conn, "SELECT id FROM cabinets WHERE id = ?", (cabinet_id,)):
                raise InventoryError("cabinet not found")

            occupied_out_of_range = self._fetchall(
                conn,
                """
                SELECT cp.id
                FROM compartments cp
                JOIN components c ON c.compartment_id = cp.id
                WHERE cp.box_id = ? AND (cp.row > ? OR cp.col > ?)
                """,
                (box_id, rows, cols),
            )
            if occupied_out_of_range:
                raise InventoryError("cannot shrink box because occupied compartments would be removed")

            conn.execute(
                """
                UPDATE boxes
                SET name = ?, rows = ?, cols = ?, description = ?, color = ?, cabinet_id = ?, cabinet_slot = ?
                WHERE id = ?
                """,
                (name, rows, cols, description, color, cabinet_id, cabinet_slot, box_id),
            )
            conn.execute(
                "DELETE FROM compartments WHERE box_id = ? AND (row > ? OR col > ?)",
                (box_id, rows, cols),
            )
            self._ensure_compartments(conn, box_id, rows, cols)

        self.file_logger.write_backend("BOX", f"更新收纳盒: ID={box_id}, 名称={name}, 规格={rows}x{cols}, color={color}")
        self.file_logger.write_backend("COMPARTMENT", f"调整格子布局: 盒子ID={box_id}, 规格={rows}x{cols}")
        return self.get_box(box_id)

    def delete_box(self, box_id: int) -> None:
        with self.connect() as conn:
            box = self._fetchone(conn, "SELECT * FROM boxes WHERE id = ?", (box_id,))
            if not box:
                raise InventoryError("收纳盒不存在")
            occupied = self._fetchone(conn, "SELECT COUNT(*) AS cnt FROM components WHERE box_id = ?", (box_id,))
            if occupied and occupied["cnt"] > 0:
                raise InventoryError("收纳盒中仍有元器件，无法删除")
            conn.execute("DELETE FROM boxes WHERE id = ?", (box_id,))
        self.file_logger.write_backend("BOX", f"删除收纳盒: ID={box_id}, 名称={box['name']}")

    def update_box_layout(self, box_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        position_x = float(payload.get("position_x") or 0)
        position_y = float(payload.get("position_y") or 0)
        with self.connect() as conn:
            conn.execute(
                "UPDATE boxes SET position_x = ?, position_y = ? WHERE id = ?",
                (position_x, position_y, box_id),
            )
        self.file_logger.write_backend("BOX", f"更新盒子地图位置: ID={box_id}, x={position_x}, y={position_y}")
        return self.get_box(box_id)

    def get_box_grid(self, box_id: int) -> dict[str, Any]:
        box = self.get_box(box_id)
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT
                    cp.id,
                    cp.row,
                    cp.col,
                    cp.label,
                    c.id AS component_id,
                    c.name AS component_name,
                    c.quantity AS component_quantity,
                    c.min_stock AS component_min_stock,
                    c.model AS component_model,
                    c.package AS component_package,
                    i.path AS primary_image
                FROM compartments cp
                LEFT JOIN components c ON c.compartment_id = cp.id
                LEFT JOIN images i ON i.component_id = c.id AND i.is_primary = 1
                WHERE cp.box_id = ?
                ORDER BY cp.row, cp.col
                """,
                (box_id,),
            )

            grid: list[list[dict[str, Any]]] = [[{} for _ in range(box["cols"])] for _ in range(box["rows"])]
            for row in rows:
                component = None
                if row["component_id"]:
                    component = {
                        "id": row["component_id"],
                        "name": row["component_name"],
                        "quantity": row["component_quantity"],
                        "min_stock": row["component_min_stock"],
                        "model": row["component_model"],
                        "package": row["component_package"],
                        "primary_image": image_url(row["primary_image"]),
                    }
                cell = {
                    "id": row["id"],
                    "row": row["id"],
                    "col": row["col"],
                    "grid_row": row["row"],
                    "grid_col": row["col"],
                    "label": row["label"] or f"{row['row']}-{row['col']}",
                    "component": component,
                }
                grid[row["row"] - 1][row["col"] - 1] = cell

            return {
                "id": box["id"],
                "box": box,
                "rows": box["rows"],
                "cols": box["cols"],
                "cells": grid,
            }

    def find_box_by_name(self, name: str) -> dict[str, Any] | None:
        text = clean_text(name)
        if not text:
            return None
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT * FROM boxes WHERE name = ?", (text,))
            return dict(row) if row else None

    def find_compartment_by_coordinates(self, box_id: int, row: int, col: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            result = self._fetchone(
                conn,
                "SELECT * FROM compartments WHERE box_id = ? AND row = ? AND col = ?",
                (box_id, row, col),
            )
            return dict(result) if result else None
