# Components Inventory — 项目结构与开发文档

## 1. 项目概述

电子元器件库存管理系统，用于管理电子元器件的入库、出库、分类、定位、NFC 标签绑定、BOM 导入/领料等操作。

技术栈：Flask + SQLite + 原生 JS/HTML/CSS，无 ORM、无前端框架。

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────┐
│  前端 (static/)                                       │
│  index.html / box.html / js / css                     │
└───────────────────────┬──────────────────────────────┘
                        │ HTTP / REST API
┌───────────────────────▼──────────────────────────────┐
│  路由层 (routes/)          — Flask 蓝图，请求解析       │
│  pages / categories / cabinets / boxes / components   │
│  stock_operations / tags / nfc / map / bom / auth     │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│  服务层 (services/)        — 纯 Python 业务逻辑        │
│  bom_service / import_service / label_service         │
│  _parsing (共享文件解析工具)                            │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│  外观层 (models.py)        — InventoryRepository      │
│  薄委托模式，对外暴露统一接口，内部分发给子仓储          │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│  仓储层 (repositories/)    — 原生 SQL 数据访问         │
│  component_repo / box_repo / stock_repo / ...         │
│  _utils (共享 URL/文件/库存日志工具)                    │
│  base (连接管理、事务、WAL 模式)                        │
└───────────────────────┬──────────────────────────────┘
                        │
                   SQLite (WAL)
```

各层职责：

| 层 | 职责 | 原则 |
|---|---|---|
| routes/ | HTTP 请求解析、响应封装 | 不包含业务逻辑，薄层委托 |
| services/ | 文件解析、算法匹配、Excel 生成 | 纯函数，不直接依赖 repo |
| models.py | InventoryRepository 外观 | 薄委托，对外接口不变 |
| repositories/ | SQL 查询、数据读写 | 不包含 HTTP 逻辑 |

---

## 3. 目录结构

```
components-inventory/
│
├── app.py                  # Flask 应用入口（~47 行）
├── config.py               # 集中配置（路径、端口、分页、颜色）
├── init_db.py              # 数据库 Schema 初始化 + 迁移
├── logger.py               # 前后端日志系统
├── models.py               # InventoryRepository 外观（~170 行）
├── inventory_cli.py        # CLI 工具入口
├── requirements.txt        # Python 依赖
│
├── routes/                 # 路由层 — 11 个 Flask 蓝图
│   ├── __init__.py         #   register_blueprints()
│   ├── _utils.py           #   success() / failure() / excel_response()
│   ├── pages.py            #   前端页面 + QR 标签打印
│   ├── categories.py       #   分类 CRUD
│   ├── cabinets.py         #   柜子 CRUD + 布局
│   ├── boxes.py            #   收纳盒 CRUD + 网格 + 布局
│   ├── components.py       #   元器件 CRUD + 导入/导出/QR
│   ├── stock_operations.py #   出入库 + 日志 + 统计
│   ├── tags.py             #   图片/文档上传删除
│   ├── nfc.py              #   NFC 绑定/写入/查询
│   ├── map.py              #   地图数据 + 背景 + 搜索
│   ├── bom.py              #   BOM 导入/领料/导出
│   └── auth.py             #   Token 管理 + 认证中间件 + 前端日志
│
├── services/               # 服务层 — 可独立测试的纯函数
│   ├── __init__.py
│   ├── _parsing.py         #   共享解析工具（CSV/XLSX 解码、表头映射）
│   ├── bom_service.py      #   BOM CSV 解析 + 元器件匹配算法
│   ├── import_service.py   #   元器件导入/导出（回调式 repo 访问）
│   └── label_service.py    #   QR 码 SVG + 标签打印页生成
│
├── repositories/           # 仓储层 — 原生 SQL 数据访问
│   ├── __init__.py         #   导出所有仓储类
│   ├── base.py             #   BaseRepository（连接管理、WAL、事务）
│   ├── _utils.py           #   共享工具（image_url / delete_files / append_stock_log）
│   ├── token_repo.py       #   TokenRepository（5 方法）
│   ├── category_repo.py    #   CategoryRepository（3 方法）
│   ├── cabinet_repo.py     #   CabinetRepository（6 方法）
│   ├── box_repo.py         #   BoxRepository（10 方法）
│   ├── component_repo.py   #   ComponentRepository（最大，33+ 方法）
│   ├── stock_repo.py       #   StockRepository（3 方法）
│   ├── document_repo.py    #   DocumentRepository（4 方法）
│   └── nfc_repo.py         #   NfcRepository（3 方法）
│
├── models.py               # InventoryRepository — 薄外观，委托给子仓储
│
├── static/                 # 前端静态文件
│   ├── index.html          #   主界面
│   ├── box.html            #   收纳盒详情页
│   ├── css/style.css       #   全局样式
│   └── js/
│       ├── api.js          #   API 通信层
│       ├── app.js          #   主应用逻辑（最大的前端文件）
│       ├── bg-fx.js        #   背景动效
│       ├── logger.js       #   前端日志收集
│       ├── map.js          #   地图可视化
│       ├── nfc.js          #   NFC 功能
│       └── scanner.js      #   QR 扫描
│
├── inventory_client/       # CLI HTTP 客户端库
│   ├── __init__.py
│   ├── client.py           #   InventoryClient（基于 urllib）
│   ├── config.py           #   配置文件管理（多 profile）
│   └── errors.py           #   错误类定义
│
├── tests/                  # pytest 测试套件（110 个测试）
│   ├── conftest.py         #   共享 fixtures
│   ├── test_categories_api.py
│   ├── test_cabinets_api.py
│   ├── test_boxes_api.py
│   ├── test_components_api.py
│   ├── test_stock_api.py
│   ├── test_images_api.py
│   ├── test_documents_api.py
│   ├── test_tokens_api.py
│   ├── test_nfc_api.py
│   ├── test_map_api.py
│   ├── test_bom_api.py
│   ├── test_stats_api.py
│   └── test_frontend_log_api.py
│
├── data/                   # SQLite 数据库存放目录
├── uploads/                # 上传文件目录
│   ├── thumbnails/         #   图片缩略图
│   └── documents/          #   文档文件
└── log/                    # 日志目录
    ├── backend.log         #   后端日志
    └── frontend.log        #   前端日志
