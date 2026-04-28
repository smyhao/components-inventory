# LED 定位器 Flask 端开发 Prompt

你现在要在一个已有 Flask + SQLite + 前端静态资源项目中开发 ESP32 LED 定位器功能。请先阅读目标项目根目录的 `AGENTS.md` 或等价开发规范，并严格按目标项目的分层约束落位代码：路由只做请求解析和响应封装，业务逻辑放入 `services/`，数据访问放入 `repositories/`，统一仓储外观通过 `models.py` 的 `InventoryRepository` 暴露，数据库结构和兼容迁移集中放在 `init_db.py`，前端页面、样式和脚本放在 `static/`。

本 prompt 是开发任务说明，不是事后总结文档。实现时请以目标项目现有代码风格为准，不要照搬不适配的文件名或旧式单文件写法；若目标项目仍是单体 `app.py` 结构，也要尽量保持路由薄层，并把可测试逻辑拆到服务和仓储层。

## 1. 目标功能

实现 ESP32 LED 定位功能：用户在网页端点击收纳盒、元器件详情、地图盒子或 BOM 页面定位按钮时，Flask 后端根据数据库中的盒子到 LED 映射，向局域网内一台或多台 ESP32 发送 HTTP 控制指令，驱动 WS2812 LED 灯带闪烁对应 LED。

系统需要支持：

- 多台 ESP32 设备，每台设备有独立名称、IP 地址、端口和启用状态。
- 每台设备多条灯带，每条灯带由一个 GPIO 引脚驱动。
- 每个收纳盒唯一映射到某条灯带上的某个 LED 索引。
- 每条盒子映射可配置独立颜色，BOM 批量定位时按各盒子的映射颜色发送。
- 全局 LED 功能开关和默认闪烁时长配置。
- 设备连接测试、单盒定位、元器件定位、BOM 批量定位、清除全部 LED。

Flask 端作为代理层：

```text
前端操作
  -> Flask 路由
  -> LED 业务服务
  -> InventoryRepository 外观
  -> LED 仓储 / SQLite
  -> LED 代理服务按设备分组发送 HTTP 请求
  -> ESP32 /api/led/set 或 /api/led/clear
```

## 2. 文件落位要求

请按目标项目规范拆分，推荐结构如下：

| 位置 | 职责 |
|------|------|
| `routes/led.py` 或现有路由模块 | LED API 路由，负责参数读取、调用服务、统一响应 |
| `services/led_service.py` | LED 业务编排：定位盒子、定位元器件、BOM 分组定位、清除 |
| `services/led_proxy.py` | 与 ESP32 的 HTTP 通信封装、超时和错误转换 |
| `repositories/led_repository.py` | LED 配置、设备、灯带、映射的 SQL 查询和写入 |
| `models.py` | 在 `InventoryRepository` 外观层暴露 LED 仓储能力 |
| `init_db.py` | 新增表结构、索引和兼容迁移 |
| `static/js/app.js` | Alpine 状态、API 调用、定位和设置页交互 |
| `static/index.html` | 设置弹窗 LED 标签页、定位按钮入口 |
| `static/css/style.css` | LED 设置页和地图定位按钮样式 |
| `requirements.txt` | 如果项目尚未包含 HTTP 客户端，加入 `requests>=2.31` |
| `tests/test_led_*.py` | 仓储、服务和 API 的关键测试 |

新增或重写的源代码文件顶部必须有简洁中文文件说明，说明职责、所属层级和边界。新增函数、类或复杂代码块补充中文 docstring 或注释，解释业务意图和关键约束。

## 3. 数据库设计

在 `init_db.py` 的集中 schema 中加入以下表，并提供兼容迁移。不要在路由或服务中散落建表逻辑。

### 3.1 全局配置表

```sql
CREATE TABLE IF NOT EXISTS led_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    blink_interval_ms INTEGER NOT NULL DEFAULT 500,
    blink_duration_ms INTEGER NOT NULL DEFAULT 10000,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

说明：

- `enabled`：全局启用/禁用 LED 定位。
- `blink_interval_ms`：预留给 ESP32 闪烁间隔配置，当前 Flask 至少要保存并返回。
- `blink_duration_ms`：定位指令持续时间。
- 不再使用全局默认颜色，颜色属于每条盒子映射。

初始化时保证存在单行配置：

```python
existing = conn.execute("SELECT COUNT(*) FROM led_config").fetchone()[0]
if existing == 0:
    conn.execute("INSERT INTO led_config (id, enabled) VALUES (1, 0)")
