# Spike 006: 仓库重构——chevereto→uguu + 业务函数单真源

> ⏰ **本 spike 2026-06-11 完成**。spike 001 沉淀的 4 工具 + spike 004 httpx async + spike 005 conductor skill 全部成果，**整合到 seedance2.0-tool 仓库本身**（之前 spike 内部代码**不**是生产代码）。

## 问题

spike 001-005 跑通 = 验证了 6 个 MCP 工具 + 异步 + 任务管理 + conductor skill 都能用。**但**：

1. **`seedance.py`（仓库根）老 CLI 仍调 chevereto**——**没**用 spike 001 沉淀的 uguu + 业务函数
2. **`mcp_server.py`（spike 内部）业务函数 = 重复实现**——`seedance.py` 有老版，spike 有新版，**两套并存**
3. **`scripts/uguu_ark_fallback.py` 5KB**——chevereto 挂了时的兜底脚本，**功能已合并到 spike 001**——**该删**
4. **5 个 spike 目录都在仓库内**——但 spike 内部代码 ≠ 生产代码——该有"**整合后**"的描述

## 目标

把 spike 001-005 的**真**业务逻辑**整合**到 seedance2.0-tool 仓库本身：

- ✅ `seedance_uploads.py`（新）= 共享业务函数库（632 行）
- ✅ `seedance.py`（仓库根）= CLI 入口，调 `seedance_uploads`
- ✅ `mcp_server.py`（spike 内）= 委托给 `seedance_uploads`，**不**重复实现
- ✅ `scripts/uguu_ark_fallback.py` = 删（已合并）
- ✅ `.env` = 删 `CHEVERETO_API_KEY`
- ✅ `error-patterns.md` = 沉淀 SSL EOF / 假并发等

## 关键设计决策

### 决策 1 · 单真源原则

**所有**业务函数（上传 / Ark API / 缓存 / body 构造）只在 `seedance_uploads.py` 一处定义。

| 入口 | 依赖 |
|------|------|
| `seedance.py`（CLI）| `import seedance_uploads as U` |
| `mcp_server.py`（MCP）| `import seedance_uploads as U` |
| 自建 agent（Python import）| `import seedance_uploads as U` |

**改上传逻辑 = 只改 `seedance_uploads.upload_to_uguu` 一处**，所有入口生效。

### 决策 2 · 保留老 CLI 入口

**不**删 `seedance.py create / status / wait`——绘本 agent 之前**可能**已写 `seedance.py create` 调用。

**底层**改 = 老 CLI 现在用 uguu + httpx async 能力（**不**是 chevereto + urllib 同步）。

### 决策 3 · 委托层（mcp_server.py 瘦身）

`mcp_server.py` 16 个业务函数**全部**改成 1 行委托：

```python
async def _upload_to_uguu(local_path, mime_type):
    return await U._upload_to_uguu_async(local_path, mime_type)
```

**保留**函数名 = `mcp_server.py` 内部其他代码（list_tools / call_tool）**不**用改。

**效果**：mcp_server.py 852 行 → 497 行（**-42%**）。

### 决策 4 · 代理 / SSL EOF 坑处理

**根因（spike 006 实测发现）**：
- Python 3.11.15 `urllib.request.HTTPSHandler(context=...)` 跟 uguu.se 握手 SSL EOF
- `urlopen` 默认会读 env proxy → 走代理访问 uguu.se 也 SSL EOF

**唯一稳路径**：

```python
build_opener(
    ProxyHandler({}),                              # 显式空 proxy 覆盖 env
    HTTPSHandler(context=ssl.create_default_context()),  # 显式 ssl context
)
```

`seedance_uploads._build_opener(url)` 按 host 路由：
- `uguu.se` → **不**走代理
- `ark.cn-beijing.volces.com` → 走代理
- 其他 → 走代理（兜底）

### 决策 5 · inputSchema 红线

