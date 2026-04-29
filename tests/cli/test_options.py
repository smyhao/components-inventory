"""
全局选项测试：--json, --pretty, --quiet, --verbose, --server, --token, --profile
"""

from __future__ import annotations

from text.cli.runner import TestContext, assert_eq, assert_in, assert_json_code


def test_json_output(ctx: TestContext) -> None:
    """--json 输出有效的 JSON"""
    result = ctx.cli("stats", "--json")
    assert_json_code(result, 0)
    assert result.stdout.startswith("{"), "json output should start with {"


def test_pretty_output(ctx: TestContext) -> None:
    """--pretty 输出缩进 JSON"""
    result = ctx.cli("stats", "--pretty")
    assert_json_code(result, 0)
    assert_in(result.stdout, "\n", "pretty should produce multi-line output")
    assert_in(result.stdout, "  ", "pretty should have indentation")


def test_quiet_output(ctx: TestContext) -> None:
    """--quiet 只输出关键信息"""
    result = ctx.cli("stats", "--quiet")
    assert result.ok
    # quiet 输出应该比正常输出短
    normal_result = ctx.cli("stats")
    assert len(result.stdout) <= len(normal_result.stdout), "quiet should not be longer than normal"


def test_server_option(ctx: TestContext) -> None:
    """--server 覆盖服务器地址"""
    # 使用一个无效地址应该得到网络错误
    result = ctx.cli("ping", "--server", "http://127.0.0.1:1", "--json", expect_ok=False)
    assert not result.ok, "invalid server should fail"


def test_json_and_pretty_combined(ctx: TestContext) -> None:
    """--json --pretty 同时使用"""
    result = ctx.cli("stats", "--json", "--pretty")
    assert_json_code(result, 0)
    assert_in(result.stdout, "\n")


def test_global_options_position(ctx: TestContext) -> None:
    """全局选项可以在命令前或命令后"""
    # 选项在命令前
    result1 = ctx.cli("--json", "stats")
    assert_json_code(result1, 0)

    # 选项在命令后
    result2 = ctx.cli("stats", "--json")
    assert_json_code(result2, 0)


def test_components_list_json_structure(ctx: TestContext) -> None:
    """components list --json 返回标准 envelope 结构"""
    result = ctx.cli("components", "list", "--json")
    assert_json_code(result, 0)
    assert "data" in result.json_data
    assert "items" in result.json_data["data"]
    assert "total" in result.json_data["data"] or "page" in result.json_data["data"], \
        "should have pagination info"


def test_boxes_list_json_structure(ctx: TestContext) -> None:
    """boxes list --json 返回列表"""
    result = ctx.cli("boxes", "list", "--json")
    assert_json_code(result, 0)
    assert isinstance(result.json_data["data"], list), "boxes data should be a list"


def test_error_json_structure(ctx: TestContext) -> None:
    """错误时也输出标准 JSON 结构"""
    result = ctx.cli("components", "get", "99999", "--json", expect_ok=False)
    if result.json_data:
        assert "code" in result.json_data, "error response should have code"
        assert "message" in result.json_data, "error response should have message"
        assert result.json_data["code"] != 0, "error code should be non-zero"


def test_table_output_format(ctx: TestContext) -> None:
    """表格输出应有对齐的列"""
    result = ctx.cli("components", "list")
    assert result.ok
    lines = result.stdout.split("\n")
    if len(lines) >= 2:
        # 第二行应该是分隔线
        assert_in(lines[1], "-", "second line should be separator")
