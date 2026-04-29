from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from models import (
    InventoryError,
    build_spec_summary,
    clean_int,
    clean_optional_int,
    clean_text,
    normalize_footprint,
    normalize_merge_part,
    normalize_value,
    now_text,
    unique_strings,
)
from config import (
    COMPONENT_DETAIL_STOCK_LOGS,
    DEFAULT_PAGE_SIZE,
    LOW_STOCK_DISPLAY_LIMIT,
    MAX_COMPONENT_PAGE_SIZE,
    SEARCH_RESULTS_LIMIT,
)
from repositories._utils import append_stock_log, delete_files, file_url, image_url
from repositories.base import BaseRepository


class ComponentRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any, upload_folder: Path | None = None) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger
        self.upload_folder = Path(upload_folder) if upload_folder else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
                result[component_id] = image_url(row["path"]) or ""
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
                "url": image_url(row["path"]),
                "thumbnail_url": image_url(row["thumbnail_path"]),
                "is_primary": bool(row["is_primary"]),
            }
            for row in rows
        ]

    def _load_documents_for_component(self, conn: sqlite3.Connection, component_id: int) -> list[dict[str, Any]]:
        rows = self._fetchall(
            conn,
            """
            SELECT id, path, original_name, mime_type, file_size, created_at
            FROM documents
            WHERE component_id = ?
            ORDER BY id DESC
            """,
            (component_id,),
        )
        return [
            {
                "id": row["id"],
                "name": row["original_name"],
                "url": file_url(row["path"]),
                "mime_type": row["mime_type"],
                "file_size": row["file_size"],
                "created_at": row["created_at"],
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
        item["documents"] = []
        return item

    def _component_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        tags = payload.get("tags")
        if isinstance(tags, str):
            tags = re.split("[,，]", tags)
        images = payload.get("images")
        if images is not None and not isinstance(images, list):
            images = [images]
        documents = payload.get("documents")
        if documents is not None and not isinstance(documents, list):
            documents = [documents]
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
            "documents": documents,
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
            text = text[len("/uploads/"):]
        row = self._fetchone(
            conn,
            """
            SELECT id FROM images
            WHERE path = ? AND (component_id IS NULL OR component_id = ? OR ? IS NULL)
            """,
            (text, component_id, component_id),
        )
        return row["id"] if row else None

    def _extract_document_id(self, conn: sqlite3.Connection, ref: Any, component_id: int | None = None) -> int | None:
        if isinstance(ref, int):
            row = self._fetchone(
                conn,
                "SELECT id FROM documents WHERE id = ? AND (component_id IS NULL OR component_id = ? OR ? IS NULL)",
                (ref, component_id, component_id),
            )
            return row["id"] if row else None
        text = clean_text(ref)
        if not text:
            return None
        if text.isdigit():
            return self._extract_document_id(conn, int(text), component_id)
        if text.startswith("/uploads/"):
            text = text[len("/uploads/"):]
        row = self._fetchone(
            conn,
            """
            SELECT id FROM documents
            WHERE path = ? AND (component_id IS NULL OR component_id = ? OR ? IS NULL)
            """,
            (text, component_id, component_id),
        )
        return row["id"] if row else None

    def _sync_documents(
        self,
        conn: sqlite3.Connection,
        component_id: int,
        document_refs: list[Any] | None,
        *,
        delete_missing: bool,
    ) -> None:
        if document_refs is None:
            return
        desired_ids = unique_strings(document_refs)
        resolved_ids: list[int] = []
        for ref in desired_ids:
            document_id = self._extract_document_id(conn, ref, component_id)
            if document_id is not None:
                resolved_ids.append(document_id)

        current_rows = self._fetchall(
            conn,
            "SELECT id, path FROM documents WHERE component_id = ?",
            (component_id,),
        )
        current_ids = {row["id"] for row in current_rows}
        keep_ids = set(resolved_ids)

        if resolved_ids:
            placeholders = ",".join("?" for _ in resolved_ids)
            conn.execute(
                f"UPDATE documents SET component_id = ? WHERE id IN ({placeholders})",
                tuple([component_id] + resolved_ids),
            )

        if delete_missing:
            remove_ids = current_ids - keep_ids
            if remove_ids:
                placeholders = ",".join("?" for _ in remove_ids)
                remove_rows = self._fetchall(
                    conn,
                    f"SELECT id, path FROM documents WHERE id IN ({placeholders})",
                    tuple(remove_ids),
                )
                delete_files(self.upload_folder, remove_rows, ("path",))
                conn.execute(
                    f"DELETE FROM documents WHERE id IN ({placeholders})",
                    tuple(remove_ids),
                )

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
                delete_files(self.upload_folder, remove_rows, ("path", "thumbnail_path"))
                conn.execute(
                    f"DELETE FROM images WHERE id IN ({placeholders})",
                    tuple(remove_ids),
                )

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def list_components(self, filters: dict[str, Any]) -> dict[str, Any]:
        page = max(1, clean_int(filters.get("page"), 1))
        page_size = clean_int(filters.get("page_size"), DEFAULT_PAGE_SIZE)
        page_size = DEFAULT_PAGE_SIZE if page_size <= 0 else min(page_size, MAX_COMPONENT_PAGE_SIZE)
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
            item["documents"] = self._load_documents_for_component(conn, component_id)
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
                    LIMIT ?
                    """,
                    (component_id, COMPONENT_DETAIL_STOCK_LOGS),
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
                if prepared["documents"] is not None:
                    self._sync_documents(conn, merge_target["id"], prepared["documents"], delete_missing=False)
                if prepared["quantity"] != 0:
                    append_stock_log(conn, merge_target["id"], prepared["quantity"], new_quantity, "initial", reason_text)
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
            if prepared["documents"] is not None:
                self._sync_documents(conn, component_id, prepared["documents"], delete_missing=False)
            if prepared["quantity"] != 0:
                append_stock_log(conn, component_id, prepared["quantity"], prepared["quantity"], "initial", reason_text)

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
                    tags = re.split("[,，]", clean_text(payload.get("tagsInput")))
                self._upsert_tags(conn, component_id, unique_strings(tags or []))
            if "images" in payload:
                self._sync_images(conn, component_id, payload.get("images"), delete_missing=True)
            if "documents" in payload:
                self._sync_documents(conn, component_id, payload.get("documents"), delete_missing=True)

            quantity_diff = prepared["quantity"] - current["quantity"]
            if quantity_diff != 0:
                append_stock_log(conn, component_id, quantity_diff, prepared["quantity"], "adjust", "编辑调整数量")

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
            delete_files(self.upload_folder, images, ("path", "thumbnail_path"))
            documents = self._fetchall(
                conn,
                "SELECT id, path FROM documents WHERE component_id = ?",
                (component_id,),
            )
            delete_files(self.upload_folder, documents, ("path",))
            conn.execute("DELETE FROM components WHERE id = ?", (component_id,))
        self.file_logger.write_backend("COMPONENT", f"删除元器件: ID={component_id}, 名称={component['name']}")

    # ------------------------------------------------------------------
    # Stats & map
    # ------------------------------------------------------------------

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
                LIMIT ?
                """,
                (LOW_STOCK_DISPLAY_LIMIT,),
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
        return {"boxes": self.list_boxes(), "cabinets": self.list_cabinets()}

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
                LIMIT ?
                """,
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", SEARCH_RESULTS_LIMIT),
            )
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # BOM candidates
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Self-contained helpers for import (also in box_repo / category_repo)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Box / cabinet list helpers used by get_map_data
    # ------------------------------------------------------------------

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

    def list_cabinets(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = self._fetchall(
                conn,
                """
                SELECT
                    cb.*,
                    COALESCE(box_stats.box_count, 0) AS box_count,
                    COALESCE(box_stats.total_slots, 0) AS total_slots,
                    COALESCE(component_stats.used_slots, 0) AS used_slots,
                    COALESCE(component_stats.total_quantity, 0) AS total_quantity
                FROM cabinets cb
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
            return [dict(row) for row in rows]