```

---

## 4. 核心模块详解

### 4.1 app.py — 应用入口

应用启动流程：

```
ensure_runtime_directories()  →  创建 data/uploads/log 目录
init_database(DATABASE_PATH)  →  初始化 SQLite（建表+WAL+索引）
Flask(__name__)               →  创建 Flask 应用
FileLogger(...)               →  创建日志器
InventoryRepository(...)      →  创建仓储外观（内含 8 个子仓储）
register_blueprints(app)      →  注册 11 个蓝图
app.run(host, port)           →  启动服务
```

错误处理：所有 `/api` 路径的异常返回 JSON `{"code": 1, "message": "..."}`，页面路径返回纯文本。

### 4.2 config.py — 集中配置

所有配置集中管理，支持环境变量覆盖：

| 常量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_PATH` | `data/inventory.db` | 数据库路径 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `5000` | 监听端口 |
| `SERVER_URL` | `http://localhost:5000` | 对外 URL（QR 码用） |
| `MAX_CONTENT_LENGTH` | `16MB` | 上传文件大小限制 |
| `DEFAULT_PAGE_SIZE` | `20` | 默认分页大小 |
| `MAX_COMPONENT_PAGE_SIZE` | `500` | 元器件最大分页 |
| `MAX_STOCK_LOG_PAGE_SIZE` | `200` | 库存日志最大分页 |
| `SEARCH_RESULTS_LIMIT` | `50` | 地图搜索结果上限 |
| `DEFAULT_BOX_COLOR` | `#84b59b` | 收纳盒默认颜色 |
| `DEFAULT_CABINET_COLOR` | `#8b9aae` | 柜子默认颜色 |
| `API_TOKEN` | `""` | 全局认证 Token |
| `API_TOKEN_REQUIRE_ALL` | `false` | 是否要求所有请求认证 |

