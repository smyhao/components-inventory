from __future__ import annotations

from flask import Blueprint, request

from config import SERVER_URL
from models import clean_int, clean_text
from routes._utils import success

nfc_bp = Blueprint("nfc", __name__)


@nfc_bp.post("/api/nfc/bind")
def api_nfc_bind():
    from app import repo

    payload = request.get_json(silent=True) or {}
    box_id = clean_int(payload.get("box_id"))
    uid = clean_text(payload.get("uid"))
    return success(repo.bind_nfc(box_id, uid))


@nfc_bp.post("/api/nfc/write")
def api_nfc_write():
    from app import repo

    payload = request.get_json(silent=True) or {}
    box_id = clean_int(payload.get("box_id"))
    return success(repo.get_nfc_payload(box_id, SERVER_URL))


@nfc_bp.get("/api/nfc/lookup/<string:uid>")
def api_nfc_lookup(uid: str):
    from app import repo

    return success(repo.lookup_nfc(uid))


@nfc_bp.get("/api/box/<int:box_id>")
def api_nfc_box_data(box_id: int):
    from app import repo

    return success(repo.get_box_grid(box_id))
