# LED 定位器 — Flask 项目开发指南

## 1. 功能概述

新增 ESP32 LED 定位功能：用户在网页端点击收纳盒/元器件/BOM 项目时，Flask 服务器通过 HTTP 将 LED 控制指令代理转发给局域网内的 ESP32，ESP32 驱动 WS2812 LED 灯带使对应 LED 闪烁或常亮。

### 多设备多灯带架构

系统支持：
- **多台 ESP32 设备**：每台设备有独立的 IP 地址和端口
- **每台设备多条灯带**：通过不同 GPIO 引脚分别驱动，对应不同柜子
- **灵活映射**：每个收纳盒映射到 某台设备的某条灯带上的某个 LED

```
Flask 服务器 (SQLite)
  ├── 设备 A (192.168.1.50)
  │     ├── 灯带 1 (GPIO 8) → 柜子 1 的盒子们
  │     └── 灯带 2 (GPIO 6) → 柜子 2 的盒子们
  └── 设备 B (192.168.1.51)
        ├── 灯带 1 (GPIO 8) → 柜子 3 的盒子们
        └── 灯带 2 (GPIO 4) → 柜子 4 的盒子们
```

Flask 是**代理层**：接收前端请求 → 查数据库获取映射 → 按设备分组 → 分发 HTTP 请求到各 ESP32 → 汇总结果返回前端。

## 2. 现有项目结构速查

### 需要修改的文件

| 文件 | 职责 | 修改内容 |
|------|------|---------|
| `init_db.py` | 数据库 schema | 追加 `led_devices`、`led_strips`、`led_box_mapping` 三张表 |
| `models.py` | SQLite 仓储层 | 追加 LED 设备/灯带/映射的 CRUD 方法 |
| `app.py` | Flask 路由 | 追加 LED 管理 API 和定位控制 API |
| `static/js/app.js` | 前端 Alpine 状态 | 追加 LED 状态属性和方法 |
| `static/index.html` | 前端页面 | 设置面板 LED 配置区域 + 各页面定位按钮 |
| `requirements.txt` | Python 依赖 | 追加 `requests>=2.31` |

### 需要新建的文件

| 文件 | 职责 |
|------|------|
| `led_proxy.py` | ESP32 HTTP 通信代理类 |

### 关键参考代码位置

| 内容 | 文件 | 位置 |
|------|------|------|
| API 响应格式 `success()` / `failure()` | `app.py` | 约第 60-65 行 |
| Token 设置面板路由 | `app.py` | 约第 897-910 行 |
| 仓储层连接模式 `connect()` / `_fetchone()` | `models.py` | 约第 108-126 行 |
| Token 创建/删除方法 | `models.py` | 约第 166-200 行 |
| 隐藏设置面板入口（5 次点击） | `static/js/app.js` | `handleBrandMarkClick()` |
| 设置面板打开方法 | `static/js/app.js` | `openSettings()` |
| Token 管理方法 | `static/js/app.js` | `loadApiTokens()` / `generateApiToken()` 等 |
| 设置弹窗 HTML | `static/index.html` | 搜索 `modal === 'settings'` |
| BOM 页面工具栏 | `static/index.html` | 搜索 `gotoBomMap` 附近 |
| 元器件详情弹窗 | `static/index.html` | 搜索 `modal === 'component-detail'` |
| 地图页面盒子元素 | `static/index.html` | 搜索 `map-box` |
| API 客户端封装 | `static/js/api.js` | `api.get/post/put/del` |
| 数据库 schema | `init_db.py` | `SCHEMA_SQL` 常量 |
| 数据库迁移模式 | `init_db.py` | `init_database()` 末尾的 PRAGMA table_info 检查 |

## 3. 数据库设计

### 3.1 实体关系

