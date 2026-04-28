from __future__ import annotations

from pathlib import Path
from typing import Any

from models import InventoryError, clean_optional_int, clean_text
from repositories.base import BaseRepository


class CategoryRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger

    def list_categories(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT c.*, COUNT(cp.id) AS component_count
                FROM categories c
                LEFT JOIN components cp ON cp.category_id = c.id
                GROUP BY c.id
                ORDER BY COALESCE(c.parent_id, c.id), c.name
                """,
            )
            return [dict(row) for row in rows]

    def create_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = clean_text(payload.get("name"))
        if not name:
            raise InventoryError("分类名称不能为空")
        parent_id = clean_optional_int(payload.get("parent_id"))
        icon = clean_text(payload.get("icon")) or None
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO categories (name, parent_id, icon) VALUES (?, ?, ?)",
                (name, parent_id, icon),
            )
            category_id = cur.lastrowid
            row = self._fetchone(
                conn,
                "SELECT id, name, parent_id, icon, created_at FROM categories WHERE id = ?",
                (category_id,),
            )
        self.file_logger.write_backend("CATEGORY", f"新增分类: {name}")
        return dict(row) if row else {"id": category_id, "name": name, "parent_id": parent_id, "icon": icon}

    def ensure_category_by_name(self, name: str) -> int | None:
        text = clean_text(name)
        if not text:
            return None
        with self.connect() as conn:
            row = self._fetchone(conn, "SELECT id FROM categories WHERE name = ?", (text,))
            if row:
                return row["id"]
            cur = conn.execute(
                "INSERT INTO categories (name, parent_id, icon) VALUES (?, NULL, NULL)",
                (text,),
            )
            category_id = cur.lastrowid
        self.file_logger.write_backend("CATEGORY", f"导入新增分类: {text}")
        return category_id
