from __future__ import annotations

# 本脚本直接读取 GLB 的 JSON chunk 做规范检查，避免为了模型入库检查引入额外三维依赖。

import argparse
import json
import math
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DRAWER_REQUIRED_NODES = {
    "FIXED_FRAME",
    "DRAWER_PART",
    "NAMEPLATE_ANCHOR",
    "LED_ANCHOR",
    "BOX_SLOT_ANCHOR",
    "DRAWER_CLOSED_ANCHOR",
    "DRAWER_OPEN_ANCHOR",
}
SHELF_REQUIRED_NODES = {
    "FIXED_FRAME",
    "NAMEPLATE_ANCHOR",
    "LED_ANCHOR",
    "BOX_SLOT_ANCHOR",
}
ANCHOR_NODES = {
    "NAMEPLATE_ANCHOR",
    "LED_ANCHOR",
    "BOX_SLOT_ANCHOR",
    "DRAWER_CLOSED_ANCHOR",
    "DRAWER_OPEN_ANCHOR",
}
KNOWN_NODES = DRAWER_REQUIRED_NODES | SHELF_REQUIRED_NODES


@dataclass
class Issue:
    level: str
    message: str


def normalize_node_name(name: str) -> str:
    """把 SW 常见导出后缀归一化，便于容忍 FIXED_FRAME-1 这类实例名。"""
    text = re.sub(r"\s+", "", name or "").upper()
    text = re.sub(r"[-_.]\d+$", "", text)
    return text


def read_glb(path: Path) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    data = path.read_bytes()
    return parse_glb_bytes(data)


def parse_glb_bytes(data: bytes) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    if len(data) < 20:
        raise ValueError("文件太小，不是有效 GLB")
    if data[:4] != b"glTF":
        raise ValueError("GLB magic 不正确，应为 glTF")
    version, total_length = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise ValueError(f"仅支持 GLB 2.0，当前版本为 {version}")
    if total_length != len(data):
        raise ValueError(f"GLB 长度不匹配：header={total_length}, actual={len(data)}")

    offset = 12
    chunks: list[dict[str, Any]] = []
    gltf_json: dict[str, Any] | None = None
    while offset + 8 <= len(data):
        chunk_length, chunk_type_raw = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk_end = offset + chunk_length
        if chunk_end > len(data):
            raise ValueError("GLB chunk 长度越界")
        chunk_type = chunk_type_raw.decode("ascii", errors="replace")
        chunks.append({"type": chunk_type, "length": chunk_length})
        if chunk_type == "JSON":
            text = data[offset:chunk_end].decode("utf-8").rstrip(" \t\r\n\0")
            gltf_json = json.loads(text)
        offset = chunk_end

    if gltf_json is None:
        raise ValueError("GLB 中缺少 JSON chunk")
    return gltf_json, version, chunks


