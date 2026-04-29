"""
components 命令测试：list, get, create, update, delete
"""

from __future__ import annotations

import json
import time

from text.cli.runner import TestContext, assert_eq, assert_in, assert_json_code, assert_json_has, assert_not_in


def test_components_list(ctx: TestContext) -> None:
    """components list 列出元器件"""
    result = ctx.cli("components", "list", "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert "items" in data, "should have 'items' in data"
    assert isinstance(data["items"], list), "items should be a list"


def test_components_list_human(ctx: TestContext) -> None:
    """components list 人类可读表格输出"""
    result = ctx.cli("components", "list")
    assert result.ok
    # 表格输出应包含表头关键词
    if len(result.stdout) > 0:
        assert_in(result.stdout, "id")


def test_components_list_with_keyword(ctx: TestContext) -> None:
    """components list --keyword 搜索"""
    result = ctx.cli("components", "list", "--keyword", "resistor", "--json")
    assert_json_code(result, 0)
    assert isinstance(result.json_data["data"]["items"], list)


def test_components_list_with_page(ctx: TestContext) -> None:
    """components list --page --page-size 分页"""
    result = ctx.cli("components", "list", "--page", "1", "--page-size", "5", "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    items = data.get("items", [])
    assert len(items) <= 5, "should respect page-size"


def test_components_list_with_category(ctx: TestContext) -> None:
    """components list --category-id 按分类筛选"""
    result = ctx.cli("components", "list", "--category-id", "1", "--json")
    assert_json_code(result, 0)


def test_components_list_with_box(ctx: TestContext) -> None:
    """components list --box-id 按盒子筛选"""
    result = ctx.cli("components", "list", "--box-id", "1", "--json")
    assert_json_code(result, 0)


def test_components_list_low_stock(ctx: TestContext) -> None:
    """components list --low-stock 低库存筛选"""
    result = ctx.cli("components", "list", "--low-stock", "--json")
    assert_json_code(result, 0)


def test_components_list_with_tag(ctx: TestContext) -> None:
    """components list --tag 按标签筛选"""
    result = ctx.cli("components", "list", "--tag", "resistor", "--json")
    assert_json_code(result, 0)


def test_components_create(ctx: TestContext) -> None:
    """components create 创建元器件"""
    unique_name = f"Test-Resistor-CREATE-{int(time.time())}"
    result = ctx.cli(
        "components", "create",
        "--name", unique_name,
        "--value", "10k",
        "--package", "0603",
        "--quantity", "100",
        "--manufacturer", "Yageo",
        "--json",
    )
    assert_json_code(result, 0)
    data = result.json_data["data"]
    comp_id = data["id"]
    # create 只返回 {id, merged, quantity}，通过 get 验证完整字段
    get_result = ctx.cli("components", "get", str(comp_id), "--json")
    assert_eq(get_result.json_data["data"]["name"], unique_name)
    assert_eq(get_result.json_data["data"]["nominal_value"], "10k")
    assert_eq(get_result.json_data["data"]["package"], "0603")
    ctx.shared["created_component_id"] = comp_id


def test_components_create_with_tags(ctx: TestContext) -> None:
    """components create --tag 创建带标签的元器件"""
    result = ctx.cli(
        "components", "create",
        "--name", "Test-Capacitor-TAGS",
        "--value", "100nF",
        "--package", "0402",
        "--tag", "capacitor",
        "--tag", "mlcc",
        "--json",
    )
    assert_json_code(result, 0)
    comp_id = result.json_data["data"]["id"]
    # 通过 get 验证标签
    get_result = ctx.cli("components", "get", str(comp_id), "--json")
    get_data = get_result.json_data["data"]
    assert "tags" in get_data or "capacitor" in str(get_data)
    ctx.shared["tagged_component_id"] = comp_id


def test_components_create_with_extra_specs(ctx: TestContext) -> None:
    """components create --extra-spec 创建带额外参数的元器件"""
    result = ctx.cli(
        "components", "create",
        "--name", "Test-IC-SPEC",
        "--model", "STM32F103",
        "--extra-spec", "mpn=STM32F103C8T6",
        "--extra-spec", "core=Cortex-M3",
        "--json",
    )
    assert_json_code(result, 0)
    comp_id = result.json_data["data"]["id"]
    # 通过 get 验证 extra_specs（服务端存储为 JSON 字符串）
    get_result = ctx.cli("components", "get", str(comp_id), "--json")
    get_data = get_result.json_data["data"]
    assert "extra_specs" in get_data
    specs = get_data["extra_specs"]
    if isinstance(specs, str):
        specs = json.loads(specs)
    assert_eq(specs.get("mpn"), "STM32F103C8T6")
    assert_eq(specs.get("core"), "Cortex-M3")
    ctx.shared["spec_component_id"] = comp_id


def test_components_create_with_description(ctx: TestContext) -> None:
    """components create --description 创建带描述的元器件"""
    result = ctx.cli(
        "components", "create",
        "--name", "Test-LED-DESC",
        "--description", "Red LED 0805 package",
        "--quantity", "500",
        "--json",
    )
    assert_json_code(result, 0)
    comp_id = result.json_data["data"]["id"]
    # 通过 get 验证 description
    get_result = ctx.cli("components", "get", str(comp_id), "--json")
    assert_eq(get_result.json_data["data"]["description"], "Red LED 0805 package")
    ctx.shared["desc_component_id"] = comp_id


def test_components_get(ctx: TestContext) -> None:
    """components get 获取元器件详情"""
    comp_id = ctx.shared.get("created_component_id")
    if not comp_id:
        return
    result = ctx.cli("components", "get", str(comp_id), "--json")
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert_eq(data["id"], comp_id)
    # 名称以 Test-Resistor-CREATE 开头即可（后缀是时间戳）
    assert data["name"].startswith("Test-Resistor-CREATE"), f"unexpected name: {data['name']}"


def test_components_get_human(ctx: TestContext) -> None:
    """components get 人类可读输出"""
    comp_id = ctx.shared.get("created_component_id")
    if not comp_id:
        return
    result = ctx.cli("components", "get", str(comp_id))
    assert result.ok
    assert_in(result.stdout, "name:")
    assert_in(result.stdout, "Test-Resistor-CREATE")


def test_components_update(ctx: TestContext) -> None:
    """components update 更新元器件"""
    comp_id = ctx.shared.get("created_component_id")
    if not comp_id:
        return
    result = ctx.cli(
        "components", "update", str(comp_id),
        "--name", "Test-Resistor-UPDATED",
        "--quantity", "200",
        "--description", "Updated via CLI test",
        "--json",
    )
    assert_json_code(result, 0)
    data = result.json_data["data"]
    assert_eq(data["name"], "Test-Resistor-UPDATED")
    assert_eq(data["quantity"], 200)
    assert_eq(data["description"], "Updated via CLI test")


def test_components_update_partial(ctx: TestContext) -> None:
    """components update 只更新部分字段"""
    comp_id = ctx.shared.get("created_component_id")
    if not comp_id:
        return
    result = ctx.cli(
        "components", "update", str(comp_id),
        "--manufacturer", "Murata",
        "--json",
    )
    assert_json_code(result, 0)
    assert_eq(result.json_data["data"]["manufacturer"], "Murata")
    # name 不应被改变
    assert_eq(result.json_data["data"]["name"], "Test-Resistor-UPDATED")


def test_components_delete(ctx: TestContext) -> None:
    """components delete --yes 删除元器件"""
    # 先创建一个专门用于删除的元器件
    create_result = ctx.cli(
        "components", "create",
        "--name", "Test-TO-DELETE",
        "--quantity", "1",
        "--json",
    )
    comp_id = create_result.json_data["data"]["id"]

    result = ctx.cli("components", "delete", str(comp_id), "--yes", "--json")
    assert_json_code(result, 0)

    # 验证删除后 get 应该失败
    get_result = ctx.cli("components", "get", str(comp_id), "--json", expect_ok=False)
    assert not get_result.ok or get_result.json_data.get("code") != 0, "component should be deleted"


def test_components_get_nonexistent(ctx: TestContext) -> None:
    """components get 不存在的元器件"""
    result = ctx.cli("components", "get", "99999", "--json", expect_ok=False)
    assert not result.ok or result.json_data.get("code") != 0, "should fail for nonexistent component"


def test_components_list_pretty(ctx: TestContext) -> None:
    """components list --pretty 格式化输出"""
    result = ctx.cli("components", "list", "--pretty")
    assert_json_code(result, 0)
    assert_in(result.stdout, "\n")


def test_components_list_quiet(ctx: TestContext) -> None:
    """components list --quiet 安静模式"""
    result = ctx.cli("components", "list", "--quiet")
    assert result.ok


def test_components_create_minimal(ctx: TestContext) -> None:
    """components create 最小参数（只有 name）"""
    result = ctx.cli(
        "components", "create",
        "--name", "Test-Minimal",
        "--json",
    )
    assert_json_code(result, 0)
    data = result.json_data["data"]
    comp_id = data["id"]
    # create 返回 {id, merged, quantity}，quantity 未指定时默认为 0
    assert_eq(data["quantity"], 0, "default quantity should be 0")
    # 通过 get 验证 name
    get_result = ctx.cli("components", "get", str(comp_id), "--json")
    assert_eq(get_result.json_data["data"]["name"], "Test-Minimal")
    ctx.shared["minimal_component_id"] = comp_id
