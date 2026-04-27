# Components Inventory CLI 命令设计文档

本文档定义 Components Inventory 远程 CLI 的命令形态、参数约定、输出格式、错误码、API 映射和后续扩展方向，便于后续开发 CLI、Python SDK、AI 接入、NFC 工具、EDA 脚本和扫码枪集成。

相关设计背景见 `docs/cli-automation-prompt.md`。

## 1. 定位

CLI 是局域网远程自动化客户端，不直接读取或写入远程服务器上的 `data/inventory.db`。所有读写操作应通过 Flask HTTP API 完成，以复用服务端的库存日志、格子占用、自动合并、BOM 扣减和文件管理规则。

建议目标架构：

```text
Flask Server / SQLite
        ↑
    HTTP API
        ↑
Python Client SDK
        ↑
CLI / AI / EDA / NFC / 扫码枪 / 自动化脚本
```

第一版命令可以通过以下方式运行：

```bash
python inventory_cli.py ...
```

后续包化后可以注册为：

```bash
inventory ...
```

下文统一使用 `inventory` 表示 CLI 命令。

## 2. 全局约定

### 2.1 全局参数

所有命令都应支持以下全局参数：

| 参数 | 说明 |
| --- | --- |
| `--server <url>` | 服务器地址，例如 `http://192.168.1.20:5000` |
| `--token <token>` | API Token，作为 `Authorization: Bearer <token>` 发送 |
| `--profile <name>` | 使用已保存的连接配置 |
| `--json` | 输出机器可读 JSON |
| `--pretty` | JSON 缩进格式化输出 |
| `--quiet` | 减少人类友好提示，只输出关键结果 |
| `--timeout <seconds>` | HTTP 请求超时，默认建议 30 秒 |
| `--verbose` | 输出调试信息，包含请求路径和错误细节 |

参数优先级建议：

```text
命令行参数 > 环境变量 > profile 配置 > 默认值
```

建议支持的环境变量：

| 环境变量 | 说明 |
| --- | --- |
| `INVENTORY_SERVER` | 默认服务器地址 |
| `INVENTORY_TOKEN` | 默认 API Token |
| `INVENTORY_PROFILE` | 默认 profile 名称 |

### 2.2 Profile 配置

CLI 应支持保存多个服务器配置，方便不同电脑或不同环境切换。

推荐配置文件路径：

```text
~/.components-inventory/config.json
```

Windows 下使用 Python 标准库获取用户目录，不要写死 `C:\Users\...`。

配置示例：

```json
{
  "default_profile": "lab",
  "profiles": {
    "lab": {
      "server": "http://192.168.1.20:5000",
      "token": "change-me"
    },
    "dev": {
      "server": "http://localhost:5000",
      "token": ""
    }
  }
}
```

### 2.3 HTTP Header

CLI 请求建议携带：

```http
Authorization: Bearer <token>
Accept: application/json
Content-Type: application/json
X-Inventory-Source: inventory-cli
X-Inventory-Actor: cli@<hostname>
```

上传文件接口使用 `multipart/form-data`，不要手动覆盖 multipart boundary。

### 2.4 响应格式

服务端 JSON API 继续沿用当前格式：

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

CLI 在 `--json` 模式下应尽量原样保留这个结构。对于网络错误、参数错误等客户端本地错误，也应输出同构 JSON：

```json
{
  "code": 1,
  "data": null,
  "message": "network error: connection refused"
}
```

### 2.5 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 服务端业务错误，例如库存不足、记录不存在 |
| `2` | CLI 参数错误 |
| `3` | 网络错误或服务不可达 |
| `4` | 认证失败 |
| `5` | 本地文件或 IO 错误 |
| `6` | 未预期错误 |

### 2.6 输出模式

默认输出面向人类阅读，`--json` 输出面向脚本和 AI。

人类输出示例：

```text
ID  Name        Value  Package  Qty  Location
12  Resistor    10k    0603     200  R-Box / 1-2
```

JSON 输出示例：

```bash
inventory components get 12 --json
```

