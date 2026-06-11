---
name: seedance-mcp-conductor
description: |
  通用视频生成 MCP 工具使用指导（v0.1 · 2026-06-11）。
  指导 agent 何时 / 怎么 / 不该怎么 调用 mcp_seedance_* 工具。
  配套工具（自动注册，命名以前缀 mcp_seedance_ 开头）：
    · generate_video       提交任务
    · check_task           查状态
    · wait_and_download    同步等待+下载
    · verify_api_key       0 元连通性
    · list_recent_tasks    本地缓存查询（可选）
    · download_cached      缓存复用下载（可选）
  
  工具数量 / 名称以 mcp server 实际暴露为准。本 skill 不写死工具名细节，
  只覆盖"该不该调 / 怎么调 / 怎么不翻车"的方法论。
  
  触发词：mcp_seedance、seedance MCP、视频生成指导、绘本视频 MCP、调用视频生成。
  
  配套 server 仓库：seedance2.0-tool（spikes/001-mcp-uguu-server/mcp_server.py）
license: Apache-2.0
metadata:
  hermes:
    tags: [mcp, video-generation, seedance, conductor, cross-profile, multi-agent]
    toolkit_role: mcp-tool-conductor
    version: 0.1.0
---

# seedance-mcp-conductor · MCP 视频生成工具使用指导

> **身份**：**不重复工具定义**（inputSchema / 默认值 server 自己暴露），只覆盖
> **方法论**（什么时候用 / 怎么用 / 不该怎么做）。
>
> **占位符思维**：本文档**不**写死 `~/.cache/...` 路径、`huiben` profile 名、
> `doubao-seedance-2-0-fast-260128` 模型 ID 等任何具体值——所有可变量都
> 标 `${VAR}` 引用。

---

## 🚦 TL;DR · 一段话

**MCP 视频生成工具 = 真金白银 API**。每次提交 = 计费。**三次必跑**：
1. **0 元 `verify_api_key`** 确认工具可用
2. **先算 cost**（duration × ratio × model）再问用户拍板
3. **单段 4s 试水** → 翻车自检 → 再批量（**不**一次提交 N 段）

**不该做的**：
- ❌ 一次提交 ≥3 段（绘本/漫剧默认 3 并发上限，超过必分批）
- ❌ duration > 12s（cost 线性增长，质量边际收益递减）
- ❌ watermark 默认值 = 错（绘本/海报场景必须无水印）
- ❌ 跳过自检直接发飞书（翻车征兆 = 文字消失 / 角色突变 / 主体丢失）

---

## 🛠️ 工具场景对照表

> **注意**：MCP server 可能改名工具，**不要硬背工具名**——用前缀 `mcp_seedance_` 匹配。
> 实际可用工具 = `MCP server list_tools()` 返回值。

| 场景 | 工具意图（中文） | 中文关键字 | 何时用 |
|------|---------------|-----------|--------|
| **接入验证** | `verify_api_key` | 验证、检查、连通性、API key、是否有效 | 第一次调该 MCP / 报错怀疑 key 失效 / 0 元 dry-run |
| **提交任务** | `generate_video` | 提交、生成、跑、起一个 | 单个 4-15s 视频，文/图参考 |
| **查状态** | `check_task` | 查、状态、轮询、succeeded? | 已知 task_id，看是否跑完 |
| **同步等待+下载** | `wait_and_download` | 等待、下载、保存 | task_id 已知，要拿到 mp4 |
| **历史任务** | `list_recent_tasks` | 列出、缓存、最近 | 24h 内复用 task，不重新提交 |
| **缓存下载** | `download_cached` | 缓存、重下、复用 | task 已在缓存，不调 API 重下 |

**核心铁律**：

- **`verify_api_key` 永远 0 元**——动手前必跑（30s 验证，**不**调 create 扣费）
- **`generate_video` 是唯一扣费点**——调之前**必问用户拍板**
- **`wait_and_download` = `check_task` 循环 + 下载**——单段场景优先这个，别自己写轮询
- **缓存命中比调 API 便宜**——同 task_id 不重复扣费

---

## 🚫 范式禁令（强约束 · 违反必翻车）

> 这些是绘本/漫剧/海报场景 **反复实战验证的翻车坑**。
> MCP 工具 inputSchema **不会**替你挡，**必须** skill 层面把关。

### 1. **duration 必须是整数**
- 工具接受 4-15s 整数（API 硬限制）
- ❌ `"duration": 4.5` / `"duration": "6s"` / `"duration": 7.0`
- ✅ `"duration": 7`（int）

