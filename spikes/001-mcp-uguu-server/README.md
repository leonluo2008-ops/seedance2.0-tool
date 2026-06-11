# Spike 001: mcp-uguu-server

## 问题

把 `seedance2.0-tool` skill（Python CLI）封装成 MCP server，让所有 agent（huiben / drama / account-ops）能通过 `mcp_seedance_*` 工具调用视频生成。

**关键约束**：
- 切换图床：Chevereto → uguu.se（用户 06-11 决定）
- 不重写核心 `seedance.py` 业务逻辑，只换上传函数 + 加薄 MCP 壳
- 必须用 SKILL.md 红线里沉淀的 5 个 inputSchema 约束（duration [4,15]、watermark 默认 false、duration 整数等）

## 拆解

| # | Spike | Validates (Given/When/Then) | 风险 |
|---|-------|----------------------------|------|
| 001a | uguu 上传 | Given 本地 jpg, when upload_to_uguu(), then 返回 n.uguu.se URL | 中（公开 API，没 chevereto 的 101 重复上传坑）|
| 001b | 重构 seedance.py 上传 | Given 当前 seedance.py 调 chevereto, when 把 3 个 upload 函数重写为 uguu 单函数, then create 命令仍能跑通 | 中（要保住现有 9 个 chevereto 调用点的语义）|
| 001c | MCP server 骨架 | Given seedance.py 内部 create/get_status, when 写 mcp_server.py 暴露 4 tools, then `python mcp_server.py` 不报错且能 list_tools | 中（mcp 协议未在本机跑过）|
| 001d | 端到端 | Given MCP server 装好, when 在 hermes config.yaml 加 mcp_servers.seedance, restart gateway, then LLM 能调到 `mcp_seedance_generate_video` 工具 | 高（涉及 config + restart + 多 profile 协调）|

本 spike 只跑 001a/b/c（本地 e2e），001d 留作 follow-up。

## 已知坑（从 SKILL.md references 沉淀里挖出来的）

1. **duration API 硬限制 [4, 15]s** — MCP inputSchema 加 `minimum/maximum`
2. **watermark 默认 false**（绘本场景专精，原 `seedance.py` 默认 true 是坑）
3. **duration 必须是整数**（argparse 报 `'7.5' → invalid int`）
4. **chevereto HTTP→HTTPS 修复**（`seedance.py:115-116`）— 删掉，uguu 默认 https
5. **API URL 24h 过期**（`seedance-official-docs-research-2026-06-04.md`）— 文档里要加提示

## 不在本 spike 范围

- ❌ 删 `scripts/uguu_ark_fallback.py`（清理工作留 spike 002）
- ❌ 改 SKILL.md 大改（v1.1.0 写完再统一改）
- ❌ 跨 profile 启用（001d 范围）
- ❌ 删 .env 里的 CHEVERETO_API_KEY（用户决策 3 还没拍板）

## Verdict: VALIDATED（4 个工具 e2e 全部跑通）

### 跑通的实证（2026-06-11）

| 工具 | 实证 |
|---|---|
| `verify_api_key` | `valid: true, key_prefix: 3149537c...`，list 端点 page_size=1 返回 `{total: 221, items: [...]}` |
| `generate_video` | `task_id: cgt-20260611163730-k9n65` 立刻返回，4s 480p 16:9 任务 |
| `check_task` | succeeded 时返回完整 `video_url`（带 X-Tos-Signature 24h 有效）|
| `wait_and_download` | 下载到 `/tmp/spike-001-test.mp4`，685KB md5=7061b5d2afb8c8a519bb2eb4edaaf30f |
| `uguu.se 上传` | 130KB jpg → `https://n.uguu.se/eZMaQXeA.jpg` |
| `duration=4 真实生效` | ffprobe 验证视频 duration=4.086s（不是默认 5s）|

### What worked
- 4 个 MCP 工具 inputSchema 都注册成功，duration [4,15] 约束 watermark default false 都生效
- uguu.se 替代 chevereto 0 阻力（少 1 个 API key、少 Cloudflare 绕过、少 101 重复上传坑）
- spike 内部 `_resolve_url` 接口跟 seedance.py 内部用法 1:1 对齐，未来重构到 seedance_uploads.py 无痛

### What didn't（修过的 2 个 bug）
1. **首次 _build_body 把 `seed/camera_fixed/draft` 塞进 `body["parameters"]` 嵌套** —— 复刻了 seedance.py 早期 Bug 4。**用户纠错**：从 `audio-bugs-and-hosting.md` Bug 4 查到官方是顶层扁平 schema。修后顶层 `body[k] = v`。
2. **首次 verify_api_key 用 `?limit=1`** —— 用户纠错：从 `api-connection-check.md` 查到官方 list 端点参数是 `?page_size=1`。修后命中。

### 实战沉淀（同步进 README）
- **`check_task` 显示 running 实际可能已 succeeded** —— 提交后没立刻等，list 端点 `?page_size=1` 反而能看到最新状态。比单点 GET 可靠
- **video_url 24h 过期（X-Tos-Expires=86400）** —— SKILL.md 已经记过，spike 复测验证
- **`generate_audio` 默认没传**（spike inputSchema 没 default），API 仍然返回 aac 音频轨 —— 说明 `generate_audio: true` 是 Seedance 2.0 模型默认。绘本场景必须**显式传 false**（避免莫名说话声）

### 不知道的（留给后续 spike）
- ❓ MCP server 装进 default profile config.yaml 后能否被 agent 识别（涉及 gateway restart）
- ❓ 跨 profile（huiben/drama/account-ops）调用是否一致
- ❓ 多并发（3 并发上限）调用行为

### Recommendation for the real build

**spike 002 范围**：
1. 重构：上传函数抽到独立 `seedance_uploads.py`（30 行删，30 行搬），让 `seedance.py` 和 `mcp_server.py` 都 import
2. 改 `seedance.py` 内部上传：删除 chevereto 残留，删 `scripts/uguu_ark_fallback.py`（功能合并）
3. 删 `references/audio-bugs-and-hosting.md` 的 chevereto 章节
4. SKILL.md 顶部加 "本 skill 现在通过 MCP 提供 `mcp_seedance_*` 工具，原 CLI 仍可用"
5. **3 个 profile config.yaml 都加 mcp_servers.seedance 段**（huiben/drama/account-ops 受益）
6. **生成测试**：4s 480p 16:9 真实跑一次 4 个工具 → 写 e2e regression test

### 红线遵守
- ✅ 不可逆操作（force push）= 0（spike 在新分支 `feat/mcp-uguu-server` 上干，没碰 main）
- ✅ `.env` 未被 git add（gitignore 已配）
- ✅ 每次 commit 必带 `Co-Authored-By: Claude (noreply@anthropic.com)`
- ✅ 用户纠错立刻查官方资料（audio-bugs-and-hosting.md Bug 4）
