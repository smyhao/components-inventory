"""
ping 和 stats 命令测试
"""

from __future__ import annotations

from text.cli.runner import TestContext, assert_in, assert_json_code, assert_json_has, skip


def test_ping(ctx: TestContext) -> None:
    """ping 检查服务器连通性"""
    result = ctx.cli("ping", "--json")
    assert_json_code(result, 0)
    assert_json_has(result, "reachable", "stats", label="ping")


def test_ping_human(ctx: TestContext) -> None:
    """ping 人类可读输出"""
    result = ctx.cli("ping")
    assert result.ok
    assert_in(result.stdout, "reachable:")


def test_stats(ctx: TestContext) -> None:
    """stats 获取统计信息"""
    result = ctx.cli("stats", "--json")
    assert_json_code(result, 0)
    # stats 返回的 data 应该是一个 dict，包含统计字段
    data = result.json_data["data"]
    assert isinstance(data, dict), f"stats data should be dict, got {type(data)}"


def test_stats_human(ctx: TestContext) -> None:
    """stats 人类可读输出"""
    result = ctx.cli("stats")
    assert result.ok
    # 应该有一些统计相关的内容输出
    assert len(result.stdout) > 0, "stats should produce output"


def test_stats_pretty(ctx: TestContext) -> None:
    """stats --pretty 格式化 JSON"""
    result = ctx.cli("stats", "--pretty")
    assert_json_code(result, 0)
    assert_in(result.stdout, "\n", "pretty should produce indented output")


def test_stats_quiet(ctx: TestContext) -> None:
    """stats --quiet 只输出关键信息"""
    result = ctx.cli("stats", "--quiet")
    assert result.ok
    # quiet 模式应该输出更少
