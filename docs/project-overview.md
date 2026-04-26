# Components Inventory 项目说明文档

本文档用于帮助后续维护者快速理解 Components Inventory 项目的用途、技术栈、目录结构、核心数据模型、后端接口、前端组织方式、运行部署方式和常见维护点。

## 1. 项目定位

Components Inventory 是一个轻量级电子元器件库存管理 Web 应用，适合实验室、个人工作台、小型硬件团队管理常用元器件。

项目关注的核心场景包括：

- 元器件资料管理：名称、分类、型号、封装、标称值、电压、电流、功率、精度、材质、厂商、描述、标签、图片。
- 收纳盒管理：每个盒子有行列网格，每个格子可以绑定一个元器件。
- 库存管理：支持入库、出库、库存变化日志和低库存提醒。
- BOM 管理：导入 CSV BOM，自动匹配库存元器件，检查短缺，执行领料扣减，导出 picklist。
- 地图视图：以可视化布局展示收纳盒位置，支持拖拽保存和搜索定位。
- NFC 与扫码：支持 NFC 标签绑定盒子，生成 NFC 写入内容，通过手机查看盒子详情；支持条码或二维码扫码辅助录入。
- 图片管理：元器件可以上传图片，系统自动生成缩略图。

项目整体设计偏单体、轻量、易部署：后端集中在 Flask 应用内，数据库使用 SQLite，前端使用原生 HTML/CSS/JavaScript 加 Alpine.js。

## 2. 技术栈

### 后端

- Python 3.10+
- Flask 3.x
- SQLite
- openpyxl：Excel 导入导出
- Pillow：图片处理和缩略图生成
- chardet：BOM CSV 编码检测

### 前端

- 原生 HTML/CSS/JavaScript
- Alpine.js 3：页面状态和交互
- Tailwind CSS 2 CDN：基础工具类
- html5-qrcode：本地扫码库，文件位于 `static/vendor/html5-qrcode.min.js`

### 数据与运行时文件

- 主数据库：`data/inventory.db`
- 上传文件：`uploads/`
- 缩略图：`uploads/thumbnails/`
- 后端日志：`log/backend.log`
- 前端日志：`log/frontend.log`

## 3. 目录结构

```text
components-inventory/
├── app.py                    # Flask 入口，页面路由、API 路由、导入导出和图片上传处理
├── models.py                 # SQLite 仓储层和核心业务逻辑
├── init_db.py                # 数据库 schema 初始化和默认分类初始化
├── config.py                 # 路径、端口、上传限制、运行目录配置
├── logger.py                 # 文件日志系统
├── requirements.txt          # Python 依赖
├── README.md                 # 项目简介，当前仓库中部分中文显示疑似存在编码问题
├── CONTRIBUTING.md           # 贡献说明
├── LICENSE                   # MIT License
├── data/
│   ├── .gitkeep
│   └── inventory.db          # 运行时生成或维护的 SQLite 数据库
├── docs/
│   ├── deploy.md             # 部署说明，当前仓库中部分中文显示疑似存在编码问题
│   └── project-overview.md   # 本文档
├── examples/
│   └── sample_bom.csv        # BOM 导入示例
├── log/
│   ├── backend.log
│   └── frontend.log
├── static/
│   ├── index.html            # 主工作台页面
│   ├── box.html              # NFC 盒子详情页面
│   ├── css/style.css         # 全局样式
│   ├── js/
│   │   ├── app.js            # 主页面 Alpine 状态和业务交互
│   │   ├── api.js            # fetch、上传、下载封装
│   │   ├── bg-fx.js          # 背景视觉效果
│   │   ├── logger.js         # 前端日志上报
│   │   ├── map.js            # 地图辅助逻辑
│   │   ├── nfc.js            # NFC 辅助逻辑
│   │   └── scanner.js        # 扫码辅助逻辑
│   └── vendor/
│       └── html5-qrcode.min.js
└── uploads/
    ├── .gitkeep
    └── thumbnails/
```

## 4. 启动流程

应用入口在 `app.py`。模块加载时会执行以下初始化：

