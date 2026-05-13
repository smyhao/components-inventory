from __future__ import annotations

from flask import Blueprint, request

from routes._utils import success

model_appearance_bp = Blueprint("model_appearance", __name__)


@model_appearance_bp.get("/api/model-assets")
def api_model_assets():
    from app import repo

    return success(repo.list_model_assets())


@model_appearance_bp.post("/api/model-assets/upload")
def api_upload_model_asset():
    from app import repo

    return success(repo.create_model_asset_from_upload(request.files.get("file"), request.form.to_dict()))


@model_appearance_bp.put("/api/model-assets/<int:asset_id>")
def api_update_model_asset(asset_id: int):
    from app import repo

    return success(repo.update_model_asset(asset_id, request.get_json(silent=True) or {}))


@model_appearance_bp.delete("/api/model-assets/<int:asset_id>")
def api_delete_model_asset(asset_id: int):
    from app import repo

    repo.delete_model_asset(asset_id)
    return success({"id": asset_id})


@model_appearance_bp.get("/api/cabinet-templates")
def api_cabinet_templates():
    from app import repo

    return success(repo.list_cabinet_templates())


@model_appearance_bp.post("/api/cabinet-templates")
def api_create_cabinet_template():
    from app import repo

    return success(repo.create_cabinet_template(request.get_json(silent=True) or {}))


@model_appearance_bp.put("/api/cabinet-templates/<int:template_id>")
def api_update_cabinet_template(template_id: int):
    from app import repo

    return success(repo.update_cabinet_template(template_id, request.get_json(silent=True) or {}))


@model_appearance_bp.delete("/api/cabinet-templates/<int:template_id>")
def api_delete_cabinet_template(template_id: int):
    from app import repo

    repo.delete_cabinet_template(template_id)
    return success({"id": template_id})


@model_appearance_bp.get("/api/box-templates")
def api_box_templates():
    from app import repo

    return success(repo.list_box_templates())


@model_appearance_bp.post("/api/box-templates")
def api_create_box_template():
    from app import repo

    return success(repo.create_box_template(request.get_json(silent=True) or {}))


@model_appearance_bp.put("/api/box-templates/<int:template_id>")
def api_update_box_template(template_id: int):
    from app import repo

    return success(repo.update_box_template(template_id, request.get_json(silent=True) or {}))


@model_appearance_bp.delete("/api/box-templates/<int:template_id>")
def api_delete_box_template(template_id: int):
    from app import repo

    repo.delete_box_template(template_id)
    return success({"id": template_id})