### 2. **watermark 默认值 ≠ 通用**
- 工具**默认无水印**（绘本/海报场景专精）
- ❌ 主动传 `"watermark": "platform"` / `"watermark": "seedance_ai"`（带水印）
- ✅ 留空 / `"watermark": "none"`
- **判断逻辑**：绘本/教学/海报 = 无水印；用户**明确**要带水印 = 才加

### 3. **首尾帧范式 = 禁用**（绘本场景）
- ❌ `--image` + `--last-frame` 锁首尾两帧（绘本翻车坑）
- ✅ 只用 `--ref-images1.jpg [2.jpg]`（多图参考）

### 4. **批量 = 分批 3 并发上限**
- ❌ 一次提交 8 段 = 600s 直接 timeout
- ✅ 3 段一批 → 全部 succeeded → 下一批
- 实战约束：单 agent 同时持有 ≤3 个 running 任务

### 5. **不写"v7 / v15 / picN" 范式号**（v1.0.0 净化）
- ❌ "用 v7 范式跑 clip3" / "v15 导演思维版" / "pic4 实战版"
- ✅ 用场景名："用绘本领读型跑 clip3" / "用知识科普型写 prompt"

### 6. **本地路径不直接喂**
- ❌ 传 `"ref_images": ["${LOCAL_REF_IMAGE_PATH}"]`（seedance API 不接本地路径）
- ✅ MCP 工具**自动**通过 uguu（${FILE_HOST}）上传转公网 URL——**不**手动上传

### 7. **参数透传铁律**（2026-06-11 用户红线 · 重要）

**MCP 工具绝不强制覆盖 agent 传过来的参数**。逻辑：

- **agent 传了值** → **严格用 agent 的值**（即使违反默认推荐）
  - 例：绘本有声绘本场景，agent 主动 `generate_audio=True` → 工具**必须**用 True（带 BGM/音效）
  - 例：用户要水印，agent 主动 `watermark="seedance_ai"` → 工具**必须**用 seedance_ai
- **agent 没传** → 走 inputSchema 的 default
  - `generate_audio` 默认 `false`（绘本无 BGM）
  - `watermark` 默认 `"none"`（绘本无水印）
  - `ratio` 默认 `"16:9"`
  - `resolution` 默认 `"720p"`
  - `model` 默认 `doubao-seedance-2-0-fast-260128`

**实现细节**（seedance_uploads.py:build_body）：

```python
# ✅ 正确：区分"没传"和"传了 None"
if "generate_audio" in args:
    body["generate_audio"] = args["generate_audio"]
else:
    body["generate_audio"] = False  # inputSchema default

# ❌ 错误：会把"传了 None"吞成 False
generate_audio = args.get("generate_audio", False)
```

**判断方法**用 `if X in args`，**不**用 `args.get(X, default)`——后者会隐式吞 None。

**目的**：绘本有声绘本 / 社媒视频 / 用户临时改需求 → agent 都能精准控制。**禁止** MCP 工具"自作主张"覆盖 agent 的明确意图。

**反例**（绘本错误改 prompt 路径）：
- ❌ 工具看到 `generate_audio=True` → "绘本不该有 BGM" → 自动改 False
- ❌ 工具看到 `watermark="seedance_ai"` → "绘本不该有水印" → 自动改 None
- ✅ 工具**不**判断场景，**只**判断"传了没传"

**全 6 字段行为矩阵**：

| 字段 | agent 传 X | agent 传 None | agent 不传 |
|------|----------|--------------|----------|
| `generate_audio` | ✅ body = X | ✅ body = None | body = False（绘本默认）|
| `watermark` | ✅ 按字符串枚举映射 | ✅ 按字符串枚举映射 | body = False（绘本默认）|
| `duration` | ✅ body = X | ❌ KeyError（必传）| ❌ KeyError（必传）|
| `ratio` | ✅ body = X | ✅ body = None | body = "16:9" |
| `resolution` | ✅ body = X | ❌ 不写入 body（None falsy）| ❌ 不写入 body |
| `model` | ✅ body = X | ✅ body = None | body = DEFAULT_MODEL |
| `seed` / `camera_fixed` / `service_tier` | ✅ body = X | ❌ 不写入 body（None falsy）| ❌ 不写入 body |

---

## 📋 标准工作流（绘本/漫剧/海报通用）