```

### 3.2 设备表

```sql
CREATE TABLE IF NOT EXISTS led_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 80,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 灯带表

```sql
CREATE TABLE IF NOT EXISTS led_strips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    gpio_num INTEGER NOT NULL,
    led_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (device_id) REFERENCES led_devices(id) ON DELETE CASCADE,
    UNIQUE(device_id, gpio_num)
);
```

### 3.4 盒子到 LED 映射表

```sql
CREATE TABLE IF NOT EXISTS led_box_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    box_id INTEGER NOT NULL UNIQUE,
    strip_id INTEGER NOT NULL,
    led_index INTEGER NOT NULL,
    color TEXT NOT NULL DEFAULT '#00ff00',
    FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE,
    FOREIGN KEY (strip_id) REFERENCES led_strips(id) ON DELETE CASCADE,
    UNIQUE(strip_id, led_index)
);
```

兼容迁移要求：

- 旧库没有 `led_config`、`led_devices`、`led_strips`、`led_box_mapping` 时应自动创建。
- 旧库已有 `led_box_mapping` 但没有 `color` 字段时，执行 `ALTER TABLE led_box_mapping ADD COLUMN color TEXT NOT NULL DEFAULT '#00ff00'`。
- 如果目标项目已有迁移工具，按项目既有迁移风格实现。

## 4. 仓储外观能力

在仓储层实现 SQL，并通过 `models.py` 的 `InventoryRepository` 暴露以下能力。清洗函数优先复用项目已有工具，例如 `clean_text()`、`clean_int()`、`clean_color()`。

```python
def get_led_config(self) -> dict[str, Any]: ...
def update_led_config(self, payload: dict[str, Any]) -> dict[str, Any]: ...

def list_led_devices(self) -> list[dict[str, Any]]: ...
def get_led_device(self, device_id: int) -> dict[str, Any] | None: ...
def create_led_device(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def update_led_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...
def delete_led_device(self, device_id: int) -> None: ...

def list_led_strips(self, device_id: int | None = None) -> list[dict[str, Any]]: ...
def create_led_strip(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def update_led_strip(self, strip_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...
def delete_led_strip(self, strip_id: int) -> None: ...

def get_led_mappings(self) -> list[dict[str, Any]]: ...
def save_led_mappings(self, mappings: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
def find_led_by_box(self, box_id: int) -> dict[str, Any] | None: ...
```

关键校验：

- 设备名称不能为空且唯一，设备地址不能为空，端口默认 80。
- 同一设备下 `gpio_num` 唯一。
- `box_id` 必须存在，且一个盒子只能映射一次。
- `strip_id` 必须存在。
- `led_index` 必须大于等于 0；当 `led_count > 0` 时必须小于 `led_count`。
- 同一灯带上的同一 `led_index` 只能映射一个盒子。
- `color` 必须规范化为 `#RRGGBB`，非法值回退为 `#00ff00` 或抛出项目约定错误。

`get_led_mappings()` 返回字段至少包含：

```json
{
  "id": 1,
  "box_id": 5,
  "box_name": "A1",
  "strip_id": 1,
  "strip_name": "柜子1",
  "gpio_num": 8,
  "device_id": 1,
  "device_name": "工作台-左",
  "led_index": 0,
  "color": "#00ff00"
}
```

`find_led_by_box()` 返回字段至少包含 `strip_id`、`led_index`、`color`、`gpio_num`、`device_id`、`device_name`、`host`、`port`。

## 5. ESP32 HTTP 代理

封装 ESP32 通信，不要把 `requests` 调用散落在路由里。

设备地址格式：

```text
http://{device.host}:{device.port}
```

ESP32 需要提供以下接口。

### 5.1 健康检查

```http
GET /api/health
```

成功示例：

```json
{
  "status": "ok",
  "strips": [
    {"gpio": 8, "led_count": 30},
    {"gpio": 6, "led_count": 20}
  ],
  "uptime_s": 12345
}
```

### 5.2 设置 LED

```http
POST /api/led/set
Content-Type: application/json
```

请求体：

```json
{
  "leds": [
    {"gpio": 8, "index": 0, "mode": "blink", "color": "#00ff00", "duration_ms": 10000},
    {"gpio": 6, "index": 1, "mode": "blink", "color": "#ff0000", "duration_ms": 10000}
  ]
}
```

