# 本工程关键事实（Cline 常驻上下文）

> 这份文件只写「不知道就会做错」的事实，不写教程。详细操作见 `02-agent-routing.md`。

## 一、MCP 服务

| server | 工具数 | 定位 | 配置文件 |
|---|---|---|---|
| **`pcs-orchestrator`** | **7** | **唯一入口** · 总控编排 | `%USERPROFILE%\.cline\data\settings\cline_mcp_settings.json` |

本机 stdio 服务，**不依赖网络**。工具有没有 7 个，是判断「挂没挂上」的第一块试金石。

> `pcs-requirement`（3 个工具）是第一步验链路时的起步脚手架，配置里已 `"disabled": true`。
> 若工具列表里出现了 `analyze_requirement`，说明它被开回来了 —— 那会与总控的 `req` 节点功能重叠，
> 见 `02-agent-routing.md` 第一节。

## 二、工作区与规则（最容易翻车的一节，先看这里）

**Cline 只读「当前打开的工程根目录」下的规则**，读这些位置（都会加载，会叠加生效）：

```
<工作区根>/.clinerules              ← 单文件形态
<工作区根>/.clinerules/**/*.md      ← 目录形态（两者可同时存在，同时生效）
<工作区根>/AGENTS.md
<工作区根>/.cline/rules
<工作区根>/.cline/skills/**         ← 技能，按需加载
```

**翻车场景（真实发生过）**：规则被装到了 A 目录，而你 VS Code 打开的是 B 目录 →
Cline 完全看不到本规则，却读到了 B 目录里**另一套**规则（比如"你内部包含 PlannerAgent /
CoderAgent / ReviewerAgent 三个角色"这种角色扮演式流程）→ 于是它自己扮演规划、自己写代码，
**全程没调一次 MCP**，你看到的现象就是「直接从需求跳到代码生成，中间没有任何确认」。

所以，开工前先确认这三件事：

1. **当前工作区**是哪个目录？（VS Code 标题栏 / 文件资源管理器根）
2. 该目录下有没有本工程的规则？（没有就 `node scripts/install-clinerules.mjs` 装）
3. 该目录下**有没有别的规则文件**？（有就存在抢方向盘的风险 —— 脚本会报警，见 `02-agent-routing.md` 效力声明）

## 三、服务端位置（排查问题时用）

- 包根：`C:\Users\GAOJING\WorkBuddy\2026-09-09-15-57-23\pcs-agent`
- 入口：`src/server.mjs`
- Node：`C:\Users\GAOJING\.workbuddy\binaries\node\versions\22.22.2-3\node.exe`

## 四、产物落在哪

```
pcs-agent/runs/<run_id>/state.json                          ← DAG / 节点状态 / 卡点 / 事件流
pcs-agent/runs/<run_id>/artifacts/A-0001/requirement-contract.md   ← 需求契约
pcs-agent/runs/<run_id>/artifacts/A-0002/DESIGN.md                 ← 设计说明 + 需求映射表
pcs-agent/runs/<run_id>/artifacts/A-0002/src/**/*.h, *.c           ← 代码
```

**不要**去翻 `runs/` 目录里"最新的那个"来猜当前 run —— 用 `list_artifacts(run_id)` 取准确路径。
状态与产物都不进对话，Cline 侧只持有 `run_id`。

## 五、关于 mock 模式（最容易误解的一点）

当前 `PCS_LLM_MODE=mock`，模型产物来自 `prompts/fixtures/*.mock.md` **固定夹具**。

因此：

- ❌ **不要**用"改需求 → 看代码变了没"来验证链路 —— mock 下代码永远是同一份夹具，这与需求无关。
- ❌ mock 下**不要**用产出内容去评判"智能体做得好不好" —— 那要切 `live`。
- ✅ mock 下该验的是：**链路是否通**（节点推进 / 卡点守门 / 产物落盘 / 跨智能体引用）。
- ✅ **例外**：域硬约束预检是**确定性文本扫描**，不经过模型 ——
  需求里出现「允许使用 malloc」这类放宽约束的表述，**任何模式下**代码生成节点都会失败并给出精确到行号的原因。
  这是刻意设计的：守门不能依赖模型自觉。

## 六、可用验证命令（在 pcs-agent/ 下执行）

```
node scripts/mcp-attach-check.mjs        配置能不能把 server 拉起来（活跃 server 逐个握手）
node scripts/mcp-orchestrate-check.mjs   多智能体协同端到端（真实 MCP 客户端）
node scripts/invariants-selftest.mjs     域约束扫描器自测（12 例）
node scripts/install-clinerules.mjs      装/查规则（--check 只做检测，不改文件）
node scripts/demo.mjs                    进程内闭环（绕过 MCP 层，只验编排逻辑）
```

服务端这几条都过了还出问题，基本可以断定问题在 **Cline 侧**（配置 / 规则装错目录 / 对话引导），
不在服务端。此时按第二节那三个问题逐条查。