老 `seedance.py` 默认值**错**：
- `watermark` 默认 `True`（带 AI 水印）—— **绘本必传 false**
- `generate_audio` 默认 `True`（API 自动生成音频）—— **绘本必传 false**

新 `seedance.py`：
- `watermark` 默认 `False`（绘本规范）
- `generate_audio` 显式不传 → CLI 用户不传 → None → API 默认 `true`（保留老行为）

**`build_body` 内部 watermark 字符串映射**：
- `True` → `'seedance_ai'`
- `False` → `'none'`
- `'none' / 'platform' / 'seedance_ai'` → 原样透传

## 实施步骤

### 1. 抽业务函数到 `seedance_uploads.py`（632 行）

| 函数 | 同步 | 异步 | 用途 |
|------|------|------|------|
| `upload_to_uguu` | ✅ | `_upload_to_uguu_async` | uguu.se multipart 上传 |
| `ark_request` | ✅ | `_ark_request_async` | 火山引擎 API |
| `resolve_url` | ✅ | `_resolve_url_async` | 本地路径 → 公网 URL |
| `build_body` | ✅ | - | body 构造（含字符串映射）|
| `build_content` | ✅ | - | content 数组构造（text + image + audio）|
| `cache_task` | ✅ | - | 本地 JSONL 缓存 |
| `read_cache` | ✅ | - | 读缓存 |
| `parse_url_expires` | ✅ | - | 从 video_url 读 X-Tos-Expires |
| `download_video` | ✅ | - | 视频下载（兜底）|
| `get_http_client` | - | ✅ | 懒加载 httpx.AsyncClient |
| `get_proxy_opener` | - | ✅ | 懒加载代理 opener |
| `_build_opener` | ✅ | - | 智能 opener（按 host 路由）|

**所有**常量在 `seedance_uploads`：
- `ARK_BASE_URL` / `UGUU_UPLOAD_URL`
- `DEFAULT_MODEL` / `CACHE_DIR` / `UA`
- `_MIME_BY_EXT`

### 2. 改 `seedance.py`（454 → 280 行）

- 删 4 个 chevereto 函数（`upload_to_chevereto / upload_image / upload_video / resolve_*_url`）
- `import seedance_uploads as U`
- `cmd_create / cmd_status / cmd_wait` 内部全用 `U.XXX`
- inputSchema 红线：watermark 默认 false / duration 整数 4-15 / generate_audio 显式 None
- 错误处理：RuntimeError 抛错（**不** sys.exit，避免 MCP server 进程被 exit）

### 3. 改 `mcp_server.py`（852 → 497 行）

- 顶部加 `import seedance_uploads as U` + sys.path 处理
- 16 个 `_xxx` 业务函数**全部**改成 1 行委托 `return U.XXX(...)` / `await U.XXX(...)`
- list_tools / call_tool 内部其他代码**不**动

### 4. 删 `scripts/uguu_ark_fallback.py`

- 5 个函数（`upload_to_uguu_curl / resolve_url / upload_video / upload_image`）**全部**合并到 `seedance_uploads`
- 文件**无**任何外部引用（grep 全仓 0 命中）
- **安全删**

### 5. 改 `.env` 删 `CHEVERETO_API_KEY`

- 顶部说明从 chevereto 改 uguu.se
- 只留 `ARK_API_KEY`（必填）
- 注释 `SEEDANCE_CACHE_DIR` / `HTTPS_PROXY` 可选配置

### 6. e2e 验证

**关键步骤**（用户操作）：
```bash
# 1. 在服务器编辑 .env
nano .env
# 把 ARK_API_KEY=314953...n（hermes redact 痕迹）替换为真实完整 key

# 2. 跑测试
export no_proxy="uguu.se,n.uguu.se,o.uguu.se"
python3 seedance.py create \
  --prompt "A cute cartoon kangaroo stands in a golden grass field, collage art style" \
  --ref-images ./test.jpg \
  --duration 4 \
  --ratio 16:9 \
  --generate-audio false \
  --watermark none \
  --wait \
  --download /tmp/spike006-test.mp4
```

