from __future__ import annotations

from flask import Blueprint, Response, request, send_from_directory

from config import STATIC_DIR, UPLOAD_FOLDER
from models import clean_int
from services.label_service import parse_component_ids, qr_label_print_page

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def index_page():
    return send_from_directory(STATIC_DIR, "index.html")


@pages_bp.get("/favicon.ico")
def favicon():
    return Response(status=204)


@pages_bp.get("/box/<int:box_id>")
def nfc_box_page(box_id: int):
    return send_from_directory(STATIC_DIR, "box.html")


@pages_bp.get("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_FOLDER, filename)


@pages_bp.get("/components/qr-labels")
def component_qr_labels_page():
    from app import repo

    ids = parse_component_ids(request.args.get("ids", ""))
    if ids:
        components = [repo.get_component(component_id) for component_id in ids]
    else:
        filters = request.args.to_dict()
        filters["page"] = clean_int(filters.get("page"), 1)
        filters["page_size"] = clean_int(filters.get("page_size"), 500)
        components = repo.list_components(filters)["items"]
    return Response(qr_label_print_page(components), mimetype="text/html")
