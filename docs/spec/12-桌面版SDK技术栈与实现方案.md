# 12 - EduMeet 桌面版 SDK 技术栈与实现方案

> 版本：v1.0 ｜ 状态：待评审 ｜ 定位：终期（M5）建设，本文档是 Spec 10 的技术栈细化实现篇
> 上游：10-桌面版SDK建设（形态/复用策略/启动 Gate）、01-系统架构、03-API 接口契约

---

## 1. 范围

为两个交付物给出完整技术栈选型、依赖清单、工程结构与关键实现方案：

1. **EduMeet Desktop 桌面客户端**（Windows / macOS）
2. **EduMeet 开放 SDK**（TypeScript / Python 双语言包）

## 2. 桌面客户端技术栈

### 2.1 核心栈

| 层 | 选型 | 版本基线 | 说明 |
|---|---|---|---|
| 应用壳 | **Tauri** | 2.x（稳定线） | Rust 内核 + 系统 WebView（macOS WKWebView / Windows WebView2），包体小、内存低 |
| 内核语言 | Rust | stable ≥ 1.80，edition 2021 | 插件与命令层开发；团队仅需掌握应用级 Rust |
| 窗口/WebView | tao + WRY | Tauri 内置 | 跨平台窗口与 WebView 抽象 |
| 前端复用 | Vue3 + TS + Vite | 与主工程同一份构建产物 | `frontend/` 增加 `platform` 抽象层，`isDesktop()` 分支加载本地能力 |
| 状态/路由 | Pinia + Vue Router | 与主工程一致 | 零改动复用 |
| UI 桥接 | `@tauri-apps/api` | 2.x | 前端 `invoke()` 调用 Rust 命令、`listen/emit` 事件总线 |

### 2.2 Tauri 插件清单（能力→插件映射）

| 能力 | 插件 | 关键配置 |
|---|---|---|
| 本地素材导入（文件选择/拖拽） | `tauri-plugin-fs` + `tauri-plugin-dialog` | capabilities 按目录白名单授权 |
| 外链打开（政策来源跳转） | `tauri-plugin-opener` / shell | 仅允许 https 白名单域 |
| 系统通知（生成完成/审核结果） | `tauri-plugin-notification` | — |
| 全局快捷键（唤起对话/截图） | `tauri-plugin-global-shortcut` | 默认 Cmd/Ctrl+Shift+E |
| 剪贴板（截图问答粘贴） | `tauri-plugin-clipboard-manager` | — |
| 屏幕截图 | `screenshots-rs`（自封装 Tauri command） | 隐藏主窗后捕获，教育答疑场景 |
| 离线缓存（会话/最近消息） | `tauri-plugin-sql`（SQLite） | 表结构随 API 契约版本迁移 |
| 凭据安全存储 | `keyring` crate 封装 command | macOS Keychain / Windows Credential Manager |
| 自动更新 | `tauri-plugin-updater` | minisign 签名 + 服务端 latest.json 清单 |
| 深链唤起（edumeet://） | `tauri-plugin-deep-link` | OAuth 回调备用通道 |
| 单实例 / 开机自启 | `tauri-plugin-single-instance` / `autostart` | 可选，用户可关 |
| 日志 | `tauri-plugin-log` + `log` | 崩溃日志脱敏后可选上传 |

### 2.3 Rust 侧依赖（Cargo.toml 核心）

```toml
[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-fs = "2"
tauri-plugin-notification = "2"
tauri-plugin-global-shortcut = "2"
tauri-plugin-updater = "2"
tauri-plugin-sql = { version = "2", features = ["sqlite"] }
tokio = { version = "1", features = ["full"] }      # 异步命令
serde = { version = "1", features = ["derive"] }
reqwest = { version = "0.12", features = ["json", "rustls-tls"] }  # 本地直连 API（备用通道）
keyring = "3"                                        # 系统凭据存储
screenshots = "0.8"                                  # 截图能力
```

### 2.4 前端 ↔ Rust 桥接规范

```rust
// src-tauri/src/commands/material.rs —— 命令层示例
#[tauri::command]
async fn import_material(path: String, state: State<'_, AppState>) -> Result<MaterialMeta, String> {
    let bytes = tokio::fs::read(&path).await.map_err(|e| e.to_string())?;
    state.api.upload(bytes).await            // 复用 05 素材流水线（presign 直传）
}
```

- 命令命名 `snake_case`，返回 `Result<T, String>`，错误码透传主工程 03 契约。
- 权限声明走 Tauri **capabilities JSON**（`src-tauri/capabilities/*.json`），最小授权原则。
- 事件：Rust → 前端（下载进度/更新状态）用 `emit`；前端统一封装进 `platform` 抽象层，Web 端同名接口为 no-op 实现。

### 2.5 安全与打包签名