def analyze_model(gltf: dict[str, Any], model_type: str) -> dict[str, Any]:
    nodes = gltf.get("nodes") or []
    node_reports = []
    normalized_map: dict[str, list[int]] = {}
    issues: list[Issue] = []

    for index, node in enumerate(nodes):
        original = str(node.get("name") or "")
        normalized = normalize_node_name(original)
        node_reports.append(
            {
                "index": index,
                "name": original,
                "normalized": normalized,
                "mesh": node.get("mesh"),
                "children": node.get("children") or [],
                "translation": node.get("translation"),
                "rotation": node.get("rotation"),
                "scale": node.get("scale"),
            }
        )
        if normalized:
            normalized_map.setdefault(normalized, []).append(index)

    required = required_nodes(model_type)
    found = {name: normalized_map.get(name, []) for name in sorted(required)}
    missing = [name for name, indexes in found.items() if not indexes]
    duplicate = {name: indexes for name, indexes in found.items() if len(indexes) > 1}

    for name in missing:
        issues.append(Issue("error", f"缺少必需节点：{name}"))
    for name, indexes in duplicate.items():
        issues.append(Issue("warning", f"节点 {name} 出现多次：{indexes}"))

    for report in node_reports:
        normalized = report["normalized"]
        original = report["name"]
        if normalized in KNOWN_NODES and original != normalized:
            issues.append(Issue("warning", f"节点 {original!r} 可识别为 {normalized}，建议改成标准名"))
        if normalized.endswith("ANCHO"):
            issues.append(Issue("warning", f"节点 {original!r} 疑似拼写错误，是否应为 *_ANCHOR"))

    anchor_reports = anchor_size_reports(gltf, node_reports)
    for anchor in anchor_reports:
        if anchor["normalized"] in ANCHOR_NODES and anchor.get("size"):
            max_size = max(anchor["size"])
            # 锚点只是定位标记，过大通常代表误把真实模型命名成了锚点。
            if max_size > 0.02:
                issues.append(Issue("warning", f"锚点 {anchor['name']!r} 尺寸偏大：{format_vec(anchor['size'])}"))

    pull = drawer_pull_report(anchor_reports)
    if model_type == "drawer-cabinet" and pull.get("distance") is not None and pull["distance"] <= 0:
        issues.append(Issue("error", "抽拉距离为 0，请检查 DRAWER_OPEN_ANCHOR 和 DRAWER_CLOSED_ANCHOR"))

    return {
        "model_type": model_type,
        "node_count": len(nodes),
        "mesh_count": len(gltf.get("meshes") or []),
        "material_count": len(gltf.get("materials") or []),
        "image_count": len(gltf.get("images") or []),
        "found": found,
        "missing": missing,
        "duplicate": duplicate,
        "anchors": anchor_reports,
        "drawer_pull": pull,
        "issues": [issue.__dict__ for issue in issues],
        "nodes": node_reports,
        "tree": build_scene_tree(gltf),
    }


def required_nodes(model_type: str) -> set[str]:
    if model_type == "drawer-cabinet":
        return DRAWER_REQUIRED_NODES
    if model_type == "open-shelf":
        return SHELF_REQUIRED_NODES
    if model_type in {"box-cell", "box-frame", "cabinet-base", "cabinet-top"}:
        return set()
    raise ValueError(f"未知模型类型：{model_type}")


