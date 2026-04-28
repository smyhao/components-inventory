from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from models import clean_int, clean_text, normalize_footprint, normalize_value
from openpyxl import Workbook
from services._parsing import decode_csv_bytes, resolve_headers, workbook_bytes

BOM_HEADER_ALIASES = {
    "comment": {"comment", "注释", "值", "partname", "part name", "comment/value"},
    "designator": {"designator", "位号", "reference", "ref"},
    "footprint": {"footprint", "封装", "package"},
    "quantity": {"quantity", "数量", "qty"},
    "value": {"value", "参数"},
    "manufacturer_part": {"manufacturerpart", "制造商零件", "mpn", "partnumber", "part number"},
    "manufacturer": {"manufacturer", "制造商"},
    "supplier_part": {"supplierpart", "供应商零件", "lcscpart"},
    "supplier": {"supplier", "供应商"},
}


def _value_score(candidate: dict[str, Any], normalized_query: str, raw_query: str) -> int:
    if not normalized_query and not raw_query:
        return 0
    if normalized_query and candidate["normalized_value"] == normalized_query:
        return 4
    if normalized_query and normalized_query in candidate["search_blob"]:
        return 3
    if normalized_query and normalized_query in candidate["normalized_value"]:
        return 2
    if raw_query and raw_query.lower() in candidate["search_blob"]:
        return 1
    return 0


def parse_bom_csv(file_bytes: bytes, filename: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    text = decode_csv_bytes(file_bytes)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel_tab if "\t" in sample else csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    project_name = Path(filename or "bom").stem
    if not rows:
        return {"project_name": project_name, "items": []}

    header_map = resolve_headers(rows[0], BOM_HEADER_ALIASES)
    items: list[dict[str, Any]] = []
    matched_count = 0

    for row in rows[1:]:
        if not any(clean_text(value) for value in row):
            continue
        comment = clean_text(row[header_map["comment"]]) if "comment" in header_map else ""
        designator = clean_text(row[header_map["designator"]]) if "designator" in header_map else ""
        footprint = clean_text(row[header_map["footprint"]]) if "footprint" in header_map else ""
        quantity_needed = clean_int(row[header_map["quantity"]], 1) if "quantity" in header_map else 1
        value = clean_text(row[header_map["value"]]) if "value" in header_map else ""

        raw_query = value or comment
        normalized_query = normalize_value(raw_query)
        normalized_package = normalize_footprint(footprint)

        ranked_exact = []
        ranked_fallback = []
        for candidate in candidates:
            score = _value_score(candidate, normalized_query, raw_query)
            if score <= 0:
                continue
            if normalized_package and candidate["normalized_package"] == normalized_package:
                ranked_exact.append((score, candidate["quantity"], candidate))
            else:
                ranked_fallback.append((score, candidate["quantity"], candidate))

        ranked_exact.sort(key=lambda item: (item[0], item[1]), reverse=True)
        ranked_fallback.sort(key=lambda item: (item[0], item[1]), reverse=True)

        matched = None
        match_level = None
        if ranked_exact:
            matched = ranked_exact[0][2]
            match_level = "footprint_value"
        elif ranked_fallback:
            matched = ranked_fallback[0][2]
            match_level = "value_only"

        matched_payload = None
        if matched:
            matched_count += 1
            matched_payload = {
                "id": matched["id"],
                "name": matched["name"],
                "model": matched["model"],
                "package": matched["package"],
                "quantity": matched["quantity"],
                "box_id": matched["box_id"],
                "box_name": matched["box_name"],
                "cell_label": matched["cell_label"],
                "row": matched["grid_row"],
                "col": matched["grid_col"],
                "position_x": matched["position_x"],
                "position_y": matched["position_y"],
            }

        items.append(
            {
                "designator": designator,
                "designators": [part.strip() for part in designator.split(",") if part.strip()],
                "comment": comment or value,
                "footprint": footprint,
                "quantity_needed": quantity_needed,
                "matched": matched_payload,
                "match_level": match_level,
            }
        )

    return {
        "project_name": project_name,
        "total_types": len(items),
        "matched": matched_count,
        "unmatched": len(items) - matched_count,
        "items": items,
    }


def export_bom_xlsx(payload: dict[str, Any]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "picklist"
    sheet.append(
        [
            "BOM位号",
            "元器件值",
            "封装",
            "需要数量",
            "库存数量",
            "盒子",
            "格子位置",
            "状态",
        ]
    )

    for item in payload.get("items") or []:
        matched = item.get("matched") or {}
        quantity_needed = clean_int(item.get("quantity_needed"), 0)
        stock_quantity = clean_int(matched.get("quantity"), 0)
        if not item.get("match_level"):
            status = "unmatched"
        elif stock_quantity < quantity_needed:
            status = "shortage"
        else:
            status = "ok"
        sheet.append(
            [
                item.get("designator"),
                item.get("comment"),
                item.get("footprint"),
                quantity_needed,
                stock_quantity if matched else "",
                matched.get("box_name"),
                matched.get("cell_label"),
                status,
            ]
        )
    return workbook_bytes(workbook)