### 4.3 init_db.py — 数据库初始化

11 张表 + 13 个索引，初始化时自动创建。

创建流程：`PRAGMA journal_mode=WAL` → `PRAGMA busy_timeout=5000` → 建表 → 建索引 → 迁移检查 → 插入默认分类。

如果 `boxes` 表缺少 `color`/`cabinet_id`/`cabinet_slot` 列，会自动 `ALTER TABLE` 添加。

### 4.4 logger.py — 日志系统

`FileLogger` 区分前后端日志，线程安全（`threading.Lock`）：

- **后端日志** `backend.log`：按标签过滤（SYSTEM / COMPONENT / BOX / STOCK / NFC / BOM）
- **前端日志** `frontend.log`：按类型过滤（ERROR / CREATE / UPDATE / DELETE / STOCK 等）

### 4.5 models.py — InventoryRepository 外观

薄委托模式：构造时创建 8 个子仓储实例，所有 public 方法直接转发。

```
InventoryRepository
  ├── _token_repo      → TokenRepository
  ├── _category_repo   → CategoryRepository
  ├── _cabinet_repo    → CabinetRepository
  ├── _box_repo        → BoxRepository
  ├── _component_repo  → ComponentRepository
  ├── _stock_repo      → StockRepository
  ├── _document_repo   → DocumentRepository
  └── _nfc_repo        → NfcRepository
```

外部调用者（routes、CLI）只与 `InventoryRepository` 交互，不直接引用子仓储。

同时包含共享工具函数（`clean_text`、`clean_int`、`normalize_value` 等），被所有层引用。

---

## 5. 数据库模型

### 5.1 表结构

```
categories          分类（电阻、电容、电感…）
├── id, name, parent_id, icon, created_at

cabinets            柜子（收纳盒的容器）
├── id, name, description, color, position_x, position_y, created_at

boxes               收纳盒（元器件存放单元，支持行列网格）
├── id, name, rows, cols, description, color
├── cabinet_id → cabinets, cabinet_slot, nfc_uid
├── position_x, position_y, created_at

compartments        格子（收纳盒的行列单元）
├── id, box_id → boxes, row, col, label
├── UNIQUE(box_id, row, col)

components          元器件（核心实体）
├── id, name, category_id → categories
├── model, package, nominal_value, voltage_rating, current_rating
├── power_rating, tolerance, material_type, manufacturer
├── extra_specs, quantity, min_stock
├── box_id → boxes, compartment_id → compartments (UNIQUE)
├── description, created_at, updated_at

tags                标签
├── id, name (UNIQUE)

component_tags      元器件-标签关联
├── component_id → components, tag_id → tags
├── PRIMARY KEY(component_id, tag_id)

images              图片
├── id, component_id → components, path (UNIQUE)
├── thumbnail_path, is_primary, created_at

documents           文档
├── id, component_id → components, path (UNIQUE)
├── original_name, mime_type, file_size, created_at

stock_logs          库存变更日志
├── id, component_id → components, type, change
├── quantity_after, reason, created_at

api_tokens          API 认证令牌
├── id, name (UNIQUE), token_hash (UNIQUE)
├── token_prefix, created_at, last_used_at, active
```

### 5.2 关键约束

- `components.compartment_id` 为 `UNIQUE`，一个格子只能放一个元器件
- `boxes.nfc_uid` 为 `UNIQUE`，一个 NFC 标签只能绑定一个收纳盒
- 所有外键启用 `PRAGMA foreign_keys = ON`
- 删除收纳盒时级联删除格子（`ON DELETE CASCADE`）
- 删除元器件时级联删除图片、文档、库存日志、标签关联

