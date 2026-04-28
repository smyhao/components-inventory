from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from config import MAX_STOCK_LOG_PAGE_SIZE
from models import InventoryError, clean_int, clean_optional_int, clean_text, now_text
from repositories._utils import append_stock_log
from repositories.base import BaseRepository


class StockRepository(BaseRepository):
    def __init__(self, db_path: Path, file_logger: Any) -> None:
        super().__init__(db_path)
        self.file_logger = file_logger

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
            append_stock_log(conn, component_id, delta, quantity_after, action, reason)

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
                append_stock_log(
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
        page_size = min(max(1, page_size), MAX_STOCK_LOG_PAGE_SIZE)
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
