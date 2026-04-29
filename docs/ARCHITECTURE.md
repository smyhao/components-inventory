# Components Inventory — 项目结构与开发文档

## 1. 项目概述

电子元器件库存管理系统，用于管理电子元器件的入库、出库、分类、定位、NFC 标签绑定、BOM 导入/领料等操作。

技术栈：Flask + SQLite + 原生 JS/HTML/CSS，无 ORM、无前端框架。

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────┐
│  前端 (static/)                                       │
│  index.html / box.html / js / css / vendor            │
│  2D 地图层 (features/map-workbench.js)                 │
│  3D 引擎层 (js/3d/)                                   │
│  scene-manager / models / interaction / labels / ...  │
└───────────────────────┬──────────────────────────────┘
                        │ HTTP / REST API
┌───────────────────────▼──────────────────────────────┐
│  路由层 (routes/)          — Flask 蓝图，请求解析       │
│  pages / categories / cabinets / boxes / components   │
│  stock_operations / tags / nfc / map / bom / auth / led│
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│  服务层 (services/)        — 纯 Python 业务逻辑        │
│  bom_service / import_service / label_service / led_*  │
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
│  component_repo / box_repo / stock_repo / led_repo / ...│
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

3D 地图视图位于前端静态层内，使用 Three.js 构建独立引擎层。`static/js/features/map-3d.js` 只负责 Alpine 状态桥接、2D/3D 切换和 API 调用，`static/js/3d/` 内的 scene/model/interaction/label/highlight/layout 模块负责 Three.js 场景、模型和动画。

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
├── prompt/                 # 前端重构等协作任务 Prompt
│   ├── 00-frontend-refactor-shared-rules.md
│   └── 01-...09-frontend-*.md
│
├── routes/                 # 路由层 — 12 个 Flask 蓝图
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
│   ├── auth.py             #   Token 管理 + 认证中间件 + 前端日志
│   └── led.py              #   LED 设置、设备测试、定位和清除 API
│
├── services/               # 服务层 — 可独立测试的纯函数
│   ├── __init__.py
│   ├── _parsing.py         #   共享解析工具（CSV/XLSX 解码、表头映射）
│   ├── bom_service.py      #   BOM CSV 解析 + 元器件匹配算法
│   ├── import_service.py   #   元器件导入/导出（回调式 repo 访问）
│   ├── label_service.py    #   QR 码 SVG + 标签打印页生成
│   ├── led_service.py      #   LED 定位业务编排 + 灯带同步到 ESP32
│   └── led_proxy.py        #   ESP32 HTTP 代理（LED 控制 + 配置同步）
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
│   ├── nfc_repo.py         #   NfcRepository（3 方法）
│   └── led_repository.py   #   LedRepository（配置/设备/灯带/映射）
│
├── models.py               # InventoryRepository — 薄外观，委托给子仓储
│
├── static/                 # 前端静态文件
│   ├── index.html          #   主界面（含 2D/3D 切换、3D 容器和 importmap）
│   ├── box.html            #   收纳盒独立查看页
│   ├── css/
│   │   ├── style.css       #   全局样式
│   │   └── map-3d.css      #   3D 地图专用样式
│   ├── js/
│       ├── api.js          #   API 兼容入口（保留 api/upload/download 全局名称）
│       ├── app.js          #   主应用入口（合并各 feature，包括 map3dFeature）
│       ├── bg-fx.js        #   背景动效
│       ├── logger.js       #   前端日志收集
│       ├── map.js          #   地图可视化
│       ├── nfc.js          #   NFC 功能
│       ├── scanner.js      #   QR 扫描
│       ├── modules/
│       │   ├── core.js     #   前端模块命名空间与特性合并工具
│       │   └── http.js     #   HTTP 请求、响应解析、上传下载基础服务
│       ├── features/
│           ├── components.js # 元器件列表、筛选、表单、详情、库存和导入导出交互
│           ├── storage.js  #   收纳盒/柜子列表、表单、详情网格交互
│           ├── map-workbench.js # 地图加载、拖拽缩放、背景、布局保存和 BOM 高亮联动
│           ├── map-3d.js   #   3D 地图 Alpine 功能模块与跨功能桥接
│           ├── bom.js      #   BOM 导入、匹配、批量选择、领料、导出和地图跳转桥接
│           ├── automation.js # Token、LED、NFC 与扫码自动化交互
│           └── box-page.js #   /box/<id> 独立查看页渲染
│       └── 3d/             #   3D 引擎层
│           ├── scene-manager.js # 场景初始化、灯光、地面、渲染循环和资源释放
│           ├── cabinet-model.js # 参数化柜子、抽屉、把手模型
│           ├── box-model.js     # 独立收纳盒、格子 InstancedMesh 和颜色更新
│           ├── interaction.js   # 射线拾取、抽屉动画、格子点击、拖拽保存
│           ├── labels.js        # CSS2DObject 名称牌、格子标签和 LOD
│           ├── highlights.js    # BOM 高亮、LED 脉冲、相机飞入、领料序号
│           └── layouts.js       # 3D 预设布局纯函数
│   └── vendor/             #   前端第三方库
│       ├── three.module.min.js # Three.js 核心 ES Module
│       ├── OrbitControls.js    # 轨道相机控制
│       ├── CSS2DRenderer.js    # CSS2DObject 标签渲染
│       └── html5-qrcode.min.js # QR 扫描库
│
├── inventory_client/       # CLI HTTP 客户端库
│   ├── __init__.py
│   ├── client.py           #   InventoryClient（基于 urllib）
│   ├── config.py           #   配置文件管理（多 profile）
│   └── errors.py           #   错误类定义
│
├── tests/                  # pytest 测试套件（128 个测试）
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