> **L1 必跑**（任何调用前）：`verify_api_key` → 30s 0 元验证
> **L2 cost 估算**：duration × resolution × model → 报给用户
> **L3 试水**：单段 4s 480p 最短（最便宜 0.1-0.3 元/段）
> **L4 翻车自检**：4 帧 vision 抽帧
> **L5 批量**：3 并发分批，**不**一次性提交 N 段

### 单段工作流（10 步）

```text
1. verify_api_key (0 元) → 拿到 total>0 确认服务在线
2. 用户拍板：
   - prompt（核心：主体/动作/场景/风格）
   - ref_images（0-N 张本地图，工具自动上传）
   - duration（整数 4-15）
   - ratio（默认 16:9）
   - resolution（默认 480p，720p 高清）
   - model（Fast/Pro，绘本 Fast 够用）
3. generate_video → 立刻拿到 task_id
4. 缓存：检查 `list_recent_tasks` 是否已有同 prompt 任务（24h 内复用）
5. wait_and_download → 5-15 分钟 → mp4 落盘
6. **vision 4 帧抽帧自检**（必跑，详 §自检规则）
7. 自检失败 → 改 prompt 重新 generate_video（**不**调 API 多次重试）
8. 自检通过 → 发飞书 / 落 ${PROJECT_DIR}/clips/
9. 单段成功后 → 批量模式（分批 3 并发）
10. 全段完成 → 4 步对账（任务数/文件数/总成本/总时长）
```

### 批量工作流（3 并发分批）

```text
batch = [clip1, clip2, clip3, clip4, clip5, clip6, clip7, clip8]  # 8 段
batches = [batch[0:3], batch[3:6], batch[6:8]]  # 3 + 3 + 2

for chunk in batches:
    3 并发 submit → 3 个 task_id
    3 并发 wait_and_download → 3 个 mp4
    3 个都 vision 自检
    全过 → 下一批
    任一翻车 → 标记重提该 clip（不阻塞同批其他）
```

---

## 💰 Cost 控制（用户 feedback 红线）

> 用户原话："**不要总提交任务**"——每次 generate_video = 真扣费。
> skill 层强制 cost 意识。

### 定价模型（参考值 · 不写死）

| 档位 | duration | resolution | 模型 | 估算单价（人民币）|
|------|---------|------------|------|---------|
| **最便宜** | 4s | 480p | Fast | ¥0.1-0.3 |
| **标准** | 6s | 480p | Fast | ¥0.2-0.4 |
| **高清** | 8s | 720p | Pro | ¥0.5-1.0 |
| **极限** | 15s | 720p | Pro | ¥1.0-2.0 |

> 实际价格以 ${PROVIDER_PRICING_URL} 为准。skill **不**硬编码数字。

### 成本意识规则

1. **0 元 dry-run**：`verify_api_key` 是唯一 0 元工具
2. **先单后批**：1 段 4s 试水 → 翻车自检 → 再批量
3. **duration 宁短不长**：12s 不一定比 6s + 6s 拼接好（cost 接近、质量更稳）
4. **不重复提交**：拿到 task_id 后必查 `list_recent_tasks`，**不**为同 prompt 重提
5. **fail 必报**：任务失败 = 已扣费 = 必告知用户（**不**静默重试）

---

## 🖼️ 翻车自检规则（D 子 agent 必跑）

> 视频生成完毕**不**直接交付——必抽帧 vision 自检。
> 工具**不**自带自检，靠 skill 指导 LLM 调 vision 工具。

### 抽帧规范

```bash
# 1 段视频抽 4 帧：1s / 中点 / 倒数 1s / 末帧
ffmpeg -y -ss 1 -i input.mp4 -vframes 1 frame1.jpg
ffmpeg -y -ss 2 -i input.mp4 -vframes 1 frame_mid.jpg  # duration/2 取整
ffmpeg -y -sseof -1 -i input.mp4 -vframes 1 frame_last1s.jpg
ffmpeg -y -sseof -0.1 -i input.mp4 -vframes 1 frame_end.jpg
```

### 6 大翻车征兆

| 征兆 | 严重度 | 表现 | 重试策略 |
|------|--------|------|---------|
| **黑屏** | 🔴 致命 | 全帧 0 像素 / 噪点 | 必重提 |
| **角色突变** | 🔴 致命 | 中间帧角色变样（袋鼠变兔子）| 必重提 |
| **文字消失** | 🟠 高 | 首帧有"KANGAROO"，中帧消失 | 必重提 |
| **主体丢失** | 🟠 高 | 中帧袋鼠出画 | 必重提 |
| **末帧定格** | 🟡 中 | 末帧跟倒数 2 帧完全一致 | 改 prompt 加"subtle motion in the last second" |
| **比例跳变** | 🟡 中 | ffprobe duration ≠ 输入 duration（±10%）| 改 prompt 强调"fixed camera stable composition" |

