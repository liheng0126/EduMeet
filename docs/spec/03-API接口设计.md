# 03 - EduMeet API 接口设计

> 版本：v1.0 ｜ 状态：待评审
> Base URL：`/api/v1`；鉴权：`Authorization: Bearer <JWT>`（auth 接口除外）
> 统一响应包：`{"code": 0, "message": "ok", "data": {...}}`；非 0 为业务错误码。

## 1. 接口总览

| 模块 | 前缀 | 说明 |
|---|---|---|
| 认证 | /auth | 注册/登录/刷新 |
| 用户 | /users | 资料、自定义模型 Key |
| 会话 | /sessions | 对话会话与消息（SSE） |
| 生成任务 | /generation-tasks | 文章自动生成 |
| 文章 | /articles | 草稿/发布/阅读 |
| 素材 | /materials | 上传/解析/列表 |
| 检索 | /search | 混合检索 |
| 内容库 | /library | 公共内容浏览 |
| 后台 | /admin | 审核等（管理员角色） |

## 2. 认证 /users、/auth

| 方法 | 路径 | 说明 | 关键参数 |
|---|---|---|---|
| POST | /auth/register | 注册 | `{username, email, password, nickname, role}` |
| POST | /auth/login | 登录，返回 access/refresh token | `{username, password}` |
| POST | /auth/refresh | 刷新 token | `{refresh_token}` |
| GET | /users/me | 当前用户信息 | — |
| PATCH | /users/me | 更新资料 | `{nickname?, region?, role?, avatar?}` |

## 3. 模型配置 /users/model-keys

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /models | 可选模型列表：官方预置 + 我的自定义 Key（Key 脱敏 `sk-***abc`） |
| POST | /users/model-keys | 新增自定义模型 `{name, base_url, api_key, model_name}` |
| PATCH | /users/model-keys/{id} | 修改 / 设为默认 `{is_default?}` |
| DELETE | /users/model-keys/{id} | 删除 |

约束：`api_key` 仅注册时提交一次，响应永不回显；保存前调用 `POST /users/model-keys/validate` 做连通性校验。

## 4. 会话与对话 /sessions

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /sessions | 新建会话 `{model_ref?, title?}` |
| GET | /sessions | 会话列表（分页，按 updated_at 倒序，前端左栏数据源） |
| GET | /sessions/{id} | 会话详情 + 历史消息 |
| PATCH | /sessions/{id} | 改名 / 归档 |
| DELETE | /sessions/{id} | 删除 |
| POST | /sessions/{id}/messages | **发送消息（SSE 流式）** |

### 4.1 SSE 流式对话契约（POST /sessions/{id}/messages）

请求：`{"content": "...", "model_ref": "gpt-4o", "use_rag": true}`

响应事件流：

```
event: message_delta      data: {"delta": "海淀区2025年政策规定…"}
event: citation           data: {"citations": [{"type":"official","title":"…","url":"…","snippet":"…"}]}
event: article_suggestion data: {"task_id": 88, "title": "海淀幼升小全攻略"}   # 问答中可触发生成
event: done               data: {"message_id": 1234, "usage": {...}}
event: error              data: {"code": 50001, "message": "模型调用失败"}
```

## 5. 文章生成 /generation-tasks

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /generation-tasks | 创建生成任务 `{topic, material_ids?, model_ref?, outline_hint?}` |
| GET | /generation-tasks/{id} | 查询任务状态与阶段进度 |
| GET | /generation-tasks | 我的任务列表 `{stage?}` |
| POST | /generation-tasks/{id}/cancel | 取消任务 |
| POST | /generation-tasks/{id}/confirm-outline | 可选：大纲确认后继续（默认自动） |

### 5.1 SSE 进度契约（GET /generation-tasks/{id}/events）

```
event: task_progress data: {"stage": "writing", "detail": "正在撰写第 2/5 节", "percent": 40}
event: task_done     data: {"article_id": 66, "title": "…"}
event: task_failed   data: {"stage": "reviewing", "reason": "…"}
```

## 6. 文章 /articles

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /articles/mine | 我的文章（草稿+已发布）`{status?}` |
| GET | /articles/{id} | 文章详情（块级 doc）；权限：私有仅作者、shared 持链接、public 所有人 |
| PATCH | /articles/{id} | 更新（仅作者）`{title?, doc?, topic_tags?...}` |
| POST | /articles/{id}/publish | 发布（触发机审） |
| POST | /articles/{id}/unpublish | 下架（仅作者或管理员） |
| DELETE | /articles/{id} | 删除（仅作者） |
| GET | /articles | 公开文章流 `{topic?, grade_level?, region?, page}` |
| POST | /articles/{id}/favorite | 收藏 |

