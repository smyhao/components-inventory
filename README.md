# Components Inventory / 电子元器件库存管理系统

一个轻量级的电子元器件库存管理 Web 应用，支持收纳盒网格化管理、BOM 匹配领料、NFC 标签绑定、条码扫描等功能。

## 功能特性

- **元器件管理** — 增删改查、多条件搜索、标签、图片、规格参数（标称值/耐压/封装/精度等）
- **收纳盒管理** — 行列网格布局、格子占用状态可视化、拖拽排列
- **库存管理** — 入库/出库、库存变更日志、低库存预警
- **BOM 管理** — 导入 CSV BOM 文件、自动匹配库存元器件、领料出库、导出 Picklist
- **Excel 导入/导出** — 批量导入元器件（xlsx）、导出元器件清单
- **NFC 功能** — NFC 标签绑定收纳盒、手机扫码直达盒子详情
- **地图视图** — 可视化展示收纳盒位置、搜索元器件快速定位
- **数据统计** — 总览面板（元器件数/总量/低库存/分类统计）

## 快速开始

### 环境要求

- Python 3.10+
- 现代浏览器（Chrome / Firefox / Edge）

### 安装

```bash
git clone https://github.com/<your-username>/components-inventory.git
cd components-inventory

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 配置

复制环境变量模板并按需修改：

```bash
cp .env.example .env
```

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `5000` | 监听端口 |
| `SERVER_URL` | `http://localhost:5000` | 服务器外部访问地址（用于 NFC 链接生成） |
| `SECRET_KEY` | — | Flask 密钥（生产环境务必修改） |
| `API_TOKEN` | 空 | 可选的部署级自动化 Bearer token |
| `API_TOKEN_REQUIRE_ALL` | `false` | 是否要求所有 `/api` 请求都携带 token |

### 运行

```bash
python app.py
```

访问 `http://localhost:5000` 即可使用。

## CLI automation

The first CLI version can be run directly from the repository:

```bash
python inventory_cli.py config set-server lab http://192.168.1.20:5000
python inventory_cli.py config set-token lab change-me
python inventory_cli.py --profile lab stats --json
python inventory_cli.py --profile lab components list --keyword 10k --json
python inventory_cli.py --profile lab components create --name "Resistor" --value "10k" --package "0603" --quantity 100 --json
python inventory_cli.py --profile lab stock out 1 --quantity 5 --reason "prototype build" --json
python inventory_cli.py --profile lab boxes grid 1 --json
```

Profile data is stored in `~/.components-inventory/config.json`. The CLI also accepts
`--server`, `--token`, `--json`, `--pretty`, `--quiet`, `--timeout`, and `--verbose`.

### Device tokens

Device-specific CLI tokens can be generated from the web UI:

1. Open the web app.
2. Click the `CI` brand mark in the upper-left corner 5 times.
3. Enter a token name such as `lab-pc` or `scanner-1`.
4. Generate and copy the token. The full token is shown only once.
5. Configure the CLI:

```bash
python inventory_cli.py config set-token lab <generated-token>
```

Generated tokens are stored in SQLite as hashes. The token list shows only the token
name, prefix, and last-used time. Deleting a token invalidates it immediately. If at
least one device token has ever been created, `inventory-cli` requests must provide a
valid token.

`API_TOKEN` is still supported as an environment-level fallback token:

```bash
API_TOKEN=change-me python app.py
```

## 项目结构

```
components-inventory/
├── app.py              # Flask 应用入口，所有 API 路由
├── models.py           # 数据仓库层，SQLite CRUD 与业务逻辑
├── init_db.py          # 数据库 Schema 与初始化
├── config.py           # 配置（路径、端口、环境变量）
├── logger.py           # 文件日志系统
├── requirements.txt    # Python 依赖
├── data/               # SQLite 数据库（运行时生成）
├── uploads/            # 图片上传目录（运行时生成）
├── static/             # 前端静态文件
│   ├── index.html      # 主页面
│   ├── box.html        # NFC 盒子详情页
│   ├── css/            # 样式
│   └── js/             # JavaScript 模块
├── examples/           # 示例文件
│   └── sample_bom.csv  # BOM 导入示例
└── log/                # 运行日志
```

## API 概览

所有 API 响应格式：`{"code": 0, "data": ..., "message": "ok"}`

### 元器件

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/components` | 列表（支持 keyword/category_id/box_id/tag/low_stock 筛选） |
| POST | `/api/components` | 新增（自动合并相同规格） |
| GET | `/api/components/<id>` | 详情 |
| PUT | `/api/components/<id>` | 更新 |
| DELETE | `/api/components/<id>` | 删除 |
| POST | `/api/components/import` | Excel 批量导入 |
| GET | `/api/components/export` | Excel 导出 |

### 收纳盒

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/boxes` | 列表 |
| POST | `/api/boxes` | 新增 |
| GET | `/api/boxes/<id>` | 详情 |
| PUT | `/api/boxes/<id>` | 更新 |
| DELETE | `/api/boxes/<id>` | 删除 |
| PUT | `/api/boxes/<id>/layout` | 更新地图位置 |
| GET | `/api/boxes/<id>/grid` | 网格详情 |

### 库存

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/stock/in` | 入库 |
| POST | `/api/stock/out` | 出库 |
| GET | `/api/stock/logs/<id>` | 变更日志 |

### BOM

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/bom/import` | 导入 CSV BOM |
| POST | `/api/bom/consume` | BOM 领料出库 |
| POST | `/api/bom/export` | 导出 Picklist |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/categories` | 分类列表 |
| POST | `/api/categories` | 新增分类 |
| POST | `/api/images/upload` | 上传图片 |
| DELETE | `/api/images/<id>` | 删除图片 |
| GET | `/api/stats` | 数据统计 |
| GET | `/api/map` | 地图数据 |
| POST | `/api/map/search` | 地图搜索 |
| POST | `/api/nfc/bind` | 绑定 NFC |
| POST | `/api/nfc/write` | 生成 NDEF 内容 |
| GET | `/api/nfc/lookup/<uid>` | NFC UID 查询 |
| GET | `/api/settings/tokens` | List active automation tokens |
| POST | `/api/settings/tokens` | Create a device automation token |
| DELETE | `/api/settings/tokens/<id>` | Revoke a device automation token |

## 技术栈

- **后端**: Python Flask + SQLite（纯 SQL，无 ORM）
- **前端**: 原生 HTML / CSS / JavaScript（无框架）
- **图片处理**: Pillow
- **Excel**: openpyxl

## 许可证

[MIT License](LICENSE)
