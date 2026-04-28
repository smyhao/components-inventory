from __future__ import annotations

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException

from config import (
    DATABASE_PATH,
    FRONTEND_LOG_FILE,
    HOST,
    LOG_FILE,
    MAX_CONTENT_LENGTH,
    PORT,
    STATIC_DIR,
    UPLOAD_FOLDER,
    ensure_runtime_directories,
)
from init_db import init_database
from led_proxy import LEDProxy
from logger import FileLogger
from models import InventoryError, InventoryRepository
from routes import register_blueprints

ensure_runtime_directories()
init_database(DATABASE_PATH)

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

file_logger = FileLogger(LOG_FILE, FRONTEND_LOG_FILE)
repo = InventoryRepository(DATABASE_PATH, file_logger, UPLOAD_FOLDER)
led_proxy = LEDProxy(repo)
file_logger.write_backend("SYSTEM", "backend initialized")

register_blueprints(app)


@app.errorhandler(Exception)
def handle_error(exc: Exception):
    from routes._utils import failure

    if request.path.startswith("/api"):
        if isinstance(exc, InventoryError):
            return failure(str(exc), 400)
        if isinstance(exc, HTTPException):
            return failure(exc.description, exc.code or 500)
        file_logger.write_backend("SYSTEM", f"exception: {exc}")
        return failure(str(exc), 500)
    if isinstance(exc, HTTPException):
        return Response(exc.description, status=exc.code or 500, mimetype="text/plain")
    file_logger.write_backend("SYSTEM", f"page exception: {exc}")
    return Response("Internal Server Error", status=500, mimetype="text/plain")


if __name__ == "__main__":
    file_logger.write_backend("SYSTEM", f"service start: http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
