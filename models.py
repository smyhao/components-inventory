from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_optional_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_int(value: Any, default: int = 0) -> int:
    parsed = clean_optional_int(value)
    return default if parsed is None else parsed


def clean_color(value: Any, default: str = "#84b59b") -> str:
    text = clean_text(value)
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.lower()
    return default


def unique_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def build_spec_summary(component: dict[str, Any]) -> str:
    parts = [
        clean_text(component.get("nominal_value")),
        clean_text(component.get("voltage_rating")),
        clean_text(component.get("current_rating")),
        clean_text(component.get("power_rating")),
        clean_text(component.get("tolerance")),
        clean_text(component.get("material_type")),
    ]
    return " / ".join([part for part in parts if part])


def normalize_merge_part(value: Any) -> str:
    return clean_text(value).lower()


def normalize_footprint(value: Any) -> str:
    text = clean_text(value).lower().replace("_", "").replace("-", "").replace(" ", "")
    if not text:
        return ""
    match = re.search(r"(\d{4})", text)
    if match:
        return match.group(1)
    return text


def normalize_value(value: Any) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    text = text.replace("μ", "u").replace("Ω", "ohm").replace("ω", "ohm").replace("欧", "ohm")
    text = text.replace("Ω", "ohm").replace(" ", "")
    text = text.replace("uf", "uF").replace("nf", "nF").replace("pf", "pF")
    text = text.lower()
    return text


class InventoryError(Exception):
    pass