### 4.0 前端边界

主界面仍由 `static/index.html` 通过 `x-data="app()"` 启动，HTML 只保留页面区块、移动端底部导航、模态框和脚本加载顺序等结构说明，不承载业务规则。

前端 JS 以 `static/js/modules/core.js` 提供 `window.InventoryModules` 命名空间、`mergeFeature` 和 `createToast` 等轻量组合工具；`static/js/modules/http.js` 负责 HTTP 请求与上传下载基础能力；领域交互逐步放入 `static/js/features/`，再由 `static/js/app.js` 保持兼容入口并按需合并。`automation.js` 承载隐藏设置入口、Token 管理、LED 定位配置与动作、NFC 读写和扫码录入，扫码识别后通过注入入口触发元器件详情或表单，避免直接耦合元器件领域内部实现。

3D 地图视图以 `static/js/3d/` 存放引擎层代码，包括场景管理、参数化模型、射线交互、标签、高亮动画和预设布局。`static/js/features/map-3d.js` 作为 Alpine 功能模块桥接 2D/3D 切换、格子数据懒加载、布局保存和跨功能高亮；Three.js、OrbitControls、CSS2DRenderer 放在 `static/vendor/`，通过 `index.html` 的 importmap 以 ES Module 方式加载。3D 引擎层不直接持有 Alpine 状态，交互层通过 `InteractionManager(sceneManager, alpineContext)` 显式桥接，3D 专用样式集中在 `static/css/map-3d.css`。

样式当前仍集中在 `static/css/style.css`，按“基础变量与 reset、应用外壳、通用组件、领域视图、模态框/反馈、工具类、响应式”顺序维护分区。若后续拆成 `base.css`、`components.css`、`features.css`、`responsive.css`，必须同步更新 `index.html` 与 `box.html` 的加载顺序。

### 4.1 app.py — 应用入口

应用启动流程：

```
ensure_runtime_directories()  →  创建 data/uploads/log 目录
init_database(DATABASE_PATH)  →  初始化 SQLite（建表+WAL+索引）
Flask(__name__)               →  创建 Flask 应用
FileLogger(...)               →  创建日志器
InventoryRepository(...)      →  创建仓储外观（内含 9 个子仓储）
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

15 张表 + 15 个索引，初始化时自动创建。

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
  ├── _nfc_repo        → NfcRepository
  └── _led_repo        → LedRepository
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

led_config          LED 定位全局配置
├── id=1, enabled, blink_interval_ms, blink_duration_ms, updated_at

led_devices         ESP32 LED 控制设备
├── id, name (UNIQUE), host, port, enabled, created_at

led_strips          设备下挂载的灯带
├── id, device_id → led_devices, name, gpio_num, led_count
├── UNIQUE(device_id, gpio_num)

led_box_mapping     收纳盒到 LED 的唯一映射
├── id, box_id → boxes, strip_id → led_strips, led_index, color
├── UNIQUE(box_id), UNIQUE(strip_id, led_index)
```

### 5.2 关键约束

- `components.compartment_id` 为 `UNIQUE`，一个格子只能放一个元器件
- `boxes.nfc_uid` 为 `UNIQUE`，一个 NFC 标签只能绑定一个收纳盒
- `led_box_mapping.box_id` 为 `UNIQUE`，一个收纳盒只能映射一个 LED
- `led_box_mapping(strip_id, led_index)` 为 `UNIQUE`，同一灯带同一 LED 只能映射一个收纳盒
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

