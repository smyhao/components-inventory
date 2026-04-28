from __future__ import annotations

from flask import Blueprint, request

from routes._utils import success

cabinets_bp = Blueprint("cabinets", __name__)


@cabinets_bp.get("/api/cabinets")
def api_cabinets():
    from app import repo

    return success(repo.list_cabinets())


@cabinets_bp.post("/api/cabinets")
def api_create_cabinet():
    from app import repo

    return success(repo.create_cabinet(request.get_json(silent=True) or {}))


@cabinets_bp.get("/api/cabinets/<int:cabinet_id>")
def api_cabinet_detail(cabinet_id: int):
    from app import repo

    return success(repo.get_cabinet(cabinet_id))


@cabinets_bp.put("/api/cabinets/<int:cabinet_id>")
def api_update_cabinet(cabinet_id: int):
    from app import repo

    return success(repo.update_cabinet(cabinet_id, request.get_json(silent=True) or {}))


@cabinets_bp.delete("/api/cabinets/<int:cabinet_id>")
def api_delete_cabinet(cabinet_id: int):
    from app import repo

    repo.delete_cabinet(cabinet_id)
    return success({"id": cabinet_id})


@cabinets_bp.put("/api/cabinets/<int:cabinet_id>/layout")
def api_update_cabinet_layout(cabinet_id: int):
    from app import repo

    return success(repo.update_cabinet_layout(cabinet_id, request.get_json(silent=True) or {}))