**自检通过标准**：6 项**全**无。

---

## 🚨 边界条件（必问 / 必读）

> 这些是实战沉淀的"坑"，**工具 schema 不挡**。

### 文件用途必问（铁律）

| 文件类型 | ❌ 反模式 | ✅ 正解 |
|---------|----------|--------|
| `*.mp3` | 自动当 TTS 拆段 | 必问："MP3 是 TTS / BGM / 不用？" |
| `*.xlsx` | 自动当旁白 | 必读 sheet 名 + header 确认结构 |
| `0.jpg` | 当封面 | 必问："0 开头是封面 / logo / 不用？" |
| `readme.txt` | 自动当简介 | 必读内容，**不**当数据源 |

**口诀**：**"文件用途 = 问 1 次 = 用 0 次假设"**——用户没明说 = 不用。

### 路径规范

- **本地路径**：绝对路径 `/...` 或 `~/...`（`~` 解析可能不稳，必用绝对）
- **公网 URL**：`http://` / `https://` / `data:` 前缀 = 工具**不**上传直传
- **不接**：`file://` / 相对路径 `./` `../`

### duration 边界

- ✅ `4 ≤ duration ≤ 15`（API 硬限制）
- ❌ 0 / 1 / 3 / 16 / 20 → 提交报 400

### ratio 边界

- ✅ 主流：`16:9` / `9:16` / `1:1` / `4:3`
- ❌ 任意字符串 `21:9` / `3:4` → 视 provider 支持而定

---

## 🔄 错误恢复（不重提 = 不解决）

| 错误 | 原因 | 恢复 |
|------|------|------|
| `401` | API key 失效 | `verify_api_key` 重跑 → 通知用户更新 ${ENV:ARK_API_KEY} |
| `image_url resource not found` | ref_images URL 失效 | 改用本地路径（工具自动重传）|
| `duration must be integer` | 传了 `4.5` | 改 int |
| `task failed` | 模型拒绝（敏感词/超长）| 改 prompt 重提（**不**重提交同 task_id） |
| `timeout 5min` | wait_and_download 超时 | 单独 `check_task` 重查，可能 succeeded |
| `URL expired` | 24h 后再下 | `list_recent_tasks` 看 URL TTL，**不**用 `wait_and_download` |

**核心铁律**：**已发任务 = 已扣费**——失败也**不**静默重试，**必**告知用户。

---

## 🔌 通用性 · 跨环境安装（不写死路径）

> 本 skill **不**写死 `~/.cache/...` / `~/.hermes/profiles/...` / 任何具体路径。
> 所有"机器相关"配置通过环境变量 / 配置文件引用。

### 必填环境变量（部署时由用户配置）

| 变量 | 用途 | 示例值 |
|------|------|--------|
| `${ENV:ARK_API_KEY}` | provider 鉴权 | `***`（填真值，**不**进 git / 文档）|
| `${ENV:SEEDANCE_BASE_URL}` | API endpoint | `https://ark.cn-beijing.volces.com/api/v3/...` |
| `${ENV:SEEDANCE_CACHE_DIR}` | 本地任务缓存目录 | `${HOME}/.cache/seedance-mcp` |
| `${ENV:FILE_HOST}` | 本地文件上传服务 | `uguu.se` / `0x0.st` / 自建 |
| `${ENV:SEEDANCE_MODEL_DEFAULT}` | 默认模型 | （具体值以 provider 文档为准） |

### MCP server 注册（按 agent 平台）

不同 agent 平台注册方式不同——**不写死**：

- **Hermes**：`config.yaml` 加 `mcp_servers.seedance`，`command: ["python", "${path}/mcp_server.py"]`
- **Claude Desktop**：`claude_desktop_config.json` 加 `mcpServers.seedance`
- **Cursor**：`mcp.json` 加
- **其他**：参考对应平台 MCP 文档

**MCP server 源码**：`${PATH_TO_REPO}/spikes/001-mcp-uguu-server/mcp_server.py`（路径按部署）

### Skill 安装（多 profile 通吃）

