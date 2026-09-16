# PCS/EMS 研发域代码生成助手 · 入口

本工作区背后有一套**真实的多智能体后端**（MCP server `pcs-orchestrator`，7 个工具）。
研发需求走它的 DAG 编排，不要在本机自行"扮演流程"。

## 一句话规则

- 需求分析 / 代码生成 **只能**由 `pcs-orchestrator` 的节点产出（`run_step`）。
- 卡点（需求契约签发、代码合并）**必须由人决定**，不要代签。
- 失败时先把 `get_run_status` 的原因**原样转述**给人，再让人选 `resolve_failure` 的 action。

## 详细规则在哪

完整流程、域硬约束、路由判据都写在 `.clinerules/` 目录下的规则文件里。
**本文件只是索引；与 `.clinerules/` 冲突时，以 `.clinerules/` 为准。**

| 文件 | 内容 |
|---|---|
| `.clinerules/00-workspace-context.md` | 工作区是什么、有哪些工具可用 |
| `.clinerules/02-agent-routing.md` | 路由规则（总控优先）+ 效力声明 + 标准动作序列 |
| `.clinerules/03-pcs-feature-workflow.md` | 走一遍完整需求的逐步剧本 |

## 与总控并行时可用的技能

`.cline/skills/` 下的技能按需加载，例如 `requirement-contract-review`
用于在需求契约签发卡点前做结构化自检。
