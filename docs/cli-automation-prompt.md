# Components Inventory CLI 自动化接入实现 Prompt

你是一个资深 Python/Flask 工程师。请在阅读本仓库文档和代码后，为 Components Inventory 项目设计并实现一套面向局域网自动化接入的 CLI 工具与配套服务端能力。

## 背景

Components Inventory 是一个轻量级电子元器件库存管理 Web 应用。当前技术栈为 Flask、SQLite、原生 HTML/CSS/JavaScript、Alpine.js。核心代码集中在：

- `app.py`：Flask 入口、页面路由、API、导入导出、上传处理。
- `models.py`：SQLite 仓储层和主要业务逻辑。
- `init_db.py`：数据库 schema、索引、轻量迁移。
- `config.py`：路径、端口、上传限制等配置。
- `static/js/app.js`：前端主交互。

请先阅读 `docs/project-overview.md`，再检查当前代码，因为代码可能已经包含文档未同步的新能力，例如文档上传、柜体、二维码标签等。

## 总体目标

新增一套 CLI 工具，使局域网内其他电脑可以通过命令行操作库存系统，后续能够接入 AI、NFC、EDA 工具、扫码枪和批量维护脚本。

CLI 不应直接操作远程机器上的 SQLite 数据库。它应通过 HTTP API 调用 Flask 服务端，确保所有库存变更、格子占用、自动合并、日志记录等行为继续复用服务端业务规则。

目标架构：

```text
Flask Server / SQLite
        ↑
    HTTP API
        ↑
Python Client SDK
        ↑
CLI / AI工具 / EDA脚本 / NFC脚本 / 扫码枪脚本
```

## 设计原则

1. CLI 是远程客户端，不 import `app.py`，不直接写数据库。
2. 服务端继续作为唯一写入入口，业务规则放在服务端。
3. CLI 和后续 AI/MCP/脚本接入应共用一套 Python HTTP Client。
4. 所有自动化输出必须支持稳定 JSON。
5. 写操作要有清晰的确认机制，危险批量操作优先支持 `--dry-run`。
6. 局域网场景也要考虑基础安全，至少支持 API Token。
7. 尽量保持项目轻量，新增依赖要有明确理由。

## 建议目录结构

可根据当前仓库风格微调，但建议采用以下结构：

```text
inventory_client/
  __init__.py
  client.py        # HTTP SDK
  errors.py        # 客户端异常和错误映射
  config.py        # CLI profile 配置读写

inventory_cli.py   # CLI 入口

docs/
  cli-automation-prompt.md
```

如命令增长较多，可进一步拆分：

```text
cli/
  commands/
    components.py
    boxes.py
    stock.py
    bom.py
    nfc.py
    scan.py
```

## 服务端能力要求

### 1. API Token 认证

为自动化 API 增加基础认证能力。建议支持：

```http
Authorization: Bearer <token>
```

Token 可先通过环境变量配置，例如：

```text
API_TOKEN=change-me
```

如果未配置 token，可在开发模式下允许本机访问，但要在文档中明确说明生产或局域网长期运行时必须配置。

当前实现还支持数据库设备 token：

- 连续点击 Web 页面左上角 `div.brand-mark` 的 `CI` 标识 5 次，进入“自动化配置”弹窗。
- 可为不同设备或脚本填写 token 名称并生成 token，例如 `lab-pc`、`scanner-1`、`eda-script`。
- 明文 token 只显示一次，服务端仅保存 SHA-256 哈希。
- token 列表显示名称、前缀和最近使用时间。
- 删除 token 后立即失效；删除采用软删除，避免删掉最后一个 token 后 CLI 回到开放状态。

如果 `API_TOKEN` 已配置，CLI 可使用环境变量 token 或数据库设备 token。如果未配置 `API_TOKEN`，且已经创建过设备 token，则 `inventory-cli` 来源的请求必须携带有效 Bearer token。

不要破坏现有浏览器页面使用体验。认证逻辑应尽量只约束自动化请求，或提供兼容策略。

### 2. 响应格式

继续沿用现有 JSON 格式：

```json
{
  "code": 0,
  "data": {},
  "message": "ok"
}
```

失败格式：

```json
{
  "code": 1,
  "data": null,
  "message": "error message"
}
```

### 3. 自动化来源信息

CLI 请求建议携带来源头：

```http
X-Inventory-Actor: cli@hostname
X-Inventory-Source: inventory-cli
```

服务端日志可逐步记录这些信息，便于审计 AI、EDA、扫码枪等自动化操作。

## CLI 基础能力

CLI 命令建议叫 `inventory`，当前可先通过以下方式运行：

```bash
python inventory_cli.py ...
```

后续如果项目包化，再注册 console script。

### 全局参数

支持：

```bash
--server http://192.168.1.20:5000
--token <api-token>
--profile lab
--json
--pretty
--quiet
```

Profile 配置示例：

```bash
python inventory_cli.py config set-server lab http://192.168.1.20:5000
python inventory_cli.py config set-token lab <token>
python inventory_cli.py --profile lab stats --json
```