1. 从 `config.py` 读取路径、端口、上传限制等配置。
2. 调用 `ensure_runtime_directories()` 创建运行目录，包括 `data/`、`uploads/`、`uploads/thumbnails/`、`log/`。
3. 调用 `init_database(DATABASE_PATH)` 初始化 SQLite 表结构和默认分类。
4. 创建 Flask app，设置 `MAX_CONTENT_LENGTH`。
5. 创建 `FileLogger` 和 `InventoryRepository`。
6. 注册页面路由、上传文件路由和 API 路由。
7. 如果直接运行 `python app.py`，使用 Flask 内置开发服务器启动。

本地运行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

默认访问地址：

```text
http://localhost:5000
```

## 5. 配置说明

配置集中在 `config.py`，主要配置项如下：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `BASE_DIR` | 项目根目录 | 通过当前文件位置推导 |
| `DATA_DIR` | `data/` | 数据库目录 |
| `DATABASE_PATH` | `data/inventory.db` | SQLite 数据库路径 |
| `UPLOAD_FOLDER` | `uploads/` | 图片上传目录 |
| `THUMBNAIL_FOLDER` | `uploads/thumbnails/` | 缩略图目录 |
| `STATIC_DIR` | `static/` | 前端静态文件目录 |
| `LOG_DIR` | `log/` | 日志目录 |
| `HOST` | `0.0.0.0` | Flask 监听地址，可通过环境变量覆盖 |
| `PORT` | `5000` | Flask 监听端口，可通过环境变量覆盖 |
| `SERVER_URL` | `http://localhost:5000` | 生成 NFC URL 时使用 |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask 密钥，生产环境应覆盖 |
| `MAX_CONTENT_LENGTH` | 16 MB | 上传文件大小限制 |
| `ALLOWED_IMAGE_EXTENSIONS` | jpg、jpeg、png、gif、webp | 允许上传的图片格式 |

仓库提供 `.env.example`，但当前 `app.py` 没有直接加载 `.env` 的逻辑。如果希望本地 `.env` 自动生效，需要通过系统环境变量、启动脚本、systemd `EnvironmentFile`，或额外引入 python-dotenv。

## 6. 数据库模型

数据库 schema 在 `init_db.py` 的 `SCHEMA_SQL` 中定义。

### categories

元器件分类表。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `name` | 分类名称 |
| `parent_id` | 父分类 ID，当前主要用于预留层级能力 |
| `icon` | 图标字段，当前主要用于预留 |
| `created_at` | 创建时间 |

### boxes

收纳盒表。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `name` | 盒子名称，唯一 |
| `rows` | 网格行数 |
| `cols` | 网格列数 |
| `description` | 描述 |
| `color` | 盒子颜色 |
| `nfc_uid` | 绑定的 NFC UID，唯一 |
| `position_x` | 地图 X 坐标 |
| `position_y` | 地图 Y 坐标 |
| `created_at` | 创建时间 |

### compartments

盒子格子表。每个盒子创建或更新时，会由仓储层确保对应格子存在。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `box_id` | 所属盒子 |
| `row` | 行号 |
| `col` | 列号 |
| `label` | 格子标签 |

约束：`UNIQUE(box_id, row, col)`。

### components

元器件主表。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `name` | 元器件名称 |
| `category_id` | 分类 ID |
| `model` | 型号 |
| `package` | 封装 |
| `nominal_value` | 标称值 |
| `voltage_rating` | 耐压 |
| `current_rating` | 耐流 |
| `power_rating` | 功率 |
| `tolerance` | 精度 |
| `material_type` | 材质或类型 |
| `manufacturer` | 厂商 |
| `extra_specs` | 扩展规格，JSON 字符串 |
| `quantity` | 当前库存数量 |
| `box_id` | 所在盒子 |
| `compartment_id` | 所在格子，唯一 |
| `description` | 描述 |
| `min_stock` | 低库存阈值 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

注意：`compartment_id` 是唯一的，这意味着同一个格子当前只能被一个元器件占用。

### tags 与 component_tags

标签表和元器件标签关联表。

- `tags.name` 唯一。
- `component_tags` 使用 `(component_id, tag_id)` 作为联合主键。

