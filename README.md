# TeamAI 团队仓库载荷

> 这个目录的内容**准备推送到远程团队仓库**（`teamai init` 的目标）。
> 完整部署与验证手册见 [`../docs/teamai-deploy.md`](../docs/teamai-deploy.md)。

## 里面有什么

| 路径 | 作用 |
|---|---|
| `teamai.yaml` | 团队仓库配置。**核心是 `toolPaths.cline`** —— 这是 Cline 能收到规则的根本原因（TeamAI 内置表里没有 cline）。 |
| `mcp/mcp.yaml` | 总控 MCP Server 声明。TeamAI 不会为 Cline 写 MCP，这份由 `../scripts/teamai-mcp-bridge.mjs` 消费。 |
| `rules/*.md` | 分发到成员工作区 `.clinerules/` 的规则。**副本**，真源在 `../cline/`。 |
| `env/env.yaml` | 团队级默认变量（只放与机器无关的值）。 |

## 两个必须知道的事

**1. 写了 `toolPaths`，TeamAI 内置的 17 个客户端会整体消失。**
zod 的 `.default()` 只在键**缺失**时生效 —— 不是合并。所以本文件里的 `toolPaths`
就是"这次到底分发给谁"的完整清单。要加回别的客户端（如 `workbuddy`），在里面逐个补条目。
（`teamai.yaml` 里有注释掉的示例。）

**2. `${VAR}` 绝不写死机器路径。**
`${PCS_NODE}` / `${PCS_AGENT_ROOT}` 由每个成员在自己机器上填：

```powershell
node ..\scripts\teamai-mcp-bridge.mjs --detect
```

解析优先级（低 → 高）：
`env/env.yaml` < `~/.teamai/pcs-cline-bridge.json` < `--var KEY=VALUE` < 进程环境变量。
解析不到就跳过该 server 并告警 —— 不写半截配置。

## 推送到团队仓库

```powershell
# 把这个目录的内容复制到团队仓库根目录后提交
# 注意：teamai.yaml 的 repo: 字段要填成真实仓库地址
git add . && git commit -m "feat: pcs-orchestrator MCP + Cline 路由规则" && git push
```

> `mcp/env/rules/teamai.yaml` 可以手工 commit push；只有 `skills` / `rules` / `agents`
> 这类资源走 `teamai push`（它会给它们补 frontmatter 并开 MR）。
