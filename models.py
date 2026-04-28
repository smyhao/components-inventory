from __future__ import annotations

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

        self._token_repo = TokenRepository(db_path, file_logger)
        self._category_repo = CategoryRepository(db_path, file_logger)
        self._cabinet_repo = CabinetRepository(db_path, file_logger)
        self._box_repo = BoxRepository(db_path, file_logger)
        self._component_repo = ComponentRepository(db_path, file_logger, upload_folder)
        self._stock_repo = StockRepository(db_path, file_logger)
        self._document_repo = DocumentRepository(db_path, file_logger, upload_folder)
        self._nfc_repo = NfcRepository(db_path, file_logger, self._box_repo)

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
        return self._component_repo.get_map_data()

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