---

## 6. API 端点参考

### 通用约定

- 所有 API 返回 `{"code": 0, "data": ..., "message": "ok"}`（成功）或 `{"code": 1, "data": null, "message": "错误描述"}`（失败）
- 需要认证时，请求头携带 `Authorization: Bearer <token>` 和 `X-Inventory-Source: inventory-cli`
- 分页参数：`page`（从 1 开始）、`page_size`（默认 20）

### 元器件

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/components` | 列表（支持 keyword/category_id/box_id/tag/low_stock 筛选） |
| POST | `/api/components` | 创建（自动合并同名元器件） |
| GET | `/api/components/<id>` | 详情（含图片、文档、库存日志） |
| PUT | `/api/components/<id>` | 更新 |
| DELETE | `/api/components/<id>` | 删除（级联删除图片/文档） |
| GET | `/api/components/<id>/qr.svg` | QR 码 SVG |
| POST | `/api/components/import` | 导入（CSV/XLSX，multipart） |
| GET | `/api/components/export` | 导出为 XLSX |

### 收纳盒

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/boxes` | 列表 |
| POST | `/api/boxes` | 创建 |
| GET | `/api/boxes/<id>` | 详情 |
| PUT | `/api/boxes/<id>` | 更新（含自动调整格子） |
| DELETE | `/api/boxes/<id>` | 删除（需为空） |
| PUT | `/api/boxes/<id>/layout` | 更新地图位置 |
| GET | `/api/boxes/<id>/grid` | 获取网格数据（含各格子的元器件信息） |

### 柜子

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/cabinets` | 列表 |
| POST | `/api/cabinets` | 创建 |
| GET | `/api/cabinets/<id>` | 详情 |
| PUT | `/api/cabinets/<id>` | 更新 |
| DELETE | `/api/cabinets/<id>` | 删除（需为空） |
| PUT | `/api/cabinets/<id>/layout` | 更新地图位置 |

### 分类

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/categories` | 列表（含每个分类的元器件数量） |
| POST | `/api/categories` | 创建 |

### 库存操作

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/stock/in` | 入库 |
| POST | `/api/stock/out` | 出库 |
| GET | `/api/stock/logs/<component_id>` | 库存变更日志 |
| GET | `/api/stats` | 统计概览（含低库存预警） |

### 图片与文档

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/images/upload` | 上传图片（自动生成缩略图） |
| DELETE | `/api/images/<id>` | 删除图片 |
| POST | `/api/documents/upload` | 上传文档 |
| DELETE | `/api/documents/<id>` | 删除文档 |

### NFC

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/nfc/bind` | 绑定 NFC 标签到收纳盒 |
| POST | `/api/nfc/write` | 生成 NFC NDEF 内容 |
| GET | `/api/nfc/lookup/<uid>` | 通过 NFC UID 查找收纳盒 |
| GET | `/api/box/<id>` | 获取收纳盒数据（NFC 扫码入口） |

### BOM

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/bom/import` | 导入 BOM CSV（自动匹配库存元器件） |
| POST | `/api/bom/consume` | BOM 领料（批量出库） |
| POST | `/api/bom/export` | 导出领料单 XLSX |

### 地图

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/map` | 地图数据（所有盒子 + 柜子） |
| POST | `/api/map/background` | 上传地图背景图 |
| DELETE | `/api/map/background` | 删除地图背景图 |
| POST | `/api/map/search` | 地图搜索元器件 |

### 认证与系统

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/settings/tokens` | 列出所有 Token |
| POST | `/api/settings/tokens` | 创建 Token |
| DELETE | `/api/settings/tokens/<id>` | 删除 Token |
| POST | `/api/frontend/log` | 前端日志上报 |

### 页面

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 主页面 |
| GET | `/box/<id>` | 收纳盒详情页 |
| GET | `/components/qr-labels` | QR 标签打印页 |
| GET | `/uploads/<path>` | 上传文件访问 |

