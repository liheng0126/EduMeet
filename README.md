# EduMeet · 教育智能体平台

> 中小学生教育 AI Agent 平台（入学政策 / 学习资料 / 家庭教育 / 学习与教学经验分享）
> 本仓库当前为 **M1 骨架阶段**：规划文档 + 可运行垂直切片（登录 → 三栏对话工作台 → SSE 流式问答 → AI 生成文章 → 我的文章）。

## 目录结构

```
EduMeet/
├── index.html              # 平台总览入口（建设背景/难点/评测汇总 + 全文档导航）
├── docs/                   # 建设规划 HTML（v1.5）+ 开发 Spec 00~12
├── evaluation/             # 评测体系规划 HTML（v2.1）+ Spec E0~E6
├── backend/                # FastAPI 后端（本骨架）
│   ├── app/
│   │   ├── api/v1/         # auth / sessions(SSE) / models / articles
│   │   ├── core/           # 配置、JWT、依赖注入、统一响应包
│   │   ├── db/             # SQLAlchemy 2.0 async（生产 PG / 开发 SQLite）
│   │   ├── llm/            # Provider 抽象 + Mock + 模型注册表（LiteLLM 待接）
│   │   └── models/         # users / sessions / messages / articles / generation_tasks
│   └── tests/              # 冒烟测试（pytest）
└── frontend/               # Vue3 + TS + Vite + Element Plus + Pinia（本骨架）
    └── src/views/          # LoginView / ChatView(三栏工作台) / ArticlesView
```

## 本地启动（无需 Docker）

```bash
# 后端（端口 8000）
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --port 8000

# 前端（端口 5173，已代理 /api → 8000）
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

## 测试

```bash
cd backend && .venv/bin/python -m pytest tests/ -q   # 冒烟：认证/流式问答/文章作者绑定
cd frontend && npm run build                          # vue-tsc 类型检查 + 构建
```

## 骨架已实现 / 待迭代（对照 Spec 09 M1）

| 已实现 | 说明 | 待迭代（M1 剩余） |
|---|---|---|
| 注册登录 JWT + 统一响应包 | Spec 03 契约 | RBAC、手机验证码登录 |
| 三栏工作台 + SSE 流式问答 | 事件契约 message_delta/task_progress/error | 会话重命名/删除 |
| 模型注册表接口（P0 清单） | Spec 07 | LiteLLM 网关接入、沙箱控制、积分扣费 |
| AI 生成文章 + 作者强制绑定 | 红线 4：author_id NOT NULL | Celery + LangGraph 5-Agent 流水线（Spec 04） |
| 文章发布（机审 stub） | 红线 1 的 stub | 安全审查节点、块级文档模型 |
| SQLite 开发降级 | 代码按 PG 编写 | Alembic 基线、ES 混合检索（M2） |

## 规划文档入口

- [平台总览（index.html）](../index.html)：建设背景、难点、评测汇总
- [平台建设规划 v1.5](docs/EduMeet建设规划.html)
- [Agent 评测体系建设规划 v2.1](evaluation/Agent评测体系建设规划.html)