字段约定：

| 字段 | 类型 | 说明 |
|------|------|------|
| `gpio` | int | 灯带对应 GPIO |
| `index` | int | 0-based LED 索引 |
| `mode` | string | 当前使用 `"blink"`，ESP32 可扩展 `"static"` |
| `color` | string | `#RRGGBB` |
| `duration_ms` | int | 自动关闭时间，0 表示永久 |

### 5.3 清除 LED

```http
POST /api/led/clear
Content-Type: application/json
```

请求体：`{}`

代理错误处理要求：

- 连接失败：抛出项目统一业务异常，消息类似 `设备 {name} 连接失败，请检查地址和端口`。
- 超时：消息类似 `设备 {name} 响应超时`。
- 非 2xx：消息类似 `设备 {name} 返回错误: {status}`。
- 响应 JSON 异常或其他错误：转换为统一业务异常。
- 连接测试接口不要抛给前端 500，应返回 `{connected: false, error: "..."}`。

## 6. 服务层业务

服务层负责把仓储查询结果转换成 ESP32 指令。

### 6.1 测试设备

`test_device(device_id)`：

- 查询设备，不存在则抛业务异常。
- 请求 `GET /api/health`。
- 成功返回 `{connected: true, latency_ms, strips}`。
- 失败返回 `{connected: false, error}`。

### 6.2 定位盒子

`locate_box(box_id)`：

- 查询盒子映射，不存在则提示 `该盒子未配置 LED 映射`。
- 查询设备，设备不存在或禁用则提示设备未启用。
- 发送单条 `/api/led/set` 指令。
- 使用映射上的 `color`，没有颜色时回退 `#00ff00`。
- 使用 `led_config.blink_duration_ms` 作为 `duration_ms`。

### 6.3 定位元器件

`locate_component(component_id)`：

- 复用项目已有 `get_component()`。
- 元器件没有关联盒子时提示 `该元器件未关联收纳盒`。
- 调用 `locate_box(component.box_id)`。

### 6.4 BOM 批量定位

`locate_bom(box_ids)`：

- 对传入盒子 ID 去重。
- 查询每个盒子的 LED 映射。
- 跳过未配置映射或设备禁用的盒子。
- 按 `device_id` 分组，每台设备只发送一次 `/api/led/set`。
- 每条 LED 指令使用该盒子映射自己的颜色。
- 返回 `{led_count, box_ids}`；部分设备失败时附加 `errors` 数组。

### 6.5 清除

`clear_all()`：

- 遍历所有启用设备。
- 对每台设备发送 `POST /api/led/clear`。
- 返回 `{cleared_devices}`，部分失败时附加 `errors`。

`clear_device(device_id)`：

- 查询单台设备并发送清除指令。

重要操作写入项目现有日志系统，例如 `file_logger.write_backend("LED", "...")`。

## 7. Flask API

所有接口必须使用项目统一响应封装，例如 `success(data)` / `failure(message)`。不要在路由里裸 `jsonify`，不要在路由里写 SQL 或直接调用 ESP32。

| 方法 | 路径 | 说明 | 是否访问 ESP32 |
|------|------|------|----------------|
| GET | `/api/settings/led` | 获取配置、设备、灯带、映射 | 否 |
| PUT | `/api/settings/led` | 更新全局开关和闪烁参数 | 否 |
| POST | `/api/settings/led/devices` | 添加设备 | 否 |
| PUT | `/api/settings/led/devices/<id>` | 更新设备 | 否 |
| DELETE | `/api/settings/led/devices/<id>` | 删除设备 | 否 |
| POST | `/api/settings/led/devices/<id>/test` | 测试设备连接 | 是，`GET /api/health` |
| POST | `/api/settings/led/strips` | 添加灯带 | 否 |
| PUT | `/api/settings/led/strips/<id>` | 更新灯带 | 否 |
| DELETE | `/api/settings/led/strips/<id>` | 删除灯带 | 否 |
| PUT | `/api/settings/led/mappings` | 全量保存映射 | 否 |
| POST | `/api/led/locate/box/<id>` | 定位盒子 | 是 |
| POST | `/api/led/locate/component/<id>` | 定位元器件所在盒子 | 是 |
| POST | `/api/led/locate/bom` | BOM 批量定位 | 是 |
| POST | `/api/led/clear` | 清除所有启用设备 LED | 是 |
| POST | `/api/led/clear/<device_id>` | 清除单台设备 LED | 是 |

