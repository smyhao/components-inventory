from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .errors import ApiError, AuthError, NetworkError, UnexpectedResponseError


class InventoryClient:
    def __init__(
        self,
        server: str,
        *,
        token: str | None = None,
        timeout: float = 30,
        actor: str | None = None,
        source: str = "inventory-cli",
    ) -> None:
        self.server = (server or "http://localhost:5000").rstrip("/")
        self.token = token or ""
        self.timeout = timeout
        self.actor = actor or f"cli@{socket.gethostname()}"
        self.source = source

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        path = "/" + path.lstrip("/")
        url = f"{self.server}{path}"
        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value not in (None, "", False)
        }
        if clean_params:
            url = f"{url}?{urllib.parse.urlencode(clean_params, doseq=True)}"
        return url

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-Inventory-Source": self.source,
            "X-Inventory-Actor": self.actor,
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._url(path, params),
            data=data,
            headers=self._headers(json_body=payload is not None),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return self._decode_json(response.read(), response.status)
        except urllib.error.HTTPError as exc:
            response = self._safe_error_json(exc)
            message = response.get("message") or exc.reason or f"HTTP {exc.code}"
            if exc.code in {401, 403}:
                raise AuthError(str(message), response=response) from exc
            raise ApiError(str(message), response=response) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise NetworkError(f"network error: {exc}") from exc

    def _decode_json(self, raw: bytes, status: int) -> dict[str, Any]:
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnexpectedResponseError(f"server returned non-JSON response (HTTP {status})") from exc
        if not isinstance(decoded, dict):
            raise UnexpectedResponseError("server returned an invalid JSON response")
        if decoded.get("code", 0) != 0:
            raise ApiError(str(decoded.get("message") or "request failed"), response=decoded)
        return decoded

    def _safe_error_json(self, exc: urllib.error.HTTPError) -> dict[str, Any]:
        try:
            raw = exc.read()
            decoded = json.loads(raw.decode("utf-8"))
            if isinstance(decoded, dict):
                return decoded
        except Exception:
            pass
        return {"code": 1, "data": None, "message": exc.reason or f"HTTP {exc.code}"}

    def stats(self) -> dict[str, Any]:
        return self._request("GET", "/api/stats")

    def ping(self) -> dict[str, Any]:
        return self.stats()

    def list_components(self, **filters: Any) -> dict[str, Any]:
        return self._request("GET", "/api/components", params=filters)

    def get_component(self, component_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/components/{component_id}")

    def create_component(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/components", payload=payload)

    def update_component(self, component_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/api/components/{component_id}", payload=payload)

    def delete_component(self, component_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/api/components/{component_id}")

    def list_boxes(self) -> dict[str, Any]:
        return self._request("GET", "/api/boxes")

    def get_box(self, box_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/boxes/{box_id}")

    def get_box_grid(self, box_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/boxes/{box_id}/grid")

    def stock_in(self, component_id: int, quantity: int, reason: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/stock/in",
            payload={"component_id": component_id, "quantity": quantity, "reason": reason or ""},
        )

    def stock_out(self, component_id: int, quantity: int, reason: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/stock/out",
            payload={"component_id": component_id, "quantity": quantity, "reason": reason or ""},
        )

    def stock_logs(self, component_id: int, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/stock/logs/{component_id}",
            params={"page": page, "page_size": page_size},
        )