```
led_devices (设备)          led_strips (灯带)          led_box_mapping (映射)
┌──────────────┐      ┌───────────────────┐      ┌──────────────────────┐
│ id           │←─────│ device_id         │←─────│ strip_id             │
│ name         │      │ id                │      │ id                   │
│ host         │      │ name              │      │ box_id → boxes.id    │
│ port         │      │ gpio_num          │      │ led_index            │
│ enabled      │      │ led_count         │      └──────────────────────┘
└──────────────┘      └───────────────────┘
```

一个设备有多条灯带，一条灯带映射多个盒子。每个盒子唯一映射到一个 LED（strip_id + led_index）。

### 3.2 led_devices — ESP32 设备表

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

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `name` | TEXT | 设备名称，唯一，如 `"工作台-左"` |
| `host` | TEXT | ESP32 IP 地址 |
| `port` | INTEGER | HTTP 端口，默认 80 |
| `enabled` | INTEGER | 0=禁用, 1=启用 |

### 3.3 led_strips — LED 灯带表

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

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `device_id` | INTEGER | 所属设备 |
| `name` | TEXT | 灯带名称，如 `"柜子1-顶部"` |
| `gpio_num` | INTEGER | ESP32 上的 GPIO 编号。同一设备下唯一（一个 GPIO 只能驱动一条灯带） |
| `led_count` | INTEGER | 该灯带的 LED 数量，前端校验用 |

### 3.4 led_box_mapping — 盒子→LED 映射表

```sql
CREATE TABLE IF NOT EXISTS led_box_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    box_id INTEGER NOT NULL UNIQUE,
    strip_id INTEGER NOT NULL,
    led_index INTEGER NOT NULL,
    FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE,
    FOREIGN KEY (strip_id) REFERENCES led_strips(id) ON DELETE CASCADE,
    UNIQUE(strip_id, led_index)
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `box_id` | INTEGER | 关联盒子，UNIQUE 保证一个盒子只映射一个 LED |
| `strip_id` | INTEGER | 关联灯带 |
| `led_index` | INTEGER | 该灯带上的 0-based LED 位置。`UNIQUE(strip_id, led_index)` 保证同一灯带上一个 LED 只映射一个盒子 |

### 3.5 全局配置（沿用 led_config 单行表）

```sql
CREATE TABLE IF NOT EXISTS led_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    default_color TEXT NOT NULL DEFAULT '#00ff00',
    blink_interval_ms INTEGER NOT NULL DEFAULT 500,
    blink_duration_ms INTEGER NOT NULL DEFAULT 10000,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

| 字段 | 说明 |
|------|------|
| `enabled` | 全局启用/禁用 LED 定位功能 |
| `default_color` | 默认定位颜色 |
| `blink_interval_ms` | 默认闪烁间隔 |
| `blink_duration_ms` | 默认闪烁持续时长 |

全局开关 + 默认参数放在 `led_config`，设备连接信息放在 `led_devices`，灯带参数放在 `led_strips`。

### 3.6 初始化

在 `init_db.py` 的 `SCHEMA_SQL` 末尾追加四张表定义，在 `init_database()` 末尾追加：

```python
# LED 全局配置默认行
existing = conn.execute("SELECT COUNT(*) FROM led_config").fetchone()[0]
if existing == 0:
    conn.execute("INSERT INTO led_config (id, enabled) VALUES (1, 0)")
```

## 4. ESP32 通信接口规范（Flask 视角）

Flask 代理层需要向 ESP32 发送以下请求。这是 Flask 开发时必须遵守的外部接口契约。

### 设备地址

每台设备独立地址：`http://{led_device.host}:{led_device.port}`

从数据库 `led_devices` 表读取，用户在设置面板配置。

### 4.1 健康检查

```
GET /api/health
```

成功响应 (200)：
```json
{"status": "ok", "strips": [{"gpio": 8, "led_count": 30}, {"gpio": 6, "led_count": 20}], "uptime_s": 12345}
```

Flask 用途：测试连接、测量延迟、验证灯带配置。

### 4.2 设置 LED

```
POST /api/led/set
Content-Type: application/json
```