### LED 定位

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/settings/led` | 获取 LED 配置、设备、灯带和映射 |
| PUT | `/api/settings/led` | 更新 LED 全局开关和闪烁参数 |
| POST | `/api/settings/led/devices` | 创建设备 |
| PUT | `/api/settings/led/devices/<id>` | 更新设备 |
| DELETE | `/api/settings/led/devices/<id>` | 删除设备，并级联删除灯带和映射 |
| POST | `/api/settings/led/devices/<id>/test` | 通过 ESP32 `/api/health` 测试连接 |
| POST | `/api/settings/led/devices/<id>/sync` | 全量同步设备灯带到 ESP32 |
| POST | `/api/settings/led/strips` | 创建灯带（自动同步到 ESP32） |
| PUT | `/api/settings/led/strips/<id>` | 更新灯带（自动同步到 ESP32） |
| DELETE | `/api/settings/led/strips/<id>` | 删除灯带，并级联删除映射（自动从 ESP32 移除） |
| PUT | `/api/settings/led/mappings` | 全量保存收纳盒到 LED 映射 |
| POST | `/api/led/locate/box/<id>` | 定位单个收纳盒 |
| POST | `/api/led/locate/component/<id>` | 定位元器件所在收纳盒 |
| POST | `/api/led/locate/bom` | 按 BOM 涉及收纳盒批量定位 |
| POST | `/api/led/clear` | 清除所有启用 LED 设备 |
| POST | `/api/led/clear/<device_id>` | 清除单台 LED 设备 |

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

### 8.5 LED 定位

LED 定位由 Flask 作为局域网代理：前端触发定位按钮 → `routes/led.py` 解析请求 → `LedService` 查询 `InventoryRepository` → `LedRepository` 读取设备、灯带和盒子映射 → `LedProxy` 向 ESP32 发送 `/api/led/set` 或 `/api/led/clear`。

关键约束：

- 全局开关和闪烁参数存储在 `led_config`，颜色属于每条 `led_box_mapping`。
- 单盒和元器件定位发送单条 LED 指令；BOM 定位按 `device_id` 分组，每台 ESP32 只发送一次请求。
- 设备连接测试失败时返回 `{connected: false, error: "..."}`，不会让前端收到 500。
- 前端设置弹窗包含 `设备 Token` 与 `LED 定位` 两个标签页，定位入口仅在 `ledConfig.enabled` 为真时显示。

### 8.6 灯带远程配置同步

灯带 CRUD 操作（创建、更新、删除）在保存到数据库后，自动同步到 ESP32 硬件。同步通过 `LedProxy` 调用 ESP32 的 `/api/config/strip` 和 `/api/config/strip/remove` 端点实现。

同步策略：

- 数据库为主、ESP32 为从。DB 保存始终成功，ESP32 同步失败时响应中附加 `sync_warning` 字段，不回滚数据库。
- 设备禁用时跳过同步，不产生警告。
- 设备卡片提供"同步"按钮，通过 `POST /api/settings/led/devices/<id>/sync` 端点调用 ESP32 `/api/config` 进行全量同步，将数据库中该设备的所有灯带一次性推送到硬件。

---

## 9. 3D 地图视图

### 9.1 概述

3D 地图视图是对 2D 地图的补充展示，使用 Three.js 将柜子和收纳盒以可交互 3D 模型呈现。用户可在地图工具栏切换 2D/3D，两种视图互斥显隐；3D 模式下可点击抽屉把手拉出收纳盒、查看格子与元器件标签、拖拽调整位置并保存到现有 layout API。

### 9.2 技术栈

- Three.js r171：3D 场景、材质、灯光、InstancedMesh
- OrbitControls：相机轨道控制
- CSS2DRenderer / CSS2DObject：将 HTML 标签渲染到 3D 空间
- 原生 Pointer Events：统一鼠标和触摸交互

### 9.3 3D 场景结构

```
Scene
├── AmbientLight + DirectionalLight × 2
├── GridHelper (地面网格)
├── GroundPlane (ShadowMaterial, 接收阴影)
└── MapGroup (坐标转换根节点, SCALE_FACTOR=0.01)
    ├── CabinetGroup (柜子模型)
    │   ├── 外壳 (顶/底/背/左右侧板)
    │   ├── DrawerGroup × N (抽屉)
    │   │   ├── 面板 (box.color)
    │   │   ├── 把手 (射线拾取目标)
    │   │   ├── 格子 InstancedMesh
    │   │   └── CSS2DObject 标签
    │   └── 层架隔板
    └── StandaloneBox (独立收纳盒)
        ├── 托盘
        ├── 格子 InstancedMesh
        └── CSS2DObject 标签