`GET /api/settings/led` 响应数据结构：

```json
{
  "config": {
    "id": 1,
    "enabled": 1,
    "blink_interval_ms": 500,
    "blink_duration_ms": 10000
  },
  "devices": [],
  "strips": [],
  "mappings": []
}
```

`PUT /api/settings/led/mappings` 请求体：

```json
{
  "mappings": [
    {"box_id": 5, "strip_id": 1, "led_index": 0, "color": "#00ff00"},
    {"box_id": 8, "strip_id": 1, "led_index": 1, "color": "#ff0000"}
  ]
}
```

`POST /api/led/locate/bom` 请求体：

```json
{"box_ids": [5, 8, 12]}
```

## 8. 前端实现要求

前端按当前优化后的界面形态实现，不要沿用旧的单长表单布局。

### 8.1 状态和方法

在 Alpine 主状态中加入：

```javascript
settingsTab: 'token',
ledConfig: { enabled: false, blink_interval_ms: 500, blink_duration_ms: 10000 },
ledDevices: [],
ledStrips: [],
ledMappings: [],
ledDeviceForm: null,
ledStripForm: null,
ledTestResults: {},
ledTestLoading: {},
```

需要实现的方法：

- `loadLedConfig()`：读取 `/api/settings/led`，填充 `ledConfig`、`ledDevices`、`ledStrips`、`ledMappings`。
- `normalizeLedConfig(config)`：将 `enabled` 转为布尔值，补齐闪烁参数。
- `normalizeLedColor(color)`：校验并规范化 `#RRGGBB`。
- `normalizeLedMappings(mappings)`：转数字字段并补齐颜色。
- `ledStripLabel(strip)`：显示 `设备名 / 灯带名 / GPIO n`。
- `nextLedIndex(stripId)`：为新增映射选择同灯带下第一个未占用 LED 索引。
- `prepareLedMapping(mapping)`：修正颜色和非法索引。
- `saveLedConfig()`、`clearLed()`。
- `createLedDevice()`、`editLedDevice(device)`、`cancelLedDeviceForm()`、`saveLedDevice()`、`deleteLedDevice(device)`、`testLedDevice(deviceId)`。
- `createLedStrip()`、`editLedStrip(strip)`、`cancelLedStripForm()`、`saveLedStrip()`、`deleteLedStrip(strip)`。
- `addLedMapping()`、`removeLedMapping(index)`、`saveLedMappings()`。
- `locateBox(boxId)`、`locateComponent(componentId)`、`locateBomItems()`。

打开设置弹窗时调用 `loadLedConfig()`。如果目标项目已有 Token 设置页，新增 `settingsTab` 标签页切换；默认仍可停留在现有 Token 标签页。

### 8.2 设置弹窗 UI

设置弹窗应使用标签页：

- `设备 Token`
- `LED 定位`

`LED 定位` 标签页按以下结构组织。

第一块：功能开关和概览

- 标题 `LED 定位功能`。
- 说明：启用后可在元器件详情、收纳盒、地图和 BOM 页面使用 LED 定位。
- 右侧开关，绑定 `ledConfig.enabled`，变更时立即 `saveLedConfig()`。
- 启用后显示概览：设备数量、灯带数量、映射数量。
- 显示闪烁时长输入框，单位 `ms`，建议范围 `1000-60000`。
- 显示说明 `每盒独立颜色`。
- 提供 `清除所有 LED` 按钮，调用 `clearLed()`。

第二块：设备管理

- 使用卡片列表展示设备，而不是传统表格。
- 每张卡显示设备名称、禁用徽标、`host:port`。
- 每张卡提供 `测试`、`编辑`、`删除` 按钮。
- 测试中按钮显示 `...`，测试结果显示 `OK · {latency_ms}ms` 或错误消息。
- 添加/编辑设备使用内联表单，字段：名称、地址、端口、启用状态。
- 删除设备时提示会连带删除灯带和映射。

第三块：灯带管理

- 使用同样的卡片列表展示灯带。
- 每张卡显示灯带名、所属设备名、GPIO、LED 数量。
- 添加/编辑灯带使用内联表单，字段：设备、名称、GPIO、LED 数量。

第四块：盒子到 LED 映射

