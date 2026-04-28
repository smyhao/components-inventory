from __future__ import annotations

from pathlib import Path

from flask import Blueprint, request

from config import ALLOWED_IMAGE_EXTENSIONS, UPLOAD_FOLDER
from models import InventoryError, clean_text
from routes._utils import success

map_bp = Blueprint("map", __name__)


def _get_map_background_url() -> str | None:
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        path = UPLOAD_FOLDER / f"map_background{ext}"
        if path.exists():
            return f"/uploads/map_background{ext}?v={int(path.stat().st_mtime)}"
    return None


@map_bp.get("/api/map")
def api_map():
    from app import repo

    data = repo.get_map_data()
    data["map_background"] = _get_map_background_url()
    return success(data)


@map_bp.post("/api/map/background")
def api_upload_map_background():
    from app import file_logger

    file = request.files.get("file")
    if not file or not file.filename:
        raise InventoryError("missing upload file")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise InventoryError("only image files are allowed")
    for old_ext in ALLOWED_IMAGE_EXTENSIONS:
        old_path = UPLOAD_FOLDER / f"map_background{old_ext}"
        if old_path.exists():
            old_path.unlink()
    target = UPLOAD_FOLDER / f"map_background{ext}"
    file.save(target)
    file_logger.write_backend("SYSTEM", f"upload map background: {target.name}")
    return success({"url": f"/uploads/map_background{ext}"})


@map_bp.delete("/api/map/background")
def api_delete_map_background():
    from app import file_logger

    deleted = False
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        path = UPLOAD_FOLDER / f"map_background{ext}"
        if path.exists():
            path.unlink()
            deleted = True
    if deleted:
        file_logger.write_backend("SYSTEM", "delete map background")
    return success({"deleted": deleted})


@map_bp.post("/api/map/search")
def api_map_search():
    from app import repo

    payload = request.get_json(silent=True) or {}
    keyword = clean_text(payload.get("keyword"))
    return success({"results": repo.search_map(keyword)})
