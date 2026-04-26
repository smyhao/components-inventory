# 贡献指南

感谢你对本项目的关注！以下是参与贡献的指南。

## 开发环境

```bash
git clone https://github.com/<your-username>/components-inventory.git
cd components-inventory
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 代码风格

- **Python**: 遵循 PEP 8，使用 4 空格缩进
- **JavaScript**: 使用 2 空格缩进，变量命名 camelCase
- **提交信息**: 使用简洁的中文或英文描述改动内容

## 提交规范

```
<类型>: <简要描述>

# 类型说明
feat:     新功能
fix:      Bug 修复
docs:     文档变更
style:    代码格式（不影响功能）
refactor: 重构
chore:    构建/工具/依赖变更
```

## PR 流程

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feat/your-feature`)
3. 提交改动 (`git commit -m "feat: add xxx"`)
4. 推送分支 (`git push origin feat/your-feature`)
5. 创建 Pull Request

## 项目结构说明

| 文件 | 职责 |
|------|------|
| `app.py` | API 路由与请求处理 |
| `models.py` | 数据库操作与业务逻辑 |
| `init_db.py` | 数据库 Schema 定义 |
| `config.py` | 配置管理 |
| `logger.py` | 日志系统 |
| `static/` | 前端代码 |
