from __future__ import annotations

# 本文件提供仓储外观和共享清洗工具，路由与服务层通过 InventoryRepository 访问各子仓储。

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_optional_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_int(value: Any, default: int = 0) -> int:
    parsed = clean_optional_int(value)
    return default if parsed is None else parsed


def clean_color(value: Any, default: str = "#84b59b") -> str:
    text = clean_text(value)
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.lower()
    return default


def unique_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def build_spec_summary(component: dict[str, Any]) -> str:
    parts = [
        clean_text(component.get("nominal_value")),
        clean_text(component.get("voltage_rating")),
        clean_text(component.get("current_rating")),
        clean_text(component.get("power_rating")),
        clean_text(component.get("tolerance")),
        clean_text(component.get("material_type")),
    ]
    return " / ".join([part for part in parts if part])


def normalize_merge_part(value: Any) -> str:
    return clean_text(value).lower()


def normalize_footprint(value: Any) -> str:
    text = clean_text(value).lower().replace("_", "").replace("-", "").replace(" ", "")
    if not text:
        return ""
    match = re.search(r"(\d{4})", text)
    if match:
        return match.group(1)
    return text


def normalize_value(value: Any) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    text = text.replace("μ", "u").replace("Ω", "ohm").replace("ω", "ohm").replace("欧", "ohm")
    text = text.replace("Ω", "ohm").replace(" ", "")
    text = text.replace("uf", "uF").replace("nf", "nF").replace("pf", "pF")
    text = text.lower()
    return text


class InventoryError(Exception):
    pass


