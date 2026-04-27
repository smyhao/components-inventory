"""
boxes 命令测试：list, get, grid
"""

from __future__ import annotations

from text.cli.runner import TestContext, assert_eq, assert_in, assert_json_code, assert_json_has


def test_boxes_list(ctx: TestContext) -> None:
    """boxes list 列出收纳盒"""
    result = ctx.cli("boxes", "list", "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert isinstance(data, list), "boxes list data should be a list"
    if data:
        box = data[0]
        assert "id" in box, "box should have id"
        assert "name" in box, "box should have name"


def test_boxes_list_human(ctx: TestContext) -> None:
    """boxes list 人类可读表格输出"""
    result = ctx.cli("boxes", "list")
    assert result.ok
    if len(result.stdout) > 0:
        assert_in(result.stdout, "id")


def test_boxes_get(ctx: TestContext) -> None:
    """boxes get 获取收纳盒详情"""
    # 先列出盒子获取一个有效 ID
    list_result = ctx.cli("boxes", "list", "--json")
    boxes = list_result.json_data["data"]
    if not boxes:
        return

    box_id = boxes[0]["id"]
    result = ctx.cli("boxes", "get", str(box_id), "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert_eq(data["id"], box_id)


def test_boxes_get_human(ctx: TestContext) -> None:
    """boxes get 人类可读输出"""
    list_result = ctx.cli("boxes", "list", "--json")
    boxes = list_result.json_data["data"]
    if not boxes:
        return

    box_id = boxes[0]["id"]
    result = ctx.cli("boxes", "get", str(box_id))
    assert result.ok
    assert_in(result.stdout, "name:")


def test_boxes_grid(ctx: TestContext) -> None:
    """boxes grid 查看格子占用"""
    list_result = ctx.cli("boxes", "list", "--json")
    boxes = list_result.json_data["data"]
    if not boxes:
        return

    box_id = boxes[0]["id"]
    result = ctx.cli("boxes", "grid", str(box_id), "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    # grid 返回应该包含格子信息
    assert isinstance(data, dict), "grid data should be dict"


def test_boxes_grid_human(ctx: TestContext) -> None:
    """boxes grid 人类可读输出"""
    list_result = ctx.cli("boxes", "list", "--json")
    boxes = list_result.json_data["data"]
    if not boxes:
        return

    box_id = boxes[0]["id"]
    result = ctx.cli("boxes", "grid", str(box_id))
    assert result.ok
    assert len(result.stdout) > 0


def test_boxes_get_nonexistent(ctx: TestContext) -> None:
    """boxes get 不存在的盒子"""
    result = ctx.cli("boxes", "get", "99999", "--json", expect_ok=False)
    assert not result.ok or result.json_data.get("code") != 0


def test_boxes_grid_nonexistent(ctx: TestContext) -> None:
    """boxes grid 不存在的盒子"""
    result = ctx.cli("boxes", "grid", "99999", "--json", expect_ok=False)
    assert not result.ok or result.json_data.get("code") != 0
