# CLI 集成测试

Components Inventory CLI 的集成测试套件，通过子进程调用 `inventory_cli.py`，验证各命令的功能、输出格式和错误处理。

## 前置条件

1. Python 3.10+
2. Flask 服务已启动（`python app.py`）
3. 如果服务启用了 Token 鉴权，需要准备好有效的 API Token

## 快速开始

```bash
# 运行全部测试（默认连接 localhost:5000，无 Token）
python text/cli/test_cli.py

# 指定服务器地址和 Token
python text/cli/test_cli.py --server http://192.168.1.20:5000 --token ci_xxxx

# 只查看有哪些测试用例
python text/cli/test_cli.py --list
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--server <url>` | 服务器地址，默认 `http://localhost:5000` |
| `--token <token>` | API Token，服务端开启鉴权时必传 |
| `--group <name>` | 只运行指定分组，可重复使用 |
| `--list` | 列出所有测试用例名称，不实际运行 |
| `--verbose`, `-v` | 显示详细输出 |

## 测试分组

| 分组名 | 覆盖范围 | 用例数 |
|--------|----------|--------|
| `config` | `config set-server/set-token/use/show` | 9 |
| `connection` | `ping`, `stats` | 6 |
| `components` | `components list/get/create/update/delete` | 21 |
| `boxes` | `boxes list/get/grid` | 8 |
| `stock` | `stock in/out/logs` | 10 |
| `options` | 全局选项 `--json/--pretty/--quiet/--server` | 11 |
| `errors` | 参数错误、网络错误、鉴权失败等 | 14 |

### 按分组运行

```bash
# 只测试 config 命令
python text/cli/test_cli.py --group config

# 测试多个分组
python text/cli/test_cli.py --group components --group stock

# 不需要服务器的分组（config 和 errors）可以离线运行
python text/cli/test_cli.py --group config --group errors
```

## 文件结构

```
text/cli/
├── README.md           # 本文档
├── test_cli.py         # 测试入口，参数解析和调度
├── runner.py           # 测试基础设施：CLI 执行器、断言工具、TestSuite
├── test_config.py      # config 命令测试
├── test_connection.py  # ping / stats 测试
├── test_components.py  # components CRUD 测试
├── test_boxes.py       # boxes 测试
├── test_stock.py       # stock 入库/出库/日志测试
├── test_options.py     # 全局选项测试
└── test_errors.py      # 错误处理和边界情况测试
```

## 输出示例

```
  PASS  text.cli.test_config.test_config_set_server
  PASS  text.cli.test_config.test_config_set_token
  PASS  text.cli.test_connection.test_ping
  FAIL  text.cli.test_components.test_components_create  (KeyError: 'name')
  SKIP  text.cli.test_boxes.test_boxes_grid  (no boxes in database)

============================================================
  FAILED 1, PASSED 77, TOTAL 79  (152.2s)
============================================================
```

- **PASS** — 测试通过（绿色）
- **FAIL** — 测试失败，括号内为错误原因（红色）
- **SKIP** — 测试跳过，数据库无数据时部分测试会自动跳过（黄色）

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 全部通过 |
| 1 | 有测试失败 |

## 工作原理

1. **独立配置**：测试运行时使用独立的临时目录存放 CLI 配置（`~/.components-inventory-test-config/`），不会污染你的真实配置
2. **子进程调用**：每个测试通过 `subprocess` 调用 `inventory_cli.py`，模拟真实使用场景
3. **共享状态**：同一分组内的测试按字母序执行，通过 `ctx.shared` 字典传递数据（如创建元器件后保存 ID 给后续 get/update/delete 测试使用）
4. **测试清理**：运行结束后自动清理临时配置目录

## 编写新测试

在 `text/cli/` 下新建或修改测试文件，函数以 `test_` 开头即可被自动发现：

```python
"""新功能测试"""
from __future__ import annotations
from text.cli.runner import TestContext, assert_eq, assert_json_code

def test_new_feature(ctx: TestContext) -> None:
    """测试新功能"""
    result = ctx.cli("new-command", "--json")
    assert_json_code(result, 0)
    assert_eq(result.json_data["data"]["field"], "expected_value")
```

可用的断言工具（`runner.py` 中定义）：

| 函数 | 用途 |
|------|------|
| `assert_eq(actual, expected)` | 相等断言 |
| `assert_in(haystack, needle)` | 包含断言 |
| `assert_not_in(haystack, needle)` | 不包含断言 |
| `assert_json_code(result, code)` | 验证 JSON 响应 code |
| `assert_json_has(result, *keys)` | 验证 JSON data 包含指定 key |
| `assert_exit_code(result, code)` | 验证退出码 |

如果需要在 `test_cli.py` 中注册新的分组，编辑 `TEST_GROUPS` 字典即可。