| 项 | 方案 |
|---|---|
| CSP | `tauri.conf.json` 严格白名单：仅 API 域 + OSS 域 + 本地 asset；禁 remote URL 加载 |
| Token 存储 | 登录后仅存系统凭据库（keyring），SQLite 缓存不含 token |
| Windows 打包 | tauri-cli bundle → NSIS 安装包；`signtool` + EV 代码签名证书 |
| macOS 打包 | .app + DMG；`notarytool` 公证 + staple；Hardened Runtime 开启 |
| 自动更新 | 发布流水线生成 `latest.json`（版本/URL/签名），minisign 私钥仅 CI secret 持有 |
| CI | GitHub Actions matrix（macos-latest / windows-latest）：lint → rust test → 前端 build → bundle → 签名公证 → 产物上传 Release |

### 2.6 桌面端关键指标（对应 Spec 10 验收）

冷启动 < 2s；安装包 macOS < 15MB / Windows < 20MB；空载内存 < 200MB；更新包增量下载。

## 3. 开放 SDK 技术栈

### 3.1 TypeScript SDK（npm `@edumeet/sdk`）

| 项 | 选型 |
|---|---|
| 语言/构建 | TypeScript 5 + `tsup`（双产物 ESM/CJS + d.ts） |
| 运行时目标 | Node ≥ 18 与现代浏览器双端可用 |
| HTTP | `fetch` 原生 + 自封装重试/超时 |
| SSE 流式 | `fetch` ReadableStream 解析（`eventsource-parser`），支持 for-await 迭代与 AbortController 中止 |
| 认证 | OAuth 授权码 + PKCE（`oauth4webapi`）与 API Key 两种模式 |
| 校验/测试 | `zod`（响应契约校验，schema 与主工程 Pydantic 对齐）+ `vitest` + `msw`（Mock） |
| 发布 | `changesets` 版本管理 + npm provenance（OIDC 可信发布）；API 契约 v1 对齐语义化版本 |

### 3.2 Python SDK（PyPI `edumeet-sdk`）

| 项 | 选型 |
|---|---|
| 核心 | `httpx`（异步+同步双客户端）+ `pydantic v2`（模型与主工程 schemas 对齐生成） |
| SSE | `httpx-sse`，`async for` 流式迭代 |
| 工程化 | `uv` 依赖管理 + `ruff` + `mypy`；`pytest` + `respx` Mock |
| 发布 | PyPI trusted publishing；版本与 TS SDK 对齐 |

### 3.3 SDK 工程结构（monorepo 内 `sdk/`）

```
sdk/
├── ts/                     # @edumeet/sdk
│   ├── src/{client,resources,streaming,auth}/
│   └── examples/           # 对话流式/生成任务/检索 三例
├── py/                     # edumeet-sdk
│   ├── src/edumeet/{client,resources,streaming}/
│   └── examples/
└── CONTRACT.md             # 与 docs/spec/03 契约的映射表（CI 校验一致性）
```

- **契约对齐机制**：CI 步骤拉取主工程 OpenAPI JSON → 脚本比对 SDK resources 与 03 契约，路径/参数漂移即红灯（SDK 永不暴露 /admin 接口）。
- SDK 流量走独立 client_id + 配额（Spec 10 §5.3），`User-Agent: edumeet-sdk/{ver}` 便于统计。

### 3.4 使用示例（JS，与 Spec 10 §5.2 一致）

```js
for await (const ev of client.chat.send(session.id, "幼升小需要准备什么？")) {
  if (ev.type === "message_delta") process.stdout.write(ev.data.delta);
}
```

## 4. 实现排期（对应 Spec 10 §6 的 M5 四周）

| 周 | 桌面客户端 | 开放 SDK |
|---|---|---|
| W1 | Tauri 工程搭建、platform 抽象层、OAuth PKCE + keyring 存储 | TS SDK 骨架 + 认证 + 对话流式 |
| W2 | fs/dialog/通知/快捷键/截图/SQLite 缓存 | TS 检索/生成/素材 + msw 测试 + 契约比对 CI |
| W3 | 自动更新 + 双平台签名公证 CI + 安全评审 | PyPI SDK 对齐实现 + 示例与 TypeDoc/mkdocs 文档 |
| W4 | 灰度发布 + 指标验收 | npm/PyPI 发布 + 示例站点 + 首批第三方接入试点 |

## 5. 验收标准

- [ ] 桌面端全部能力均有对应 Tauri 插件实现，capabilities 最小授权通过安全评审
- [ ] 双平台 CI 签名公证流水线一次通过；自动更新全流程演练成功（含签名校验失败回滚）
- [ ] platform 抽象层改造后 Web 端回归零破坏（CI 双端测试）
- [ ] TS/Py SDK 契约比对 CI 上线：SDK 与 03 文档漂移自动红灯
- [ ] SDK 发布 npm/PyPI 成功且 provenance/trusted publishing 生效；三类示例可运行
- [ ] 桌面端指标达 Spec 10 §7 基线（包体/冷启动/内存）
