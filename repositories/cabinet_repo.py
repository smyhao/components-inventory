from __future__ import annotations

from pathlib import Path
from typing import Any

from config import DEFAULT_CABINET_COLOR
from models import InventoryError, clean_color, clean_int, clean_optional_int, clean_text
from repositories._utils import file_url
from repositories.base import BaseRepository


class CabinetRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger

    def list_cabinets(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT
                    cb.*,
                    ct.name AS template_name,
                    ct.structure_type AS template_structure_type,
                    ct.layer_model_asset_id AS template_layer_model_asset_id,
                    ct.base_model_asset_id AS template_base_model_asset_id,
                    ct.top_model_asset_id AS template_top_model_asset_id,
                    ct.layer_height_mm AS template_layer_height_mm,
                    ct.pull_axis AS template_pull_axis,
                    ct.pull_distance_mm AS template_pull_distance_mm,
                    ct.slot_offset_x_mm AS template_slot_offset_x_mm,
                    ct.slot_offset_y_mm AS template_slot_offset_y_mm,
                    ct.slot_offset_z_mm AS template_slot_offset_z_mm,
                    la.file_path AS layer_asset_file_path,
                    la.width_mm AS layer_asset_width_mm,
                    la.height_mm AS layer_asset_height_mm,
                    la.depth_mm AS layer_asset_depth_mm,
                    ba.file_path AS base_asset_file_path,
                    ba.width_mm AS base_asset_width_mm,
                    ba.height_mm AS base_asset_height_mm,
                    ba.depth_mm AS base_asset_depth_mm,
                    ta.file_path AS top_asset_file_path,
                    ta.width_mm AS top_asset_width_mm,
                    ta.height_mm AS top_asset_height_mm,
                    ta.depth_mm AS top_asset_depth_mm,
                    COALESCE(box_stats.box_count, 0) AS box_count,
                    COALESCE(box_stats.total_slots, 0) AS total_slots,
                    COALESCE(component_stats.used_slots, 0) AS used_slots,
                    COALESCE(component_stats.total_quantity, 0) AS total_quantity
                FROM cabinets cb
                LEFT JOIN cabinet_templates ct ON ct.id = cb.template_id
                LEFT JOIN model_assets la ON la.id = ct.layer_model_asset_id
                LEFT JOIN model_assets ba ON ba.id = ct.base_model_asset_id
                LEFT JOIN model_assets ta ON ta.id = ct.top_model_asset_id
                LEFT JOIN (
                    SELECT cabinet_id, COUNT(*) AS box_count, SUM(rows * cols) AS total_slots
                    FROM boxes
                    GROUP BY cabinet_id
                ) box_stats ON box_stats.cabinet_id = cb.id
                LEFT JOIN (
                    SELECT b.cabinet_id,
                           COUNT(DISTINCT c.compartment_id) AS used_slots,
                           SUM(c.quantity) AS total_quantity
                    FROM boxes b
                    LEFT JOIN components c ON c.box_id = b.id
                    GROUP BY b.cabinet_id
                ) component_stats ON component_stats.cabinet_id = cb.id
                ORDER BY cb.name
                """,
            )
            return [self._cabinet_to_dict(row) for row in rows]

    def get_cabinet(self, cabinet_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(
                conn,
                """
                SELECT
                    cb.*,
                    ct.name AS template_name,
                    ct.structure_type AS template_structure_type,
                    ct.layer_model_asset_id AS template_layer_model_asset_id,
                    ct.base_model_asset_id AS template_base_model_asset_id,
                    ct.top_model_asset_id AS template_top_model_asset_id,
                    ct.layer_height_mm AS template_layer_height_mm,
                    ct.pull_axis AS template_pull_axis,
                    ct.pull_distance_mm AS template_pull_distance_mm,
                    ct.slot_offset_x_mm AS template_slot_offset_x_mm,
                    ct.slot_offset_y_mm AS template_slot_offset_y_mm,
                    ct.slot_offset_z_mm AS template_slot_offset_z_mm,
                    la.file_path AS layer_asset_file_path,
                    la.width_mm AS layer_asset_width_mm,
                    la.height_mm AS layer_asset_height_mm,
                    la.depth_mm AS layer_asset_depth_mm,
                    ba.file_path AS base_asset_file_path,
                    ba.width_mm AS base_asset_width_mm,
                    ba.height_mm AS base_asset_height_mm,
                    ba.depth_mm AS base_asset_depth_mm,
                    ta.file_path AS top_asset_file_path,
                    ta.width_mm AS top_asset_width_mm,
                    ta.height_mm AS top_asset_height_mm,
                    ta.depth_mm AS top_asset_depth_mm,
                    COALESCE(box_stats.box_count, 0) AS box_count,
                    COALESCE(box_stats.total_slots, 0) AS total_slots,
                    COALESCE(component_stats.used_slots, 0) AS used_slots,
                    COALESCE(component_stats.total_quantity, 0) AS total_quantity
                FROM cabinets cb
                LEFT JOIN cabinet_templates ct ON ct.id = cb.template_id
                LEFT JOIN model_assets la ON la.id = ct.layer_model_asset_id
                LEFT JOIN model_assets ba ON ba.id = ct.base_model_asset_id
                LEFT JOIN model_assets ta ON ta.id = ct.top_model_asset_id
                LEFT JOIN (
                    SELECT cabinet_id, COUNT(*) AS box_count, SUM(rows * cols) AS total_slots
                    FROM boxes
                    GROUP BY cabinet_id
                ) box_stats ON box_stats.cabinet_id = cb.id
                LEFT JOIN (
                    SELECT b.cabinet_id,
                           COUNT(DISTINCT c.compartment_id) AS used_slots,
                           SUM(c.quantity) AS total_quantity
                    FROM boxes b
                    LEFT JOIN components c ON c.box_id = b.id
                    GROUP BY b.cabinet_id
                ) component_stats ON component_stats.cabinet_id = cb.id
                WHERE cb.id = ?
                """,
                (cabinet_id,),
            )
            if not row:
                raise InventoryError("cabinet not found")
            return self._cabinet_to_dict(row)

    def create_cabinet(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = clean_text(payload.get("name"))
        description = clean_text(payload.get("description")) or None
        color = clean_color(payload.get("color"), DEFAULT_CABINET_COLOR)
        template_id = clean_optional_int(payload.get("template_id"))
        layer_count = clean_int(payload.get("layer_count"), 1)
        if not name:
            raise InventoryError("cabinet name is required")
        if layer_count < 1:
            raise InventoryError("柜子层数必须大于 0")
        with self.connect() as conn:
            self._validate_template(conn, template_id)
            cur = conn.execute(
                """
                INSERT INTO cabinets (name, description, color, template_id, layer_count, position_x, position_y)
                VALUES (?, ?, ?, ?, ?, 0, 0)
                """,
                (name, description, color, template_id, layer_count),
            )
            cabinet_id = cur.lastrowid
        self.file_logger.write_backend("BOX", f"create cabinet: {name}, color={color}")
        return self.get_cabinet(cabinet_id)

    def update_cabinet(self, cabinet_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            existing = self._fetchone(conn, "SELECT * FROM cabinets WHERE id = ?", (cabinet_id,))
            if not existing:
                raise InventoryError("cabinet not found")
            name = clean_text(payload.get("name")) or existing["name"]
            description = clean_text(payload.get("description")) if "description" in payload else existing["description"]
            color = clean_color(payload.get("color"), existing["color"] or DEFAULT_CABINET_COLOR)
            template_id = clean_optional_int(payload.get("template_id")) if "template_id" in payload else existing["template_id"]
            layer_count = clean_int(payload.get("layer_count"), existing["layer_count"] or 1)
            if layer_count < 1:
                raise InventoryError("柜子层数必须大于 0")
            self._validate_template(conn, template_id)
            blocked = self._fetchone(
                conn,
                "SELECT COUNT(*) AS cnt FROM boxes WHERE cabinet_id = ? AND cabinet_slot > ?",
                (cabinet_id, layer_count),
            )
            if blocked and blocked["cnt"] > 0:
                raise InventoryError("缩小层数会移除已有收纳盒所在层，无法保存")
            conn.execute(
                "UPDATE cabinets SET name = ?, description = ?, color = ?, template_id = ?, layer_count = ? WHERE id = ?",
                (name, description, color, template_id, layer_count, cabinet_id),
            )
        self.file_logger.write_backend("BOX", f"update cabinet: ID={cabinet_id}, name={name}, color={color}")
        return self.get_cabinet(cabinet_id)

    def _validate_template(self, conn, template_id: int | None) -> None:
        if template_id is None:
            return
        if not self._fetchone(conn, "SELECT id FROM cabinet_templates WHERE id = ?", (template_id,)):
            raise InventoryError("柜体模板不存在")

    def _asset_dict(self, row, prefix: str) -> dict[str, Any] | None:
        if not row[f"{prefix}_asset_file_path"]:
            return None
        return {
            "url": file_url(row[f"{prefix}_asset_file_path"]),
            "width_mm": row[f"{prefix}_asset_width_mm"],
            "height_mm": row[f"{prefix}_asset_height_mm"],
            "depth_mm": row[f"{prefix}_asset_depth_mm"],
        }

    def _cabinet_to_dict(self, row) -> dict[str, Any]:
        item = dict(row)
        if row["template_id"]:
            item["template"] = {
                "id": row["template_id"],
                "name": row["template_name"],
                "structure_type": row["template_structure_type"],
                "layer_model_asset_id": row["template_layer_model_asset_id"],
                "base_model_asset_id": row["template_base_model_asset_id"],
                "top_model_asset_id": row["template_top_model_asset_id"],
                "layer_height_mm": row["template_layer_height_mm"],
                "pull_axis": row["template_pull_axis"],
                "pull_distance_mm": row["template_pull_distance_mm"],
                "slot_offset_x_mm": row["template_slot_offset_x_mm"],
                "slot_offset_y_mm": row["template_slot_offset_y_mm"],
                "slot_offset_z_mm": row["template_slot_offset_z_mm"],
                "layer_model_asset": self._asset_dict(row, "layer"),
                "base_model_asset": self._asset_dict(row, "base"),
                "top_model_asset": self._asset_dict(row, "top"),
            }
        else:
            item["template"] = None
        return item

    def delete_cabinet(self, cabinet_id: int) -> None:
        with self.connect() as conn:
            cabinet = self._fetchone(conn, "SELECT * FROM cabinets WHERE id = ?", (cabinet_id,))
            if not cabinet:
                raise InventoryError("cabinet not found")
            occupied = self._fetchone(conn, "SELECT COUNT(*) AS cnt FROM boxes WHERE cabinet_id = ?", (cabinet_id,))
            if occupied and occupied["cnt"] > 0:
                raise InventoryError("cabinet contains boxes")
            conn.execute("DELETE FROM cabinets WHERE id = ?", (cabinet_id,))
        self.file_logger.write_backend("BOX", f"delete cabinet: ID={cabinet_id}, name={cabinet['name']}")

    def update_cabinet_layout(self, cabinet_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        position_x = float(payload.get("position_x") or 0)
        position_y = float(payload.get("position_y") or 0)
        with self.connect() as conn:
            conn.execute(
                "UPDATE cabinets SET position_x = ?, position_y = ? WHERE id = ?",
                (position_x, position_y, cabinet_id),
            )
        self.file_logger.write_backend("BOX", f"update cabinet map position: ID={cabinet_id}, x={position_x}, y={position_y}")
        return self.get_cabinet(cabinet_id)
