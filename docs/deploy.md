# 部署指南 - 香橙派 Zero3 (Ubuntu)

本文档指导将 components-inventory 部署到香橙派 Zero3，通过局域网访问。

## 环境要求

| 项目 | 要求 |
|------|------|
| 设备 | 香橙派 Zero3 |
| 系统 | Ubuntu (ARM) |
| 网络 | 与访问设备在同一局域网 |
| Python | 3.10+ |
| 内存 | 建议 1GB+ |

## 第一步：系统准备

### 1.1 安装基础依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 1.2 查看香橙派局域网 IP

```bash
hostname -I
```

记下输出的 IP 地址（例如 `192.168.1.60`），后续步骤会用到。确保该 IP 固定，避免重启后变化。

> **固定 IP 的方法**：在路由器管理页面中，将香橙派的 MAC 地址绑定到固定 IP。

## 第二步：部署代码

### 2.1 克隆仓库

```bash
cd /opt
sudo git clone https://github.com/smyhao/components-inventory.git
```

### 2.2 修改目录权限

将 `orangeapi` 替换为你的实际用户名：

```bash
sudo chown -R orangeapi:orangeapi /opt/components-inventory
```

### 2.3 创建虚拟环境并安装依赖

```bash
cd /opt/components-inventory

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

验证安装：

```bash
pip list | grep -iE "flask|gunicorn|openpyxl|pillow|chardet"
```

应输出类似：

```
Flask       3.x.x
Gunicorn    2x.x.x
openpyxl    3.x.x
Pillow      1x.x.x
chardet     5.x.x
```

### 2.4 测试启动

```bash
cd /opt/components-inventory
source .venv/bin/activate
python app.py
```

看到类似输出说明启动成功：

```
 * Running on http://0.0.0.0:5000
```

在同一局域网的电脑浏览器中访问 `http://香橙派IP:5000`，确认页面能正常加载。按 `Ctrl+C` 停止测试。

## 第三步：配置环境变量

### 3.1 生成随机密钥

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

复制输出的字符串。

### 3.2 创建 .env 文件

```bash
cat > /opt/components-inventory/.env << 'EOF'
HOST=0.0.0.0
PORT=5000
SERVER_URL=http://192.168.1.60:5000
SECRET_KEY=粘贴上一步生成的随机密钥
API_TOKEN=
API_TOKEN_REQUIRE_ALL=false
EOF
```

将 `192.168.1.60` 替换为第一步查到的实际 IP。

### 3.3 自动化 Token

推荐为每台自动化设备生成独立 token：

1. 启动服务并打开 Web 页面。
2. 连续点击左上角 `CI` 标识 5 次，打开“自动化配置”。
3. 输入设备名，例如 `lab-pc`、`scanner-1` 或 `eda-script`。
4. 生成并复制 token。
5. 在设备上执行：

```bash
python inventory_cli.py config set-token lab <generated-token>
```

生成的 token 只保存哈希，删除后立即失效。创建过设备 token 后，`inventory-cli`
来源的请求必须携带有效 Bearer token。`API_TOKEN` 仍可作为部署级 fallback token；
如果设置 `API_TOKEN_REQUIRE_ALL=true`，所有 `/api` 请求都需要 token，启用前请确认浏览器端也已准备好发送授权头。

## 第四步：配置系统服务

### 4.1 创建 systemd 服务文件

```bash
sudo tee /etc/systemd/system/components-inventory.service << 'EOF'
[Unit]
Description=Components Inventory
After=network.target

[Service]
User=orangeapi
Group=orangeapi
WorkingDirectory=/opt/components-inventory
EnvironmentFile=/opt/components-inventory/.env
ExecStart=/opt/components-inventory/.venv/bin/gunicorn \
    --workers 2 \
    --bind 0.0.0.0:5000 \
    --timeout 120 \
    --max-requests 500 \
    "app:app"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

> **注意**：将 `User` 和 `Group` 中的 `orangeapi` 替换为你的实际用户名。

### 4.2 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable components-inventory
sudo systemctl start components-inventory
```

### 4.3 检查服务状态

```bash
sudo systemctl status components-inventory
```

看到 `Active: active (running)` 即为成功。

## 第五步：验证访问

在局域网内的电脑或手机浏览器中打开：

```
http://香橙派IP:5000
```

- 能看到管理页面 = 部署成功
- 无法访问：检查防火墙和 IP 是否正确

## 日常运维

### 查看日志

```bash
# 实时查看服务日志
sudo journalctl -u components-inventory -f

# 查看最近 100 行日志
sudo journalctl -u components-inventory -n 100

# 查看应用运行日志
tail -f /opt/components-inventory/log/backend.log
```

### 更新代码

```bash
cd /opt/components-inventory
source .venv/bin/activate
git pull
pip install -r requirements.txt
sudo systemctl restart components-inventory
```

### 重启服务

```bash
sudo systemctl restart components-inventory
```

### 停止服务

```bash
sudo systemctl stop components-inventory
```

### 备份数据

```bash
# 备份数据库和上传图片
cp /opt/components-inventory/data/inventory.db ~/backup/inventory_$(date +%Y%m%d).db
cp -r /opt/components-inventory/uploads ~/backup/uploads_$(date +%Y%m%d)
```

## 常见问题

### 端口被占用

```bash
# 查看端口占用
sudo lsof -i :5000

# 杀掉占用进程后重启
sudo systemctl restart components-inventory
```

### 启动失败

```bash
# 查看详细错误
sudo journalctl -u components-inventory -n 50 --no-pager
```

常见原因：
- `.env` 文件中 `SECRET_KEY` 未替换
- 用户名与实际不符
- 虚拟环境路径错误

### 页面能打开但图片不显示

检查 uploads 目录权限：

```bash
sudo chown -R orangeapi:orangeapi /opt/components-inventory/uploads
```

### 香橙派重启后服务未启动

```bash
sudo systemctl enable components-inventory
sudo systemctl start components-inventory
```

### 设备存储空间不足

```bash
# 查看磁盘使用
df -h

# 清理日志
sudo journalctl --vacuum-size=50M

# 清理 Python 缓存
find /opt/components-inventory -type d -name __pycache__ -exec rm -rf {} +
```
