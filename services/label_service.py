from __future__ import annotations

import io
import re
from html import escape
from typing import Any

from models import InventoryError, clean_int


def component_qr_svg(component_id: int, base_url: str) -> bytes:
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError as exc:
        raise InventoryError("missing dependency qrcode, please run pip install -r requirements.txt") from exc

    url = f"{base_url.rstrip('/')}/?component={component_id}"
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
        image_factory=qrcode.image.svg.SvgPathImage,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image()
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue()


def parse_component_ids(value: str) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for part in re.split(r"[,，\s]+", value or ""):
        component_id = clean_int(part, 0)
        if component_id > 0 and component_id not in seen:
            ids.append(component_id)
            seen.add(component_id)
    return ids[:500]


def qr_label_print_page(components: list[dict[str, Any]]) -> str:
    label_count = len(components)
    cards = []
    for item in components:
        component_id = item["id"]
        spec = " / ".join(
            str(value)
            for value in [item.get("model"), item.get("package"), item.get("nominal_value")]
            if value
        )
        location = " / ".join(
            str(value)
            for value in [item.get("box_name"), item.get("cell_label")]
            if value
        )
        quantity = item.get("quantity") if item.get("quantity") is not None else 0
        cards.append(
            f"""
            <article class="label">
                <img src="/api/components/{component_id}/qr.svg" alt="QR">
                <div class="label-text">
                    <strong>{escape(str(item.get("name") or ""))}</strong>
                    <span>{escape(spec or "无规格信息")}</span>
                    <small>{escape(location or "未入盒")} · 库存 {escape(str(quantity))}</small>
                </div>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>元器件二维码标签</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #1f2933; background: #f7f5ef; }}
        header {{ position: sticky; top: 0; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 18px; background: rgba(255,255,255,.94); border-bottom: 1px solid #ddd6c8; }}
        h1 {{ margin: 0; font-size: 18px; }}
        p {{ margin: 4px 0 0; color: #697386; font-size: 13px; }}
        button {{ border: 0; border-radius: 8px; padding: 10px 16px; background: #2563eb; color: white; font-weight: 700; cursor: pointer; }}
        main {{ padding: 18px; }}
        .sheet {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }}
        .label {{ min-height: 96px; display: grid; grid-template-columns: 78px minmax(0, 1fr); gap: 10px; align-items: center; padding: 8px; background: white; border: 1px dashed #a8b0bd; border-radius: 8px; break-inside: avoid; }}
        .label img {{ width: 78px; height: 78px; display: block; }}
        .label-text {{ min-width: 0; display: flex; flex-direction: column; gap: 4px; }}
        .label-text strong {{ font-size: 14px; line-height: 1.2; overflow-wrap: anywhere; }}
        .label-text span, .label-text small {{ font-size: 11px; color: #52606d; overflow-wrap: anywhere; }}
        .empty {{ padding: 40px; text-align: center; color: #697386; background: white; border-radius: 8px; }}
        @media print {{
            body {{ background: white; }}
            header {{ display: none; }}
            main {{ padding: 0; }}
            .sheet {{ grid-template-columns: repeat(3, 1fr); gap: 4mm; }}
            .label {{ border-color: #777; border-radius: 2mm; page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <header>
        <div>
            <h1>元器件二维码标签</h1>
            <p>共 {label_count} 个标签。扫码后会打开对应元器件详情，可继续修改参数或库存。</p>
        </div>
        <button onclick="window.print()">打印</button>
    </header>
    <main>
        {"<section class='sheet'>" + "".join(cards) + "</section>" if cards else "<div class='empty'>没有可打印的元器件</div>"}
    </main>
</body>
</html>"""