Profile 可保存在用户目录下，例如：

```text
~/.components-inventory/config.json
```

Windows 下应使用 Python 标准库获取用户目录，避免写死路径。

## 第一阶段命令范围

先实现高价值、低风险闭环：

```text
inventory
  config
    set-server <profile> <url>
    set-token <profile> <token>
    show [profile]

  stats

  components
    list
    get <id>
    create
    update <id>
    delete <id>

  boxes
    list
    get <id>
    grid <id>

  stock
    in <component-id>
    out <component-id>
    logs <component-id>
```

示例：

```bash
python inventory_cli.py --profile lab components list --keyword 10k --json
python inventory_cli.py --profile lab components get 123 --json
python inventory_cli.py --profile lab components create --name "Resistor" --value "10k" --package "0603" --quantity 100 --json
python inventory_cli.py --profile lab stock in 123 --quantity 50 --reason "purchase"
python inventory_cli.py --profile lab stock out 123 --quantity 10 --reason "prototype build"
python inventory_cli.py --profile lab boxes grid 1 --json
```

## 第二阶段命令范围

在第一阶段稳定后，再扩展自动化数据流：

```text
components
  import <file>
  export --output <file>

bom
  import <csv>
  match <csv>
  consume <match-json> --dry-run
  consume <match-json> --yes
  export-picklist <match-json> --output <file>

nfc
  payload --box-id <id>
  bind --box-id <id> --uid <uid>
  lookup <uid>

scan
  lookup --code <code>
  ingest --interactive

documents
  upload --component-id <id> --file <path>
  delete <document-id>
```

## 后续 AI 接入方向

不要让 AI 直接解析人类友好文本输出。应让 AI 使用以下能力之一：

1. 调用同一套 `InventoryClient`。
2. 调用 CLI 的 `--json` 输出。
3. 后续新增 MCP Server，共用 `InventoryClient`。

AI 写操作建议默认分两步：

```text
dry-run -> 用户确认 -> commit
```

优先支持的 AI 场景：

- 根据 BOM 匹配库存候选。
- 归一化封装和值，例如 `4.7uF 0603`。
- 推荐分类和标签。
- 查找低库存并生成采购建议。
- 生成 picklist 或盘点清单。

## NFC、EDA、扫码枪接入建议

### NFC

第一版只要求支持手动 UID：

```bash
inventory nfc bind --box-id 3 --uid 04AABBCCDD
inventory nfc payload --box-id 3
inventory nfc lookup 04AABBCCDD
```

后续再根据具体读卡器支持 PC/SC、串口或厂商 SDK。

### EDA/BOM

优先支持 CSV BOM。后续可加：

```bash
--format auto|kicad|altium|lcsc
```

不同 EDA 的表头兼容逻辑应复用或抽离当前 `app.py` 中的 BOM 解析能力，避免 CLI 和 Web 行为分叉。

### 扫码枪

第一版支持键盘输入模式或手动传 code。后续串口扫码枪可加：

```bash
inventory scan listen --port COM3
```

如要长期支持外部条码、二维码、厂商料号、LCSC 编号，建议新增 `component_codes` 表，而不是只依赖 `components.id`。

## 错误和退出码

CLI 应稳定返回退出码：

```text
0 成功
1 业务错误
2 参数错误
3 网络或服务不可达
4 认证失败
5 文件或 IO 错误
6 未预期错误
```

JSON 错误输出示例：

```json
{
  "code": 1,
  "data": null,
  "message": "component not found"
}
```

## 测试建议

至少覆盖：

1. Client 正确拼接 URL、headers、query params。
2. Client 正确处理成功响应、业务错误、HTTP 错误、网络错误。
3. CLI 参数解析和 JSON 输出。
4. `stock in/out` 的请求 payload。
5. Profile 配置读写。

如果当前项目还没有测试框架，可先添加轻量单元测试；不要为了 CLI 第一版大规模重构现有代码。

## 实施顺序建议

1. 阅读 `docs/project-overview.md` 和相关代码。
2. 盘点现有 API，确认第一阶段命令需要的接口是否齐全。
3. 增加 `InventoryClient`。
4. 增加 `inventory_cli.py` 和 profile 配置。
5. 实现 `stats/components/boxes/stock` 第一阶段命令。
6. 增加基础 API Token 支持。
7. 补充 README 或 docs 中的 CLI 使用说明。
8. 运行基础验证，确保不影响现有 Web 页面。

## 验收标准

第一阶段完成后，至少应满足：

- 局域网另一台机器可以通过 `--server` 调用库存系统。
- CLI 支持 profile 保存 server 和 token。
- `components list/get/create/update/delete` 可用。
- `stock in/out/logs` 可用。
- `boxes list/get/grid` 可用。
- 所有命令支持 `--json`。
- 认证失败、网络失败、业务失败有稳定错误输出和退出码。
- 不直接访问远程 SQLite。
- 不破坏现有 Web UI 和 API 行为。
