from __future__ import annotations

from flask import Blueprint, request

from config import SERVER_URL
from models import clean_int, clean_text
from routes._utils import success
from services.nfc_device_service import NfcDeviceService

nfc_bp = Blueprint("nfc", __name__)


def _device_service() -> NfcDeviceService:
    from app import file_logger, repo

    return NfcDeviceService(repo, file_logger)


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


@nfc_bp.get("/api/settings/nfc")
def api_nfc_settings():
    return success(_device_service().settings())


@nfc_bp.put("/api/settings/nfc")
def api_update_nfc_config():
    from app import repo

    return success(repo.update_nfc_config(request.get_json(silent=True) or {}))


@nfc_bp.post("/api/settings/nfc/devices")
def api_create_nfc_device():
    from app import repo

    return success(repo.create_nfc_device(request.get_json(silent=True) or {}))


@nfc_bp.put("/api/settings/nfc/devices/<int:device_id>")
def api_update_nfc_device(device_id: int):
    from app import repo

    return success(repo.update_nfc_device(device_id, request.get_json(silent=True) or {}))


@nfc_bp.delete("/api/settings/nfc/devices/<int:device_id>")
def api_delete_nfc_device(device_id: int):
    from app import repo

    repo.delete_nfc_device(device_id)
    return success({"id": device_id})


@nfc_bp.post("/api/settings/nfc/devices/<int:device_id>/test")
def api_test_nfc_device(device_id: int):
    return success(_device_service().test_device(device_id))


@nfc_bp.post("/api/settings/nfc/devices/<int:device_id>/sync")
def api_sync_nfc_device(device_id: int):
    return success(_device_service().sync_device(device_id))


@nfc_bp.post("/api/nfc/devices/<int:device_id>/read")
def api_read_nfc_device(device_id: int):
    return success(_device_service().read_device(device_id, request.get_json(silent=True) or {}))


@nfc_bp.post("/api/nfc/devices/<int:device_id>/write-box")
def api_write_box_nfc_device(device_id: int):
    return success(_device_service().write_box(device_id, request.get_json(silent=True) or {}))


@nfc_bp.post("/api/nfc/devices/<int:device_id>/write")
def api_write_custom_nfc_device(device_id: int):
    return success(_device_service().write_custom(device_id, request.get_json(silent=True) or {}))


@nfc_bp.post("/api/nfc/devices/<int:device_id>/erase")
def api_erase_nfc_device(device_id: int):
    return success(_device_service().erase_device(device_id, request.get_json(silent=True) or {}))


@nfc_bp.post("/api/nfc/devices/<int:device_id>/cancel")
def api_cancel_nfc_device(device_id: int):
    return success(_device_service().cancel_device(device_id, request.get_json(silent=True) or {}))
