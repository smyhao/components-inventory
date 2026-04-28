from __future__ import annotations

from flask import Blueprint, request

from routes._utils import success

boxes_bp = Blueprint("boxes", __name__)


@boxes_bp.get("/api/boxes")
def api_boxes():
    from app import repo

    return success(repo.list_boxes())


@boxes_bp.post("/api/boxes")
def api_create_box():
    from app import repo

    return success(repo.create_box(request.get_json(silent=True) or {}))


@boxes_bp.get("/api/boxes/<int:box_id>")
def api_box_detail(box_id: int):
    from app import repo

    return success(repo.get_box(box_id))


@boxes_bp.put("/api/boxes/<int:box_id>")
def api_update_box(box_id: int):
    from app import repo

    return success(repo.update_box(box_id, request.get_json(silent=True) or {}))


@boxes_bp.delete("/api/boxes/<int:box_id>")
def api_delete_box(box_id: int):
    from app import repo

    repo.delete_box(box_id)
    return success({"id": box_id})


@boxes_bp.put("/api/boxes/<int:box_id>/layout")
def api_update_box_layout(box_id: int):
    from app import repo

    return success(repo.update_box_layout(box_id, request.get_json(silent=True) or {}))


@boxes_bp.get("/api/boxes/<int:box_id>/grid")
def api_box_grid(box_id: int):
    from app import repo

    return success(repo.get_box_grid(box_id))
