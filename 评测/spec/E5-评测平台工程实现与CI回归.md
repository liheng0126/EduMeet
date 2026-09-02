# E5 - 评测平台工程实现与 CI 回归

> 版本：v1.0 ｜ 状态：待评审 ｜ 上游：E0~E4 ｜ 落地物：`评测/evals/` 工程

---

## 1. 目标与范围

实现评测体系的工程载体：评测执行器（runner）、套件（suites）、指标库（metrics）、报告与趋势看板、CI/CD 门禁集成。与主工程解耦（独立目录独立依赖），但通过 API/LiteLLM/Langfuse 与主工程互通。

## 2. 工程结构

```
评测/evals/
├── datasets/            # E1：DS1~DS6 JSONL + VERSIONS.md
├── metrics/
│   ├── l1_rules.py      # 结构/引用/时效标注等规则断言
│   ├── l2_stats.py      # NDCG/MRR/Recall/RAGAS 封装
│   └── l3_judge.py      # LLM-as-Judge（Rubric 版本化加载）
├── suites/
│   ├── smoke.yaml       # PR 门禁：DS2×10 + DS4×20，≤10 分钟
│   ├── nightly.yaml     # 每夜：DS1/DS2/DS3 全量（D1~D5）
│   └── release.yaml     # 发布门禁：全部数据集 + 阈值引用
├── runner.py            # 并发执行、超时重试、结果聚合、报告生成
├── gate.py              # 门禁判定：套件阈值 → exit code
└── reports/             # {run_id}/report.html + metrics.json
```

## 3. 套件定义（YAML）

```yaml
# suites/smoke.yaml
name: smoke
datasets:
  - {id: DS2, version: v1.0, subset: smoke, size: 10}
  - {id: DS4, version: v1.0, subset: hard_rules, size: 20}
targets:
  - {domain: D1, pipeline: article_generation, model_ref: doubao-pro}
  - {domain: D4, chain: review_agent}
gates:
  - {metric: task_success_rate, op: "==", value: 1.0}
  - {metric: safety_block_rate, op: "==", value: 1.0}
timeout_per_case_sec: 300
```

## 4. 执行与被测环境

- **评测环境**：docker-compose 拉起主工程完整栈（backend/worker/pg/redis/es/litellm/minio），种子数据预置；runner 通过 API 发起真实调用。
- **隔离**：独立 compose project（`edumeet-eval`）与数据卷，评测数据不污染开发库；评测集文件不进入主工程镜像（防泄漏）。
- **被测能力开关**：检索三模式对照、降级链关闭、故障注入（D5 断点恢复）均由环境变量控制，runner 每用例声明所需开关。

## 5. CI/CD 门禁集成

| 触发 | 套件 | 行为 |
|---|---|---|
| PR（backend/agents/prompts 变更） | smoke.yaml | 阻断式：gates 失败 → CI 红灯，附报告链接 |
| 每夜 02:00 | nightly.yaml | 非阻断：报告 + 劣化 >3% 告警（飞书） |
| 发布 tag | release.yaml + E2 人工抽检清单 | 阻断式：全部门禁 + 人工确认双签 |
| 手动 | 任意套件/单数据集 | 专项评测（模型对比、故障演练） |

- 门禁阈值集中维护于 `gate.py`（对应 E0 第 4 章总表），修改需 PR 评审。
- 报告上传为 CI artifact 并推送链接至 PR/飞书；metrics.json 归档供趋势看板消费。

## 6. 趋势看板（M3）

- 存储：metrics.json 汇入主工程 PostgreSQL（eval_runs / eval_metrics 两表，随 02 文档体系增补）。
- 看板：分域得分曲线、版本对比（vX vs vX-1）、模型对比散点（联动 E4 报告）。
- 告警：连续 3 次 Nightly 同指标下滑 >3% 自动开 issue 指认负责人。

## 7. 成本控制

- 评测调用走独立 LiteLLM 虚拟 Key（`eval-team`），月预算上限 ≈ 平台模型总预算 8%，超限告警并自动降 Smoke 频率。
- Judge 调用缓存：同输入同 Rubric 版本命中缓存不重复计费。

## 8. 验收标准

- [ ] M1：evals 骨架 + smoke.yaml 接入主仓 CI，PR 变更触发且 <10 分钟完成
- [ ] M2：nightly/release 套件生效，报告/告警/门禁全链路可用；发布门禁一次真实拦截演练留档
- [ ] 评测环境一键拉起（make eval-up），与开发环境数据完全隔离
- [ ] 评测成本月报：实际花费 ≤ 预算上限；Judge 缓存命中率 ≥ 30%
- [ ] gate.py 阈值与 E0 指标总表一致（脚本比对校验）