class InventoryRepository:
    def __init__(self, db_path: Path, file_logger: Any, upload_folder: Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.file_logger = file_logger
        self.upload_folder = Path(upload_folder) if upload_folder else None

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _fetchone(self, conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return conn.execute(sql, params).fetchone()

    def _fetchall(self, conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return conn.execute(sql, params).fetchall()

    def _component_base_sql(self) -> str:
        return """
            SELECT
                c.*,
                cat.name AS category_name,
                b.name AS box_name,
                cp.id AS compartment_ref,
                cp.row AS grid_row,
                cp.col AS grid_col,
                cp.label AS cell_label
            FROM components c
            LEFT JOIN categories cat ON cat.id = c.category_id
            LEFT JOIN boxes b ON b.id = c.box_id
            LEFT JOIN compartments cp ON cp.id = c.compartment_id
        """

    def _image_url(self, relative_path: str | None) -> str | None:
        if not relative_path:
            return None
        return "/uploads/" + relative_path.replace("\\", "/")

    def _load_tags_map(self, conn: sqlite3.Connection, component_ids: list[int]) -> dict[int, list[str]]:
        if not component_ids:
            return {}
        placeholders = ",".join("?" for _ in component_ids)
        rows = self._fetchall(
            conn,
            f"""
            SELECT ct.component_id, t.name
            FROM component_tags ct
            JOIN tags t ON t.id = ct.tag_id
            WHERE ct.component_id IN ({placeholders})
            ORDER BY t.name
            """,
            tuple(component_ids),
        )
        result: dict[int, list[str]] = {}
        for row in rows:
            result.setdefault(row["component_id"], []).append(row["name"])
        return result

    def _load_primary_image_map(self, conn: sqlite3.Connection, component_ids: list[int]) -> dict[int, str]:
        if not component_ids:
            return {}
        placeholders = ",".join("?" for _ in component_ids)
        rows = self._fetchall(
            conn,
            f"""
            SELECT i.component_id, i.path
            FROM images i
            INNER JOIN (
                SELECT component_id, MIN(CASE WHEN is_primary = 1 THEN 0 ELSE 1 END) AS primary_rank
                FROM images
                WHERE component_id IN ({placeholders})
                GROUP BY component_id
            ) r ON r.component_id = i.component_id
            WHERE i.component_id IN ({placeholders})
            ORDER BY i.component_id, i.is_primary DESC, i.id ASC
            """,
            tuple(component_ids + component_ids),
        )
        result: dict[int, str] = {}
        for row in rows:
            component_id = row["component_id"]
            if component_id not in result:
                result[component_id] = self._image_url(row["path"]) or ""
        return result

    def _load_images_for_component(self, conn: sqlite3.Connection, component_id: int) -> list[dict[str, Any]]:
        rows = self._fetchall(
            conn,
            """
            SELECT id, path, thumbnail_path, is_primary
            FROM images
            WHERE component_id = ?
            ORDER BY is_primary DESC, id ASC
            """,
            (component_id,),
        )
        return [
            {
                "id": row["id"],
                "url": self._image_url(row["path"]),
                "thumbnail_url": self._image_url(row["thumbnail_path"]),
                "is_primary": bool(row["is_primary"]),
            }
            for row in rows
        ]

    def _component_from_row(
        self,
        row: sqlite3.Row,
        tags_map: dict[int, list[str]] | None = None,
        primary_images: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        item = dict(row)
        item["tags"] = (tags_map or {}).get(item["id"], [])
        item["primary_image"] = (primary_images or {}).get(item["id"])
        item["cell_row"] = item.get("compartment_id")
        item["cell_col"] = item.get("grid_col")
        item["spec_summary"] = build_spec_summary(item)
        item["images"] = []
        return item

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

    def list_boxes(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT
                    b.*,
                    COUNT(DISTINCT c.compartment_id) AS occupied_count,
                    COUNT(c.id) AS component_count,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM boxes b
                LEFT JOIN components c ON c.box_id = b.id
                GROUP BY b.id
                ORDER BY b.name
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
                    COUNT(DISTINCT c.compartment_id) AS occupied_count,
                    COUNT(c.id) AS component_count,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM boxes b
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
        if not name:
            raise InventoryError("box name is required")
        if rows < 1 or cols < 1:
            raise InventoryError("rows and cols must be greater than 0")

        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO boxes (name, rows, cols, description, color, position_x, position_y)
                VALUES (?, ?, ?, ?, ?, 0, 0)
                """,
                (name, rows, cols, description, color),
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
            color = clean_color(payload.get("color"), existing["color"] or "#84b59b")
            if rows < 1 or cols < 1:
                raise InventoryError("行列数量必须大于 0")

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
                "UPDATE boxes SET name = ?, rows = ?, cols = ?, description = ?, color = ? WHERE id = ?",
                (name, rows, cols, description, color, box_id),
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
                        "primary_image": self._image_url(row["primary_image"]),
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

    def _resolve_location(
        self,
        conn: sqlite3.Connection,
        box_id_value: Any,
        cell_row_value: Any,
        cell_col_value: Any,
        compartment_id_value: Any = None,
        current_component_id: int | None = None,
    ) -> tuple[int | None, int | None]:
        box_id = clean_optional_int(box_id_value)
        if box_id is None:
            return None, None
        box = self._fetchone(conn, "SELECT id FROM boxes WHERE id = ?", (box_id,))
        if not box:
            raise InventoryError("收纳盒不存在")

        compartment_id = clean_optional_int(compartment_id_value)
        cell_row = clean_optional_int(cell_row_value)
        cell_col = clean_optional_int(cell_col_value)
        compartment = None

        if compartment_id is not None:
            compartment = self._fetchone(
                conn,
                "SELECT * FROM compartments WHERE id = ? AND box_id = ?",
                (compartment_id, box_id),
            )
        elif cell_row is not None:
            compartment = self._fetchone(
                conn,
                "SELECT * FROM compartments WHERE id = ? AND box_id = ?",
                (cell_row, box_id),
            )
            if not compartment and cell_col is not None:
                compartment = self._fetchone(
                    conn,
                    "SELECT * FROM compartments WHERE box_id = ? AND row = ? AND col = ?",
                    (box_id, cell_row, cell_col),
                )

        if cell_row is not None and not compartment:
            raise InventoryError("target compartment does not exist")

        if compartment:
            occupied = self._fetchone(
                conn,
                """
                SELECT id FROM components
                WHERE compartment_id = ? AND (? IS NULL OR id != ?)
                """,
                (compartment["id"], current_component_id, current_component_id),
            )
            if occupied:
                raise InventoryError("target compartment is already occupied")
            return box_id, compartment["id"]

        return box_id, None

    def _find_merge_candidate(
        self,
        conn: sqlite3.Connection,
        payload: dict[str, Any],
        exclude_id: int | None = None,
    ) -> sqlite3.Row | None:
        params = [
            normalize_merge_part(payload.get("name")),
            normalize_merge_part(payload.get("model")),
            normalize_merge_part(payload.get("package")),
            normalize_merge_part(payload.get("nominal_value") or payload.get("value")),
            normalize_merge_part(payload.get("voltage_rating")),
            normalize_merge_part(payload.get("current_rating")),
            normalize_merge_part(payload.get("power_rating")),
            normalize_merge_part(payload.get("tolerance")),
            normalize_merge_part(payload.get("material_type") or payload.get("material")),
        ]
        sql = """
            SELECT *
            FROM components
            WHERE LOWER(TRIM(COALESCE(name, ''))) = ?
              AND LOWER(TRIM(COALESCE(model, ''))) = ?
              AND LOWER(TRIM(COALESCE(package, ''))) = ?
              AND LOWER(TRIM(COALESCE(nominal_value, ''))) = ?
              AND LOWER(TRIM(COALESCE(voltage_rating, ''))) = ?
              AND LOWER(TRIM(COALESCE(current_rating, ''))) = ?
              AND LOWER(TRIM(COALESCE(power_rating, ''))) = ?
              AND LOWER(TRIM(COALESCE(tolerance, ''))) = ?
              AND LOWER(TRIM(COALESCE(material_type, ''))) = ?
        """
        if exclude_id is not None:
            sql += " AND id != ?"
            params.append(exclude_id)
        sql += " LIMIT 1"
        return self._fetchone(conn, sql, tuple(params))

    def _upsert_tags(self, conn: sqlite3.Connection, component_id: int, tags: list[str] | None) -> None:
        if tags is None:
            return
        normalized = unique_strings(tags)
        conn.execute("DELETE FROM component_tags WHERE component_id = ?", (component_id,))
        for tag in normalized:
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            tag_row = self._fetchone(conn, "SELECT id FROM tags WHERE name = ?", (tag,))
            if tag_row:
                conn.execute(
                    "INSERT OR IGNORE INTO component_tags (component_id, tag_id) VALUES (?, ?)",
                    (component_id, tag_row["id"]),
                )

    def _extract_image_id(self, conn: sqlite3.Connection, ref: Any, component_id: int | None = None) -> int | None:
        if isinstance(ref, int):
            row = self._fetchone(
                conn,
                "SELECT id FROM images WHERE id = ? AND (component_id IS NULL OR component_id = ? OR ? IS NULL)",
                (ref, component_id, component_id),
            )
            return row["id"] if row else None
        text = clean_text(ref)
        if not text:
            return None
        if text.isdigit():
            return self._extract_image_id(conn, int(text), component_id)
        if text.startswith("/uploads/"):
            text = text[len("/uploads/") :]
        row = self._fetchone(
            conn,
            """
            SELECT id FROM images
            WHERE path = ? AND (component_id IS NULL OR component_id = ? OR ? IS NULL)
            """,
            (text, component_id, component_id),
        )
        return row["id"] if row else None

    def _delete_image_files(self, rows: Iterable[sqlite3.Row]) -> None:
        if not self.upload_folder:
            return
        for row in rows:
            for key in ("path", "thumbnail_path"):
                relative = row[key]
                if not relative:
                    continue
                target = self.upload_folder / relative
                try:
                    if target.exists():
                        target.unlink()
                except OSError:
                    continue

    def _sync_images(
        self,
        conn: sqlite3.Connection,
        component_id: int,
        image_refs: list[Any] | None,
        *,
        delete_missing: bool,
    ) -> None:
        if image_refs is None:
            return
        desired_ids = unique_strings(image_refs)
        resolved_ids: list[int] = []
        for ref in desired_ids:
            image_id = self._extract_image_id(conn, ref, component_id)
            if image_id is not None:
                resolved_ids.append(image_id)

        current_rows = self._fetchall(
            conn,
            "SELECT id, path, thumbnail_path FROM images WHERE component_id = ?",
            (component_id,),
        )
        current_ids = {row["id"] for row in current_rows}
        keep_ids = set(resolved_ids)

        if resolved_ids:
            placeholders = ",".join("?" for _ in resolved_ids)
            conn.execute(
                f"UPDATE images SET component_id = ?, is_primary = 0 WHERE id IN ({placeholders})",
                tuple([component_id] + resolved_ids),
            )
            conn.execute("UPDATE images SET is_primary = 0 WHERE component_id = ?", (component_id,))
            conn.execute("UPDATE images SET is_primary = 1 WHERE id = ?", (resolved_ids[0],))
        else:
            conn.execute("UPDATE images SET is_primary = 0 WHERE component_id = ?", (component_id,))

        if delete_missing:
            remove_ids = current_ids - keep_ids
            if remove_ids:
                placeholders = ",".join("?" for _ in remove_ids)
                remove_rows = self._fetchall(
                    conn,
                    f"SELECT id, path, thumbnail_path FROM images WHERE id IN ({placeholders})",
                    tuple(remove_ids),
                )
                self._delete_image_files(remove_rows)
                conn.execute(
                    f"DELETE FROM images WHERE id IN ({placeholders})",
                    tuple(remove_ids),
                )

    def _component_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        tags = payload.get("tags")
        if isinstance(tags, str):
            tags = re.split("[,\uFF0C]", tags)
        images = payload.get("images")
        if images is not None and not isinstance(images, list):
            images = [images]
        extra_specs = payload.get("extra_specs")
        if extra_specs is not None and not isinstance(extra_specs, str):
            extra_specs = json.dumps(extra_specs, ensure_ascii=False)
        return {
            "name": clean_text(payload.get("name")),
            "category_id": clean_optional_int(payload.get("category_id")),
            "model": clean_text(payload.get("model")),
            "package": clean_text(payload.get("package")),
            "nominal_value": clean_text(payload.get("nominal_value") or payload.get("value")),
            "voltage_rating": clean_text(payload.get("voltage_rating")),
            "current_rating": clean_text(payload.get("current_rating")),
            "power_rating": clean_text(payload.get("power_rating")),
            "tolerance": clean_text(payload.get("tolerance")),
            "material_type": clean_text(payload.get("material_type") or payload.get("material")),
            "manufacturer": clean_text(payload.get("manufacturer")),
            "extra_specs": extra_specs,
            "quantity": clean_int(payload.get("quantity"), 0),
            "description": clean_text(payload.get("description")),
            "min_stock": clean_int(payload.get("min_stock"), 0),
            "box_id": payload.get("box_id"),
            "compartment_id": payload.get("compartment_id"),
            "cell_row": payload.get("cell_row"),
            "cell_col": payload.get("cell_col"),
            "tags": unique_strings(tags or []),
            "images": images,
        }

    def _append_stock_log(
        self,
        conn: sqlite3.Connection,
        component_id: int,
        change: int,
        quantity_after: int,
        log_type: str,
        reason: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO stock_logs (component_id, type, change, quantity_after, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (component_id, log_type, change, quantity_after, reason, now_text()),
        )

    def list_components(self, filters: dict[str, Any]) -> dict[str, Any]:
        page = max(1, clean_int(filters.get("page"), 1))
        page_size = clean_int(filters.get("page_size"), 20)
        page_size = 20 if page_size <= 0 else min(page_size, 500)
        keyword = clean_text(filters.get("keyword"))
        category_id = clean_optional_int(filters.get("category_id"))
        box_id = clean_optional_int(filters.get("box_id"))
        tag = clean_text(filters.get("tag"))
        low_stock = str(filters.get("low_stock") or "").lower() in {"1", "true", "yes"}

        where = ["1 = 1"]
        params: list[Any] = []
        if keyword:
            where.append(
                "(c.name LIKE ? OR c.model LIKE ? OR c.description LIKE ? OR c.manufacturer LIKE ? OR c.nominal_value LIKE ?)"
            )
            like_value = f"%{keyword}%"
            params.extend([like_value] * 5)
        if category_id is not None:
            where.append("c.category_id = ?")
            params.append(category_id)
        if box_id is not None:
            where.append("c.box_id = ?")
            params.append(box_id)
        if tag:
            where.append(
                """
                EXISTS (
                    SELECT 1
                    FROM component_tags ct
                    JOIN tags t ON t.id = ct.tag_id
                    WHERE ct.component_id = c.id AND t.name = ?
                )
                """
            )
            params.append(tag)
        if low_stock:
            where.append("c.quantity <= c.min_stock")

        where_sql = " AND ".join(where)

        with self.connect() as conn:
            total_row = self._fetchone(
                conn,
                f"SELECT COUNT(*) AS total FROM components c WHERE {where_sql}",
                tuple(params),
            )
            rows = self._fetchall(
                conn,
                f"""
                {self._component_base_sql()}
                WHERE {where_sql}
                ORDER BY c.updated_at DESC, c.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params + [page_size, (page - 1) * page_size]),
            )
            component_ids = [row["id"] for row in rows]
            tags_map = self._load_tags_map(conn, component_ids)
            primary_map = self._load_primary_image_map(conn, component_ids)
            items = [self._component_from_row(row, tags_map, primary_map) for row in rows]

        return {
            "items": items,
            "total": total_row["total"] if total_row else 0,
            "page": page,
            "page_size": page_size,
        }

    def get_component(self, component_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._fetchone(
                conn,
                f"{self._component_base_sql()} WHERE c.id = ?",
                (component_id,),
            )
            if not row:
                raise InventoryError("元器件不存在")
            tags_map = self._load_tags_map(conn, [component_id])
            primary_map = self._load_primary_image_map(conn, [component_id])
            item = self._component_from_row(row, tags_map, primary_map)
            item["images"] = self._load_images_for_component(conn, component_id)
            item["stock_logs"] = [
                {
                    "id": log["id"],
                    "operation_type": log["type"],
                    "quantity_change": log["change"],
                    "quantity_after": log["quantity_after"],
                    "reason": log["reason"],
                    "created_at": log["created_at"],
                }
                for log in self._fetchall(
                    conn,
                    """
                    SELECT id, type, change, quantity_after, reason, created_at
                    FROM stock_logs
                    WHERE component_id = ?
                    ORDER BY id DESC
                    LIMIT 10
                    """,
                    (component_id,),
                )
            ]
            return item

    def create_component(self, payload: dict[str, Any], *, source: str = "manual") -> dict[str, Any]:
        prepared = self._component_payload(payload)
        if not prepared["name"]:
            raise InventoryError("component name is required")

        with self.connect() as conn:
            box_id, compartment_id = self._resolve_location(
                conn,
                prepared["box_id"],
                prepared["cell_row"],
                prepared["cell_col"],
                prepared["compartment_id"],
            )
            prepared["box_id"] = box_id
            prepared["compartment_id"] = compartment_id

            merge_target = self._find_merge_candidate(conn, prepared)
            reason_text = "导入初始入库" if source == "import" else "初始入库"

            if merge_target:
                if prepared["compartment_id"] and merge_target["compartment_id"] and prepared["compartment_id"] != merge_target["compartment_id"]:
                    raise InventoryError("matched component exists, but the requested location conflicts with the current one")

                new_quantity = merge_target["quantity"] + prepared["quantity"]
                final_box_id = merge_target["box_id"] or prepared["box_id"]
                final_compartment_id = merge_target["compartment_id"] or prepared["compartment_id"]
                final_category_id = merge_target["category_id"] or prepared["category_id"]
                final_manufacturer = merge_target["manufacturer"] or prepared["manufacturer"]
                final_description = merge_target["description"] or prepared["description"]
                final_min_stock = max(merge_target["min_stock"], prepared["min_stock"])

                conn.execute(
                    """
                    UPDATE components
                    SET quantity = ?, box_id = ?, compartment_id = ?, category_id = ?, manufacturer = ?,
                        description = ?, min_stock = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        new_quantity,
                        final_box_id,
                        final_compartment_id,
                        final_category_id,
                        final_manufacturer,
                        final_description,
                        final_min_stock,
                        now_text(),
                        merge_target["id"],
                    ),
                )
                merged_tags = set(self._load_tags_map(conn, [merge_target["id"]]).get(merge_target["id"], []))
                merged_tags.update(prepared["tags"])
                self._upsert_tags(conn, merge_target["id"], list(merged_tags))
                if prepared["images"] is not None:
                    self._sync_images(conn, merge_target["id"], prepared["images"], delete_missing=False)
                if prepared["quantity"] != 0:
                    self._append_stock_log(conn, merge_target["id"], prepared["quantity"], new_quantity, "initial", reason_text)
                component_id = merge_target["id"]
                message = f"合并库存: {prepared['name']}, +{prepared['quantity']}, 现有={new_quantity}"
                self.file_logger.write_backend("COMPONENT", message)
                self.file_logger.write_backend("STOCK", message)
                return {"id": component_id, "merged": True, "quantity": new_quantity}

            cur = conn.execute(
                """
                INSERT INTO components (
                    name, category_id, model, package, nominal_value, voltage_rating, current_rating,
                    power_rating, tolerance, material_type, manufacturer, extra_specs, quantity, box_id,
                    compartment_id, description, min_stock, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prepared["name"],
                    prepared["category_id"],
                    prepared["model"],
                    prepared["package"],
                    prepared["nominal_value"],
                    prepared["voltage_rating"],
                    prepared["current_rating"],
                    prepared["power_rating"],
                    prepared["tolerance"],
                    prepared["material_type"],
                    prepared["manufacturer"],
                    prepared["extra_specs"],
                    prepared["quantity"],
                    prepared["box_id"],
                    prepared["compartment_id"],
                    prepared["description"],
                    prepared["min_stock"],
                    now_text(),
                    now_text(),
                ),
            )
            component_id = cur.lastrowid
            self._upsert_tags(conn, component_id, prepared["tags"])
            if prepared["images"] is not None:
                self._sync_images(conn, component_id, prepared["images"], delete_missing=False)
            if prepared["quantity"] != 0:
                self._append_stock_log(conn, component_id, prepared["quantity"], prepared["quantity"], "initial", reason_text)

        location = f", 位置={prepared['box_id']}-{prepared['compartment_id']}" if prepared["compartment_id"] else ""
        self.file_logger.write_backend("COMPONENT", f"新增元器件: {prepared['name']}, 数量={prepared['quantity']}{location}")
        if prepared["quantity"] != 0:
            self.file_logger.write_backend("STOCK", f"初始入库: {prepared['name']}, 变化=+{prepared['quantity']}, 结余={prepared['quantity']}")
        return {"id": component_id, "merged": False, "quantity": prepared["quantity"]}

    def update_component(self, component_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            current = self._fetchone(conn, "SELECT * FROM components WHERE id = ?", (component_id,))
            if not current:
                raise InventoryError("元器件不存在")

            merged_payload = dict(current)
            merged_payload.update(payload)
            prepared = self._component_payload(merged_payload)
            if not prepared["name"]:
                raise InventoryError("component name is required")
            prepared["quantity"] = clean_int(merged_payload.get("quantity"), current["quantity"])
            prepared["min_stock"] = clean_int(merged_payload.get("min_stock"), current["min_stock"])

            box_id, compartment_id = self._resolve_location(
                conn,
                prepared["box_id"],
                prepared["cell_row"],
                prepared["cell_col"],
                prepared["compartment_id"] or current["compartment_id"],
                current_component_id=component_id,
            )
            prepared["box_id"] = box_id
            prepared["compartment_id"] = compartment_id

            conn.execute(
                """
                UPDATE components
                SET name = ?, category_id = ?, model = ?, package = ?, nominal_value = ?, voltage_rating = ?,
                    current_rating = ?, power_rating = ?, tolerance = ?, material_type = ?, manufacturer = ?,
                    extra_specs = ?, quantity = ?, box_id = ?, compartment_id = ?, description = ?,
                    min_stock = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    prepared["name"],
                    prepared["category_id"],
                    prepared["model"],
                    prepared["package"],
                    prepared["nominal_value"],
                    prepared["voltage_rating"],
                    prepared["current_rating"],
                    prepared["power_rating"],
                    prepared["tolerance"],
                    prepared["material_type"],
                    prepared["manufacturer"],
                    prepared["extra_specs"],
                    prepared["quantity"],
                    prepared["box_id"],
                    prepared["compartment_id"],
                    prepared["description"],
                    prepared["min_stock"],
                    now_text(),
                    component_id,
                ),
            )

            if "tags" in payload or "tagsInput" in payload:
                tags = payload.get("tags")
                if tags is None and "tagsInput" in payload:
                    tags = re.split("[,\uFF0C]", clean_text(payload.get("tagsInput")))
                self._upsert_tags(conn, component_id, unique_strings(tags or []))
            if "images" in payload:
                self._sync_images(conn, component_id, payload.get("images"), delete_missing=True)

            quantity_diff = prepared["quantity"] - current["quantity"]
            if quantity_diff != 0:
                self._append_stock_log(conn, component_id, quantity_diff, prepared["quantity"], "adjust", "编辑调整数量")

        self.file_logger.write_backend("COMPONENT", f"更新元器件: ID={component_id}, 名称={prepared['name']}")
        if quantity_diff != 0:
            self.file_logger.write_backend("STOCK", f"编辑调整: {prepared['name']}, 变化={quantity_diff}, 结余={prepared['quantity']}")
        return self.get_component(component_id)

    def delete_component(self, component_id: int) -> None:
        with self.connect() as conn:
            component = self._fetchone(conn, "SELECT id, name FROM components WHERE id = ?", (component_id,))
            if not component:
                raise InventoryError("元器件不存在")
            images = self._fetchall(
                conn,
                "SELECT id, path, thumbnail_path FROM images WHERE component_id = ?",
                (component_id,),
            )
            self._delete_image_files(images)
            conn.execute("DELETE FROM components WHERE id = ?", (component_id,))
        self.file_logger.write_backend("COMPONENT", f"删除元器件: ID={component_id}, 名称={component['name']}")

    def record_stock(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        component_id = clean_int(payload.get("component_id"))
        quantity = clean_int(payload.get("quantity"))
        reason = clean_text(payload.get("reason")) or ("入库" if action == "in" else "出库")
        if quantity <= 0:
            raise InventoryError("数量必须大于 0")
        if action not in {"in", "out"}:
            raise InventoryError("不支持的库存操作")

        with self.connect() as conn:
            component = self._fetchone(
                conn,
                "SELECT id, name, quantity, min_stock FROM components WHERE id = ?",
                (component_id,),
            )
            if not component:
                raise InventoryError("元器件不存在")
            delta = quantity if action == "in" else -quantity
            quantity_after = component["quantity"] + delta
            if quantity_after < 0:
                raise InventoryError("insufficient stock for stock-out")

            conn.execute(
                "UPDATE components SET quantity = ?, updated_at = ? WHERE id = ?",
                (quantity_after, now_text(), component_id),
            )
            self._append_stock_log(conn, component_id, delta, quantity_after, action, reason)

        self.file_logger.write_backend(
            "STOCK",
            f"{'入库' if action == 'in' else '出库'}: {component['name']}, 变化={delta}, 原因={reason}, 结余={quantity_after}",
        )
        warning = quantity_after <= component["min_stock"]
        if warning:
            self.file_logger.write_backend(
                "STOCK",
                f"低库存预警: {component['name']} 当前={quantity_after}, 阈值={component['min_stock']}",
            )
        return {
            "component_id": component_id,
            "quantity_after": quantity_after,
            "warning": warning,
        }

    def consume_bom(self, payload: dict[str, Any]) -> dict[str, Any]:
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise InventoryError("BOM data is required")

        project_name = clean_text(payload.get("project_name")) or "BOM"
        custom_reason = clean_text(payload.get("reason"))
        reason = custom_reason or f"BOM stock-out: {project_name}"

        aggregated: dict[int, dict[str, Any]] = {}
        rows_consumed = 0

        for index, item in enumerate(items, start=1):
            quantity_needed = clean_int(item.get("quantity_needed"), 0)
            if quantity_needed <= 0:
                continue

            matched = item.get("matched") or {}
            component_id = clean_optional_int(matched.get("id") or item.get("component_id"))
            if component_id is None:
                raise InventoryError(f"BOM row {index} is unmatched and cannot be stocked out")

            entry = aggregated.setdefault(
                component_id,
                {
                    "component_id": component_id,
                    "name": clean_text(matched.get("name")) or clean_text(item.get("comment")) or f"component-{component_id}",
                    "quantity_out": 0,
                },
            )
            entry["quantity_out"] += quantity_needed
            rows_consumed += 1

        if not aggregated:
            raise InventoryError("BOM contains no valid rows to stock out")

        total_quantity = sum(item["quantity_out"] for item in aggregated.values())
        results: list[dict[str, Any]] = []

        with self.connect() as conn:
            components: dict[int, sqlite3.Row] = {}
            for component_id, aggregate in aggregated.items():
                component = self._fetchone(
                    conn,
                    "SELECT id, name, quantity, min_stock FROM components WHERE id = ?",
                    (component_id,),
                )
                if not component:
                    raise InventoryError(f"component not found: {component_id}")
                if component["quantity"] < aggregate["quantity_out"]:
                    raise InventoryError(
                        f"{component['name']} has insufficient stock: need {aggregate['quantity_out']}, current {component['quantity']}"
                    )
                components[component_id] = component

            for component_id, aggregate in aggregated.items():
                component = components[component_id]
                quantity_after = component["quantity"] - aggregate["quantity_out"]
                conn.execute(
                    "UPDATE components SET quantity = ?, updated_at = ? WHERE id = ?",
                    (quantity_after, now_text(), component_id),
                )
                self._append_stock_log(
                    conn,
                    component_id,
                    -aggregate["quantity_out"],
                    quantity_after,
                    "out",
                    reason,
                )
                warning = quantity_after <= component["min_stock"]
                results.append(
                    {
                        "component_id": component_id,
                        "name": component["name"],
                        "quantity_out": aggregate["quantity_out"],
                        "quantity_after": quantity_after,
                        "warning": warning,
                    }
                )

        self.file_logger.write_backend(
            "BOM",
            f"bom stock-out: project={project_name}, types={len(results)}, total_quantity={total_quantity}",
        )
        for item in results:
            self.file_logger.write_backend(
                "STOCK",
                f"BOM stock-out: {item['name']}, change=-{item['quantity_out']}, remain={item['quantity_after']}, project={project_name}",
            )
            if item["warning"]:
                self.file_logger.write_backend(
                    "STOCK",
                    f"low stock warning after BOM stock-out: {item['name']}, current={item['quantity_after']}",
                )

        return {
            "project_name": project_name,
            "components_consumed": len(results),
            "rows_consumed": rows_consumed,
            "total_quantity": total_quantity,
            "results": results,
        }

    def list_stock_logs(self, component_id: int, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        where = "1 = 1"
        params: list[Any] = []
        if component_id > 0:
            where = "sl.component_id = ?"
            params.append(component_id)
        with self.connect() as conn:
            total_row = self._fetchone(
                conn,
                f"SELECT COUNT(*) AS total FROM stock_logs sl WHERE {where}",
                tuple(params),
            )
            rows = self._fetchall(
                conn,
                f"""
                SELECT
                    sl.id,
                    sl.component_id,
                    c.name AS component_name,
                    sl.type AS operation_type,
                    sl.change AS quantity_change,
                    sl.quantity_after,
                    sl.reason,
                    sl.created_at
                FROM stock_logs sl
                JOIN components c ON c.id = sl.component_id
                WHERE {where}
                ORDER BY sl.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params + [page_size, (page - 1) * page_size]),
            )
            return {
                "items": [dict(row) for row in rows],
                "total": total_row["total"] if total_row else 0,
                "page": page,
                "page_size": page_size,
            }

    def get_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            totals = self._fetchone(
                conn,
                """
                SELECT
                    COUNT(*) AS total_components,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COALESCE(SUM(CASE WHEN quantity <= min_stock THEN 1 ELSE 0 END), 0) AS low_stock_count
                FROM components
                """,
            )
            box_totals = self._fetchone(
                conn,
                """
                SELECT
                    COUNT(*) AS total_boxes,
                    COALESCE(SUM(rows * cols), 0) AS total_slots
                FROM boxes
                """,
            )
            used = self._fetchone(
                conn,
                "SELECT COUNT(*) AS used_slots FROM components WHERE compartment_id IS NOT NULL",
            )
            low_rows = self._fetchall(
                conn,
                f"""
                {self._component_base_sql()}
                WHERE c.quantity <= c.min_stock
                ORDER BY (c.min_stock - c.quantity) DESC, c.updated_at DESC
                LIMIT 10
                """,
            )
            tags_map = self._load_tags_map(conn, [row["id"] for row in low_rows])
            primary_map = self._load_primary_image_map(conn, [row["id"] for row in low_rows])
            category_rows = self._fetchall(
                conn,
                """
                SELECT
                    COALESCE(cat.name, '未分类') AS category,
                    COUNT(c.id) AS component_count,
                    COALESCE(SUM(c.quantity), 0) AS total_quantity
                FROM components c
                LEFT JOIN categories cat ON cat.id = c.category_id
                GROUP BY COALESCE(cat.name, '未分类')
                ORDER BY component_count DESC, category ASC
                """,
            )
            return {
                "total_components": totals["total_components"] if totals else 0,
                "total_quantity": totals["total_quantity"] if totals else 0,
                "total_boxes": box_totals["total_boxes"] if box_totals else 0,
                "total_slots": box_totals["total_slots"] if box_totals else 0,
                "used_slots": used["used_slots"] if used else 0,
                "low_stock_count": totals["low_stock_count"] if totals else 0,
                "low_stock_items": [self._component_from_row(row, tags_map, primary_map) for row in low_rows],
                "category_stats": [dict(row) for row in category_rows],
            }

    def get_map_data(self) -> dict[str, Any]:
        return {"boxes": self.list_boxes()}

    def search_map(self, keyword: str) -> list[dict[str, Any]]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT
                    c.id AS component_id,
                    c.name,
                    c.quantity,
                    b.id AS box_id,
                    b.name AS box_name,
                    cp.row,
                    cp.col,
                    cp.label AS cell_label,
                    b.position_x,
                    b.position_y
                FROM components c
                JOIN boxes b ON b.id = c.box_id
                JOIN compartments cp ON cp.id = c.compartment_id
                WHERE c.name LIKE ? OR c.model LIKE ? OR c.description LIKE ?
                ORDER BY c.updated_at DESC
                LIMIT 50
                """,
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
            )
            return [dict(row) for row in rows]

    def create_image_record(
        self,
        relative_path: str,
        thumbnail_path: str | None,
        component_id: int | None = None,
        is_primary: bool = False,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO images (component_id, path, thumbnail_path, is_primary)
                VALUES (?, ?, ?, ?)
                """,
                (component_id, relative_path, thumbnail_path, 1 if is_primary else 0),
            )
            image_id = cur.lastrowid
            if component_id and is_primary:
                conn.execute("UPDATE images SET is_primary = 0 WHERE component_id = ? AND id != ?", (component_id, image_id))
            row = self._fetchone(
                conn,
                "SELECT id, component_id, path, thumbnail_path, is_primary FROM images WHERE id = ?",
                (image_id,),
            )
        self.file_logger.write_backend("IMAGE", f"上传图片: 组件ID={component_id or '未绑定'}, 文件={relative_path}")
        return {
            "id": row["id"],
            "component_id": row["component_id"],
            "url": self._image_url(row["path"]),
            "thumbnail_url": self._image_url(row["thumbnail_path"]),
            "is_primary": bool(row["is_primary"]),
        }

    def delete_image(self, image_id: int) -> None:
        with self.connect() as conn:
            image = self._fetchone(
                conn,
                "SELECT id, component_id, path, thumbnail_path FROM images WHERE id = ?",
                (image_id,),
            )
            if not image:
                raise InventoryError("image not found")
            self._delete_image_files([image])
            conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        self.file_logger.write_backend("IMAGE", f"删除图片: ID={image_id}")

    def bind_nfc(self, box_id: int, uid: str) -> dict[str, Any]:
        uid = clean_text(uid).upper()
        if not uid:
            raise InventoryError("UID 不能为空")
        with self.connect() as conn:
            box = self._fetchone(conn, "SELECT id, name, nfc_uid FROM boxes WHERE id = ?", (box_id,))
            if not box:
                raise InventoryError("收纳盒不存在")
            existing = self._fetchone(conn, "SELECT id FROM boxes WHERE nfc_uid = ?", (uid,))
            if existing and existing["id"] != box_id:
                raise InventoryError("该 UID 已绑定其他收纳盒")
            conn.execute("UPDATE boxes SET nfc_uid = ? WHERE id = ?", (uid, box_id))
        self.file_logger.write_backend("NFC", f"绑定 NFC: 盒子ID={box_id}, UID={uid}")
        return {"box_id": box_id, "uid": uid}

    def get_nfc_payload(self, box_id: int, server_url: str) -> dict[str, Any]:
        box = self.get_box(box_id)
        url = f"{server_url.rstrip('/')}/box/{box_id}"
        text = f"{box['name']} | {box['rows']}x{box['cols']} | {box['occupied_count']}/{box['total_slots']}"
        self.file_logger.write_backend("NFC", f"生成 NDEF 内容: 盒子ID={box_id}")
        return {"box_id": box_id, "url": url, "text": text}

    def lookup_nfc(self, uid: str) -> dict[str, Any]:
        uid = clean_text(uid).upper()
        with self.connect() as conn:
            box = self._fetchone(conn, "SELECT id FROM boxes WHERE nfc_uid = ?", (uid,))
        if not box:
            raise InventoryError("no box is bound to this uid")
        return {
            "box": self.get_box(box["id"]),
            "grid": self.get_box_grid(box["id"]),
        }

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

    def bom_component_candidates(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT
                    c.id,
                    c.name,
                    c.model,
                    c.package,
                    c.nominal_value,
                    c.description,
                    c.quantity,
                    b.id AS box_id,
                    b.name AS box_name,
                    b.position_x,
                    b.position_y,
                    cp.row AS grid_row,
                    cp.col AS grid_col,
                    cp.label AS cell_label
                FROM components c
                LEFT JOIN boxes b ON b.id = c.box_id
                LEFT JOIN compartments cp ON cp.id = c.compartment_id
                ORDER BY c.quantity DESC, c.updated_at DESC
                """,
            )
            items = []
            for row in rows:
                item = dict(row)
                search_blob = " ".join(
                    [
                        clean_text(item.get("name")),
                        clean_text(item.get("model")),
                        clean_text(item.get("description")),
                        clean_text(item.get("nominal_value")),
                    ]
                ).lower()
                item["search_blob"] = search_blob
                item["normalized_package"] = normalize_footprint(item.get("package"))
                item["normalized_value"] = normalize_value(item.get("nominal_value") or item.get("name"))
                items.append(item)
            return items
