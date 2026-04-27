"""
stock 命令测试：in, out, logs
"""

from __future__ import annotations

from text.cli.runner import TestContext, assert_eq, assert_in, assert_json_code


def _ensure_test_component(ctx: TestContext) -> int:
    """确保测试元器件存在并返回其 ID"""
    comp_id = ctx.shared.get("stock_component_id")
    if comp_id:
        return comp_id
    result = ctx.cli(
        "components", "create",
        "--name", "Test-Stock-Component",
        "--quantity", "100",
        "--json",
    )
    comp_id = result.json_data["data"]["id"]
    ctx.shared["stock_component_id"] = comp_id
    return comp_id


def test_stock_in(ctx: TestContext) -> None:
    """stock in 入库"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli(
        "stock", "in", str(comp_id),
        "--quantity", "50",
        "--reason", "CLI test stock-in",
        "--json",
    )
    assert_json_code(result, 0)
    data = result.json_data["data"]
    # stock in 返回 {component_id, quantity_after, warning}
    assert_eq(data["component_id"], comp_id)
    assert isinstance(data.get("quantity_after"), int), "should have quantity_after"


def test_stock_out(ctx: TestContext) -> None:
    """stock out 出库"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli(
        "stock", "out", str(comp_id),
        "--quantity", "10",
        "--reason", "CLI test stock-out",
        "--json",
    )
    assert_json_code(result, 0)


def test_stock_in_human(ctx: TestContext) -> None:
    """stock in 人类可读输出"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli(
        "stock", "in", str(comp_id),
        "--quantity", "5",
        "--reason", "human readable test",
    )
    assert result.ok


def test_stock_out_human(ctx: TestContext) -> None:
    """stock out 人类可读输出"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli(
        "stock", "out", str(comp_id),
        "--quantity", "5",
    )
    assert result.ok


def test_stock_out_overdraw(ctx: TestContext) -> None:
    """stock out 扣成负库存应被拒绝"""
    comp_id = _ensure_test_component(ctx)
    # 尝试扣掉一个非常大的数量
    result = ctx.cli(
        "stock", "out", str(comp_id),
        "--quantity", "999999",
        "--json",
        expect_ok=False,
    )
    # 应该失败
    assert not result.ok or result.json_data.get("code") != 0, "should reject overdraw"


def test_stock_logs(ctx: TestContext) -> None:
    """stock logs 查看库存日志"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli("stock", "logs", str(comp_id), "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert "items" in data, "should have items in logs"
    assert isinstance(data["items"], list)


def test_stock_logs_human(ctx: TestContext) -> None:
    """stock logs 人类可读输出"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli("stock", "logs", str(comp_id))
    assert result.ok


def test_stock_logs_with_page(ctx: TestContext) -> None:
    """stock logs 分页"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli(
        "stock", "logs", str(comp_id),
        "--page", "1",
        "--page-size", "5",
        "--json",
    )
    assert_json_code(result, 0)
    items = result.json_data["data"]["items"]
    assert len(items) <= 5, "should respect page-size"


def test_stock_logs_global(ctx: TestContext) -> None:
    """stock logs 0 全局日志"""
    result = ctx.cli("stock", "logs", "0", "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert "items" in data


def test_stock_in_pretty(ctx: TestContext) -> None:
    """stock in --pretty 格式化输出"""
    comp_id = _ensure_test_component(ctx)
    result = ctx.cli(
        "stock", "in", str(comp_id),
        "--quantity", "1",
        "--reason", "pretty test",
        "--pretty",
    )
    assert_json_code(result, 0)
    assert_in(result.stdout, "\n")
