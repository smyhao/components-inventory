from __future__ import annotations

# 本文件属于路由层，仅负责 LED API 的请求解析、服务调用和统一响应封装。

from flask import Blueprint, request

from routes._utils import success
from services.led_service import LedService

led_bp = Blueprint("led", __name__)


def _service() -> LedService:
    from app import file_logger, repo

    return LedService(repo, file_logger)


@led_bp.get("/api/settings/led")
def api_led_settings():
    return success(_service().settings())


@led_bp.put("/api/settings/led")
def api_update_led_config():
    from app import repo

    return success(repo.update_led_config(request.get_json(silent=True) or {}))


@led_bp.post("/api/settings/led/devices")
def api_create_led_device():
    from app import repo

    return success(repo.create_led_device(request.get_json(silent=True) or {}))


@led_bp.put("/api/settings/led/devices/<int:device_id>")
def api_update_led_device(device_id: int):
    from app import repo

    return success(repo.update_led_device(device_id, request.get_json(silent=True) or {}))


@led_bp.delete("/api/settings/led/devices/<int:device_id>")
def api_delete_led_device(device_id: int):
    from app import repo

    repo.delete_led_device(device_id)
    return success({"id": device_id})


@led_bp.post("/api/settings/led/devices/<int:device_id>/test")
def api_test_led_device(device_id: int):
    return success(_service().test_device(device_id))


@led_bp.post("/api/settings/led/devices/<int:device_id>/sync")
def api_sync_device_strips(device_id: int):
    return success(_service().sync_device_strips(device_id))


@led_bp.post("/api/settings/led/strips")
def api_create_led_strip():
    return success(_service().create_strip_with_sync(request.get_json(silent=True) or {}))


@led_bp.put("/api/settings/led/strips/<int:strip_id>")
def api_update_led_strip(strip_id: int):
    return success(_service().update_strip_with_sync(strip_id, request.get_json(silent=True) or {}))


@led_bp.delete("/api/settings/led/strips/<int:strip_id>")
def api_delete_led_strip(strip_id: int):
    return success(_service().delete_strip_with_sync(strip_id))


@led_bp.put("/api/settings/led/mappings")
def api_save_led_mappings():
    from app import repo

    payload = request.get_json(silent=True) or {}
    return success(repo.save_led_mappings(payload.get("mappings") or []))


@led_bp.post("/api/led/locate/box/<int:box_id>")
def api_locate_led_box(box_id: int):
    return success(_service().locate_box(box_id))


@led_bp.post("/api/led/locate/component/<int:component_id>")
def api_locate_led_component(component_id: int):
    return success(_service().locate_component(component_id))


@led_bp.post("/api/led/locate/bom")
def api_locate_led_bom():
    payload = request.get_json(silent=True) or {}
    return success(_service().locate_bom(payload.get("box_ids") or []))


@led_bp.post("/api/led/clear")
def api_clear_led():
    return success(_service().clear_all())


@led_bp.post("/api/led/clear/<int:device_id>")
def api_clear_led_device(device_id: int):
    return success(_service().clear_device(device_id))
