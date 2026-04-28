from __future__ import annotations

from flask import Blueprint, request

from models import clean_int
from routes._utils import success

stock_bp = Blueprint("stock", __name__)


@stock_bp.post("/api/stock/in")
def api_stock_in():
    from app import repo

    return success(repo.record_stock("in", request.get_json(silent=True) or {}))


@stock_bp.post("/api/stock/out")
def api_stock_out():
    from app import repo

    return success(repo.record_stock("out", request.get_json(silent=True) or {}))


@stock_bp.get("/api/stock/logs/<int:component_id>")
def api_stock_logs(component_id: int):
    from app import repo

    page = clean_int(request.args.get("page"), 1)
    page_size = clean_int(request.args.get("page_size"), 20)
    return success(repo.list_stock_logs(component_id, page, page_size))


@stock_bp.get("/api/stats")
def api_stats():
    from app import repo

    return success(repo.get_stats())