### images

元器件图片表。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `component_id` | 关联元器件，可为空。为空时表示临时上传或尚未绑定 |
| `path` | 原图相对路径，唯一 |
| `thumbnail_path` | 缩略图相对路径 |
| `is_primary` | 是否主图 |
| `created_at` | 创建时间 |

### stock_logs

库存变化日志。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `component_id` | 元器件 ID |
| `type` | 操作类型，例如 `in` 或 `out` |
| `change` | 数量变化，入库为正，出库为负 |
| `quantity_after` | 操作后的库存数量 |
| `reason` | 原因 |
| `created_at` | 创建时间 |

## 7. 后端模块说明

### app.py

`app.py` 是应用入口，也是路由集中定义的位置。主要职责：

- 返回主页面 `/` 和 NFC 盒子页面 `/box/<box_id>`。
- 暴露上传文件 `/uploads/<filename>`。
- 统一 API 响应格式。
- 处理 Excel 元器件导入导出。
- 处理 BOM CSV 导入、领料、picklist 导出。
- 处理图片上传、缩略图生成和图片记录创建。
- 处理全局异常。

统一成功响应格式：

```json
{
  "code": 0,
  "data": {},
  "message": "ok"
}
```

统一失败响应格式：

```json
{
  "code": 1,
  "data": null,
  "message": "错误信息"
}
```

### models.py

`models.py` 包含两类内容：

- 数据清洗和规格归一化工具函数，例如 `clean_text()`、`clean_int()`、`normalize_footprint()`、`normalize_value()`。
- `InventoryRepository` 仓储类，封装 SQLite 访问和业务逻辑。

仓储类主要能力：

- 分类：列表、新增、按名称确保存在。
- 盒子：列表、创建、更新、删除、网格初始化、网格详情、地图位置更新、NFC 绑定。
- 元器件：列表、详情、新增、更新、删除、自动合并相同规格、标签同步、图片同步。
- 库存：入库、出库、库存日志。
- BOM：库存候选、领料扣减。
- 地图：地图数据、搜索。
- 图片：创建记录、删除数据库记录和磁盘文件。

所有数据库写入都通过 `connect()` 上下文管理器提交或回滚，并启用 SQLite 外键约束。

### init_db.py

负责创建表、索引和默认分类。初始化函数是幂等的，可以在每次应用启动时调用。

当前还包含一个轻量迁移逻辑：如果旧的 `boxes` 表缺少 `color` 字段，会执行 `ALTER TABLE boxes ADD COLUMN color ...`。

### logger.py

负责写入后端和前端日志。日志不是全量写入，而是经过筛选：

- 后端只写入重要 tag，例如 `SYSTEM`、`COMPONENT`、`BOX`、`STOCK`、`NFC`、`BOM`。
- 前端只写入重要类型，例如 `ERROR`、`CREATE`、`UPDATE`、`DELETE`、`STOCK`、`IMPORT`、`EXPORT`、`BOM`、`NFC`、`SCAN`，或者包含错误关键词的日志。

这样可以减少拖拽地图等高频操作产生的噪声。

## 8. API 清单

### 页面与静态资源

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 主工作台页面 |
| GET | `/favicon.ico` | 返回 204 |
| GET | `/box/<box_id>` | NFC 盒子详情页面 |
| GET | `/uploads/<filename>` | 访问上传文件 |

### 分类

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/categories` | 分类列表 |
| POST | `/api/categories` | 新增分类 |

### 收纳盒

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/boxes` | 盒子列表 |
| POST | `/api/boxes` | 新增盒子 |
| GET | `/api/boxes/<box_id>` | 盒子详情 |
| PUT | `/api/boxes/<box_id>` | 更新盒子 |
| DELETE | `/api/boxes/<box_id>` | 删除盒子 |
| PUT | `/api/boxes/<box_id>/layout` | 更新地图位置 |
| GET | `/api/boxes/<box_id>/grid` | 获取盒子网格和格子占用情况 |

