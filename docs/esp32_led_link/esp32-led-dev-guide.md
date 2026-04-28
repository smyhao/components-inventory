# ESP32 LED 定位器 — 固件开发指南

## 1. 项目概述

ESP32 LED 定位器是一个独立的 ESP-IDF 固件项目，运行在 ESP32-S3 芯片上，通过 HTTP API 接收 Flask 服务器发来的 LED 控制指令，驱动 WS2812 LED 灯带。

### 多灯带架构

一台 ESP32 可以通过**不同 GPIO 引脚**分别驱动多条 WS2812 灯带，每条灯带对应一个柜子或一排收纳盒。Flask 服务器通过 `gpio` 字段指定操作哪条灯带上的哪个 LED。

```
ESP32-S3
  ├── GPIO 8 → 灯带 A (30 颗 LED) → 柜子 1
  ├── GPIO 6 → 灯带 B (20 颗 LED) → 柜子 2
  └── GPIO 4 → 灯带 C (15 颗 LED) → 柜子 3
```

多台 ESP32 可部署在不同位置，Flask 服务器统一管理。

### 系统架构

```
[浏览器] → [Flask 服务器] → HTTP POST ─┬→ [ESP32-A] → 灯带1(GPIO8) + 灯带2(GPIO6)
                                         └→ [ESP32-B] → 灯带1(GPIO8)
```

ESP32 是**纯被动方**：不主动连接 Flask，只监听 HTTP 请求并执行 LED 操作。

### 通信协议

- 传输层：HTTP over TCP/IP（局域网）
- 数据格式：JSON
- 方向：Flask → ESP32（单向请求/响应）
- 端口：默认 80，可通过 menuconfig 修改

## 2. 硬件需求

| 硬件 | 说明 |
|------|------|
| ESP32-S3 开发板 | 带 WiFi 的 MCU，RMT 外设支持多通道 |
| WS2812B LED 灯带 | 多条，每条独立连接一个 GPIO |
| 5V 电源 | 每条灯带独立供电或共用大功率电源 |
| 杜邦线 | 连接 ESP32 GPIO → 各灯带 DIN |

### 引脚分配示例

| 功能 | GPIO | 说明 |
|------|------|------|
| 灯带 1 DIN | GPIO 8 | 柜子 1 |
| 灯带 2 DIN | GPIO 6 | 柜子 2 |
| 灯带 3 DIN | GPIO 4 | 柜子 3 |

GPIO 分配通过 menuconfig 或 AP 配网页配置，不硬编码。

### 功耗估算

- 每颗 WS2812 全亮（白色）约 60mA
- 30 颗 LED 全亮约 1.8A
- 多条灯带需确保总电流不超过电源额定功率
- ESP32 开发板通过 USB 供电即可，LED 部分独立供电

## 3. ESP32 HTTP API 规范（必须严格实现）

ESP32 必须暴露以下 HTTP 端点。Flask 服务器（`led_proxy.py`）依赖这些接口。

### 3.0 基础约定

- 所有端点路径以 `/api/` 开头
- 所有 POST 端点接受 `Content-Type: application/json`
- 所有响应均为 JSON，字符编码 UTF-8
- 成功响应包含 `"status": "ok"`
- 错误响应包含 `"status": "error"` 和 `"message"` 字段
- 请求体最大 4096 字节

### 3.1 健康检查

```
GET /api/health
```