请求体：
```json
{
  "leds": [
    {"gpio": 8, "index": 0, "mode": "blink", "color": "#00ff00", "duration_ms": 10000},
    {"gpio": 8, "index": 3, "mode": "static", "color": "#ff0000", "duration_ms": 0},
    {"gpio": 6, "index": 1, "mode": "blink", "color": "#0000ff", "duration_ms": 5000}
  ]
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `gpio` | int | 是 | — | 灯带对应的 GPIO 编号 |
| `index` | int | 是 | — | 该灯带上的 0-based LED 位置 |
| `mode` | string | 是 | — | `"static"` 常亮, `"blink"` 闪烁 |
| `color` | string | 是 | — | `"#RRGGBB"` 格式 |
| `duration_ms` | int | 否 | 0 | 自动关闭毫秒数。0 = 永久 |

特殊规则：
- `leds` 为空数组 `[]` 等同于 clear（关闭该设备所有灯带的所有 LED）
- `gpio` 对应的灯带不存在时，该条目静默忽略
- `index` 超出该灯带范围时，该条目静默忽略

成功响应 (200)：
```json
{"status": "ok", "applied": 3}
```

### 4.3 清除所有 LED

```
POST /api/led/clear
Content-Type: application/json
```

请求体：`{}`

响应：
```json
{"status": "ok"}
```

关闭该设备上所有灯带的所有 LED。

### 4.4 错误处理规范

| 场景 | 处理方式 |
|------|---------|
| 连接拒绝 | `InventoryError("设备 {name} 连接失败")` |
| 连接超时 (3s) | `InventoryError("设备 {name} 连接超时")` |
| 读取超时 (5s) | `InventoryError("设备 {name} 响应超时")` |
| 非 200 状态码 | `InventoryError("设备 {name} 返回错误: {status}")` |
| JSON 解析失败 | `InventoryError("设备 {name} 响应格式异常")` |

## 5. 仓储层方法设计 — `models.py`

在 `InventoryRepository` 类中追加。遵循现有 `connect()` / `_fetchone()` / `_fetchall()` 模式。

### 5.1 全局配置

```python
def get_led_config(self) -> dict[str, Any]:
    """读取 led_config 单行全局配置。"""

def update_led_config(self, payload: dict[str, Any]) -> dict[str, Any]:
    """更新 led_config。只更新 payload 中存在的字段。"""
```

### 5.2 设备管理

```python
def list_led_devices(self) -> list[dict[str, Any]]:
    """列出所有设备。"""

def get_led_device(self, device_id: int) -> dict[str, Any] | None:
    """获取单个设备。"""

def create_led_device(self, payload: dict[str, Any]) -> dict[str, Any]:
    """创建设备。清洗 name/host/port。"""