---

## 7. 认证机制

采用 Bearer Token 认证，两种模式：

1. **全局 Token 模式**：通过环境变量 `API_TOKEN` 设置一个全局 Token
2. **多 Token 模式**：通过 `/api/settings/tokens` 创建多个独立 Token

中间件逻辑（`routes/auth.py` 的 `before_app_request`）：

```
如果 API_TOKEN_REQUIRE_ALL=true → 所有 /api 请求必须认证
如果 API_TOKEN_REQUIRE_ALL=false:
  └── 仅当数据库中存在 Token 时，非 CLI 来源的请求需要认证
```

CLI 来源识别：请求头 `X-Inventory-Source: inventory-cli` 可跳过 Token 验证（当 `API_TOKEN_REQUIRE_ALL=false` 时）。

---

## 8. 关键业务逻辑

### 8.1 元器件自动合并

创建元器件时（`component_repo.create_component`），系统会检查是否存在完全匹配的元器件（名称、型号、封装、标称值等 9 个字段全部匹配）：

- **匹配到**：合并数量，保留第一个的仓位，合并标签/图片/文档
- **未匹配到**：创建新元器件

### 8.2 BOM 匹配算法

`services/bom_service.parse_bom_csv` 实现：

1. 解析 CSV/XLSX 文件，提取 comment/designator/footprint/quantity/value
2. 获取所有元器件候选列表（`bom_component_candidates`）
3. 对每行 BOM，计算 `value_score`（0-4 分）衡量值匹配度
4. 优先匹配封装（footprint）+ 值完全一致的（`footprint_value`）
5. 其次匹配仅值一致的（`value_only`）

### 8.3 元器件导入

`services/import_service.parse_component_import` 支持 CSV 和 XLSX：

- 自动识别编码（chardet）
- 通过中文/英文别名映射表头到字段名
- 支持按收纳盒名称 + 行列号定位格子
- 自动创建不存在的分类

### 8.4 仓位解析

`component_repo._resolve_location` 处理三种定位方式：

1. 直接指定 `compartment_id`
2. 指定 `cell_row`（实际上是 compartment_id）
3. 指定 `cell_row` + `cell_col`（通过行列坐标查找格子）

---

## 9. 测试

### 运行测试

```bash
python -m pytest tests/ -v
```

### 测试架构

`conftest.py` 使用 monkeypatch 策略，每个测试函数获得独立的临时环境：

1. `tmp_dirs` — 临时 data/uploads/log 目录
2. `db` — 临时 SQLite 数据库
3. `repo` — 指向临时数据库的 InventoryRepository
4. `app` — monkeypatch 后的 Flask 应用（替换 repo/file_logger/config 常量）
5. `client` — Flask test client
6. `auth_token` / `auth_headers` — 认证辅助

### 测试覆盖

110 个测试覆盖所有 API 端点，包括正常流程和错误场景。按领域分为 13 个文件：

| 文件 | 覆盖 | 用例数 |
|---|---|---|
| test_categories_api.py | 分类列表、创建 | 5 |
| test_cabinets_api.py | 柜子 CRUD + 布局 | 9 |
| test_boxes_api.py | 收纳盒 CRUD + 网格 + 布局 | 14 |
| test_components_api.py | 元器件 CRUD + 导入/导出/QR | 20 |
| test_stock_api.py | 出入库 + 日志 + 分页 | 10 |
| test_images_api.py | 图片上传/删除 | 7 |
| test_documents_api.py | 文档上传/删除 | 6 |
| test_tokens_api.py | Token CRUD + 认证中间件 | 10 |
| test_stats_api.py | 统计概览 | 4 |
| test_nfc_api.py | NFC 绑定/写入/查询/盒子数据 | 8 |
| test_map_api.py | 地图数据/背景/搜索 | 8 |
| test_bom_api.py | BOM 导入/领料/导出 | 8 |
| test_frontend_log_api.py | 前端日志上报 | 4 |