```bash
# 通用安装（**不** profile 专属）
# Claude/Hermes 全局：~/.claude/skills/creative/seedance-mcp-conductor/
# 或 ~/.hermes/skills/creative/seedance-mcp-conductor/

# 本 skill 自身路径 = 任意位置，**不**写死（agent 通过 name 自动发现）
```

---

## 🧷 不写进 skill 的内容（占位符思维）

> 任何"实际值" / "实测数据" / "用户私有路径"**不**进 skill。
> skill 只写"工作流骨架 + 变量结构 + 约束条件"。

| ❌ 不写（反例占位） | ✅ 写（占位符版） |
|--------|---------|---------|
| 缓存文件绝对路径 | `${ENV:SEEDANCE_CACHE_DIR}/tasks.jsonl` |
| 具体模型 ID | `${ENV:SEEDANCE_MODEL_DEFAULT}` |
| 具体 profile 名 | "任意 agent profile，按部署" |
| 具体金额数字 | "duration × resolution × model 决定，参考 ${PROVIDER_PRICING_URL}" |
| 具体绘本/项目名 | "绘本场景"（场景化） |
| 具体 CLI 命令 | 工具不依赖任何具体 CLI，**只**走 MCP |

---

## 📊 工具元信息（给 LLM 自检用）

> 这部分**不**是工作流，只是"工具能用"的硬指标，便于 LLM 拿到工具时校验。

| 工具意图 | 是否扣费 | 必要输入 | 典型输出 |
|---------|---------|---------|---------|
| **0 元连通性验证** | ❌ 0 元 | 无 | `{valid: bool, total: int}` |
| **提交视频生成** | ✅ 真扣费 | `prompt` + `duration` | `{task_id, status: queued/running}` |
| **查询任务状态** | ❌ 0 元 | `task_id` | `{status, video_url, url_ttl_sec}` |
| **同步等待+下载** | ❌ 0 元 | `task_id` + `output_path` | `{output_path, size_bytes, md5}` |
| **本地缓存查询** | ❌ 0 元 | `limit` (可选) | `[{task_id, status, video_url, ...}]` |
| **缓存命中下载** | ❌ 0 元 | `task_id` | mp4 bytes（同上） |

> **关键提醒**：**实际工具名** = `MCP server list_tools()` 返回值（可能跟默认命名不同）。
> skill 不硬编码具体工具名，**只**匹配 `mcp_seedance_*` 前缀 + 用意图判断。

**自检问题**（LLM 拿到工具时必问）：
1. 这是不是**唯一**扣费工具？→ **是** 提交视频生成（看 inputSchema 是否有 duration/必填 prompt）
2. 不知道调哪个 = **0 元连通性验证工具** 先跑（看 inputSchema 是否只接受 `{}` 或无 required）
3. 已有 task_id = **查询状态/同步等待+下载/缓存命中下载** 三选一（不重提）
4. 24h 内复用 = **本地缓存查询** + **缓存命中下载**（不调 API）

---

## 🚧 v0.1 不写的内容（占位给后续版本）

- ❌ **5 类型路由表**（绘本领读/押韵/短句/故事/知识）—— v0.2 加，**不**进 skill 让 LLM 用 routing 表
- ❌ **evals 评估**—— v0.2 用 darwin-skill 跑 8 维评分
- ❌ **多 profile 协调示例**（huiben/drama/account-ops 各自场景）—— v0.2 补
- ❌ **失败重试策略细节**（指数退避 / 任务优先级队列）—— v0.2 加
- ❌ **TTS / BGM 配套**（绘本无 BGM 是默认，但用户要 BGM 时如何）—— v0.2 拆独立 skill
- ❌ **跨平台 MCP 注册模板**（Claude / Cursor / Cline 等）—— 留给各平台文档

---

## 🔗 配套资源

- **MCP server 源码仓库**：`seedance2.0-tool`（spikes/001-mcp-uguu-server/mcp_server.py）
- **MCP 协议参考**：参见具体 agent 平台文档
- **上游模型文档**：参考 ${PROVIDER_DOCS_URL}
- **本 skill 元信息**：见 YAML frontmatter

---

## 📌 维护记录

- **v0.1** (2026-06-11): MVP。基于 spike 001-004 实战沉淀 + Task 5 e2e 验证。
  - 6 工具场景对照 + 范式禁令 + 工作流 + cost 控制 + 自检规则 + 错误恢复
  - **不**绑死路径 / **不**写死 profile / **不**含 evals / **不**含 5 类型路由
  - 跨环境安装靠环境变量 / 配置文件，不写硬路径
