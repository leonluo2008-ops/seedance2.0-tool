# Seedance 2.0 Tool · 错误模式积累

> 实战踩过的坑，按**问题 → 根因 → 修复**记录。新人遇到类似错先来这查。

## 已修复

| 日期 | 错误类型 | 根因 | 修复 |
|------|---------|------|------|
| 2026-06-04 | 全部时长都是 5s | `duration/ratio/resolution` 塞 `body["parameters"]` 嵌套 | 改**顶层扁平 schema**（参考 `audio-bugs-and-hosting.md` Bug 4）|
| 2026-06-04 | chevereto HTTP URL → 火山内网 400 | chevereto 返回 http，DNS 走不通 | 改 HTTPS（已**整体废** chevereto，转 uguu.se）|
| 2026-06-04 | audio_url 缺 `role: reference_audio` | 早期 body 构造没设 role | content 数组里 audio 加 `"role": "reference_audio"` |
| 2026-06-05 | `image_url resource not found` | ref_images URL 失效 / chevereto 上传失败 | 转 uguu.se（spike 001）|
| 2026-06-07 | chevereto 整段 timeout | 公司网络对 chevereto.aistar.work 不友好 | 转 uguu.se（Pic4 实战触发）|
| 2026-06-10 | video_url 24h 过期 → 下不回来 | 不知道 X-Tos-Expires=86400 | 缓存里读 TTL，过期 fallback 到 check_task 重拿 |
| 2026-06-11 | MCP server 假并发 | `_ark_request` 同步阻塞事件循环 | 改 `httpx.AsyncClient` 真异步（spike 004）|
| 2026-06-11 | `SSL: UNEXPECTED_EOF_WHILE_READING` | 走公司代理访问 uguu.se | `seedance_uploads._build_opener` 按 host 决定是否走代理（uguu.se 永远直连）|
| 2026-06-11 | `--image + --last-frame` 首尾帧范式绘本翻车 | 锁住首尾两帧 = 绘本场景必翻车 | 仅用 `--ref-images` 多图参考 |
| 2026-06-11 | `generate_audio` 默认 True | Seedance 2.0 模型默认生成音频（含莫名说话声）| 绘本/海报场景**必传** `false` |
| 2026-06-11 | MCP inputSchema `?limit=1` 错 | 抄了 OpenAI 兼容风格 | 火山引擎 list 端点参数是 `?page_size=1` |

## 经验教训

### 网络

- **公司代理对 uguu.se 不友好**（SSL EOF）—— **永远**让 uguu.se 走直连
- **公司代理对 ark.cn-beijing.volces.com 友好**——走代理更快更稳
- 代码内置 `seedance_uploads._build_opener(url)` 按 host 路由，**不要**自己处理
- `Python 3.11.15` 的 `HTTPSHandler(context=...)` 跟 uguu.se 握手有 SSL EOF bug
  - **唯一稳的路径**：`urllib.request.urlopen(req, context=ssl.create_default_context())`
  - 详见 [TROUBLESHOOTING.md §SSL EOF](./TROUBLESHOOTING.md)

### Seedance API 参数

- **duration 必为整数 4-15**——`4.5` / `"6s"` 都报 400
- **watermark 三选一**：`"none"` / `"platform"` / `"seedance_ai"`——绘本 = `"none"`
- **所有可选参数走顶层**（不嵌套 `parameters`）—— `seed/camera_fixed/draft/return_last_frame/service_tier`
- **list 端点**参数是 `page_size`（**不**是 `limit`）——抄 OpenAI 风格会 400
- **官方文档跟实战偶尔有偏差**——以 `audio-bugs-and-hosting.md` 沉淀的 Bug 4 / 5 为准

### 成本 & 范式

- **每次 generate_video = 真扣费**——提交前必 `verify_api_key` + 单段试水
- **批量 3 并发上限**（绘本/漫剧场景）——单 agent 同时持有 ≤3 running 任务
- **首尾帧范式 = 禁用**（绘本场景）——`--image` + `--last-frame` 必翻车
- **`generate_audio: false` 是绘本场景的默认**——`True` 会让 AI 生成莫名说话声
- **范式号（v7 / v15 / picN）= 已废**——v1.0.0 起只按场景路由（领读/押韵/短句/故事/知识）
- **同 prompt 不重提**——`seedance.py status <task_id>` / `seedance.py list --page-size N` 查官方 API，**已发任务 = 已扣费**

### 缓存（2026-06-13 起 = 已删）

- **本地 cache 已删**——不存在 `~/.cache/seedance-mcp/tasks.jsonl`，`SEEDANCE_CACHE_DIR` 环境变量无效
- **历史背景**：原 cache 是为了跨 session 查 task_id，但官方 ark list 端点（`GET /tasks?page_size=N`）同样能查，且不会滞后
- **唯一权威信源**：官方 ark API（`GET /tasks/{id}` + `GET /tasks?page_size=N`）
- **唯一缓存机制**：video_url 24h 有效（平台控制），过期调 `status` 拿新 URL

### 翻车自检（必跑）

视频生成完毕**不**直接交付——必抽 4 帧 vision 自检：

| 征兆 | 严重度 | 重试策略 |
|------|--------|---------|
| 黑屏 | 🔴 致命 | 必重提 |
| 角色突变 | 🔴 致命 | 必重提 |
| 文字消失 | 🟠 高 | 必重提 |
| 主体丢失 | 🟠 高 | 必重提 |
| 末帧定格 | 🟡 中 | 改 prompt 加 "subtle motion" |
| 比例跳变 | 🟡 中 | 改 prompt 强调 "fixed camera" |