### 元器件

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/components` | 元器件分页列表，支持筛选 |
| POST | `/api/components` | 新增元器件 |
| GET | `/api/components/<component_id>` | 元器件详情 |
| PUT | `/api/components/<component_id>` | 更新元器件 |
| DELETE | `/api/components/<component_id>` | 删除元器件 |
| POST | `/api/components/import` | Excel 批量导入 |
| GET | `/api/components/export` | Excel 批量导出 |

常见筛选参数包括：

- `keyword`
- `category_id`
- `box_id`
- `tag`
- `low_stock`
- `page`
- `page_size`

### 图片

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/images/upload` | 上传图片并生成缩略图 |
| DELETE | `/api/images/<image_id>` | 删除图片记录和文件 |

图片上传使用 multipart form-data。字段包括：

- `file`：图片文件
- `component_id`：可选，关联元器件
- `is_primary`：可选，是否主图

### 库存

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/stock/in` | 入库 |
| POST | `/api/stock/out` | 出库 |
| GET | `/api/stock/logs/<component_id>` | 查询库存日志。`component_id` 为 0 时用于首页最近日志 |

### 统计与地图

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/stats` | 首页统计数据 |
| GET | `/api/map` | 地图视图数据 |
| POST | `/api/map/search` | 地图搜索 |

### NFC

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/nfc/bind` | 绑定盒子和 NFC UID |
| POST | `/api/nfc/write` | 生成 NFC 写入 payload |
| GET | `/api/nfc/lookup/<uid>` | 通过 UID 查询盒子 |
| GET | `/api/box/<box_id>` | 获取 NFC 盒子详情数据 |

### BOM

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/bom/import` | 导入 CSV BOM 并匹配库存 |
| POST | `/api/bom/consume` | 按 BOM 执行领料扣减 |
| POST | `/api/bom/export` | 导出 picklist Excel |

## 9. 前端结构

主界面是 `static/index.html`，通过 `x-data="app()"` 初始化 Alpine 应用，主要逻辑在 `static/js/app.js`。

### app.js 状态分区

`app()` 返回一个大的状态对象，主要包含：

- 页面状态：`page`、`modal`、`loading`、`loadingOverlay`
- 基础数据：`categories`、`boxes`
- 首页数据：`stats`、`lowStockList`、`recentLogs`
- 元器件列表：`searchKeyword`、`filterCategory`、`filterBox`、`filterStock`、`componentList`、`componentPagination`
- 元器件表单：`componentForm`、`availableCells`、`currentComponent`
- 库存表单：`stockForm`
- 盒子表单和详情：`boxForm`、`currentBox`、`boxGrid`
- 地图状态：`mapBoxes`、`mapHighlights`、`mapState`、`mapDirty`、拖拽相关状态
- BOM 状态：`bomFile`、`bomData`、`bomStats`
- NFC 状态：`nfcBoxId`、`nfcStatus`、`nfcSupported`
- 扫码状态：`scannerManualText`、`scannerError`

### 主页面视图

`index.html` 通过 `page` 控制不同 section 显示：

- `dashboard`：首页统计、低库存、最近库存变化
- `components`：元器件列表、筛选、详情、表单、Excel 导入导出
- `boxes`：盒子列表和盒子表单
- `box-detail`：盒子网格详情
- `map`：盒子地图和搜索定位
- `bom`：BOM 导入、匹配、短缺、领料、导出
- `nfc`：NFC 绑定和写入

### api.js

`api.js` 封装了：

- `api.get(path, params)`
- `api.post(path, data)`
- `api.put(path, data)`
- `api.del(path)`
- `uploadFile(path, file, extraFields)`
- `downloadFile(path, data, filename)`
- `downloadPostFile(path, data, filename)`

所有普通 JSON API 都期望后端返回 `{ code, data, message }`。当 `code !== 0` 时抛出错误，并通过前端 logger 记录。

### box.html

`box.html` 是独立的盒子详情页面，通常由 NFC URL 打开。页面通过 `/api/box/<box_id>` 获取盒子网格和格子内元器件信息。

## 10. 核心业务流程

### 新增元器件

