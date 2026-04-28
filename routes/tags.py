from __future__ import annotations

import uuid
from pathlib import Path

from flask import Blueprint, request
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    DOCUMENT_FOLDER,
    UPLOAD_FOLDER,
)
from models import InventoryError, clean_optional_int, clean_text
from routes._utils import success

tags_bp = Blueprint("tags", __name__)


@tags_bp.post("/api/images/upload")
def api_upload_image():
    from app import repo

    file = request.files.get("file")
    if not file or not file.filename:
        raise InventoryError("missing image file")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise InventoryError("only jpg/png/gif/webp images are allowed")

    component_id = clean_optional_int(request.form.get("component_id"))
    is_primary = str(request.form.get("is_primary") or "").lower() in {"1", "true", "yes"}
    filename = f"{uuid.uuid4().hex}{ext}"
    thumb_filename = f"thumbnails/{uuid.uuid4().hex}{ext}"

    target = UPLOAD_FOLDER / filename
    thumb_target = UPLOAD_FOLDER / thumb_filename
    target.parent.mkdir(parents=True, exist_ok=True)
    thumb_target.parent.mkdir(parents=True, exist_ok=True)
    file.save(target)

    with Image.open(target) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((200, 200))
        image.save(thumb_target)

    return success(repo.create_image_record(filename, thumb_filename, component_id, is_primary))


@tags_bp.delete("/api/images/<int:image_id>")
def api_delete_image(image_id: int):
    from app import repo

    repo.delete_image(image_id)
    return success({"id": image_id})


@tags_bp.post("/api/documents/upload")
def api_upload_document():
    from app import repo

    file = request.files.get("file")
    if not file or not file.filename:
        raise InventoryError("missing document file")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise InventoryError("only pdf/doc/xls/ppt/txt/csv/zip documents are allowed")

    component_id = clean_optional_int(request.form.get("component_id"))
    original_name = clean_text(Path(file.filename).name) or secure_filename(file.filename) or f"document{ext}"
    stored_name = f"{uuid.uuid4().hex}{ext}"
    filename = f"documents/{stored_name}"
    target = DOCUMENT_FOLDER / stored_name
    target.parent.mkdir(parents=True, exist_ok=True)
    file.save(target)

    return success(
        repo.create_document_record(
            filename,
            original_name,
            file.mimetype,
            target.stat().st_size,
            component_id,
        )
    )


@tags_bp.delete("/api/documents/<int:document_id>")
def api_delete_document(document_id: int):
    from app import repo

    repo.delete_document(document_id)
    return success({"id": document_id})