```json
{
  "code": 0,
  "data": {
    "id": 12,
    "name": "Resistor",
    "nominal_value": "10k",
    "package": "0603",
    "quantity": 200
  },
  "message": "ok"
}
```

## 3. 命令总览

建议命令树：

```text
inventory
  config
  ping
  stats
  categories
  cabinets
  boxes
  components
  stock
  images
  documents
  qr
  bom
  nfc
  map
  scan
```

实现优先级：

| 阶段 | 范围 |
| --- | --- |
| P0 | `config`、`ping`、`stats`、`components list/get/create/update/delete`、`boxes list/get/grid`、`stock in/out/logs` |
| P1 | `categories`、`cabinets`、`components import/export`、`documents`、`images`、`qr` |
| P2 | `bom import/consume/export-picklist`、`nfc`、`map` |
| P3 | `scan`、EDA 格式适配、AI/MCP 专用工具 |

## 4. Config 命令

### 4.1 `config set-server`

保存 profile 的服务器地址。

```bash
inventory config set-server <profile> <url>
```

示例：

```bash
inventory config set-server lab http://192.168.1.20:5000
```

本地操作，不调用服务端 API。

### 4.2 `config set-token`

保存 profile 的 API Token。

```bash
inventory config set-token <profile> <token>
```

示例：

```bash
inventory config set-token lab change-me
```

注意：第一版可以明文保存在用户配置文件中；后续可接入系统凭据管理器。

### 4.3 `config use`

设置默认 profile。

```bash
inventory config use <profile>
```

### 4.4 `config show`

查看配置。默认隐藏 token。

```bash
inventory config show [profile] [--show-token]
```

示例输出：

```json
{
  "code": 0,
  "data": {
    "profile": "lab",
    "server": "http://192.168.1.20:5000",
    "token": "***"
  },
  "message": "ok"
}
```

## 5. 连接与统计命令

### 5.1 `ping`

检查服务器是否可访问。

```bash
inventory ping
```