def anchor_size_reports(gltf: dict[str, Any], node_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    for report in node_reports:
        if report["normalized"] not in ANCHOR_NODES:
            continue
        mesh_index = report.get("mesh")
        bounds = mesh_bounds(gltf, mesh_index) if mesh_index is not None else None
        item = {
            "index": report["index"],
            "name": report["name"],
            "normalized": report["normalized"],
            "translation": report.get("translation"),
        }
        if bounds:
            item["local_bounds"] = bounds
            item["size"] = [bounds["max"][i] - bounds["min"][i] for i in range(3)]
            item["center"] = [(bounds["max"][i] + bounds["min"][i]) / 2 for i in range(3)]
        reports.append(item)
    return reports


def mesh_bounds(gltf: dict[str, Any], mesh_index: int | None) -> dict[str, list[float]] | None:
    if mesh_index is None:
        return None
    meshes = gltf.get("meshes") or []
    accessors = gltf.get("accessors") or []
    if mesh_index < 0 or mesh_index >= len(meshes):
        return None
    bounds_min: list[float] | None = None
    bounds_max: list[float] | None = None
    for primitive in meshes[mesh_index].get("primitives") or []:
        position_accessor = (primitive.get("attributes") or {}).get("POSITION")
        if position_accessor is None or position_accessor >= len(accessors):
            continue
        accessor = accessors[position_accessor]
        if "min" not in accessor or "max" not in accessor:
            continue
        item_min = [float(value) for value in accessor["min"]]
        item_max = [float(value) for value in accessor["max"]]
        if bounds_min is None:
            bounds_min = item_min
            bounds_max = item_max
            continue
        bounds_min = [min(bounds_min[i], item_min[i]) for i in range(3)]
        bounds_max = [max(bounds_max[i], item_max[i]) for i in range(3)]
    if bounds_min is None or bounds_max is None:
        return None
    return {"min": bounds_min, "max": bounds_max}


def drawer_pull_report(anchor_reports: list[dict[str, Any]]) -> dict[str, Any]:
    closed = first_anchor(anchor_reports, "DRAWER_CLOSED_ANCHOR")
    open_anchor = first_anchor(anchor_reports, "DRAWER_OPEN_ANCHOR")
    if not closed or not open_anchor:
        return {"available": False}
    closed_center = anchor_position(closed)
    open_center = anchor_position(open_anchor)
    if not closed_center or not open_center:
        return {"available": False}
    vector = [open_center[i] - closed_center[i] for i in range(3)]
    distance = math.sqrt(sum(value * value for value in vector))
    direction = [value / distance for value in vector] if distance else [0.0, 0.0, 0.0]
    return {
        "available": True,
        "closed": closed_center,
        "open": open_center,
        "vector": vector,
        "direction": direction,
        "distance": distance,
    }


def first_anchor(anchor_reports: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for anchor in anchor_reports:
        if anchor["normalized"] == name:
            return anchor
    return None


def anchor_position(anchor: dict[str, Any]) -> list[float] | None:
    # GLB 节点 position 是锚点最稳定的语义；没有 translation 时再退回本地几何中心。
    if anchor.get("translation"):
        return [float(value) for value in anchor["translation"]]
    if anchor.get("center"):
        return [float(value) for value in anchor["center"]]
    return None


def build_scene_tree(gltf: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = gltf.get("nodes") or []
    scenes = gltf.get("scenes") or []
    scene_index = int(gltf.get("scene") or 0)
    scene = scenes[scene_index] if 0 <= scene_index < len(scenes) else {}

    def build(index: int) -> dict[str, Any]:
        node = nodes[index]
        return {
            "index": index,
            "name": node.get("name") or "",
            "children": [build(child) for child in node.get("children") or [] if 0 <= child < len(nodes)],
        }

    return [build(index) for index in scene.get("nodes") or [] if 0 <= index < len(nodes)]


def format_vec(values: list[float]) -> str:
    return ", ".join(f"{value:.6g}" for value in values)


def print_text_report(path: Path, report: dict[str, Any]) -> None:
    print(f"GLB 模型检查：{path}")
    print(f"模型类型：{report['model_type']}")
    print(f"节点/网格/材质/图片：{report['node_count']} / {report['mesh_count']} / {report['material_count']} / {report['image_count']}")
    print()

    if report["found"]:
        print("必需节点：")
        for name, indexes in report["found"].items():
            status = "OK" if indexes else "缺失"
            suffix = f" -> {indexes}" if indexes else ""
            print(f"  {name:<22} {status}{suffix}")
        print()

    pull = report["drawer_pull"]
    if pull.get("available"):
        print("抽拉参数：")
        print(f"  方向：{format_vec(pull['direction'])}")
        print(f"  距离：{pull['distance']:.6g} GLB 单位")
        print()

    if report["anchors"]:
        print("锚点：")
        for anchor in report["anchors"]:
            position = anchor_position(anchor)
            pos_text = format_vec(position) if position else "未知"
            size_text = format_vec(anchor["size"]) if anchor.get("size") else "未知"
            print(f"  {anchor['name']} -> {anchor['normalized']}，位置 {pos_text}，尺寸 {size_text}")
        print()

    if report["issues"]:
        print("问题：")
        for issue in report["issues"]:
            print(f"  [{issue['level']}] {issue['message']}")
    else:
        print("未发现规范问题。")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 GLB 模型节点命名规范。")
    parser.add_argument("path", type=Path, help="GLB 文件路径")
    parser.add_argument(
        "--type",
        choices=["drawer-cabinet", "open-shelf", "box-cell", "box-frame", "cabinet-base", "cabinet-top"],
        default="drawer-cabinet",
        help="模型类型，默认 drawer-cabinet",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        gltf, version, chunks = read_glb(args.path)
        report = analyze_model(gltf, args.type)
        report["glb"] = {
            "path": str(args.path),
            "version": version,
            "chunks": chunks,
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(args.path, report)

    has_error = any(issue["level"] == "error" for issue in report["issues"])
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
