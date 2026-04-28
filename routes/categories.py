from __future__ import annotations

from flask import Blueprint, request

from routes._utils import success

categories_bp = Blueprint("categories", __name__)


@categories_bp.get("/api/categories")
def api_categories():
    from app import repo

    return success(repo.list_categories())


@categories_bp.post("/api/categories")
def api_create_category():
    from app import repo

    return success(repo.create_category(request.get_json(silent=True) or {}))
