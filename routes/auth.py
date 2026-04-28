from __future__ import annotations

import hmac
from typing import Any

from flask import Blueprint, request

from config import API_TOKEN, API_TOKEN_REQUIRE_ALL
from models import InventoryError
from routes._utils import failure, success

auth_bp = Blueprint("auth", __name__)


def _bearer_token() -> str:
    value = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if value.startswith(prefix):
        return value[len(prefix):].strip()
    return ""


def _api_token_identity(token: str) -> dict[str, Any] | None:
    from app import repo

    if API_TOKEN and hmac.compare_digest(token, API_TOKEN):
        return {"id": None, "name": "env:API_TOKEN"}
    if token:
        return repo.validate_api_token(token)
    return None


@auth_bp.before_app_request
def require_api_token_for_automation():
    if not API_TOKEN or not request.path.startswith("/api"):
        if not request.path.startswith("/api"):
            return None
        from app import repo

        source = request.headers.get("X-Inventory-Source", "")
        should_require_generated = source == "inventory-cli" and repo.has_api_tokens()
        if not should_require_generated:
            return None
        identity = _api_token_identity(_bearer_token())
        if not identity:
            return failure("authentication failed", 401)
        request.inventory_token = identity
        return None
    source = request.headers.get("X-Inventory-Source", "")
    should_require = API_TOKEN_REQUIRE_ALL or source == "inventory-cli"
    if should_require:
        identity = _api_token_identity(_bearer_token())
        if not identity:
            return failure("authentication failed", 401)
        request.inventory_token = identity
    return None


@auth_bp.after_app_request
def log_automation_write(response):
    from app import file_logger

    identity = getattr(request, "inventory_token", None)
    if (
        identity
        and request.path.startswith("/api")
        and request.method in {"POST", "PUT", "DELETE"}
        and response.status_code < 500
    ):
        actor = request.headers.get("X-Inventory-Actor") or identity.get("name") or "automation"
        file_logger.write_backend(
            "SYSTEM",
            f"api write: token={identity.get('name')}, actor={actor}, method={request.method}, path={request.path}, status={response.status_code}",
        )
    return response


@auth_bp.get("/api/settings/tokens")
def api_settings_tokens():
    from app import repo

    return success(repo.list_api_tokens())


@auth_bp.post("/api/settings/tokens")
def api_settings_create_token():
    from app import repo

    return success(repo.create_api_token(request.get_json(silent=True) or {}))


@auth_bp.delete("/api/settings/tokens/<int:token_id>")
def api_settings_delete_token(token_id: int):
    from app import repo

    repo.delete_api_token(token_id)
    return success({"id": token_id})


@auth_bp.post("/api/frontend/log")
def api_frontend_log():
    from app import file_logger

    payload = request.get_json(silent=True) or {}
    logs = payload.get("logs")
    if not isinstance(logs, list):
        raise InventoryError("logs must be a list")
    if len(logs) > 100:
        raise InventoryError("at most 100 logs per request")
    written = file_logger.write_frontend_batch(logs)
    return success({"written": written})
