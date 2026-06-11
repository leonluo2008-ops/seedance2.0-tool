# Spike 005: mcp-conductor-skill

> ⏰ **截至 2026-06-11 spike 001-006 全部完成**。本 skill `seedance-mcp-conductor` v0.1 已在 `~/.hermes/skills/creative/seedance-mcp-conductor`（symlink 到本目录）。

## 问题

`spike 001-004` 完成了 MCP server 本身（6 工具 + 异步 + 任务管理 + e2e 验证）。
**但** LLM 拿到工具后**会乱调**：

- ❌ 不知道绘本场景**禁用**首尾帧范式
- ❌ 不知道 watermark 默认值 = 错（绘本无水印是必加）
- ❌ 不知道一次提交 ≥3 段 = timeout
- ❌ 不知道 duration 必须是整数（argparse 报 `'7.5'`）
- ❌ 不知道 cost 控制（用户 feedback："不要总提交任务"）
- ❌ 不知道翻车自检必跑（vision 4 帧抽帧）

**MCP 工具 = 能力层，Skill = 方法论层**。两者必须配套。

## 拆解

| # | Spike | Validates | 风险 |
|---|-------|-----------|------|
| 005a | skill 文件创建 | Given spike 001-004 沉淀, when 写 `SKILL.md`, then skill 能 load + 触发词命中 | 低 |
| 005b | 占位符思维 | Given "通用性" 约束, when 写完, then 0 真实路径 / 0 真实模型 ID / 0 真实 profile | 中（容易不自觉硬编码）|
| 005c | 红线遵守 | Given git 红线 5 问, when 准备 commit, then 5 问全清 | 低（按 references 跑） |
| 005d | skill 配套 MCP | Given MCP 6 工具, when LLM 同时拿 skill, then skill 不重复工具定义, 只覆盖方法论 | 中（容易写成"工具说明"）|

## 设计原则

### 1. Skill 不写 inputSchema / 默认值
- MCP 工具**自己**暴露 inputSchema
- skill **不**重复（避免双源不一致）
- skill **只**写"什么时候用、怎么用、不该怎么做"

### 2. 工具名匹配意图，不硬编码
- MCP server 可能改工具名（如 `generate_video` → `submit_task`）
- skill 描述**意图**（"0 元连通性验证"）而非固定名
- LLM 拿工具时**自己**用前缀 `mcp_seedance_*` 匹配

### 3. 占位符思维
- ❌ 不写：`~/.cache/seedance-mcp` / `huiben` profile / `doubao-seedance-2-0-fast-260128`
- ✅ 写：`${ENV:SEEDANCE_CACHE_DIR}` / "任意 profile, 按部署" / `${ENV:SEEDANCE_MODEL_DEFAULT}`

### 4. 跨环境安装不写死
- skill 路径 = `${SKILL_INSTALL_DIR}`（用户配置）
- MCP server 路径 = `${PATH_TO_REPO}/spikes/001-mcp-uguu-server/mcp_server.py`
- 环境变量 = `${ENV:ARK_API_KEY}` 等

## 验证

- ✅ `skill_view seedance-mcp-conductor` 正常加载
- ✅ `readiness_status: "available"`（无缺失环境变量/命令/凭证）
- ✅ 触发词命中：`mcp_seedance` / `seedance MCP` / `视频生成指导` / `绘本视频 MCP` / `调用视频生成`
- ✅ 硬编码真实值扫描：3 处全部在**反例陈述**里（"不写 `~/.cache/...`"）
- ✅ 14 个 `${VAR}` 占位符引用（5 个 `${ENV:...}` + provider/path/file_host 占位）

## 配套安装

skill 实际安装位置（symlink 到 spike 目录）：

```bash
# 真源（在 seedance2.0-tool 仓库内）
${REPO_ROOT}/spikes/005-mcp-conductor-skill/SKILL.md

# 安装位置（symlink → 真源）
~/.hermes/skills/creative/seedance-mcp-conductor
```

**为什么 symlink**：单真源，跟 MCP server 源码同仓库管理（红线 4 = 独立仓库不混）。

## v0.1 不写的内容（占位给后续版本）

- 5 类型路由表（绘本领读/押韵/短句/故事/知识）—— v0.2 加
- evals 评估（darwin-skill 跑 8 维评分）—— v0.2 加
- 多 profile 协调示例（huiben/drama/account-ops 各自场景）—— v0.2 补
- 失败重试策略细节（指数退避 / 任务优先级队列）—— v0.2 加
- TTS / BGM 配套（绘本无 BGM 是默认，但用户要 BGM 时如何）—— v0.2 拆独立 skill
- 跨平台 MCP 注册模板（Claude / Cursor / Cline 等）—— 留给各平台文档

## Verdict: VALIDATED v0.1

### 跑通的实证（2026-06-11）

| 维度 | 实证 |
|------|------|
| 加载 | `skill_view seedance-mcp-conductor` 200 OK + 完整 364 行内容 |
| 触发词 | 5 个触发词全部命中（mcp_seedance / seedance MCP / 视频生成指导 / 绘本视频 MCP / 调用视频生成）|
| 通用性 | 0 真实路径 / 0 真实模型 ID / 0 真实 profile 名 |
| 占位符 | 14 个 `${VAR}` 引用（5 个 `${ENV:...}` + provider/path/file_host 等） |
| 章节完整 | 9 大章节：TL;DR / 工具对照 / 范式禁令 / 工作流 / cost / 自检 / 边界 / 错误恢复 / 通用性 |

### 用户 review 路径

- 用户已 review Task 5 的 3 个袋鼠视频（绘本风格保留良好）
- 用户已拍板 5 件事（名字 / 范围 / 路径 / evals / 路由表）
- 用户已选 B 方案（放进 seedance2.0-tool 仓库的 spike 目录）
- 用户已授权"动手 commit"

## 下一步

- **spike 006**（生产重构）：把 `video-executor` 子 agent 改成调 MCP（不再调 `seedance.py` CLI）
- **v0.2**（skill 演进）：加 5 类型路由表 + evals 评估
- **跨平台模板**（skill 演进）：Claude Desktop / Cursor / Cline MCP 注册模板

## 维护记录

- **2026-06-11** v0.1 MVP