**规则**：创建只经生成任务或前端本地创建后保存，任何写接口服务端强制 `author_id = 当前 JWT 用户`，请求体中不允许传 author_id。

## 7. 素材 /materials

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /materials/presign | 获取预签名直传地址 `{filename, size, mime_type}` → `{upload_url, file_key}` |
| POST | /materials | 直传完成后登记 `{file_key, title, mtype, source_url?}` → 异步解析打标 |
| POST | /materials/from-url | URL 导入 `{url}` → 抓取解析 |
| GET | /materials | 我的素材库 `{mtype?, keyword?, tags?}` |
| GET | /materials/{id} | 详情（含解析状态、标签） |
| PATCH | /materials/{id} | 改名/编辑标签 |
| DELETE | /materials/{id} | 删除（被文章引用时提示） |

## 8. 检索 /search

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /search | 混合检索 `q, scope=all|library|articles, content_type?, region?, grade_level?, page` |
| GET | /search/suggest | 输入联想 |
| GET | /search/facets | 筛选聚合（地区/学段/类型计数） |

响应要点：`data.items[] = {type: article|library_item, id, title, summary, cover_url, source_label(官方政策/社区经验/私有文章), region, grade_level, updated_at, highlight[]}`。

## 9. 内容库 /library

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /library/items | 浏览（分页/筛选） |
| GET | /library/items/{id} | 详情（含来源与版权声明、时效标注） |
| GET | /library/policies/timeline | 政策时间轴 `{region, year}`（三期） |

## 10. 管理后台 /admin（role=admin）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /admin/audit/pending | 待审列表 |
| POST | /admin/audit/{id} | 审核操作 `{result, reason}` |
| GET | /admin/reports | 举报列表；POST /admin/reports/{id}/handle |
| CRUD | /admin/sources | 内容源配置 |
| GET | /admin/dashboard | 用量看板（生成量、模型调用量、成本） |

## 11. 会员与积分计费 /membership、/billing（详见 Spec 11）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /membership | 当前等级、到期时间、可用模型范围 |
| POST | /membership/subscribe | 创建订阅订单 `{sku}` → 支付回调生效 |
| GET | /billing/summary | 积分余额（充值/赠送分列）、本月消耗 |
| GET | /billing/pricing | 模型积分价目表（模型选择器展示消耗） |
| GET | /billing/ledger | 积分流水 `{type?, page}` |
| POST | /billing/recharge | 创建充值订单 `{sku}` |
| POST | /billing/notify | 支付渠道异步回调（验签、幂等入账） |

沙箱控制（服务端强制，不可由请求参数绕过）：免费用户请求付费模型时自动降级 Free 模型并在响应附 `downgrade` 提示；付费会员等级不足返回 40302；余额预检不足返回 40303；免费日额度用尽返回 40304。

## 12. 错误码

| 码 | 含义 |
|---|---|
| 40100/40101 | 未登录 / token 过期 |
| 40300 | 无权限（访问他人私有内容等） |
| 40400 | 资源不存在 |
| 42200 | 参数校验失败 |
| 42900 | 频率/配额超限 |
| 40302 | 会员等级不足（该模型需升级会员） |
| 40303 | 积分余额不足 |
| 40304 | 免费日额度已用完 |
| 50001 | LLM 调用失败（可重试） |
| 50002 | 生成任务失败 |
| 50003 | 内容安全拦截 |
| 50004 | 文件解析失败 |

## 13. 验收标准

- [ ] FastAPI `/docs` OpenAPI 与本文档一致；schemas 由 `app/schemas` 生成
- [ ] SSE 事件名与 data 结构与 4.1 / 5.1 完全一致（前端 mock 与真实联调均通过）
- [ ] 所有列表接口支持 `page/page_size`，默认 20，最大 100
- [ ] 越权访问他人私有文章返回 40300；未登录访问受保护接口返回 40100
- [ ] model-keys 的读接口不返回明文 api_key（单测覆盖）
- [ ] 沙箱：免费账号请求付费模型被降级/拦截（40302/40303/40304 语义正确）；积分流水幂等不重复扣
