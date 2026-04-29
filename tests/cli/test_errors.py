"""
错误处理和边界情况测试
"""

from __future__ import annotations

from text.cli.runner import TestContext, assert_eq, assert_in


def test_no_command(ctx: TestContext) -> None:
    """不带子命令应报错"""
    result = ctx.cli("--json", expect_ok=False)
    assert result.exit_code != 0, "should fail without command"


def test_invalid_command(ctx: TestContext) -> None:
    """无效命令应报错"""
    result = ctx.cli("invalid-command", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_components_missing_name(ctx: TestContext) -> None:
    """components create 缺少必填 name"""
    result = ctx.cli("components", "create", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_stock_missing_quantity(ctx: TestContext) -> None:
    """stock in 缺少必填 --quantity"""
    result = ctx.cli("stock", "in", "1", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_stock_out_missing_quantity(ctx: TestContext) -> None:
    """stock out 缺少必填 --quantity"""
    result = ctx.cli("stock", "out", "1", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_extra_spec_invalid_format(ctx: TestContext) -> None:
    """--extra-spec 格式错误（缺少 =）"""
    result = ctx.cli(
        "components", "create",
        "--name", "BadSpec",
        "--extra-spec", "no_equals_sign",
        "--json",
        expect_ok=False,
    )
    assert result.exit_code != 0, "should reject invalid extra-spec format"


def test_nonexistent_component_update(ctx: TestContext) -> None:
    """更新不存在的元器件"""
    result = ctx.cli(
        "components", "update", "99999",
        "--name", "Ghost",
        "--json",
        expect_ok=False,
    )
    assert not result.ok or result.json_data.get("code") != 0


def test_nonexistent_component_delete(ctx: TestContext) -> None:
    """删除不存在的元器件"""
    result = ctx.cli("components", "delete", "99999", "--yes", "--json", expect_ok=False)
    assert not result.ok or result.json_data.get("code") != 0


def test_network_unreachable(ctx: TestContext) -> None:
    """服务器不可达"""
    result = ctx.cli("ping", "--server", "http://127.0.0.1:1", "--json", expect_ok=False)
    assert not result.ok
    assert result.exit_code == 3, f"should exit with network error code (3), got {result.exit_code}"


def test_network_unreachable_message(ctx: TestContext) -> None:
    """网络错误应输出友好信息"""
    result = ctx.cli("ping", "--server", "http://127.0.0.1:1", "--json", expect_ok=False)
    combined = result.combined.lower()
    assert "network" in combined or "connection" in combined or "error" in combined, \
        f"should contain network error message, got: {result.combined[:200]}"


def test_missing_subcommand_components(ctx: TestContext) -> None:
    """components 不带子命令应报错"""
    result = ctx.cli("components", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_missing_subcommand_boxes(ctx: TestContext) -> None:
    """boxes 不带子命令应报错"""
    result = ctx.cli("boxes", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_missing_subcommand_stock(ctx: TestContext) -> None:
    """stock 不带子命令应报错"""
    result = ctx.cli("stock", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_config_missing_subcommand(ctx: TestContext) -> None:
    """config 不带子命令应报错"""
    result = ctx.cli("config", "--json", expect_ok=False)
    assert result.exit_code != 0


def test_global_option_missing_value(ctx: TestContext) -> None:
    """--server 缺少值应报错"""
    result = ctx.cli("--server", "--json", expect_ok=False)
    assert result.exit_code != 0