成功响应 (200)：
```json
{
  "status": "ok",
  "strips": [
    {"gpio": 8, "led_count": 30},
    {"gpio": 6, "led_count": 20},
    {"gpio": 4, "led_count": 15}
  ],
  "uptime_s": 12345
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 固定 `"ok"` |
| `strips` | array | 本设备的所有灯带信息 |
| `strips[].gpio` | int | GPIO 编号 |
| `strips[].led_count` | int | 该灯带 LED 数量 |
| `uptime_s` | int | 启动后秒数（可选） |

Flask 使用此接口：测试连接、验证灯带配置是否匹配。

### 3.2 设置 LED

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

**字段规范：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `leds` | array | 是 | — | LED 指令数组 |
| `leds[].gpio` | int | 是 | — | 灯带对应的 GPIO 编号 |
| `leds[].index` | int | 是 | — | 该灯带上的 0-based LED 位置 |
| `leds[].mode` | string | 是 | — | `"static"` 常亮 或 `"blink"` 闪烁 |
| `leds[].color` | string | 是 | — | `"#RRGGBB"` 格式十六进制颜色 |
| `leds[].duration_ms` | int | 否 | 0 | 自动关闭时间（毫秒）。0 = 永久 |

**特殊规则：**

- `leds` 为空数组 `[]` 时，关闭该设备所有灯带的所有 LED，等同于 clear
- `gpio` 对应的灯带不存在时，该条目**静默忽略**
- `index` 超出该灯带的 `[0, led_count)` 范围时，该条目**静默忽略**
- 同一个 `(gpio, index)` 多次出现时，使用**最后一个**
- `mode` 只接受 `"static"` 和 `"blink"`，其他值返回 400 错误
- `color` 必须是 7 字符的 `"#RRGGBB"` 格式

成功响应 (200)：
```json
{
  "status": "ok",
  "applied": 3
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 固定 `"ok"` |
| `applied` | int | 成功应用的 LED 数量 |

### 3.3 清除所有 LED

```
POST /api/led/clear
Content-Type: application/json
```

请求体：`{}`（空 JSON 对象，或无请求体）

成功响应 (200)：
```json
{
  "status": "ok"
}
```

效果：关闭该设备上**所有灯带**的所有 LED，取消所有闪烁定时器，重置所有 LED 状态为 OFF。

### 3.4 统一错误响应格式

```json
{
  "status": "error",
  "message": "人类可读的错误描述"
}
```

| 场景 | HTTP 状态码 | message 示例 |
|------|------------|-------------|
| JSON 解析失败 | 400 | `"invalid JSON body"` |
| 缺少 `leds` 字段 | 400 | `"missing required field: leds"` |
| `gpio` 缺失 | 400 | `"missing required field: gpio"` |
| `index` 缺失 | 400 | `"missing required field: index"` |
| `mode` 值非法 | 400 | `"invalid mode: xxx, expected static or blink"` |
| `color` 格式非法 | 400 | `"invalid color format: xxx"` |
| 内部错误 | 500 | `"internal error: ..."` |

**注意：** `gpio` 对应的灯带不存在或 `index` 超出范围**不返回错误**，静默忽略该条目。

## 4. LED 行为规范

### 4.1 static 模式（常亮）

- LED **立即**点亮为指定颜色
- 保持亮起直到被新的指令覆盖或 `clear`
- `duration_ms > 0` 时，在指定毫秒后**自动熄灭**并重置为 OFF
- `duration_ms = 0` 时，永久亮起

### 4.2 blink 模式（闪烁）

- LED 以约 **500ms** 间隔交替亮灭（亮 500ms → 灭 500ms，总周期约 1 秒）
- 亮起时显示指定颜色，熄灭时为全黑
- `duration_ms > 0` 时，在**总时长**到达后自动熄灭并停止闪烁
- `duration_ms = 0` 时，持续闪烁直到被新的指令覆盖或 `clear`
- 闪烁切换在 100ms 定时器 tick 中完成（每 5 个 tick 切换一次）

### 4.3 优先级和覆盖

- 新指令**立即覆盖**同一 `(gpio, index)` 的旧状态
- `clear` 清除**所有灯带**的**所有** LED 状态
- 不同灯带的 LED 完全独立，互不影响
- 同一请求中，后面的指令覆盖前面的（相同 gpio+index）

### 4.4 状态转换表

| 当前状态 | 新指令 | 结果 |
|---------|--------|------|
| OFF | static | 立即常亮 |
| OFF | blink | 开始闪烁 |
| static | static | 更新颜色，重启定时 |
| static | blink | 切换到闪烁 |
| blink | static | 停止闪烁，立即常亮 |
| blink | blink | 更新颜色，重启定时 |
| 任意 | clear | 立即熄灭 |
| 任意 | 超时 | 自动熄灭为 OFF |

## 5. 模块设计

### 5.1 项目目录结构

```
esp32-led-locator/
├── CMakeLists.txt                # 项目顶层 CMake
├── main/
│   ├── CMakeLists.txt            # 组件 CMake（注册源文件和依赖）
│   ├── main.c                    # app_main 入口
│   ├── strip_config.h            # 灯带配置数据结构
│   ├── strip_config.c            # 灯带配置加载（NVS / Kconfig）
│   ├── led_driver.h              # 多灯带 WS2812 底层驱动接口
│   ├── led_driver.c              # RMT 多通道 + ws2812_encoder
│   ├── led_controller.h          # LED 状态管理接口
│   ├── led_controller.c          # 闪烁/定时/状态机逻辑
│   ├── http_api.h                # HTTP API 接口
│   ├── http_api.c                # esp_http_server + cJSON 路由处理
│   ├── wifi_setup.h              # WiFi 连接和配网接口
│   ├── wifi_setup.c              # STA 连接 + AP 配网页
│   └── Kconfig.projbuild         # menuconfig 配置项
```

### 5.2 模块依赖关系

```
main.c
  ├── wifi_setup         (WiFi 连接)
  ├── strip_config       (灯带配置加载)
  ├── led_controller     (LED 状态管理)
  │     └── led_driver       (多灯带 WS2812 驱动)
  └── http_api           (HTTP 路由)
        └── led_controller   (调用 set/clear)
```

调用方向：`http_api → led_controller → led_driver`，禁止反向调用。

### 5.3 strip_config — 灯带配置

**职责：** 定义本设备上有哪些灯带（GPIO + LED 数量）。

```c
// strip_config.h

#ifndef STRIP_CONFIG_H
#define STRIP_CONFIG_H

#include "esp_err.h"
#include <stdint.h>

#define MAX_STRIPS 8

typedef struct {
    int gpio_num;
    int led_count;
} strip_entry_t;

typedef struct {
    strip_entry_t strips[MAX_STRIPS];
    int strip_count;
    int http_port;
} device_config_t;

/**
 * 加载设备配置
 * 优先从 NVS 读取，NVS 无配置时使用 Kconfig 默认值
 */
esp_err_t strip_config_load(device_config_t *config);

/**
 * 保存配置到 NVS
 */
esp_err_t strip_config_save(const device_config_t *config);

/**
 * 获取当前配置（缓存）
 */
const device_config_t *strip_config_get(void);

#endif // STRIP_CONFIG_H
```

**配置来源优先级：** AP 配网页写入 NVS > Kconfig 默认值。

**Kconfig 默认值：**

```
config STRIP0_GPIO
    int "Strip 0 GPIO"  default 8
config STRIP0_COUNT
    int "Strip 0 LED Count"  default 30
config STRIP1_GPIO
    int "Strip 1 GPIO"  default -1   # -1 = 不启用
config STRIP1_COUNT
    int "Strip 1 LED Count"  default 0
...
```

最多支持 8 条灯带（MAX_STRIPS）。未启用的灯带 GPIO 设为 -1。

### 5.4 led_driver — 多灯带 WS2812 底层驱动

**职责：** 管理多条灯带，每条灯带独立的 RMT 通道和像素缓冲区。

```c
// led_driver.h

#ifndef LED_DRIVER_H
#define LED_DRIVER_H

#include "esp_err.h"
#include <stdint.h>

#define LED_DRIVER_MAX_LEDS_PER_STRIP 256
#define LED_DRIVER_MAX_STRIPS 8

typedef struct {
    int gpio_num;
    int led_count;
} led_strip_config_t;

typedef struct {
    led_strip_config_t strips[LED_DRIVER_MAX_STRIPS];
    int strip_count;
} led_driver_config_t;

/**
 * 初始化所有灯带的 RMT 通道和编码器
 * 为每条灯带分配像素缓冲区
 */
esp_err_t led_driver_init(const led_driver_config_t *config);

/**
 * 设置指定灯带的单个像素颜色
 * @param strip_index 灯带索引（0-based，对应 strips 数组下标）
 * @param pixel_index 该灯带上的 LED 索引
 */
esp_err_t led_driver_set_pixel(int strip_index, uint16_t pixel_index,
                                uint8_t r, uint8_t g, uint8_t b);

/**
 * 清除指定灯带的所有像素
 */
esp_err_t led_driver_clear_strip(int strip_index);

/**
 * 清除所有灯带的所有像素
 */
esp_err_t led_driver_clear_all(void);

/**
 * 刷新指定灯带（发送缓冲区数据）
 */
esp_err_t led_driver_refresh_strip(int strip_index);

/**
 * 刷新所有灯带
 */
esp_err_t led_driver_refresh_all(void);

/**
 * 根据 GPIO 编号查找灯带索引
 * @return 灯带索引，-1 表示未找到
 */
int led_driver_find_strip_by_gpio(int gpio_num);

/**
 * 获取指定灯带的 LED 数量
 */
int led_driver_get_strip_count(int strip_index);

/**
 * 获取灯带总数
 */
int led_driver_get_strip_count_total(void);

#endif // LED_DRIVER_H
```

**实现要点：**

- 每条灯带分配独立的 RMT TX 通道（`rmt_new_tx_channel`）
- 每条灯带独立的 `ws2812_encoder` 实例
- 每条灯带独立的像素缓冲区：`uint8_t pixels[LED_DRIVER_MAX_LEDS_PER_STRIP * 3]`
- `led_driver_find_strip_by_gpio()` 供 http_api 层将 JSON 中的 `gpio` 字段转换为内部 strip_index
- `led_driver_refresh_strip()` 只刷新一条灯带，避免刷新不相关的灯带
- WS2812 时序：T0H=0.4us, T0L=0.85us, T1H=0.8us, T1L=0.45us, RESET>280us
- GRB 颜色顺序

### 5.5 led_controller — LED 状态管理

**职责：** 管理所有灯带上每个 LED 的模式、颜色、定时器。

```c
// led_controller.h

#ifndef LED_CONTROLLER_H
#define LED_CONTROLLER_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    LED_MODE_OFF = 0,
    LED_MODE_STATIC,
    LED_MODE_BLINK
} led_mode_t;

typedef struct {
    led_mode_t mode;
    uint8_t r, g, b;
    int64_t duration_ms;
    int64_t start_time_ms;
    bool blink_on;
    int tick_count;
} led_state_t;

/**
 * 初始化 LED 控制器
 * 内部调用 led_driver_init
 * @param config 灯带配置（gpio + count 数组）
 */
esp_err_t led_controller_init(const led_driver_config_t *config);

/**
 * 设置单个 LED 的状态
 * @param strip_index 灯带索引
 * @param pixel_index LED 索引
 */
esp_err_t led_controller_set(int strip_index, int pixel_index,
                              led_mode_t mode,
                              uint8_t r, uint8_t g, uint8_t b,
                              int duration_ms);

/**
 * 清除所有灯带的所有 LED
 */
esp_err_t led_controller_clear_all(void);

/**
 * 获取指定灯带的 LED 数量
 */
int led_controller_get_strip_led_count(int strip_index);

/**
 * 获取灯带总数
 */
int led_controller_get_strip_count(void);

/**
 * 根据 GPIO 查找灯带索引
 */
int led_controller_find_strip_by_gpio(int gpio_num);

/**
 * 周期调用函数（100ms 间隔）
 * 驱动闪烁切换和自动关闭
 */
void led_controller_tick(void);

#endif // LED_CONTROLLER_H
```

**实现要点：**

- 内部维护 `led_state_t states[MAX_STRIPS][MAX_LEDS]` 二维数组
- `led_controller_set()` 更新状态、更新 driver 缓冲区、调用 `led_driver_refresh_strip()`
- `led_controller_tick()` 由 100ms 定时器调用：
  - 遍历所有灯带的所有非 OFF 状态 LED
  - BLINK 模式：每 5 个 tick（500ms）切换 `blink_on`
  - 有 `duration_ms` 的 LED：检查超时
  - 变化的灯带只 refresh 该灯带（不是全部）
- 使用 `esp_timer_get_time()` 获取微秒时间戳

### 5.6 http_api — HTTP JSON API

**职责：** 注册 URI 处理程序，解析 JSON，通过 gpio 定位灯带，调用 led_controller。

```c
// http_api.h

#ifndef HTTP_API_H
#define HTTP_API_H

#include "esp_err.h"

esp_err_t http_api_start(int port);
esp_err_t http_api_stop(void);

#endif // HTTP_API_H
```

**注册的 URI 处理程序：**

| 方法 | 路径 | 处理函数 |
|------|------|---------|
| GET | `/api/health` | `health_get_handler` |
| POST | `/api/led/set` | `led_set_post_handler` |
| POST | `/api/led/clear` | `led_clear_post_handler` |

**`health_get_handler` 伪代码：**

```
1. 构造 strips 数组：遍历所有灯带，输出 [{gpio, led_count}, ...]
2. 获取 uptime
3. 返回 {"status":"ok", "strips": [...], "uptime_s": N}
```

**`led_set_post_handler` 伪代码：**

```
1. 读取 body (max 4096)
2. cJSON_Parse(body)
3. 获取 "leds" 数组
4. 如果 leds 为空 → led_controller_clear_all() → 返回 ok
5. 遍历 leds 数组：
   a. 获取 gpio (int), index (int), mode (string), color (string), duration_ms (int)
   b. 校验 mode 是 "static" 或 "blink"
   c. 解析 color "#RRGGBB" → r,g,b
   d. led_controller_find_strip_by_gpio(gpio) → strip_index
   e. 如果 strip_index >= 0 → led_controller_set(strip_index, index, mode, r, g, b, duration)
   f. applied++
6. 返回 {"status":"ok", "applied": N}
```

**关键点：** JSON 中的 `gpio` 字段需要通过 `find_strip_by_gpio()` 转换为内部 `strip_index`。

### 5.7 wifi_setup — WiFi 连接和配网

```c
// wifi_setup.h

#ifndef WIFI_SETUP_H
#define WIFI_SETUP_H

#include "esp_err.h"

esp_err_t wifi_setup_init(void);
esp_err_t wifi_setup_wait_connected(int timeout_ms);
const char *wifi_setup_get_ip(void);

#endif // WIFI_SETUP_H
```

实现要点与单设备版本相同：
- NVS 存储 SSID/password
- 首次启动 AP 模式配网
- 配网页 `GET /` → HTML 表单，`POST /save` → 存 NVS → 重启

### 5.8 main.c — 入口

```c
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_event.h"

#include "strip_config.h"
#include "led_driver.h"
#include "led_controller.h"
#include "http_api.h"
#include "wifi_setup.h"

static const char *TAG = "main";

void app_main(void)
{
    ESP_LOGI(TAG, "ESP32 LED Locator starting...");

    // 初始化 NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // 加载灯带配置
    device_config_t dev_cfg;
    ESP_ERROR_CHECK(strip_config_load(&dev_cfg));

    // 构造 led_driver_config
    led_driver_config_t drv_cfg = {0};
    for (int i = 0; i < dev_cfg.strip_count && i < LED_DRIVER_MAX_STRIPS; i++) {
        drv_cfg.strips[i].gpio_num = dev_cfg.strips[i].gpio_num;
        drv_cfg.strips[i].led_count = dev_cfg.strips[i].led_count;
    }
    drv_cfg.strip_count = dev_cfg.strip_count;

    // 初始化 LED 控制器（含驱动）
    ESP_ERROR_CHECK(led_controller_init(&drv_cfg));
    ESP_LOGI(TAG, "LED controller: %d strips", drv_cfg.strip_count);
    for (int i = 0; i < drv_cfg.strip_count; i++) {
        ESP_LOGI(TAG, "  strip %d: gpio=%d, count=%d",
                 i, drv_cfg.strips[i].gpio_num, drv_cfg.strips[i].led_count);
    }

    // 启动 100ms tick 定时器
    // esp_timer 或 FreeRTOS software timer
    // 每 100ms 调用 led_controller_tick()

    // 初始化 WiFi
    ESP_ERROR_CHECK(wifi_setup_init());
    ESP_ERROR_CHECK(wifi_setup_wait_connected(30000));

    ESP_LOGI(TAG, "WiFi connected, IP: %s", wifi_setup_get_ip());

    // 启动 HTTP API
    ESP_ERROR_CHECK(http_api_start(dev_cfg.http_port));
    ESP_LOGI(TAG, "HTTP server on port %d", dev_cfg.http_port);
}
```

## 6. Kconfig.projbuild

```
menu "LED Locator Configuration"

config STRIP0_GPIO
    int "Strip 0 GPIO"
    default 8
    help
        第一条灯带的数据引脚 GPIO 编号。

config STRIP0_COUNT
    int "Strip 0 LED Count"
    default 30
    range 0 256

config STRIP1_GPIO
    int "Strip 1 GPIO (-1 = disabled)"
    default -1

config STRIP1_COUNT
    int "Strip 1 LED Count"
    default 0

config STRIP2_GPIO
    int "Strip 2 GPIO (-1 = disabled)"
    default -1

config STRIP2_COUNT
    int "Strip 2 LED Count"
    default 0

config STRIP3_GPIO
    int "Strip 3 GPIO (-1 = disabled)"
    default -1

config STRIP3_COUNT
    int "Strip 3 LED Count"
    default 0

config HTTP_SERVER_PORT
    int "HTTP Server Port"
    default 80
    range 1 65535

endmenu
```

## 7. 编译和烧录

```bash
. $HOME/esp/esp-idf/export.sh

idf.py set-target esp32s3
idf.py menuconfig    # 配置灯带 GPIO、数量、HTTP 端口
idf.py build
idf.py flash monitor
```

### 首次配网

1. 烧录后 ESP32 进入 AP 模式
2. 连接 WiFi `ESP32-LED-Setup`
3. 浏览器打开 `http://192.168.4.1`
4. 填写 WiFi SSID 和密码 → 保存 → ESP32 重启
5. 串口监视器显示 IP 地址和灯带信息

### 串口输出示例

```
I (xxx) main: ESP32 LED Locator starting...
I (xxx) main: LED controller: 3 strips
I (xxx) main:   strip 0: gpio=8, count=30
I (xxx) main:   strip 1: gpio=6, count=20
I (xxx) main:   strip 2: gpio=4, count=15
I (xxx) main: WiFi connected, IP: 192.168.1.50
I (xxx) main: HTTP server on port 80
```

## 8. 调试方法

### 8.1 curl 测试

```bash
# 健康检查（应返回所有灯带信息）
curl http://192.168.1.50/api/health

# 单条灯带单颗 LED 闪烁
curl -X POST http://192.168.1.50/api/led/set \
  -H "Content-Type: application/json" \
  -d '{"leds":[{"gpio":8,"index":0,"mode":"blink","color":"#00ff00","duration_ms":10000}]}'

# 同一灯带多颗 LED
curl -X POST http://192.168.1.50/api/led/set \
  -H "Content-Type: application/json" \
  -d '{"leds":[
    {"gpio":8,"index":0,"mode":"blink","color":"#00ff00","duration_ms":5000},
    {"gpio":8,"index":5,"mode":"blink","color":"#ff0000","duration_ms":5000}
  ]}'

# 不同灯带同时操作
curl -X POST http://192.168.1.50/api/led/set \
  -H "Content-Type: application/json" \
  -d '{"leds":[
    {"gpio":8,"index":0,"mode":"blink","color":"#00ff00","duration_ms":5000},
    {"gpio":6,"index":3,"mode":"static","color":"#ff0000","duration_ms":0}
  ]}'

# 清除所有
curl -X POST http://192.168.1.50/api/led/clear -d '{}'

# 空数组等同 clear
curl -X POST http://192.168.1.50/api/led/set \
  -H "Content-Type: application/json" \
  -d '{"leds":[]}'
```

### 8.2 Flask 联调

1. Flask 设置面板添加设备 `192.168.1.50:80`
2. 测试连接 → 成功 + 延迟 + 灯带列表
3. 添加灯带（GPIO 8 / 30颗），添加映射
4. 定位盒子 → 对应灯带上的 LED 闪烁

### 8.3 常见问题排查

| 问题 | 排查方式 |
|------|---------|
| 所有灯带都不亮 | 检查电源、串口日志确认初始化成功 |
| 某条灯带不亮 | 检查该 GPIO 接线、menuconfig 配置 |
| 连接不上 WiFi | 检查 NVS 凭据、AP 配网页 |
| curl 超时 | 检查 IP、防火墙、WiFi 连接状态 |
| LED 颜色不对 | WS2812 使用 GRB 顺序 |
| 闪烁不对 | 检查 tick 定时器是否 100ms 运行 |
| health 中灯带数不对 | 检查 menuconfig 或 NVS 配置 |

## 9. 通信接口变更流程

如果未来修改 ESP32 HTTP API，**必须同步修改**以下三处：

| 序号 | 位置 | 文件 | 修改内容 |
|------|------|------|---------|
| 1 | ESP32 固件 | `http_api.c` | JSON 解析/构造逻辑 |
| 2 | Flask 项目 | `led_proxy.py` | 请求构造逻辑 |
| 3 | 文档 | 本文件第 3 节 | 接口规范描述 |

**禁止**单方面修改接口。变更应向后兼容（新增可选字段，不删除或重命名已有字段）。

## 10. 扩展方向（参考）

| 功能 | 相关模块 | 说明 |
|------|---------|------|
| 呼吸灯模式 | `led_controller` | 新增 `LED_MODE_BREATHE` |
| 彩虹效果 | `led_controller` | 新增 `LED_MODE_RAINBOW` |
| 灯带亮度调节 | `led_driver` | 全局 brightness 乘数 |
| LED 状态查询 | `http_api` | 新增 `GET /api/led/state` |
| OTA 升级 | `main.c` | `esp_ota` 组件 |
| mDNS | `wifi_setup` | `esp_mdns` 域名发现 |
| NVS 远程配置 | `http_api` | 通过 HTTP 修改灯带 GPIO/数量 |
