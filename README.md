# EduMeet 教育智能体平台

EduMeet 是面向中小学生教育场景的 AI Agent 平台，当前已提供注册登录、会话管理、SSE 流式问答、模型选择、AI 文章生成与发布等可运行功能。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia
- 后端：FastAPI、SQLAlchemy 2.0 Async、JWT、pytest
- 业务数据库：MySQL 8；后端自动化测试仍可使用 SQLite 隔离运行
- 可观测性：Langfuse SDK，沿用现有 Langfuse 服务与原有存储
- 模型：Provider 抽象，当前支持 DeepSeek API 与本地 Mock Provider

## 目录结构

```text
EduMeet/
├── README.md                       # 项目说明、环境配置与启动命令
├── index.html                      # 项目规划文档总览入口
├── docs/                           # 平台建设规划及开发 Spec
├── evaluation/                     # Agent 评测规划及评测 Spec
├── backend/
│   ├── .env.example                # 后端环境变量示例
│   ├── requirements.txt            # Python 依赖
│   ├── db/
│   │   └── schema_mysql.sql        # MySQL DB、业务表及模型初始数据
│   ├── app/
│   │   ├── main.py                 # FastAPI 应用入口与路由注册
│   │   ├── api/v1/                 # auth、models、sessions、articles 接口
│   │   ├── core/                   # 配置、鉴权、响应与可观测性
│   │   ├── db/                     # 异步引擎、会话及初始化逻辑
│   │   ├── llm/                    # LLM Provider、DeepSeek 与 Mock 实现
│   │   ├── models/                 # SQLAlchemy 数据模型
│   │   └── schemas/                # Pydantic 请求/响应结构
│   └── tests/                      # 后端冒烟测试
└── frontend/
    ├── package.json                # 前端依赖与 npm 命令
    ├── vite.config.ts              # Vite 配置及 /api 代理
    └── src/
        ├── api/                    # 后端接口调用封装
        ├── router/                 # 页面路由
        ├── stores/                 # Pinia 状态管理
        └── views/                  # 登录、会话与文章页面
```

## 数据库表

| 表名 | 用途 |
| --- | --- |
| `users` | 用户账号、昵称与密码摘要 |
| `llm_models` | 可选模型、厂商、Provider、启用状态与排序 |
| `sessions` | 用户会话 |
| `messages` | 会话消息、引用及使用的模型 |
| `articles` | 用户文章、正文与发布状态 |
| `generation_tasks` | AI 文章生成任务及产物关联 |

完整 DDL 位于 [`backend/db/schema_mysql.sql`](backend/db/schema_mysql.sql)。脚本使用 `CREATE DATABASE/TABLE IF NOT EXISTS`，可重复执行且不会清空已有业务数据。

### 存储边界

`edumeet` MySQL DB 只保存本项目的六类业务数据。Langfuse 监听产生的 trace、span、generation、retriever、模型输入输出和 usage 等观测数据，仍由 `LANGFUSE_HOST` 指向的现有 Langfuse 服务按原方式存储。本次数据库调整不创建 Langfuse 表、不迁移 Langfuse 数据，也不修改 `backend/app/core/observability.py` 的上报流程。

## 首次启动

要求：Python 3.11+、Node.js 18+、npm、MySQL 8。

### 1. 创建 MySQL 数据库与表

在项目根目录执行：

```bash
mysql -u root -p < backend/db/schema_mysql.sql
```

脚本会创建 `edumeet` 数据库、六张业务表，并写入默认模型目录。也可以使用其他具备建库和建表权限的 MySQL 账号执行。

### 2. 配置并启动后端

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

编辑 `backend/.env`，将 `DATABASE_URL` 中的账号和密码替换为本机 MySQL 配置：

```dotenv
DATABASE_URL=mysql+aiomysql://root:your_password@127.0.0.1:3306/edumeet?charset=utf8mb4
```

现有 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST` 等配置保持不变。它们不会使用上面的 `DATABASE_URL`。

随后启动后端：

```bash
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址为 `http://127.0.0.1:8000`，健康检查为 `http://127.0.0.1:8000/api/v1/health`，接口文档为 `http://127.0.0.1:8000/docs`。

### 3. 启动前端

新开一个终端，在项目根目录执行：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。Vite 会将 `/api` 请求代理到 `http://127.0.0.1:8000`。

## 日常启动顺序

MySQL 服务已安装且依赖已初始化时，只需依次执行：

```bash
# 终端 1：后端
cd backend
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# 终端 2：前端
cd frontend
npm run dev
```

## 数据来源说明

- 用户、会话、消息、文章和生成任务均由 SQLAlchemy 读写数据库。
- `/api/v1/models` 从 `llm_models` 表读取已启用模型；聊天和文章生成也会从该表校验模型并选择 Provider，不再依赖硬编码模型接口数据。
- `llm_models.provider=deepseek` 会调用 DeepSeek，需在 `backend/.env` 配置 `DEEPSEEK_API_KEY`。
- 默认种子中的豆包与通义模型仍配置为 `mock` Provider，因为项目目前没有这两家厂商的 API 适配和密钥。这不影响用户、会话、文章及模型目录本身使用真实数据库。

## 验证

```bash
# 后端测试
cd backend
.venv/bin/python -m pytest tests/ -q

# 前端类型检查与生产构建
cd frontend
npm run build
```

## 规划文档

- [项目总览](index.html)
- [平台建设规划 v1.5](docs/EduMeet建设规划.html)
- [Agent 评测体系建设规划 v2.1](evaluation/Agent评测体系建设规划.html)
