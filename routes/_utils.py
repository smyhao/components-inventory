from __future__ import annotations

import io
from typing import Any

from flask import jsonify, send_file


def success(data: Any = None, message: str = "ok", status: int = 200):
    return jsonify({"code": 0, "data": data, "message": message}), status


def failure(message: str, status: int = 400):
    return jsonify({"code": 1, "data": None, "message": message}), status


def excel_response(data: bytes, filename: str):
    return send_file(
        io.BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