def update_led_device(self, device_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """更新设备。"""

def delete_led_device(self, device_id: int) -> None:
    """删除设备。CASCADE 会自动删除关联的灯带和映射。"""
```

### 5.3 灯带管理

```python
def list_led_strips(self, device_id: int | None = None) -> list[dict[str, Any]]:
    """列出灯带。device_id 不为 None 时只返回该设备的灯带。
    JOIN led_devices 带 device_name。"""

def create_led_strip(self, payload: dict[str, Any]) -> dict[str, Any]:
    """创建灯带。验证 device_id 存在，gpio_num 在该设备内唯一。"""

def update_led_strip(self, strip_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """更新灯带。"""

def delete_led_strip(self, strip_id: int) -> None:
    """删除灯带。CASCADE 会自动删除关联的映射。"""
```

### 5.4 映射管理

```python
def get_led_mappings(self) -> list[dict[str, Any]]:
    """查询所有映射。
    JOIN led_strips (带 strip name, gpio_num)
    JOIN led_devices (带 device name)
    JOIN boxes (带 box name)
    返回: [{id, box_id, box_name, strip_id, strip_name, gpio_num,
            device_id, device_name, led_index}, ...]"""

def save_led_mappings(self, mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """全量替换映射。验证 box_id 存在，strip_id 存在，
    led_index 在该 strip 内唯一且 < led_count。"""

def find_led_by_box(self, box_id: int) -> dict[str, Any] | None:
    """查某个盒子的 LED 映射。
    返回 {strip_id, gpio_num, led_index, device_id, device_name, host, port}
    或 None。"""
```

### 可复用的现有方法

- `get_component(component_id)` — 返回 dict 包含 `box_id` 字段
- `list_boxes()` — 返回所有盒子列表
- `clean_text()` / `clean_int()` / `clean_color()` — 数据清洗工具

## 6. LED 代理类设计 — `led_proxy.py`

新建文件。封装所有与 ESP32 的 HTTP 通信逻辑。

### 6.1 核心设计

```python
from __future__ import annotations
import time
import requests
from models import InventoryError, InventoryRepository


class LEDProxy:
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 5

    def __init__(self, repo: InventoryRepository) -> None:
        self.repo = repo

    # ── HTTP 通信 ──────────────────────────────────────

    def _device_url(self, device: dict, path: str) -> str:
        return f"http://{device['host']}:{device['port']}{path}"

    def _request(self, device: dict, method: str, path: str,
                 payload: dict | None = None) -> dict:
        """发送 HTTP 请求到指定 ESP32 设备。"""
        try:
            resp = requests.request(
                method,
                self._device_url(device, path),
                json=payload,
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT),
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise InventoryError(
                f"设备 {device.get('name', '?')} 连接失败，请检查地址和端口")
        except requests.exceptions.Timeout:
            raise InventoryError(f"设备 {device.get('name', '?')} 响应超时")
        except requests.exceptions.HTTPError as e:
            raise InventoryError(
                f"设备 {device.get('name', '?')} 返回错误: {e.response.status_code}")
        except Exception as e:
            raise InventoryError(
                f"设备 {device.get('name', '?')} 通信异常: {e}")

    # ── 测试连接 ───────────────────────────────────────

    def test_device(self, device_id: int) -> dict:
        """测试单个设备连接。返回 {connected, latency_ms, error?, strips?}"""
        device = self.repo.get_led_device(device_id)
        if not device:
            raise InventoryError("设备不存在")
        start = time.monotonic()
        try:
            result = self._request(device, "GET", "/api/health")
            latency = int((time.monotonic() - start) * 1000)
            return {"connected": True, "latency_ms": latency,
                    "strips": result.get("strips", [])}
        except InventoryError as e:
            return {"connected": False, "error": str(e)}

    # ── 单个定位 ───────────────────────────────────────

    def locate_box(self, box_id: int) -> dict:
        """定位单个盒子。查映射 → 找设备 → 发送指令。"""
        cfg = self.repo.get_led_config()
        mapping = self.repo.find_led_by_box(box_id)
        if not mapping:
            raise InventoryError("该盒子未配置 LED 映射")
        device = self.repo.get_led_device(mapping["device_id"])
        if not device or not device.get("enabled"):
            raise InventoryError(f"设备 {mapping.get('device_name', '?')} 未启用")
        self._request(device, "POST", "/api/led/set", {
            "leds": [{
                "gpio": mapping["gpio_num"],
                "index": mapping["led_index"],
                "mode": "blink",
                "color": cfg["default_color"],
                "duration_ms": cfg["blink_duration_ms"],
            }]
        })
        return {"box_id": box_id, "device_name": mapping["device_name"],
                "gpio": mapping["gpio_num"], "led_index": mapping["led_index"],
                "mode": "blink"}

    def locate_component(self, component_id: int) -> dict:
        """定位元器件所在盒子。"""
        comp = self.repo.get_component(component_id)
        if not comp or not comp.get("box_id"):
            raise InventoryError("该元器件未关联收纳盒")
        result = self.locate_box(comp["box_id"])
        result["component_id"] = component_id
        return result

    # ── 批量定位 ───────────────────────────────────────

    def locate_bom(self, box_ids: list[int]) -> dict:
        """批量定位 BOM 涉及的盒子。按设备分组，每组发一次请求。"""
        cfg = self.repo.get_led_config()
        # 收集每个盒子的映射信息
        device_leds: dict[int, list[dict]] = {}  # device_id -> [led指令]
        devices: dict[int, dict] = {}
        resolved = []
        for box_id in box_ids:
            mapping = self.repo.find_led_by_box(box_id)
            if not mapping:
                continue
            did = mapping["device_id"]
            device = self.repo.get_led_device(did)
            if not device or not device.get("enabled"):
                continue
            devices.setdefault(did, device)
            device_leds.setdefault(did, []).append({
                "gpio": mapping["gpio_num"],
                "index": mapping["led_index"],
                "mode": "blink",
                "color": cfg["default_color"],
                "duration_ms": cfg["blink_duration_ms"],
            })
            resolved.append(box_id)
        # 按设备分组发送
        errors = []
        for did, leds in device_leds.items():
            try:
                self._request(devices[did], "POST", "/api/led/set",
                              {"leds": leds})
            except InventoryError as e:
                errors.append(str(e))
        result = {"led_count": sum(len(v) for v in device_leds.values()),
                  "box_ids": resolved}
        if errors:
            result["errors"] = errors
        return result

    # ── 清除 ───────────────────────────────────────────

    def clear_all(self) -> dict:
        """清除所有已启用设备上的所有 LED。"""
        devices = self.repo.list_led_devices()
        errors = []
        cleared = 0
        for device in devices:
            if not device.get("enabled"):
                continue
            try:
                self._request(device, "POST", "/api/led/clear", {})
                cleared += 1
            except InventoryError as e:
                errors.append(str(e))
        result = {"cleared_devices": cleared}
        if errors:
            result["errors"] = errors
        return result

    def clear_device(self, device_id: int) -> dict:
        """清除单个设备上的所有 LED。"""
        device = self.repo.get_led_device(device_id)
        if not device:
            raise InventoryError("设备不存在")
        self._request(device, "POST", "/api/led/clear", {})
        return {"cleared": True, "device_name": device["name"]}
```

### 6.2 初始化位置

在 `app.py` 中，紧接 `repo = InventoryRepository(...)` 之后：

```python
from led_proxy import LEDProxy
led_proxy = LEDProxy(repo)
```

## 7. Flask API 路由设计 — `app.py`

所有接口遵循 `success(data)` / `failure(msg)` 格式。追加在 token API 路由之后。

### 7.1 全局配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings/led` | 获取全局配置 |
| PUT | `/api/settings/led` | 更新全局配置 |

```python
@app.get("/api/settings/led")
def api_settings_led():
    config = repo.get_led_config()
    devices = repo.list_led_devices()
    strips = repo.list_led_strips()
    mappings = repo.get_led_mappings()
    return success({"config": config, "devices": devices,
                    "strips": strips, "mappings": mappings})

@app.put("/api/settings/led")
def api_settings_led_update():
    payload = request.get_json(silent=True) or {}
    config = repo.update_led_config(payload)
    return success({"config": config})
```

GET 响应示例：
```json
{
  "code": 0,
  "data": {
    "config": {
      "enabled": true, "default_color": "#00ff00",
      "blink_interval_ms": 500, "blink_duration_ms": 10000
    },
    "devices": [
      {"id": 1, "name": "工作台-左", "host": "192.168.1.50", "port": 80, "enabled": 1}
    ],
    "strips": [
      {"id": 1, "device_id": 1, "name": "柜子1", "gpio_num": 8, "led_count": 30},
      {"id": 2, "device_id": 1, "name": "柜子2", "gpio_num": 6, "led_count": 20}
    ],
    "mappings": [
      {"id": 1, "box_id": 5, "box_name": "A1", "strip_id": 1,
       "strip_name": "柜子1", "gpio_num": 8, "device_name": "工作台-左", "led_index": 0}
    ]
  },
  "message": "ok"
}
```

### 7.2 设备管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/settings/led/devices` | 添加设备 |
| PUT | `/api/settings/led/devices/<id>` | 更新设备 |
| DELETE | `/api/settings/led/devices/<id>` | 删除设备 |
| POST | `/api/settings/led/devices/<id>/test` | 测试设备连接 |

```python
@app.post("/api/settings/led/devices")
def api_led_device_create():
    payload = request.get_json(silent=True) or {}
    device = repo.create_led_device(payload)
    return success(device)

@app.put("/api/settings/led/devices/<int:device_id>")
def api_led_device_update(device_id: int):
    payload = request.get_json(silent=True) or {}
    device = repo.update_led_device(device_id, payload)
    return success(device)

@app.delete("/api/settings/led/devices/<int:device_id>")
def api_led_device_delete(device_id: int):
    repo.delete_led_device(device_id)
    return success({"id": device_id})

@app.post("/api/settings/led/devices/<int:device_id>/test")
def api_led_device_test(device_id: int):
    result = led_proxy.test_device(device_id)
    return success(result)
```

### 7.3 灯带管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/settings/led/strips` | 添加灯带 |
| PUT | `/api/settings/led/strips/<id>` | 更新灯带 |
| DELETE | `/api/settings/led/strips/<id>` | 删除灯带 |

```python
@app.post("/api/settings/led/strips")
def api_led_strip_create():
    payload = request.get_json(silent=True) or {}
    strip = repo.create_led_strip(payload)
    return success(strip)

@app.put("/api/settings/led/strips/<int:strip_id>")
def api_led_strip_update(strip_id: int):
    payload = request.get_json(silent=True) or {}
    strip = repo.update_led_strip(strip_id, payload)
    return success(strip)

@app.delete("/api/settings/led/strips/<int:strip_id>")
def api_led_strip_delete(strip_id: int):
    repo.delete_led_strip(strip_id)
    return success({"id": strip_id})
```

### 7.4 映射管理

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/api/settings/led/mappings` | 全量替换映射 |

```python
@app.put("/api/settings/led/mappings")
def api_settings_led_mappings():
    payload = request.get_json(silent=True) or {}
    mappings = repo.save_led_mappings(payload.get("mappings", []))
    return success({"mappings": mappings})
```

请求体：
```json
{
  "mappings": [
    {"box_id": 5, "strip_id": 1, "led_index": 0},
    {"box_id": 8, "strip_id": 1, "led_index": 1},
    {"box_id": 12, "strip_id": 2, "led_index": 0}
  ]
}
```

### 7.5 LED 控制接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/led/locate/box/<int:box_id>` | 定位单个盒子 |
| POST | `/api/led/locate/component/<int:component_id>` | 定位元器件所在盒子 |
| POST | `/api/led/locate/bom` | 批量定位 BOM 盒子 |
| POST | `/api/led/clear` | 清除所有设备的 LED |
| POST | `/api/led/clear/<int:device_id>` | 清除单个设备的 LED |

```python
@app.post("/api/led/locate/box/<int:box_id>")
def api_led_locate_box(box_id: int):
    result = led_proxy.locate_box(box_id)
    return success(result)

@app.post("/api/led/locate/component/<int:component_id>")
def api_led_locate_component(component_id: int):
    result = led_proxy.locate_component(component_id)
    return success(result)

@app.post("/api/led/locate/bom")
def api_led_locate_bom():
    payload = request.get_json(silent=True) or {}
    box_ids = payload.get("box_ids", [])
    result = led_proxy.locate_bom(box_ids)
    return success(result)

@app.post("/api/led/clear")
def api_led_clear():
    result = led_proxy.clear_all()
    return success(result)

@app.post("/api/led/clear/<int:device_id>")
def api_led_clear_device(device_id: int):
    result = led_proxy.clear_device(device_id)
    return success(result)
```

### 7.6 完整路由汇总

| 方法 | 路径 | 说明 | 代理到 ESP32 |
|------|------|------|-------------|
| GET | `/api/settings/led` | 获取全部配置 | 否 |
| PUT | `/api/settings/led` | 更新全局配置 | 否 |
| POST | `/api/settings/led/devices` | 添加设备 | 否 |
| PUT | `/api/settings/led/devices/<id>` | 更新设备 | 否 |
| DELETE | `/api/settings/led/devices/<id>` | 删除设备 | 否 |
| POST | `/api/settings/led/devices/<id>/test` | 测试连接 | GET `/api/health` |
| POST | `/api/settings/led/strips` | 添加灯带 | 否 |
| PUT | `/api/settings/led/strips/<id>` | 更新灯带 | 否 |
| DELETE | `/api/settings/led/strips/<id>` | 删除灯带 | 否 |
| PUT | `/api/settings/led/mappings` | 替换映射 | 否 |
| POST | `/api/led/locate/box/<id>` | 定位盒子 | POST `/api/led/set` |
| POST | `/api/led/locate/component/<id>` | 定位元器件 | POST `/api/led/set` |
| POST | `/api/led/locate/bom` | BOM 批量定位 | POST `/api/led/set` (多设备) |
| POST | `/api/led/clear` | 清除所有 | POST `/api/led/clear` (多设备) |
| POST | `/api/led/clear/<device_id>` | 清除单设备 | POST `/api/led/clear` |

## 8. 前端开发指南

### 8.1 Alpine 状态追加 — `static/js/app.js`

**新增状态属性：**

```javascript
// LED 全局配置
ledConfig: {
    enabled: false, default_color: '#00ff00',
    blink_interval_ms: 500, blink_duration_ms: 10000
},
// 设备列表
ledDevices: [],          // [{id, name, host, port, enabled}, ...]
// 灯带列表
ledStrips: [],           // [{id, device_id, name, gpio_num, led_count, device_name}, ...]
// 映射列表
ledMappings: [],
// 设备表单
ledDeviceForm: null,     // 编辑中: {id?, name, host, port, enabled}，null=新增模式
// 灯带表单
ledStripForm: null,
// 测试结果
ledTestResults: {},      // {device_id: {connected, latency_ms, error?}}
ledTestLoading: {},
```

**新增方法（概要）：**

- `loadLedConfig()` — GET `/api/settings/led`，填充全部状态
- `saveLedConfig()` — PUT `/api/settings/led`，保存全局配置
- `saveLedMappings()` — PUT `/api/settings/led/mappings`
- `createLedDevice()` / `editLedDevice(device)` / `saveLedDevice()` / `deleteLedDevice(device)`
- `createLedStrip()` / `editLedStrip(strip)` / `saveLedStrip()` / `deleteLedStrip(strip)`
- `testLedDevice(deviceId)` — POST `/api/settings/led/devices/{id}/test`
- `locateBox(boxId)` — POST `/api/led/locate/box/{id}`
- `locateComponent(compId)` — POST `/api/led/locate/component/{id}`
- `locateBomItems()` — 收集 BOM box_ids → POST `/api/led/locate/bom`
- `clearLed()` — POST `/api/led/clear`
- `addLedMapping()` / `removeLedMapping(idx)`

**修改现有方法：**

`openSettings()` 末尾追加 `this.loadLedConfig()`。

### 8.2 设置面板 — `static/index.html`

在 Token 管理区域之后追加以下 section：

**Section 1 — 全局配置：**
- 复选框：启用 LED 定位
- 颜色选择器：默认定位颜色
- 数字框：闪烁时长 ms
- 保存按钮

**Section 2 — 设备管理：**
- 设备列表：每行显示 name、host:port、启用状态、测试按钮、编辑按钮、删除按钮
- 测试结果显示（每个设备独立）
- 添加设备按钮 → 弹出内联表单（name、host、port）
- 编辑设备 → 同样内联表单

**Section 3 — 灯带管理：**
- 灯带列表：每行显示所属设备名、灯带名、GPIO、LED 数量、编辑/删除
- 添加灯带按钮 → 内联表单（选择设备、name、gpio_num、led_count）

**Section 4 — 映射管理：**
- 映射列表：每行选择盒子（下拉）→ 选择灯带（下拉）→ 输入 LED 索引 → 删除
- 添加映射 / 保存映射按钮

### 8.3 定位按钮（条件显示 `x-show="ledConfig.enabled"`）

| 页面位置 | 插入位置 | 按钮 | 方法调用 |
|---------|---------|------|---------|
| 元器件详情弹窗 | 工具栏 | "LED 定位" | `locateComponent(currentComponent.id)` |
| 盒子详情页 | 标题旁工具栏 | "LED 定位" | `locateBox(currentBox.id)` |
| 地图页面 | 每个 map-box 内部 | 小图标 | `locateBox(box.id)`，需 `@click.stop` |
| BOM 页面 | 工具栏 | "LED 定位" | `locateBomItems()` |

## 9. 开发顺序

1. `init_db.py` — 追加四张表定义 + 默认行
2. `models.py` — 追加全局配置、设备、灯带、映射的 CRUD 方法
3. `led_proxy.py` — 新建代理类（支持多设备分发）
4. `requirements.txt` — 追加 `requests>=2.31`
5. `app.py` — 追加 import + 初始化 + 15 个路由
6. `static/js/app.js` — 追加状态和方法
7. `static/index.html` — 追加设置面板 + 定位按钮
8. 测试

## 10. 编码规范

- Python: 遵循项目现有风格，type hints，不引入不必要依赖
- API 响应: 必须使用 `success(data)` / `failure(msg)`，禁止裸 `jsonify`
- 错误: 使用 `InventoryError` 抛出，由全局异常处理器捕获
- 前端: 遵循 Alpine.js 模式，使用 `api.get/post/put/del`，toast 提示
- 日志: 重要操作写入 `file_logger.write_backend("LED", ...)`
- 数据库: 所有写操作通过 `connect()` 上下文管理器

## 11. 测试方法

### 11.1 后端测试（ESP32 未连接）

```bash
python app.py

# 验证表创建
sqlite3 data/inventory.db ".tables"
# 应包含 led_config, led_devices, led_strips, led_box_mapping

# 获取全局配置
curl http://localhost:5000/api/settings/led

# 启用并设置全局配置
curl -X PUT http://localhost:5000/api/settings/led \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "default_color": "#00ff00", "blink_duration_ms": 10000}'

# 添加设备
curl -X POST http://localhost:5000/api/settings/led/devices \
  -H "Content-Type: application/json" \
  -d '{"name": "工作台-左", "host": "192.168.1.50", "port": 80}'

# 添加灯带
curl -X POST http://localhost:5000/api/settings/led/strips \
  -H "Content-Type: application/json" \
  -d '{"device_id": 1, "name": "柜子1", "gpio_num": 8, "led_count": 30}'

# 添加映射
curl -X PUT http://localhost:5000/api/settings/led/mappings \
  -H "Content-Type: application/json" \
  -d '{"mappings": [{"box_id": 1, "strip_id": 1, "led_index": 0}]}'

# 测试连接（应返回 connected: false）
curl -X POST http://localhost:5000/api/settings/led/devices/1/test

# 定位（应返回连接失败）
curl -X POST http://localhost:5000/api/led/locate/box/1
```

### 11.2 前端测试

1. 5 次点击 CI 图标打开设置面板
2. 全局配置区域正常渲染
3. 添加设备 → 保存 → 刷新确认持久化
4. 添加灯带 → 选择设备 → 保存
5. 添加映射 → 选择盒子和灯带 → 保存
6. 测试连接按钮应返回失败（ESP32 未运行）

### 11.3 联调测试

1. ESP32 烧录固件并连接 WiFi
2. 添加设备 → 测试连接 → 成功 + 延迟
3. 元器件详情点击定位 → LED 闪烁
4. BOM 页面点击定位 → 所有匹配盒子的 LED 闪烁（跨设备也正常）
5. 清除按钮 → 所有 LED 熄灭
