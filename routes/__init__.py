from __future__ import annotations

# 本文件集中注册 Flask 蓝图，是路由层对应用入口的唯一导出点。

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from routes.pages import pages_bp
    from routes.categories import categories_bp
    from routes.cabinets import cabinets_bp
    from routes.boxes import boxes_bp
    from routes.components import components_bp
    from routes.stock_operations import stock_bp
    from routes.tags import tags_bp
    from routes.nfc import nfc_bp
    from routes.map import map_bp
    from routes.bom import bom_bp
    from routes.auth import auth_bp
    from routes.led import led_bp
    from routes.model_appearance import model_appearance_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(cabinets_bp)
    app.register_blueprint(boxes_bp)
    app.register_blueprint(components_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(nfc_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(bom_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(led_bp)
    app.register_blueprint(model_appearance_bp)
