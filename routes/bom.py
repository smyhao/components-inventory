from __future__ import annotations

from flask import Blueprint, request

from models import InventoryError
from routes._utils import excel_response, success
from services.bom_service import export_bom_xlsx, parse_bom_csv

bom_bp = Blueprint("bom", __name__)


@bom_bp.post("/api/bom/import")
def api_bom_import():
    from app import file_logger, repo

    file = request.files.get("file")
    if not file:
        raise InventoryError("missing csv file")
    candidates = repo.bom_component_candidates()
    result = parse_bom_csv(file.read(), file.filename or "bom", candidates)
    file_logger.write_backend(
        "SYSTEM",
        f"bom import finished: project={result['project_name']}, "
        f"total={result['total_types']}, matched={result['matched']}, unmatched={result['unmatched']}",
    )
    return success(result)


@bom_bp.post("/api/bom/consume")
def api_bom_consume():
    from app import repo

    payload = request.get_json(silent=True) or {}
    return success(repo.consume_bom(payload))


@bom_bp.post("/api/bom/export")
def api_bom_export():
    from app import file_logger

    payload = request.get_json(silent=True) or {}
    data = export_bom_xlsx(payload)
    file_logger.write_backend("SYSTEM", "export bom picklist")
    return excel_response(data, "bom_picklist.xlsx")