### 添加新测试

在 `tests/` 下新建文件，使用 `conftest.py` 提供的 fixtures：

```python
class TestNewFeature:
    def test_something(self, client, auth_headers):
        resp = client.get("/api/something", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["code"] == 0
```

---

## 10. 开发指南

### 10.1 开发流程 Rule

项目根目录 `AGENTS.md` 是后续开发的强制流程规范。所有开发、重构、修复和文档更新都应遵循以下原则：

- 相关内容放在规范位置：路由在 `routes/`，业务逻辑在 `services/`，数据访问在 `repositories/`，配置在 `config.py`，数据库 Schema 与迁移在 `init_db.py`，测试在 `tests/`。
- 每个新增或重写的源代码文件都要在文件顶部写明中文职责注释；新增类、函数或复杂代码块应补充必要中文说明。
- 改动必须保持现有分层结构完整，不绕过 `InventoryRepository` 外观层，不把 HTTP、业务逻辑和 SQL 访问混杂在同一层。
- 代码应保持可读、可维护，优先复用已有工具函数、响应封装、仓储基类和测试 fixtures。
- 每次更改完成后都要同步检查并更新本 `docs/ARCHITECTURE.md`；若架构内容无需变化，应在提交说明中明确记录已检查。

### 添加新的 API 端点

1. 在 `repositories/` 中对应的仓储类添加数据方法
2. 在 `models.py` 的 `InventoryRepository` 中添加委托方法
3. 在 `routes/` 中对应的蓝图文件添加路由函数
4. 如果涉及复杂业务逻辑，提取到 `services/`
5. 在 `tests/` 中添加测试

### 添加新的数据表

1. 在 `init_db.py` 的 `SCHEMA_SQL` 中添加 `CREATE TABLE` 和 `CREATE INDEX`
2. 在 `repositories/` 中创建新的仓储类（继承 `BaseRepository`）
3. 在 `models.py` 中添加子仓储实例和委托方法
4. 运行 `init_database()` 时会自动创建新表（`IF NOT EXISTS`）

### 路由中使用 repo

路由函数中使用延迟导入避免循环依赖：

```python
@some_bp.get("/api/example")
def api_example():
    from app import repo
    return success(repo.some_method())
```

### 服务函数设计原则

- 接收数据作为参数，不直接 `from app import repo`
- 需要 repo 功能时，通过回调函数注入
- 返回纯数据结构，不依赖 Flask 对象
- 可独立进行单元测试

### 配置项扩展

在 `config.py` 中添加新常量，支持环境变量覆盖：

```python
NEW_SETTING = os.environ.get("NEW_SETTING", "default_value")
```

---

## 11. 部署

### 环境变量

```bash
HOST=0.0.0.0                    # 监听地址
PORT=5000                       # 监听端口
SERVER_URL=http://localhost:5000 # 对外 URL
API_TOKEN=                       # 全局认证 Token
API_TOKEN_REQUIRE_ALL=false      # 是否强制所有请求认证
MAX_CONTENT_LENGTH=16777216      # 上传大小限制
SECRET_KEY=                      # Flask 密钥
```

### 启动

```bash
pip install -r requirements.txt
python app.py
```

### CLI 工具

```bash
python inventory_cli.py --help
python inventory_cli.py --server http://localhost:5000 components list
```

---

## 12. 依赖

| 包 | 版本 | 用途 |
|---|---|---|
| Flask | >=3.0,<4.0 | Web 框架 |
| openpyxl | >=3.1,<4.0 | Excel 读写 |
| Pillow | >=10.0,<12.0 | 图片处理（缩略图） |
| chardet | >=5.0,<6.0 | 文件编码检测 |
| qrcode | >=7.4,<8.0 | QR 码生成 |
| pytest | >=8.0,<9.0 | 测试框架 |