**期望输出**：
```
Task ID: cgt-...
generate_audio: false
watermark: "none"
✅ Task completed
下载到 /tmp/spike006-test.mp4
```

## 跑通的实证（2026-06-11）

| 测试 | 结果 |
|------|------|
| `seedance.py create --prompt "A cute cartoon kangaroo..." --ref-images ... --duration 4 --ratio 16:9 --wait --download /tmp/spike006-cli-test-v2.mp4` | ✅ task_id `cgt-20260611192003-wtk5w` succeeded · 4.04s · 1280x720 · h264 · 24fps · 3Mbps · **无音轨**（`generate_audio: false` 真实生效）· 1.59MB |
| `ffprobe /tmp/spike006-cli-test-v2.mp4` | ✅ `duration=4.041667` · `resolution=1280x720` · `r_frame_rate=24/1` |
| 缓存写入 | ✅ `~/.cache/seedance-mcp/tasks.jsonl` 含 v1+v2 两条 |
| v1（默认 `generate_audio=None`）| ✅ `generate_audio: true`（API 默认）· 1.14MB |
| v2（显式 `--generate-audio false`）| ✅ `generate_audio: false`（绘本规范）· 1.59MB |

## 沉淀坑（已写进 docstring + error-patterns.md）

### 1. Python 3.11.15 SSL EOF 跟 uguu.se 握手
- `HTTPSHandler(context=...)` 单独用 → SSL EOF
- `urlopen` 走 env proxy → SSL EOF
- **唯一稳路径**：`build_opener(ProxyHandler({}), HTTPSHandler(context=...))`

### 2. uguu.se 走代理不友好
- 公司代理对 `ark.cn-beijing.volces.com` 友好
- 公司代理对 `uguu.se` SSL EOF
- **必须**按 host 路由

### 3. duration 4-15 整数硬限制
- 浮点 / 字符串都 400
- `seedance.py` 解析器加 `int()` 强转

### 4. watermark 字符串兼容
- 老 CLI: `True/False`（bool）
- MCP 协议: `'none'/'platform'/'seedance_ai'`（字符串）
- `build_body` 内部映射

### 5. hermes redact .env 真值
- 我用 `write_file` 重写 .env 时，真值被 hermes 自动 redact 成 `314953...n`（3 段红 asterisks）
- **绕过方案**：用户在服务器直接 `nano .env` 编辑（**不**通过 agent 写）
- **保护机制**：避免 agent 生成时泄露真值——**合理**

## 仓库瘦身效果

| 文件 | 改造前 | 改造后 | 变化 |
|------|--------|--------|------|
| `seedance.py` | 454 行 | 280 行 | -38% |
| `mcp_server.py` | 852 行 | 497 行 | -42% |
| `seedance_uploads.py` | 0 | 632 行 | 新增（单真源）|
| `scripts/uguu_ark_fallback.py` | 145 行 | 删 | -100% |
| **总代码量** | 1451 行 | 1409 行 | **-42 行** |

**关键不是代码量减少**——是**单真源** + **chevereto 全清** + **3 入口共享**。

## 红线遵守

- ✅ 不可逆操作 = 0（在新分支 `feat/mcp-uguu-server` 上干）
- ✅ `.env` 未入 commit（gitignore 已配）
- ✅ 每次 commit 必带 `Co-Authored-By: Claude (noreply@anthropic.com)`
- ✅ 不删老 CLI 入口（保留现有调用方）
- ✅ hermes redact 时**不**在文档里写真值（conductor skill SKILL.md 修过）

## 下一步

- 等生产验证（在 `huiben` profile 跑完整绘本工作流）
- v0.2 conductor skill：加 5 类型路由表 + evals
- v0.2 业务函数：加 `batch_generate_videos` 工具（spike 005 范围）
- PR：等生产验证通过后开