1. 前端打开元器件表单。
2. 可选择分类、盒子、格子、标签、图片。
3. 前端调用 `POST /api/components`。
4. 后端 `repo.create_component()` 清洗 payload。
5. 如果存在相同规格的合并候选，仓储层会合并库存，而不是创建重复记录。
6. 同步标签和图片。
7. 如果初始数量不为 0，记录库存日志。

### 更新元器件

1. 前端获取详情并填充表单。
2. 调用 `PUT /api/components/<id>`。
3. 仓储层更新主表字段、标签和图片关系。
4. 如果库存数量变化，写入库存日志。

### 入库和出库

1. 前端从元器件详情打开库存弹窗。
2. 调用 `/api/stock/in` 或 `/api/stock/out`。
3. 后端校验数量。
4. 更新 `components.quantity`。
5. 插入 `stock_logs`。

### 盒子网格

1. 创建盒子时提供 `rows` 和 `cols`。
2. 仓储层调用 `_ensure_compartments()` 创建缺失格子。
3. 元器件通过 `box_id` 和 `compartment_id` 绑定到具体格子。
4. `/api/boxes/<id>/grid` 返回格子占用详情。

### BOM 导入和领料

1. 前端上传 CSV 到 `/api/bom/import`。
2. 后端使用 `chardet` 检测编码，并解析表头别名。
3. BOM 行与库存候选进行匹配，优先根据 value、footprint、manufacturer part 等信息。
4. 前端展示匹配、短缺、未匹配统计。
5. 用户确认后调用 `/api/bom/consume`。
6. 后端按匹配结果扣减库存并写库存日志。
7. 可调用 `/api/bom/export` 导出 picklist。

### NFC 绑定和写入

1. 在 NFC 页面选择盒子。
2. 绑定时调用 `/api/nfc/bind`，写入 `boxes.nfc_uid`。
3. 生成写入内容时调用 `/api/nfc/write`，使用 `SERVER_URL` 生成 `/box/<box_id>` URL。
4. 手机扫描 NFC 后访问盒子详情页面。

## 11. 导入导出格式

### 元器件 Excel 导入

接口：`POST /api/components/import`

支持的表头别名在 `app.py` 的 `COMPONENT_HEADER_ALIASES` 中定义。常用字段：

- 名称 / 元器件名称 / name
- 分类 / category
- 型号 / model
- 封装 / package / footprint
- 标称值 / 值 / value / comment
- 耐压 / voltage
- 耐流 / 电流 / current
- 功率 / power
- 精度 / tolerance
- 材质 / 类型 / material
- 厂商 / manufacturer
- 数量 / qty / quantity
- 盒子名称 / 收纳盒 / box
- 行 / row
- 列 / col / column
- 描述 / 备注 / description
- 标签 / tags

导入时如果指定盒子和行列，会查找对应格子。如果盒子或格子不存在，当前行导入失败并记录错误。

### 元器件 Excel 导出

接口：`GET /api/components/export`

导出文件名：`components_export.xlsx`

### BOM CSV 导入

接口：`POST /api/bom/import`

支持表头别名在 `app.py` 的 `BOM_HEADER_ALIASES` 中定义。常用字段：

- comment / 注释 / 值 / part name
- designator / 位号 / reference / ref
- footprint / 封装 / package
- quantity / 数量 / qty
- value / 参数
- manufacturer part / mpn / part number
- manufacturer
- supplier part / lcscpart
- supplier

### BOM Picklist 导出

接口：`POST /api/bom/export`

导出文件名：`bom_picklist.xlsx`

## 12. 日志

日志由 `logger.py` 写入本地文件。

后端日志文件：

```text
log/backend.log
```

前端日志文件：

```text
log/frontend.log
```

前端日志上报接口：

```text
POST /api/frontend/log
```

单次最多接受 100 条日志。

## 13. 部署建议

### 开发环境

直接运行：

```bash
python app.py
```

注意：`app.py` 中开发服务器使用 `debug=True`，只适合本地开发。

### 生产或局域网长期运行

建议使用 gunicorn 加 systemd：

```bash
gunicorn --workers 2 --bind 0.0.0.0:5000 --timeout 120 "app:app"
```

生产环境建议设置：

