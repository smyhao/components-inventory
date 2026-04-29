"""
config 命令测试：set-server, set-token, use, show
"""

from __future__ import annotations

from text.cli.runner import CLIResult, TestContext, assert_eq, assert_in, assert_json_code, assert_json_has


def test_config_set_server(ctx: TestContext) -> None:
    """config set-server 保存服务器地址"""
    result = ctx.cli("config", "set-server", "test-profile", "http://192.168.1.20:5000", "--json")
    assert_json_code(result, 0, "set-server")
    assert_json_has(result, "profile", "server", "config_path", label="set-server")


def test_config_set_server_pretty(ctx: TestContext) -> None:
    """config set-server --pretty 格式化输出"""
    result = ctx.cli("config", "set-server", "test-profile", "http://192.168.1.20:5000", "--pretty")
    assert_json_code(result, 0)
    assert_in(result.stdout, "\n", "pretty should be indented")


def test_config_set_token(ctx: TestContext) -> None:
    """config set-token 保存 token"""
    result = ctx.cli("config", "set-token", "test-profile", "my-secret-token", "--json")
    assert_json_code(result, 0, "set-token")
    # token 应该被隐藏
    data = result.json_data["data"]
    assert_eq(data["token"], "***", "token should be masked")
    assert_in(str(data["config_path"]), "config.json", "config_path")


def test_config_use(ctx: TestContext) -> None:
    """config use 设置默认 profile"""
    ctx.cli("config", "set-server", "lab", "http://192.168.1.20:5000")
    result = ctx.cli("config", "use", "lab", "--json")
    assert_json_code(result, 0)
    assert_eq(result.json_data["data"]["default_profile"], "lab")


def test_config_show(ctx: TestContext) -> None:
    """config show 查看配置"""
    ctx.cli("config", "set-server", "lab", "http://192.168.1.20:5000")
    ctx.cli("config", "set-token", "lab", "my-token")
    ctx.cli("config", "use", "lab")

    result = ctx.cli("config", "show", "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert_eq(data["profile"], "lab", "profile name")
    assert_eq(data["server"], "http://192.168.1.20:5000", "server")
    # 默认不显示 token
    assert_eq(data["token"], "***", "token should be hidden by default")


def test_config_show_token(ctx: TestContext) -> None:
    """config show --show-token 显示真实 token"""
    ctx.cli("config", "set-server", "lab", "http://192.168.1.20:5000")
    ctx.cli("config", "set-token", "lab", "real-token-123")
    ctx.cli("config", "use", "lab")

    result = ctx.cli("config", "show", "--show-token", "--json")
    assert_json_code(result, 0)
    assert_eq(result.json_data["data"]["token"], "real-token-123", "token should be visible with --show-token")


def test_config_show_specific_profile(ctx: TestContext) -> None:
    """config show <profile> 查看指定 profile"""
    ctx.cli("config", "set-server", "dev", "http://localhost:5000")
    ctx.cli("config", "set-server", "lab", "http://192.168.1.20:5000")

    result = ctx.cli("config", "show", "dev", "--json")
    assert_json_code(result, 0)
    assert_eq(result.json_data["data"]["server"], "http://localhost:5000")


def test_config_show_human_readable(ctx: TestContext) -> None:
    """config show 人类可读输出"""
    ctx.cli("config", "set-server", "lab", "http://192.168.1.20:5000")
    ctx.cli("config", "use", "lab")

    result = ctx.cli("config", "show")
    assert result.ok
    assert_in(result.stdout, "profile:")
    assert_in(result.stdout, "server:")
    assert_in(result.stdout, "http://192.168.1.20:5000")


def test_config_multiple_profiles(ctx: TestContext) -> None:
    """config 管理多个 profile"""
    ctx.cli("config", "set-server", "lab", "http://192.168.1.20:5000")
    ctx.cli("config", "set-token", "lab", "lab-token")
    ctx.cli("config", "set-server", "dev", "http://localhost:5000")
    ctx.cli("config", "set-token", "dev", "dev-token")

    result_lab = ctx.cli("config", "show", "lab", "--show-token", "--json")
    assert_eq(result_lab.json_data["data"]["server"], "http://192.168.1.20:5000")
    assert_eq(result_lab.json_data["data"]["token"], "lab-token")

    result_dev = ctx.cli("config", "show", "dev", "--show-token", "--json")
    assert_eq(result_dev.json_data["data"]["server"], "http://localhost:5000")
    assert_eq(result_dev.json_data["data"]["token"], "dev-token")