class InventoryRepository:
    def __init__(self, db_path: Path, file_logger: Any, upload_folder: Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.file_logger = file_logger
        self.upload_folder = Path(upload_folder) if upload_folder else None

        from repositories.token_repo import TokenRepository
        from repositories.category_repo import CategoryRepository
        from repositories.cabinet_repo import CabinetRepository
        from repositories.box_repo import BoxRepository
        from repositories.component_repo import ComponentRepository
        from repositories.stock_repo import StockRepository
        from repositories.document_repo import DocumentRepository
        from repositories.nfc_repo import NfcRepository
        from repositories.nfc_device_repository import NfcDeviceRepository
        from repositories.led_repository import LedRepository
        from repositories.model_appearance_repo import ModelAppearanceRepository

        self._token_repo = TokenRepository(db_path, file_logger)
        self._category_repo = CategoryRepository(db_path, file_logger)
        self._cabinet_repo = CabinetRepository(db_path, file_logger)
        self._box_repo = BoxRepository(db_path, file_logger)
        self._component_repo = ComponentRepository(db_path, file_logger, upload_folder)
        self._stock_repo = StockRepository(db_path, file_logger)
        self._document_repo = DocumentRepository(db_path, file_logger, upload_folder)
        self._nfc_repo = NfcRepository(db_path, file_logger, self._box_repo)
        self._nfc_device_repo = NfcDeviceRepository(db_path, file_logger)
        self._led_repo = LedRepository(db_path, file_logger)
        self._model_appearance_repo = ModelAppearanceRepository(db_path, file_logger, upload_folder)

    # --- Token ---
    def has_api_tokens(self) -> bool:
        return self._token_repo.has_api_tokens()

    def validate_api_token(self, token: str) -> dict[str, Any] | None:
        return self._token_repo.validate_api_token(token)

    def list_api_tokens(self) -> list[dict[str, Any]]:
        return self._token_repo.list_api_tokens()

    def create_api_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._token_repo.create_api_token(payload)

    def delete_api_token(self, token_id: int) -> None:
        self._token_repo.delete_api_token(token_id)

    # --- Category ---
    def list_categories(self) -> list[dict[str, Any]]:
        return self._category_repo.list_categories()

    def create_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._category_repo.create_category(payload)

    def ensure_category_by_name(self, name: str) -> int | None:
        return self._category_repo.ensure_category_by_name(name)

    # --- Cabinet ---
    def list_cabinets(self) -> list[dict[str, Any]]:
        return self._cabinet_repo.list_cabinets()

    def get_cabinet(self, cabinet_id: int) -> dict[str, Any]:
        return self._cabinet_repo.get_cabinet(cabinet_id)

    def create_cabinet(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._cabinet_repo.create_cabinet(payload)

    def update_cabinet(self, cabinet_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._cabinet_repo.update_cabinet(cabinet_id, payload)

    def delete_cabinet(self, cabinet_id: int) -> None:
        self._cabinet_repo.delete_cabinet(cabinet_id)

    def update_cabinet_layout(self, cabinet_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._cabinet_repo.update_cabinet_layout(cabinet_id, payload)

    # --- 3D appearance model library ---
    def list_model_assets(self) -> list[dict[str, Any]]:
        return self._model_appearance_repo.list_model_assets()

    def create_model_asset_from_upload(self, file: Any, payload: dict[str, Any]) -> dict[str, Any]:
        return self._model_appearance_repo.create_model_asset_from_upload(file, payload)

    def update_model_asset(self, asset_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._model_appearance_repo.update_model_asset(asset_id, payload)

    def delete_model_asset(self, asset_id: int) -> None:
        self._model_appearance_repo.delete_model_asset(asset_id)

    def list_cabinet_templates(self) -> list[dict[str, Any]]:
        return self._model_appearance_repo.list_cabinet_templates()

    def create_cabinet_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._model_appearance_repo.create_cabinet_template(payload)

    def update_cabinet_template(self, template_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._model_appearance_repo.update_cabinet_template(template_id, payload)

    def delete_cabinet_template(self, template_id: int) -> None:
        self._model_appearance_repo.delete_cabinet_template(template_id)

    def list_box_templates(self) -> list[dict[str, Any]]:
        return self._model_appearance_repo.list_box_templates()

    def create_box_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._model_appearance_repo.create_box_template(payload)

    def update_box_template(self, template_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._model_appearance_repo.update_box_template(template_id, payload)

    def delete_box_template(self, template_id: int) -> None:
        self._model_appearance_repo.delete_box_template(template_id)

    # --- Box ---
    def list_boxes(self) -> list[dict[str, Any]]:
        return self._box_repo.list_boxes()

    def get_box(self, box_id: int) -> dict[str, Any]:
        return self._box_repo.get_box(box_id)

    def create_box(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._box_repo.create_box(payload)

    def update_box(self, box_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._box_repo.update_box(box_id, payload)

    def delete_box(self, box_id: int) -> None:
        self._box_repo.delete_box(box_id)

    def update_box_layout(self, box_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._box_repo.update_box_layout(box_id, payload)

    def get_box_grid(self, box_id: int) -> dict[str, Any]:
        return self._box_repo.get_box_grid(box_id)

    def find_box_by_name(self, name: str) -> dict[str, Any] | None:
        return self._box_repo.find_box_by_name(name)

    def find_compartment_by_coordinates(self, box_id: int, row: int, col: int) -> dict[str, Any] | None:
        return self._box_repo.find_compartment_by_coordinates(box_id, row, col)

    # --- Component ---
    def list_components(self, filters: dict[str, Any]) -> dict[str, Any]:
        return self._component_repo.list_components(filters)

    def get_component(self, component_id: int) -> dict[str, Any]:
        return self._component_repo.get_component(component_id)

    def create_component(self, payload: dict[str, Any], *, source: str = "manual") -> dict[str, Any]:
        return self._component_repo.create_component(payload, source=source)

    def update_component(self, component_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._component_repo.update_component(component_id, payload)

    def delete_component(self, component_id: int) -> None:
        self._component_repo.delete_component(component_id)

    def get_stats(self) -> dict[str, Any]:
        return self._component_repo.get_stats()

    def get_map_data(self) -> dict[str, Any]:
        # 3D 外观模板属于柜子/收纳盒本体属性，地图直接复用对应仓储可避免旧地图查询遗漏模板信息。
        return {"boxes": self._box_repo.list_boxes(), "cabinets": self._cabinet_repo.list_cabinets()}

    def search_map(self, keyword: str) -> list[dict[str, Any]]:
        return self._component_repo.search_map(keyword)

    def bom_component_candidates(self) -> list[dict[str, Any]]:
        return self._component_repo.bom_component_candidates()

    # --- Stock ---
    def record_stock(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._stock_repo.record_stock(action, payload)

    def consume_bom(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._stock_repo.consume_bom(payload)

    def list_stock_logs(self, component_id: int, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        return self._stock_repo.list_stock_logs(component_id, page, page_size)

    # --- Image & Document ---
    def create_image_record(
        self,
        relative_path: str,
        thumbnail_path: str | None,
        component_id: int | None = None,
        is_primary: bool = False,
    ) -> dict[str, Any]:
        return self._document_repo.create_image_record(relative_path, thumbnail_path, component_id, is_primary)

    def delete_image(self, image_id: int) -> None:
        self._document_repo.delete_image(image_id)

    def create_document_record(
        self,
        relative_path: str,
        original_name: str,
        mime_type: str | None,
        file_size: int,
        component_id: int | None = None,
    ) -> dict[str, Any]:
        return self._document_repo.create_document_record(relative_path, original_name, mime_type, file_size, component_id)

    def delete_document(self, document_id: int) -> None:
        self._document_repo.delete_document(document_id)

    # --- NFC ---
    def bind_nfc(self, box_id: int, uid: str) -> dict[str, Any]:
        return self._nfc_repo.bind_nfc(box_id, uid)

    def get_nfc_payload(self, box_id: int, server_url: str) -> dict[str, Any]:
        return self._nfc_repo.get_nfc_payload(box_id, server_url)

    def lookup_nfc(self, uid: str) -> dict[str, Any]:
        return self._nfc_repo.lookup_nfc(uid)

    def lookup_nfc_summary(self, uid: str) -> dict[str, Any]:
        return self._nfc_repo.lookup_nfc_summary(uid)

    def get_nfc_config(self) -> dict[str, Any]:
        return self._nfc_device_repo.get_nfc_config()

    def update_nfc_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._nfc_device_repo.update_nfc_config(payload)

    def list_nfc_devices(self) -> list[dict[str, Any]]:
        return self._nfc_device_repo.list_nfc_devices()

    def get_nfc_device(self, device_id: int) -> dict[str, Any] | None:
        return self._nfc_device_repo.get_nfc_device(device_id)

    def create_nfc_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._nfc_device_repo.create_nfc_device(payload)

    def update_nfc_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._nfc_device_repo.update_nfc_device(device_id, payload)

    def delete_nfc_device(self, device_id: int) -> None:
        self._nfc_device_repo.delete_nfc_device(device_id)

    def mark_nfc_device_tested(self, device_id: int) -> None:
        self._nfc_device_repo.mark_nfc_device_tested(device_id)

    def find_nfc_device_for_led_device(self, led_device_id: int) -> dict[str, Any] | None:
        return self._nfc_device_repo.find_nfc_device_for_led_device(led_device_id)

    def find_nfc_devices_by_endpoint(self, host: str, port: int) -> list[dict[str, Any]]:
        return self._nfc_device_repo.find_nfc_devices_by_endpoint(host, port)

    # --- LED ---
    def get_led_config(self) -> dict[str, Any]:
        return self._led_repo.get_led_config()

    def update_led_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._led_repo.update_led_config(payload)

    def list_led_devices(self) -> list[dict[str, Any]]:
        return self._led_repo.list_led_devices()

    def get_led_device(self, device_id: int) -> dict[str, Any] | None:
        return self._led_repo.get_led_device(device_id)

    def create_led_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._led_repo.create_led_device(payload)

    def update_led_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._led_repo.update_led_device(device_id, payload)

    def delete_led_device(self, device_id: int) -> None:
        self._led_repo.delete_led_device(device_id)

    def list_led_strips(self, device_id: int | None = None) -> list[dict[str, Any]]:
        return self._led_repo.list_led_strips(device_id)

    def create_led_strip(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._led_repo.create_led_strip(payload)

    def update_led_strip(self, strip_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._led_repo.update_led_strip(strip_id, payload)

    def delete_led_strip(self, strip_id: int) -> None:
        self._led_repo.delete_led_strip(strip_id)

    def get_led_mappings(self) -> list[dict[str, Any]]:
        return self._led_repo.get_led_mappings()

    def save_led_mappings(self, mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._led_repo.save_led_mappings(mappings)

    def find_led_by_box(self, box_id: int) -> dict[str, Any] | None:
        return self._led_repo.find_led_by_box(box_id)