- `HOST=0.0.0.0`
- `PORT=5000`
- `SERVER_URL=http://实际访问地址:5000`
- `SECRET_KEY=随机长字符串`

需要持久备份的目录：

- `data/inventory.db`
- `uploads/`

可选备份：

- `log/`

## 14. 维护注意事项

### 编码问题

当前仓库中部分中文内容在 PowerShell 下读取时显示为乱码，涉及文件包括：

- `README.md`
- `docs/deploy.md`
- `static/index.html`
- `static/js/app.js`
- `init_db.py` 中的默认分类
- `logger.py` 中的部分中文匹配文本

其中代码里的很多中文字段使用 Unicode 转义，通常不会影响运行。但 HTML、JS、Markdown 中的可见文案如果文件本身已经被错误编码保存，浏览器界面也可能出现乱码。

后续建议：

1. 确认这些文件实际编码。
2. 统一保存为 UTF-8。
3. 对已经损坏的中文文案重新修复。
4. 修复后检查浏览器显示和导入导出表头兼容性。

### 数据库迁移

项目当前没有独立迁移工具。schema 变更主要通过 `init_db.py` 中的幂等 SQL 或手写 `ALTER TABLE` 完成。

新增字段时建议：

1. 修改 `SCHEMA_SQL` 中对应表定义。
2. 在 `init_database()` 中加入兼容旧数据库的迁移逻辑。
3. 更新 `models.py` 的读写逻辑。
4. 更新前端表单和展示。
5. 备份现有 `data/inventory.db` 后再验证。

### 图片文件一致性

图片信息同时存在于数据库 `images` 表和磁盘 `uploads/` 目录。删除图片时应通过仓储层 `delete_image()`，避免只删数据库或只删文件造成残留。

### 格子占用约束

`components.compartment_id` 有唯一约束。修改位置相关逻辑时，需要保证同一个格子不会同时绑定多个元器件。

### 自动合并元器件

新增元器件时，仓储层可能根据规格寻找合并候选并合并库存。修改规格字段、归一化规则或导入逻辑时，需要注意这会影响自动合并行为。

### API 响应格式

前端 `api.js` 假定所有 JSON API 都返回 `{ code, data, message }`。新增 API 时应保持这个格式，否则前端错误处理会失效。

### NFC URL

NFC 写入内容依赖 `SERVER_URL`。部署到局域网设备时，如果 `SERVER_URL` 仍是 `localhost`，手机扫描后会访问手机自己的 localhost，导致无法打开服务。

## 15. 后续开发建议

可优先考虑的改进方向：

- 修复仓库中文编码问题，统一为 UTF-8。
- 将 `app.py` 按领域拆分为 Blueprint，例如 components、boxes、stock、bom、nfc。
- 为 SQLite schema 引入简单迁移机制。
- 为 `models.py` 中的关键业务逻辑补充测试，尤其是库存扣减、BOM 匹配、格子占用和自动合并。
- 为导入导出格式补充示例文件和字段说明。
- 为生产部署提供更完整的 `.env` 加载方案。
- 将前端大文件 `app.js` 按页面或领域拆分，降低维护成本。

## 16. 快速排查索引

| 问题 | 优先查看 |
| --- | --- |
| 页面打不开 | `app.py` 启动日志、端口占用、浏览器控制台 |
| API 报错 | `log/backend.log`、浏览器 Network、`app.py` 对应路由 |
| 前端交互异常 | `static/js/app.js`、`static/js/api.js`、`log/frontend.log` |
| 数据异常 | `models.py` 对应仓储方法、`data/inventory.db` |
| 图片不显示 | `uploads/` 文件是否存在、`images.path`、`/uploads/<filename>` 路由 |
| 盒子格子不对 | `boxes.rows/cols`、`compartments`、`repo._ensure_compartments()` |
| 库存数量不对 | `components.quantity`、`stock_logs`、`repo.record_stock()` |
| BOM 匹配不准 | `parse_bom_csv()`、`normalize_value()`、`normalize_footprint()`、`bom_component_candidates()` |
| NFC 打不开 | `SERVER_URL`、`boxes.nfc_uid`、`/box/<box_id>`、`/api/box/<box_id>` |

