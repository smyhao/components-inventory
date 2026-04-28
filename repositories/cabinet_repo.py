from __future__ import annotations

from pathlib import Path
from typing import Any

from config import DEFAULT_CABINET_COLOR
from models import InventoryError, clean_color, clean_text
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
                    COUNT(b.id) AS box_count,
                    COALESCE(SUM(b.rows * b.cols), 0) AS total_slots,
                    COUNT(DISTINCT c.compartment_id) AS used_slots,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM cabinets cb
                LEFT JOIN boxes b ON b.cabinet_id = cb.id
                LEFT JOIN components c ON c.box_id = b.id
                GROUP BY cb.id
                ORDER BY cb.name
                """,
            )
            return [dict(row) for row in rows]

    def get_cabinet(self, cabinet_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(
                conn,
                """
                SELECT
                    cb.*,
                    COUNT(b.id) AS box_count,
                    COALESCE(SUM(b.rows * b.cols), 0) AS total_slots,
                    COUNT(DISTINCT c.compartment_id) AS used_slots,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM cabinets cb
                LEFT JOIN boxes b ON b.cabinet_id = cb.id
                LEFT JOIN components c ON c.box_id = b.id
                WHERE cb.id = ?
                GROUP BY cb.id
                """,
                (cabinet_id,),
            )
            if not row:
                raise InventoryError("cabinet not found")
            return dict(row)

    def create_cabinet(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = clean_text(payload.get("name"))
        description = clean_text(payload.get("description")) or None
        color = clean_color(payload.get("color"), DEFAULT_CABINET_COLOR)
        if not name:
            raise InventoryError("cabinet name is required")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO cabinets (name, description, color, position_x, position_y)
                VALUES (?, ?, ?, 0, 0)
                """,
                (name, description, color),
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
            conn.execute(
                "UPDATE cabinets SET name = ?, description = ?, color = ? WHERE id = ?",
                (name, description, color, cabinet_id),
            )
        self.file_logger.write_backend("BOX", f"update cabinet: ID={cabinet_id}, name={name}, color={color}")
        return self.get_cabinet(cabinet_id)

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