```

### 9.4 参数化尺寸

| 常量 | 值 | 说明 |
|---|---|---|
| `SCALE_FACTOR` | `0.01` | 2D 像素坐标 → 3D 世界坐标 |
| `CABINET_WIDTH` | `1.2` | 柜子 X 轴宽度 |
| `CABINET_DEPTH` | `0.8` | 柜子 Z 轴深度 |
| `LAYER_HEIGHT` | `0.35` | 每层抽屉高度 |
| `WALL_THICKNESS` | `0.03` | 板壁厚度 |
| `PULL_OUT_DISTANCE` | `0.7` | 抽屉拉出距离 |

### 9.5 交互设计

- **抽屉拉出/推回**：点击把手后设置 `targetZ`，渲染循环以 0.12 系数缓动；同一柜子内抽屉互斥打开。
- **格子点击**：射线命中 `InstancedMesh` 后读取 `instanceId`，反推 row/col，查找懒加载的格子数据并调用现有 `openComponentDetail()`。
- **拖拽移动**：射线与 `Y=0` 平面求交，更新柜子或独立盒位置，松手后按 `SCALE_FACTOR` 反转换并调用 layout API 保存。
- **相机控制**：OrbitControls 限制距离 2-30，极角 0.1 到 `Math.PI / 2 - 0.05`，拖拽对象时临时禁用相机控制。

### 9.6 标签系统

| 标签类型 | CSS 类名 | 显示内容 | 可见性 |
|---|---|---|---|
| 柜子标签框 | `.nameplate-3d` | 颜色圆点 + 柜子名称 | 始终可见 |
| 抽屉标签框 | `.nameplate-3d` | 颜色圆点 + 收纳盒名称 | 始终可见 |
| 格子标签 | `.compartment-label-3d` | 名称、封装、库存数量 | 距离 LOD 控制 |
| 领料序号 | `.pick-label-3d` | BOM 领料序号 | BOM 高亮时可见 |

格子标签在相机距离小于 5 时显示完整信息，5-15 时仅显示名称，大于 15 时隐藏；名称牌不受 LOD 影响。

### 9.7 跨功能集成

| 功能 | 3D 实现 |
|---|---|
| BOM 高亮 | 抽屉面板或独立盒 emissive 发光，并可自动拉出高亮抽屉 |
| BOM 领料序号 | CSS2DObject 序号标签挂在抽屉或独立盒上 |
| LED 定位 | 指定盒子发光正弦脉冲，持续时间来自 LED 配置 |
| 地图定位/搜索 | 相机平滑飞入目标盒子，柜内盒飞入后自动打开抽屉 |
| 元器件详情 | 点击格子复用现有元器件详情弹窗 |

### 9.8 性能策略

- 格子使用 `THREE.InstancedMesh` 减少 draw call。
- 格子数据在抽屉打开时通过 `/api/boxes/<id>/grid` 懒加载。
- CSS2D 格子标签按距离 LOD 控制显示内容和可见性。
- 3D 场景按需创建/销毁，切回 2D 时释放控制器、渲染器、几何体、材质和标签 DOM。
- 渲染器像素比限制为 `Math.min(devicePixelRatio, 2)`，降低高 DPI 设备的 GPU 压力。

---

## 10. 测试

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

128 个测试覆盖所有 API 端点，包括正常流程和错误场景。按领域分为 14 个文件：

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
| test_led_feature.py | LED 表初始化、仓储、服务、API 和灯带同步 | 19 |

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

## 11. 开发指南

### 11.1 开发流程 Rule

项目根目录 `AGENTS.md` 是后续开发的强制流程规范。所有开发、重构、修复和文档更新都应遵循以下原则：

- 相关内容放在规范位置：路由在 `routes/`，业务逻辑在 `services/`，数据访问在 `repositories/`，配置在 `config.py`，数据库 Schema 与迁移在 `init_db.py`，测试在 `tests/`。
- 每个新增或重写的源代码文件都要在文件顶部写明中文职责注释；新增类、函数或复杂代码块应补充必要中文说明。
- 改动必须保持现有分层结构完整，不绕过 `InventoryRepository` 外观层，不把 HTTP、业务逻辑和 SQL 访问混杂在同一层。
- 代码应保持可读、可维护，优先复用已有工具函数、响应封装、仓储基类和测试 fixtures。
- 每次更改完成后都要同步检查并更新本 `docs/ARCHITECTURE.md`；若架构内容无需变化，应在提交说明中明确记录已检查。

### 前端重构 Prompt

前端重构协作 Prompt 放在项目根目录 `prompt/` 下。该目录用于拆分可并行执行的前端重构任务，包含共享规则、领域模块抽取任务和最终集成验收任务。执行这些 Prompt 时仍需遵守 `AGENTS.md` 的分层、中文注释、测试和文档同步要求。

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

## 12. 部署

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

## 13. 依赖

| 包 | 版本 | 用途 |
|---|---|---|
| Flask | >=3.0,<4.0 | Web 框架 |
| openpyxl | >=3.1,<4.0 | Excel 读写 |
| Pillow | >=10.0,<12.0 | 图片处理（缩略图） |
| chardet | >=5.0,<6.0 | 文件编码检测 |
| qrcode | >=7.4,<8.0 | QR 码生成 |
| pytest | >=8.0,<9.0 | 测试框架 |
| Three.js | r171 | 3D 地图渲染、OrbitControls 和 CSS2D 标签 |
