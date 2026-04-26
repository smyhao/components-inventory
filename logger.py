from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Iterable


IMPORTANT_BACKEND_TAGS = {
    "SYSTEM",
    "COMPONENT",
    "BOX",
    "STOCK",
    "NFC",
    "BOM",
}

SUPPRESSED_BACKEND_PATTERNS = (
    "更新盒子地图位置",
    "create compartments",
)

IMPORTANT_FRONTEND_TYPES = {
    "ERROR",
    "CREATE",
    "UPDATE",
    "DELETE",
    "STOCK",
    "IMPORT",
    "EXPORT",
    "BOM",
    "NFC",
    "SCAN",
}


def _parse_timestamp(value: object | None) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, str) and value.strip():
        text = value.strip()
        for candidate in (
            text,
            text.replace("Z", "+00:00"),
            text.replace("T", " "),
        ):
            try:
                return datetime.fromisoformat(candidate).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return text[:19]
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FileLogger:
    def __init__(self, backend_log_file: Path, frontend_log_file: Path) -> None:
        self.backend_log_file = Path(backend_log_file)
        self.frontend_log_file = Path(frontend_log_file)
        self._lock = Lock()

    def _write(self, path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line.rstrip() + "\n")

    def _should_write_backend(self, tag: str, detail: str) -> bool:
        if not detail.strip():
            return False
        normalized_tag = tag.strip().upper()
        if normalized_tag not in IMPORTANT_BACKEND_TAGS:
            return False
        return not any(pattern in detail for pattern in SUPPRESSED_BACKEND_PATTERNS)

    def _should_write_frontend(self, log_type: str, detail: str) -> bool:
        if not detail.strip():
            return False
        normalized_type = log_type.strip().upper()
        if normalized_type in IMPORTANT_FRONTEND_TYPES:
            return True
        detail_lower = detail.lower()
        return "失败" in detail or "异常" in detail or "error" in detail_lower or "exception" in detail_lower

    def write_backend(self, tag: str, detail: str, when: object | None = None) -> None:
        if not self._should_write_backend(tag, detail):
            return
        line = f"[{_parse_timestamp(when)}] [{tag}] {detail}"
        self._write(self.backend_log_file, line)

    def write_frontend_batch(self, logs: Iterable[dict]) -> int:
        written = 0
        for entry in logs:
            if not isinstance(entry, dict):
                continue
            log_type = str(entry.get("type") or "INFO").strip() or "INFO"
            detail = str(entry.get("detail") or "").strip()
            if not self._should_write_frontend(log_type, detail):
                continue
            line = f"[{_parse_timestamp(entry.get('time'))}] [{log_type}] {detail}"
            self._write(self.frontend_log_file, line)
            written += 1
        return written
