from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from config import DEFAULT_BOX_COLOR
from models import InventoryError, clean_color, clean_int, clean_optional_int, clean_text
from repositories._utils import file_url, image_url
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
                    cb.layer_count AS cabinet_layer_count,
                    bt.name AS template_name,
                    bt.cell_width_mm AS template_cell_width_mm,
                    bt.cell_depth_mm AS template_cell_depth_mm,
                    bt.cell_height_mm AS template_cell_height_mm,
                    bt.gap_x_mm AS template_gap_x_mm,
                    bt.gap_z_mm AS template_gap_z_mm,
                    bt.padding_x_mm AS template_padding_x_mm,
                    bt.padding_z_mm AS template_padding_z_mm,
                    ca.file_path AS cell_asset_file_path,
                    ca.width_mm AS cell_asset_width_mm,
                    ca.height_mm AS cell_asset_height_mm,
                    ca.depth_mm AS cell_asset_depth_mm,
                    fa.file_path AS frame_asset_file_path,
                    fa.width_mm AS frame_asset_width_mm,
                    fa.height_mm AS frame_asset_height_mm,
                    fa.depth_mm AS frame_asset_depth_mm,
                    COUNT(DISTINCT c.compartment_id) AS occupied_count,
                    COUNT(c.id) AS component_count,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM boxes b
                LEFT JOIN cabinets cb ON cb.id = b.cabinet_id
                LEFT JOIN box_templates bt ON bt.id = b.template_id
                LEFT JOIN model_assets ca ON ca.id = bt.cell_model_asset_id
                LEFT JOIN model_assets fa ON fa.id = bt.frame_model_asset_id
                LEFT JOIN components c ON c.box_id = b.id
                GROUP BY b.id
                ORDER BY COALESCE(cb.name, ''), b.cabinet_slot, b.name
                """,
            )
            items = []
            for row in rows:
                item = self._box_to_dict(row)
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
                    cb.layer_count AS cabinet_layer_count,
                    bt.name AS template_name,
                    bt.cell_width_mm AS template_cell_width_mm,
                    bt.cell_depth_mm AS template_cell_depth_mm,
                    bt.cell_height_mm AS template_cell_height_mm,
                    bt.gap_x_mm AS template_gap_x_mm,
                    bt.gap_z_mm AS template_gap_z_mm,
                    bt.padding_x_mm AS template_padding_x_mm,
                    bt.padding_z_mm AS template_padding_z_mm,
                    ca.file_path AS cell_asset_file_path,
                    ca.width_mm AS cell_asset_width_mm,
                    ca.height_mm AS cell_asset_height_mm,
                    ca.depth_mm AS cell_asset_depth_mm,
                    fa.file_path AS frame_asset_file_path,
                    fa.width_mm AS frame_asset_width_mm,
                    fa.height_mm AS frame_asset_height_mm,
                    fa.depth_mm AS frame_asset_depth_mm,
                    COUNT(DISTINCT c.compartment_id) AS occupied_count,
                    COUNT(c.id) AS component_count,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM boxes b
                LEFT JOIN cabinets cb ON cb.id = b.cabinet_id
                LEFT JOIN box_templates bt ON bt.id = b.template_id
                LEFT JOIN model_assets ca ON ca.id = bt.cell_model_asset_id
                LEFT JOIN model_assets fa ON fa.id = bt.frame_model_asset_id
                LEFT JOIN components c ON c.box_id = b.id
                WHERE b.id = ?
                GROUP BY b.id
                """,
                (box_id,),
            )
            if not row:
                raise InventoryError("收纳盒不存在")
            item = self._box_to_dict(row)
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
        template_id = clean_optional_int(payload.get("template_id"))
        if not name:
            raise InventoryError("box name is required")
        if rows < 1 or cols < 1:
            raise InventoryError("rows and cols must be greater than 0")

        with self.connect() as conn:
            self._validate_template(conn, template_id)
            cabinet_slot = self._validate_cabinet_slot(conn, cabinet_id, cabinet_slot)
            cur = conn.execute(
                """
                INSERT INTO boxes (name, rows, cols, description, color, cabinet_id, cabinet_slot, template_id, position_x, position_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (name, rows, cols, description, color, cabinet_id, cabinet_slot, template_id),
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
            template_id = clean_optional_int(payload.get("template_id")) if "template_id" in payload else existing["template_id"]
            if rows < 1 or cols < 1:
                raise InventoryError("行列数量必须大于 0")

            self._validate_template(conn, template_id)
            cabinet_slot = self._validate_cabinet_slot(conn, cabinet_id, cabinet_slot, box_id)

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
                SET name = ?, rows = ?, cols = ?, description = ?, color = ?, cabinet_id = ?, cabinet_slot = ?, template_id = ?
                WHERE id = ?
                """,
                (name, rows, cols, description, color, cabinet_id, cabinet_slot, template_id, box_id),
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

    def _validate_template(self, conn: sqlite3.Connection, template_id: int | None) -> None:
        if template_id is None:
            return
        if not self._fetchone(conn, "SELECT id FROM box_templates WHERE id = ?", (template_id,)):
            raise InventoryError("收纳盒模板不存在")

    def _validate_cabinet_slot(
        self,
        conn: sqlite3.Connection,
        cabinet_id: int | None,
        cabinet_slot: int,
        box_id: int | None = None,
    ) -> int:
        if cabinet_id is None:
            return 0
        cabinet = self._fetchone(conn, "SELECT id, layer_count FROM cabinets WHERE id = ?", (cabinet_id,))
        if not cabinet:
            raise InventoryError("cabinet not found")
        layer_count = max(1, int(cabinet["layer_count"] or 1))
        if cabinet_slot < 1:
            for candidate in range(1, layer_count + 1):
                params = (cabinet_id, candidate, box_id) if box_id else (cabinet_id, candidate)
                sql = "SELECT id FROM boxes WHERE cabinet_id = ? AND cabinet_slot = ? AND id <> ?" if box_id else "SELECT id FROM boxes WHERE cabinet_id = ? AND cabinet_slot = ?"
                if not self._fetchone(conn, sql, params):
                    return candidate
            raise InventoryError("柜子已满，无法继续放入收纳盒")
        if cabinet_slot < 1 or cabinet_slot > layer_count:
            raise InventoryError(f"柜内层位必须在 1..{layer_count} 范围内")
        params: tuple[Any, ...]
        if box_id:
            sql = "SELECT id FROM boxes WHERE cabinet_id = ? AND cabinet_slot = ? AND id <> ?"
            params = (cabinet_id, cabinet_slot, box_id)
        else:
            sql = "SELECT id FROM boxes WHERE cabinet_id = ? AND cabinet_slot = ?"
            params = (cabinet_id, cabinet_slot)
        if self._fetchone(conn, sql, params):
            raise InventoryError("该柜子层位已经放置了收纳盒")
        return cabinet_slot

    def _asset_dict(self, row: sqlite3.Row, prefix: str) -> dict[str, Any] | None:
        key = f"{prefix}_asset_file_path"
        if not row[key]:
            return None
        return {
            "url": file_url(row[key]),
            "width_mm": row[f"{prefix}_asset_width_mm"],
            "height_mm": row[f"{prefix}_asset_height_mm"],
            "depth_mm": row[f"{prefix}_asset_depth_mm"],
        }

    def _box_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        if row["template_id"]:
            item["template"] = {
                "id": row["template_id"],
                "name": row["template_name"],
                "cell_width_mm": row["template_cell_width_mm"],
                "cell_depth_mm": row["template_cell_depth_mm"],
                "cell_height_mm": row["template_cell_height_mm"],
                "gap_x_mm": row["template_gap_x_mm"],
                "gap_z_mm": row["template_gap_z_mm"],
                "padding_x_mm": row["template_padding_x_mm"],
                "padding_z_mm": row["template_padding_z_mm"],
                "cell_model_asset": self._asset_dict(row, "cell"),
                "frame_model_asset": self._asset_dict(row, "frame"),
            }
        else:
            item["template"] = None
        return item