- 仅在 LED 已启用且存在灯带时显示。
- 顶部显示 `已配置 n 条映射`。
- 提供 `+ 添加` 和 `保存映射` 按钮。
- 每条映射使用一行紧凑表单：盒子下拉、灯带下拉、LED 索引输入、颜色选择器、删除按钮。
- 颜色选择器旁显示当前颜色文本。
- 切换灯带时自动填入 `nextLedIndex(strip_id)`。

### 8.3 定位入口

仅在 `ledConfig.enabled` 为真时显示定位入口。

| 页面位置 | UI | 调用 |
|---------|----|------|
| 收纳盒详情 / 当前盒子区域 | `LED 定位` 按钮 | `locateBox(currentBox.id)` |
| 元器件详情弹窗 | `LED 定位` 按钮 | `locateComponent(currentComponent.id)` |
| 地图页面每个盒子 | 小型灯泡按钮，点击需 `@click.stop` | `locateBox(box.id)` |
| BOM 页面工具栏 | `LED 定位` 按钮 | `locateBomItems()` |

地图盒子按钮样式建议：

- 默认不干扰盒子主体信息。
- hover 盒子或按钮时清晰可见。
- 使用现有按钮和颜色体系，不引入突兀的新主题。

## 9. 样式要求

遵循目标项目现有视觉系统。参考类名可使用：

- `.settings-tabs`、`.settings-tab`
- `.led-toggle-row`、`.led-section-header`
- `.led-overview`、`.led-overview-item`
- `.led-config-row`
- `.led-device-list`、`.led-device-card`
- `.led-inline-form`、`.led-form-grid`
- `.led-mapping-list`、`.led-mapping-row`
- `.map-box-led-btn`

实现时注意：

- 不要把大量业务逻辑塞进 HTML。
- 按钮、输入框、卡片、空状态与已有设置弹窗风格一致。
- 移动端下卡片、表单、映射行要能换行，不得文字重叠。
- 不要创建营销式页面；这是设置和操作界面，应保持紧凑、清晰、适合反复使用。

## 10. 测试要求

至少覆盖以下测试：

- 数据库初始化会创建四张 LED 表，并创建 `led_config` 默认行。
- 旧库 `led_box_mapping` 缺少 `color` 字段时能兼容迁移。
- 设备 CRUD：名称不能为空、名称唯一、删除级联关联灯带和映射。
- 灯带 CRUD：设备必须存在，同设备 GPIO 唯一，LED 数量约束有效。
- 映射保存：盒子必须存在、灯带必须存在、同盒唯一、同灯带同索引唯一、颜色规范化。
- `locate_box()`：未映射、设备禁用、正常发送指令三种路径。
- `locate_component()`：元器件未关联盒子的失败路径。
- `locate_bom()`：按设备分组发送、跳过未映射盒子、部分设备失败时返回 errors。
- API 成功路径和关键失败路径。

前端手动验收：

1. 打开设置弹窗，切换到 `LED 定位` 标签页。
2. 启用 LED 定位，概览区显示设备、灯带、映射数量。
3. 添加设备，刷新后仍存在。
4. 添加灯带，GPIO 和 LED 数量显示正确。
5. 添加映射，选择盒子、灯带、索引和颜色，保存后颜色保持。
6. 未连接 ESP32 时测试设备返回失败提示，不导致页面崩溃。
7. 地图、元器件详情、盒子详情、BOM 页面在启用时显示定位按钮，禁用时隐藏。
8. 连接真实 ESP32 后，单盒定位和 BOM 批量定位能按映射颜色闪烁，清除按钮能熄灭所有 LED。

## 11. 开发顺序

1. 阅读目标项目规范、现有路由、仓储、响应封装、前端状态结构和测试 fixtures。
2. 在 `init_db.py` 添加表结构和兼容迁移。
3. 实现 LED 仓储，并通过 `InventoryRepository` 暴露外观方法。
4. 实现 LED 服务和 ESP32 代理。
5. 接入 Flask API 路由。
6. 实现前端设置标签页、设备/灯带/映射管理、定位入口和样式。
7. 补充后端测试和必要前端手动验收。
8. 运行项目现有测试；如因目标环境缺少依赖或硬件无法完整验证，请在交付说明中明确说明。

不要因为本 prompt 单独创建目标项目不存在的架构文档；如果目标项目已有架构文档或本地规范要求同步，则按目标项目规范更新。
