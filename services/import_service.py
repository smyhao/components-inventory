from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from models import (
    InventoryError,
    clean_int,
    clean_optional_int,
    clean_text,
)
from openpyxl import Workbook
from services._parsing import parse_csv_rows, parse_xlsx_rows, resolve_headers, workbook_bytes

COMPONENT_HEADER_ALIASES = {
    "name": {"名称", "元器件名称", "name"},
    "category": {"分类", "category"},
    "model": {"型号", "model"},
    "package": {"封装", "package", "footprint"},
    "nominal_value": {"标称值", "值", "value", "comment"},
    "voltage_rating": {"耐压", "voltage", "voltage_rating"},
    "current_rating": {"耐流", "电流", "current", "current_rating"},
    "power_rating": {"功率", "power", "power_rating"},
    "tolerance": {"精度", "tolerance"},
    "material_type": {"材质/类型", "材质", "类型", "material", "material_type"},
    "manufacturer": {"厂商", "manufacturer"},
    "quantity": {"数量", "qty", "quantity"},
    "box_name": {"盒子名称", "收纳盒", "box", "box_name"},
    "row": {"行", "row"},
    "col": {"列", "col", "column"},
    "description": {"描述", "备注", "description"},
    "tags": {"标签", "tags"},
}


def _split_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    return [item.strip() for item in re.split("[,，]", str(value)) if item.strip()]


def parse_component_import(
    file_bytes: bytes,
    filename: str,
    ensure_category_fn: Callable[[str], int | None],
    find_box_fn: Callable[[str], dict[str, Any] | None],
    find_compartment_fn: Callable[[int, int, int], dict[str, Any] | None],
    create_component_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    ext = Path(filename).suffix.lower()
    if ext == ".csv" or ext == ".txt":
        rows = parse_csv_rows(file_bytes)
        file_type = "csv"
    elif ext == ".xlsx":
        rows = parse_xlsx_rows(file_bytes)
        file_type = "xlsx"
    else:
        raise InventoryError("only csv and xlsx files are supported")

    if not rows:
        return {"success": 0, "failed": 0, "errors": [], "file_type": file_type}

    header_map = resolve_headers(list(rows[0]), COMPONENT_HEADER_ALIASES)
    if "name" not in header_map:
        raise InventoryError("missing required header: name")

    def cell(row: Any, field: str, default: Any = "") -> Any:
        index = header_map.get(field)
        if index is None:
            return default
        return row[index] if index < len(row) else default

    errors: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    for row_index, row in enumerate(rows[1:], start=2):
        if not any(value not in (None, "") for value in row):
            continue
        try:
            name = clean_text(cell(row, "name"))
            if not name:
                raise InventoryError("missing component name")

            category_name = clean_text(cell(row, "category"))
            category_id = ensure_category_fn(category_name) if category_name else None

            box = None
            compartment = None
            box_name = clean_text(cell(row, "box_name"))
            if box_name:
                box = find_box_fn(box_name)
                if not box:
                    raise InventoryError(f"box not found: {box_name}")
                grid_row = clean_optional_int(cell(row, "row"))
                grid_col = clean_optional_int(cell(row, "col"))
                if grid_row is not None and grid_col is not None:
                    compartment = find_compartment_fn(box["id"], grid_row, grid_col)
                    if not compartment:
                        raise InventoryError(f"compartment not found: {box_name} {grid_row}-{grid_col}")

            payload = {
                "name": name,
                "category_id": category_id,
                "model": clean_text(cell(row, "model")),
                "package": clean_text(cell(row, "package")),
                "nominal_value": clean_text(cell(row, "nominal_value")),
                "voltage_rating": clean_text(cell(row, "voltage_rating")),
                "current_rating": clean_text(cell(row, "current_rating")),
                "power_rating": clean_text(cell(row, "power_rating")),
                "tolerance": clean_text(cell(row, "tolerance")),
                "material_type": clean_text(cell(row, "material_type")),
                "manufacturer": clean_text(cell(row, "manufacturer")),
                "quantity": clean_int(cell(row, "quantity"), 0),
                "description": clean_text(cell(row, "description")),
                "tags": _split_tags(cell(row, "tags")) if "tags" in header_map else [],
                "box_id": box["id"] if box else None,
                "compartment_id": compartment["id"] if compartment else None,
                "cell_row": compartment["id"] if compartment else None,
                "cell_col": compartment["col"] if compartment else None,
            }
            create_component_fn(payload)
            success_count += 1
        except Exception as exc:
            failed_count += 1
            errors.append({"row": row_index, "reason": str(exc)})

    return {"success": success_count, "failed": failed_count, "errors": errors, "file_type": file_type}


def export_components_xlsx(list_components_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "components"
    sheet.append(
        [
            "名称",
            "分类",
            "型号",
            "封装",
            "标称值",
            "耐压",
            "耐流",
            "功率",
            "精度",
            "材质/类型",
            "厂商",
            "数量",
            "收纳盒",
            "行",
            "列",
            "描述",
            "标签",
        ]
    )

    page = 1
    while True:
        result = list_components_fn({"page": page, "page_size": 500})
        for item in result["items"]:
            sheet.append(
                [
                    item.get("name"),
                    item.get("category_name"),
                    item.get("model"),
                    item.get("package"),
                    item.get("nominal_value"),
                    item.get("voltage_rating"),
                    item.get("current_rating"),
                    item.get("power_rating"),
                    item.get("tolerance"),
                    item.get("material_type"),
                    item.get("manufacturer"),
                    item.get("quantity"),
                    item.get("box_name"),
                    item.get("grid_row"),
                    item.get("grid_col"),
                    item.get("description"),
                    ", ".join(item.get("tags") or []),
                ]
            )
        if len(result["items"]) < result["page_size"]:
            break
        page += 1
    return workbook_bytes(workbook)
