from __future__ import annotations

from flask import Blueprint, Response, request

from config import SERVER_URL
from models import InventoryError
from routes._utils import excel_response, success
from services.import_service import export_components_xlsx, parse_component_import
from services.label_service import component_qr_svg

components_bp = Blueprint("components", __name__)


@components_bp.get("/api/components")
def api_components():
    from app import repo

    return success(repo.list_components(request.args.to_dict()))


@components_bp.post("/api/components")
def api_create_component():
    from app import repo

    return success(repo.create_component(request.get_json(silent=True) or {}))


@components_bp.get("/api/components/<int:component_id>")
def api_component_detail(component_id: int):
    from app import repo

    return success(repo.get_component(component_id))


@components_bp.put("/api/components/<int:component_id>")
def api_update_component(component_id: int):
    from app import repo

    return success(repo.update_component(component_id, request.get_json(silent=True) or {}))


@components_bp.delete("/api/components/<int:component_id>")
def api_delete_component(component_id: int):
    from app import repo

    repo.delete_component(component_id)
    return success({"id": component_id})


@components_bp.get("/api/components/<int:component_id>/qr.svg")
def api_component_qr_svg(component_id: int):
    from app import repo
    from flask import request as req

    repo.get_component(component_id)
    base_url = req.url_root or SERVER_URL
    return Response(
        component_qr_svg(component_id, base_url),
        mimetype="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@components_bp.post("/api/components/import")
def api_import_components():
    from app import file_logger, repo

    file = request.files.get("file")
    if not file:
        raise InventoryError("missing upload file")
    result = parse_component_import(
        file.read(),
        file.filename or "",
        repo.ensure_category_by_name,
        repo.find_box_by_name,
        repo.find_compartment_by_coordinates,
        lambda payload: repo.create_component(payload, source="import"),
    )
    file_logger.write_backend(
        "COMPONENT",
        f"component {result['file_type']} import finished: "
        f"success={result['success']}, failed={result['failed']}",
    )
    return success(result)


@components_bp.get("/api/components/export")
def api_export_components():
    from app import file_logger, repo

    data = export_components_xlsx(repo.list_components)
    file_logger.write_backend("COMPONENT", "export components excel")
    return excel_response(data, "components_export.xlsx")