建议 API：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/stats` |

当前没有专用 ping API，可先用 `/api/stats` 实现。后续可新增 `/api/ping`。

### 5.2 `stats`

获取首页统计信息。

```bash
inventory stats [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/stats` |

示例：

```bash
inventory --profile lab stats --json
```

## 6. Categories 命令

### 6.1 `categories list`

列出分类。

```bash
inventory categories list [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/categories` |

### 6.2 `categories create`

新增分类。

```bash
inventory categories create --name <name> [--parent-id <id>] [--icon <icon>]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/categories` |

请求体：

```json
{
  "name": "Resistor",
  "parent_id": null,
  "icon": null
}
```

## 7. Cabinets 命令

柜体是当前代码中已有、但项目概览可能未完全同步的新能力。CLI 应将其作为 P1 能力。

### 7.1 `cabinets list`

```bash
inventory cabinets list [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/cabinets` |

### 7.2 `cabinets get`

```bash
inventory cabinets get <cabinet-id> [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/cabinets/<cabinet_id>` |

### 7.3 `cabinets create`

```bash
inventory cabinets create --name <name> [--description <text>] [--color <hex>]
```

请求体：

```json
{
  "name": "Main Cabinet",
  "description": "Left wall",
  "color": "#8b9aae"
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/cabinets` |

### 7.4 `cabinets update`

```bash
inventory cabinets update <cabinet-id> [--name <name>] [--description <text>] [--color <hex>]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `PUT` | `/api/cabinets/<cabinet_id>` |

### 7.5 `cabinets delete`

```bash
inventory cabinets delete <cabinet-id> [--yes]
```

CLI 默认应要求确认；脚本模式使用 `--yes`。

API 映射：

| 方法 | 路径 |
| --- | --- |
| `DELETE` | `/api/cabinets/<cabinet_id>` |

### 7.6 `cabinets layout`

更新地图坐标。

```bash
inventory cabinets layout <cabinet-id> --x <number> --y <number>
```

请求体：

```json
{
  "position_x": 100,
  "position_y": 220
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `PUT` | `/api/cabinets/<cabinet_id>/layout` |

## 8. Boxes 命令

### 8.1 `boxes list`

列出收纳盒。

```bash
inventory boxes list [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/boxes` |

### 8.2 `boxes get`

获取收纳盒详情。

```bash
inventory boxes get <box-id> [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/boxes/<box_id>` |

### 8.3 `boxes create`

创建收纳盒。创建后服务端会自动生成格子。

```bash
inventory boxes create --name <name> --rows <n> --cols <n> \
  [--description <text>] [--color <hex>] [--cabinet-id <id>] [--cabinet-slot <n>]
```

请求体：

```json
{
  "name": "R-0603",
  "rows": 5,
  "cols": 8,
  "description": "0603 resistors",
  "color": "#84b59b",
  "cabinet_id": 1,
  "cabinet_slot": 2
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/boxes` |

### 8.4 `boxes update`

更新收纳盒。

```bash
inventory boxes update <box-id> [--name <name>] [--rows <n>] [--cols <n>] \
  [--description <text>] [--color <hex>] [--cabinet-id <id>] [--cabinet-slot <n>]
```

注意：如果缩小行列会删除已有格子，且被占用的格子超出新范围，服务端应拒绝。

API 映射：

| 方法 | 路径 |
| --- | --- |
| `PUT` | `/api/boxes/<box_id>` |

### 8.5 `boxes delete`

删除收纳盒。

```bash
inventory boxes delete <box-id> [--yes]
```

CLI 默认应要求确认。若盒子中仍有元器件，服务端会拒绝删除。

API 映射：

| 方法 | 路径 |
| --- | --- |
| `DELETE` | `/api/boxes/<box_id>` |

### 8.6 `boxes grid`

查看收纳盒格子和占用情况。

```bash
inventory boxes grid <box-id> [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/boxes/<box_id>/grid` |

### 8.7 `boxes layout`

更新盒子地图坐标。

```bash
inventory boxes layout <box-id> --x <number> --y <number>
```

请求体：

```json
{
  "position_x": 120,
  "position_y": 260
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `PUT` | `/api/boxes/<box_id>/layout` |

## 9. Components 命令

### 9.1 `components list`

分页列出元器件。

```bash
inventory components list [--keyword <text>] [--category-id <id>] [--box-id <id>] \
  [--tag <tag>] [--low-stock] [--page <n>] [--page-size <n>] [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/components` |

Query 参数：

| 参数 | 说明 |
| --- | --- |
| `keyword` | 搜索名称、型号、描述、厂商、标称值 |
| `category_id` | 按分类筛选 |
| `box_id` | 按盒子筛选 |
| `tag` | 按标签筛选 |
| `low_stock` | `1` 表示只看低库存 |
| `page` | 页码，默认 1 |
| `page_size` | 每页数量，服务端最大 500 |

示例：

```bash
inventory components list --keyword 10k --package 0603 --json
```

注意：当前服务端 `list_components` 尚不支持 `package` query。若要支持该参数，需要先扩展后端筛选逻辑；CLI 第一版不要伪造本地筛选，避免分页结果不准确。

### 9.2 `components get`

获取元器件详情。

```bash
inventory components get <component-id> [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/components/<component_id>` |

详情包含图片、文档、最近库存日志。

### 9.3 `components create`

新增元器件。

```bash
inventory components create --name <name> \
  [--category-id <id>] [--model <text>] [--package <text>] [--value <text>] \
  [--voltage <text>] [--current <text>] [--power <text>] [--tolerance <text>] \
  [--material <text>] [--manufacturer <text>] [--quantity <n>] [--min-stock <n>] \
  [--box-id <id>] [--compartment-id <id>] [--cell-row <n>] [--cell-col <n>] \
  [--description <text>] [--tag <tag>]... [--extra-spec key=value]...
```

请求体字段：

```json
{
  "name": "Resistor",
  "category_id": 1,
  "model": "",
  "package": "0603",
  "nominal_value": "10k",
  "voltage_rating": "",
  "current_rating": "",
  "power_rating": "1/10W",
  "tolerance": "1%",
  "material_type": "Thick Film",
  "manufacturer": "Yageo",
  "quantity": 100,
  "min_stock": 20,
  "box_id": 1,
  "cell_row": 1,
  "cell_col": 2,
  "description": "",
  "tags": ["resistor", "0603"],
  "extra_specs": {
    "mpn": "RC0603FR-0710KL"
  }
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/components` |

服务端行为：

- `name` 必填。
- `quantity` 默认为 0。
- 可通过 `box_id + cell_row + cell_col` 或 `compartment_id` 指定位置。
- 新增时可能与已有相同规格元器件自动合并库存。
- 初始数量不为 0 时会写库存日志。

### 9.4 `components update`

更新元器件。

```bash
inventory components update <component-id> \
  [--name <name>] [--category-id <id>] [--model <text>] [--package <text>] \
  [--value <text>] [--quantity <n>] [--min-stock <n>] [--box-id <id>] \
  [--compartment-id <id>] [--cell-row <n>] [--cell-col <n>] \
  [--description <text>] [--tag <tag>]... [--replace-tags]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `PUT` | `/api/components/<component_id>` |

注意：

- 直接修改 `quantity` 会产生 `adjust` 库存日志。
- 常规入库/出库应优先使用 `stock in/out`。
- 如果传入 `tags`，服务端会同步标签；CLI 应明确 `--replace-tags` 或文档说明标签是覆盖行为。

### 9.5 `components delete`

删除元器件。

```bash
inventory components delete <component-id> [--yes]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `DELETE` | `/api/components/<component_id>` |

服务端会同时删除关联图片和文档文件。CLI 默认应要求确认。

### 9.6 `components import`

批量导入元器件 Excel。

```bash
inventory components import <xlsx-file> [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/components/import` |

请求格式：

```text
multipart/form-data
file=<xlsx-file>
```

注意：当前服务端方法名为 `parse_component_import`，文档中应以实际实现为准确认支持 `.xlsx`，不要在 CLI 端另行解析后写数据库。

### 9.7 `components export`

导出元器件 Excel。

```bash
inventory components export --output components_export.xlsx
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/components/export` |

响应是文件流，不是 JSON。CLI 应保存到 `--output` 指定路径。

### 9.8 `components qr`

获取单个元器件二维码 SVG。

```bash
inventory components qr <component-id> --output component-12.svg
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/components/<component_id>/qr.svg` |

### 9.9 `components qr-labels`

生成二维码标签打印页。

```bash
inventory components qr-labels --ids 1,2,3 --output labels.html
inventory components qr-labels --keyword 10k --page-size 200 --output labels.html
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/components/qr-labels` |

Query 参数：

| 参数 | 说明 |
| --- | --- |
| `ids` | 逗号分隔的元器件 ID 列表 |
| `keyword`、`category_id`、`box_id`、`tag`、`low_stock` | 与 `components list` 类似 |
| `page`、`page_size` | 分页参数 |

响应是 HTML，CLI 应保存到文件。

## 10. Stock 命令

### 10.1 `stock in`

入库。

```bash
inventory stock in <component-id> --quantity <n> [--reason <text>] [--json]
```

请求体：

```json
{
  "component_id": 12,
  "quantity": 50,
  "reason": "purchase"
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/stock/in` |

### 10.2 `stock out`

出库。

```bash
inventory stock out <component-id> --quantity <n> [--reason <text>] [--json]
```

请求体：

```json
{
  "component_id": 12,
  "quantity": 10,
  "reason": "prototype build"
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/stock/out` |

服务端会拒绝扣成负库存。

### 10.3 `stock logs`

查看库存日志。

```bash
inventory stock logs <component-id> [--page <n>] [--page-size <n>] [--json]
inventory stock logs 0 --page-size 50 --json
```

`component-id` 为 `0` 时表示查询全局最近库存日志。

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/stock/logs/<component_id>` |

Query 参数：

| 参数 | 说明 |
| --- | --- |
| `page` | 页码 |
| `page_size` | 每页数量，服务端最大 200 |

## 11. Images 命令

### 11.1 `images upload`

上传元器件图片。

```bash
inventory images upload --file <image-file> [--component-id <id>] [--primary] [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/images/upload` |

请求格式：

```text
multipart/form-data
file=<image-file>
component_id=<optional>
is_primary=true|false
```

服务端允许扩展名：

```text
.jpg .jpeg .png .gif .webp
```

### 11.2 `images delete`

删除图片记录和磁盘文件。

```bash
inventory images delete <image-id> [--yes]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `DELETE` | `/api/images/<image_id>` |

## 12. Documents 命令

### 12.1 `documents upload`

上传数据手册、表格、压缩包等文档。

```bash
inventory documents upload --file <document-file> [--component-id <id>] [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/documents/upload` |

请求格式：

```text
multipart/form-data
file=<document-file>
component_id=<optional>
```

服务端允许扩展名：

```text
.pdf .txt .md .csv .xls .xlsx .doc .docx .ppt .pptx .zip
```

### 12.2 `documents delete`

删除文档记录和磁盘文件。

```bash
inventory documents delete <document-id> [--yes]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `DELETE` | `/api/documents/<document_id>` |

## 13. BOM 命令

BOM 命令是自动化接入 EDA 工具的核心。第一版应复用服务端已有 CSV 解析和 BOM 扣减逻辑，不在 CLI 端重写匹配规则。

### 13.1 `bom import`

导入 CSV BOM 并获取匹配结果。

```bash
inventory bom import <csv-file> [--json] [--output match.json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/bom/import` |

请求格式：

```text
multipart/form-data
file=<csv-file>
```

若指定 `--output`，CLI 将服务端返回的 `data` 或完整响应写入文件。建议默认写完整响应，使用 `--data-only` 时只写 `data`。

### 13.2 `bom consume`

按 BOM 匹配结果执行领料扣减。

```bash
inventory bom consume <match-json> [--reason <text>] [--yes] [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/bom/consume` |

请求体结构应与服务端 `repo.consume_bom()` 兼容：

```json
{
  "project_name": "my-board",
  "reason": "BOM stock-out: my-board",
  "items": [
    {
      "comment": "10k",
      "quantity_needed": 2,
      "matched": {
        "id": 12,
        "name": "Resistor"
      }
    }
  ]
}
```

CLI 默认应在真正扣库存前要求确认；脚本模式使用 `--yes`。

### 13.3 `bom consume --dry-run`

预演 BOM 扣减。

```bash
inventory bom consume <match-json> --dry-run --json
```

当前服务端没有专用 dry-run API。实现选择：

1. P2 阶段优先新增服务端 dry-run 能力。
2. 在新增服务端能力前，CLI 不应通过本地推算假装 dry-run 成功。

建议服务端新增：

```text
POST /api/bom/consume/preview
```

或在 `/api/bom/consume` 请求体中支持：

```json
{
  "dry_run": true
}
```

### 13.4 `bom export-picklist`

导出 picklist Excel。

```bash
inventory bom export-picklist <match-json> --output bom_picklist.xlsx
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/bom/export` |

响应是文件流。

### 13.5 EDA 格式参数

后续可以扩展：

```bash
inventory bom import board.csv --format auto|kicad|altium|lcsc
```

当前服务端已有表头别名兼容逻辑，第一版可以只支持 `--format auto`。

## 14. NFC 命令

### 14.1 `nfc bind`

绑定 NFC UID 到收纳盒。

```bash
inventory nfc bind --box-id <id> --uid <uid> [--json]
```

请求体：

```json
{
  "box_id": 3,
  "uid": "04AABBCCDD"
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/nfc/bind` |

### 14.2 `nfc payload`

生成 NFC 写入内容。

```bash
inventory nfc payload --box-id <id> [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/nfc/write` |

返回内容包含：

```json
{
  "box_id": 3,
  "url": "http://server:5000/box/3",
  "text": "Box Name | 5x8 | 3/40"
}
```

注意：服务端当前使用 `SERVER_URL` 生成 URL。局域网部署时必须配置成手机可访问的地址，而不是 `localhost`。

### 14.3 `nfc lookup`

根据 UID 查询收纳盒。

```bash
inventory nfc lookup <uid> [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/nfc/lookup/<uid>` |

### 14.4 NFC 硬件读取

第一版不绑定具体 NFC 读卡器。后续可扩展：

```bash
inventory nfc read --driver pcsc
inventory nfc read --driver serial --port COM3
```

硬件读取层应作为 adapter，不应影响 HTTP Client 和普通 `nfc bind/lookup` 命令。

## 15. Map 命令

### 15.1 `map data`

获取地图视图数据。

```bash
inventory map data [--json]
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `GET` | `/api/map` |

### 15.2 `map search`

搜索地图中的盒子或元器件位置。

```bash
inventory map search <keyword> [--json]
```

请求体：

```json
{
  "keyword": "10k"
}
```

API 映射：

| 方法 | 路径 |
| --- | --- |
| `POST` | `/api/map/search` |

## 16. Scan 命令

扫码枪接入建议分阶段实现。很多扫码枪默认是键盘输入模式，因此第一版可以只支持手动传入 code。

### 16.1 `scan lookup`

根据扫码内容查询元器件或盒子。

```bash
inventory scan lookup --code <text> [--json]
```

当前服务端没有通用 code lookup API。实现建议：

1. 若 code 是元器件详情 URL，解析其中的 `component=<id>` 或 `/components/<id>`。
2. 若 code 是 NFC 盒子 URL，解析 `/box/<id>`。
3. 若 code 是纯数字，可按元器件 ID 尝试查询。
4. 长期建议新增 `component_codes` 表和 `/api/codes/lookup/<code>` API。

### 16.2 `scan ingest`

交互式读取键盘扫码枪输入。

```bash
inventory scan ingest --interactive
```

建议行为：

```text
Scan code > 12
Found component: Resistor 10k 0603, qty=200
Action [in/out/open/skip] >
```

### 16.3 `scan listen`

串口扫码枪监听，后续规划。

```bash
inventory scan listen --port COM3 [--baud 9600]
```

不建议 P0/P1 实现，除非已确定硬件型号。

## 17. AI/MCP 接入命令

CLI 不应让 AI 解析人类友好输出。AI 应优先使用：

1. `InventoryClient` Python SDK。
2. CLI 的 `--json` 输出。
3. 后续 MCP Server。

可预留命令：

```bash
inventory ai suggest-tags <component-id> --json
inventory ai normalize --name "10K resistor 0603 1%" --json
inventory ai purchase-plan --low-stock --json
```

这些命令不建议第一阶段实现。涉及写操作时，应遵循：

```text
dry-run -> 用户确认 -> commit
```

## 18. 文件下载命令约定

对 Excel、SVG、HTML 等非 JSON 响应，CLI 必须要求或推导输出路径。

推荐参数：

| 参数 | 说明 |
| --- | --- |
| `--output <path>` | 保存路径 |
| `--overwrite` | 允许覆盖已有文件 |

如果目标文件已存在且未指定 `--overwrite`，应返回退出码 `5`。

示例：

```bash
inventory components export --output components_export.xlsx
inventory components qr 12 --output component-12.svg
inventory bom export-picklist match.json --output picklist.xlsx
```

## 19. 批量写操作确认约定

以下命令默认要求确认：

- `components delete`
- `boxes delete`
- `cabinets delete`
- `images delete`
- `documents delete`
- `bom consume`
- 未来任何批量更新或批量删除

脚本可使用：

```bash
--yes
```

若在非交互环境中缺少 `--yes`，CLI 应失败并提示，而不是阻塞等待输入。

## 20. 建议的 Client SDK 方法

CLI 应尽量薄，HTTP 细节放在 `InventoryClient`。

建议方法：

```python
class InventoryClient:
    def stats(self): ...
    def list_categories(self): ...
    def create_category(self, payload): ...
    def list_cabinets(self): ...
    def get_cabinet(self, cabinet_id): ...
    def create_cabinet(self, payload): ...
    def update_cabinet(self, cabinet_id, payload): ...
    def delete_cabinet(self, cabinet_id): ...
    def list_boxes(self): ...
    def get_box(self, box_id): ...
    def create_box(self, payload): ...
    def update_box(self, box_id, payload): ...
    def delete_box(self, box_id): ...
    def get_box_grid(self, box_id): ...
    def list_components(self, **filters): ...
    def get_component(self, component_id): ...
    def create_component(self, payload): ...
    def update_component(self, component_id, payload): ...
    def delete_component(self, component_id): ...
    def stock_in(self, component_id, quantity, reason=None): ...
    def stock_out(self, component_id, quantity, reason=None): ...
    def stock_logs(self, component_id, page=1, page_size=20): ...
    def upload_image(self, path, component_id=None, is_primary=False): ...
    def upload_document(self, path, component_id=None): ...
    def import_bom(self, path): ...
    def consume_bom(self, payload): ...
    def nfc_bind(self, box_id, uid): ...
    def nfc_payload(self, box_id): ...
    def nfc_lookup(self, uid): ...
```

## 21. P0 最小可交付清单

第一阶段建议只做这些，先让远程自动化跑起来：

```text
config set-server
config set-token
config use
config show
ping
stats
components list
components get
components create
components update
components delete
boxes list
boxes get
boxes grid
stock in
stock out
stock logs
```

P0 验收示例：

```bash
inventory config set-server lab http://192.168.1.20:5000
inventory config set-token lab change-me
inventory config use lab
inventory ping
inventory stats --json
inventory components list --keyword 10k --json
inventory components create --name "Resistor" --value "10k" --package "0603" --quantity 100 --json
inventory stock out 1 --quantity 5 --reason "test build" --json
inventory boxes grid 1 --json
```

## 22. 后端缺口清单

为了让 CLI 更完整，后续建议补充：

1. `GET /api/ping`：轻量健康检查。
2. 更完整的管理界面鉴权。目前已支持 CLI 设备 token 和 `API_TOKEN`，但隐藏配置入口本身不是管理员登录系统。
3. `POST /api/bom/consume/preview` 或 `dry_run` 参数。
4. `GET /api/documents/<id>` 或文档列表接口，如果需要独立管理文档。
5. `component_codes` 表和 `/api/codes/lookup/<code>`，用于扫码枪和外部条码。
6. 更细的组件筛选参数，例如 `package`、`value`、`manufacturer`、`model`。
7. 服务端审计字段或日志增强，记录 `X-Inventory-Actor` 和 `X-Inventory-Source`。

## 23. Device Token Management

The current implementation supports device-specific automation tokens in addition to
the optional `API_TOKEN` environment variable.

### Generate a token from the web UI

1. Open the Components Inventory web app.
2. Click the upper-left `CI` brand mark 5 times.
3. In the automation settings dialog, enter a token name such as `lab-pc`,
   `scanner-1`, or `eda-script`.
4. Click generate and copy the token immediately. The full token is shown only once.
5. Configure the CLI profile:

```bash
python inventory_cli.py config set-token lab <generated-token>
```

Generated tokens are stored in the `api_tokens` SQLite table as SHA-256 hashes. The UI
lists only active tokens and shows the token name, prefix, created time, and last-used
time. Deleting a token soft-deletes it and invalidates it immediately.

### Authentication behavior

- If `API_TOKEN` is set, CLI automation requests may use either the environment token
  or a generated device token.
- If `API_TOKEN` is not set and no device token has ever been created, CLI automation
  requests are allowed for development convenience.
- After the first device token is created, `inventory-cli` requests must include a
  valid Bearer token.
- If all generated tokens are deleted, the token requirement remains enabled. Create a
  new token from the hidden settings dialog to authorize new devices.
- Browser page requests are kept compatible and are not required to send CLI tokens.

### Token API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/settings/tokens` | List active generated tokens without token plaintext |
| `POST` | `/api/settings/tokens` | Generate a new device token with JSON body `{ "name": "lab-pc" }` |
| `DELETE` | `/api/settings/tokens/<id>` | Revoke a generated device token |

Automation write requests log the token name, actor header, HTTP method, path, and
status to the backend log so different devices can be distinguished later.

## 24. 文档维护规则

实现 CLI 时，如果命令、参数或输出发生变化，请同步更新本文档。尤其是：

- 新增命令。
- 参数命名变化。
- JSON 输出结构变化。
- API 路径变化。
- 新增需要确认的危险操作。
- 新增扫码、NFC、EDA 或 AI 相关行为。
