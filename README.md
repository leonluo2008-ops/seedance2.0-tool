# Seedance 2.0 Tool · 视频生成工具集

> **仓库口径**：CLI + MCP server + 共享业务函数库 + 实战沉淀 = **一个工具集**

调用 Volcengine Seedance 2.0 API 生成视频，**统一图床 uguu.se**。提供 3 种入口：

| 入口 | 用途 | 适合 |
|------|------|------|
| **CLI** (`seedance.py`) | 命令行直接跑 | 本地开发、CI/CD 脚本 |
| **MCP server** (`mcp_server.py`) | 6 个 `mcp_seedance_*` 工具，LLM 调用 | Hermes / Claude Desktop / Cursor |
| **Shared lib** (`seedance_uploads.py`) | Python import | 自建 agent / 工作流脚本 |

**3 个入口**共享**单真源**业务函数（上传 / Ark API / 任务缓存 / body 构造）——改一处生效所有入口。

---

## 🎬 核心能力

- ✅ 调 Seedance 2.0 模型生成视频（4-15s · 480p/720p/1080p）
- ✅ 图片参考（角色 / 风格）
- ✅ 视频参考（动作模仿）
- ✅ 音频参考（绘本 BGM）
- ✅ 文生视频 / 图生视频
- ✅ 任务管理（缓存 TTL=86400s 自动同步）
- ✅ 并发 3 上限（绘本/漫剧批量友好）

---

## 📂 仓库结构

```
seedance2.0-tool/
├── README.md                ← 你在这里
├── INSTALL.md               ← 5 步安装
├── QUICKSTART.md            ← 3 个最快跑通示例
├── TROUBLESHOOTING.md       ← 4 常见错
├── .env.example             ← 环境变量模板
├── SKILL.md                 ← skill description（94KB 实战沉淀）
├── error-patterns.md        ← 错误模式积累
│
├── seedance.py              ← CLI 入口（python3 seedance.py）
├── seedance_uploads.py      ← 共享业务函数库（单真源）
│
├── spikes/                  ← 5 个改造历程
│   ├── 001-mcp-uguu-server/     ← MCP server 骨架
│   ├── 002-lightweight-hints/   ← 任务管理 + 平台 TTL 自适应
│   ├── 003-concurrency/         ← 并发测试（0 成本）
│   ├── 004-async-httpx/         ← httpx 真异步改造
│   └── 005-mcp-conductor-skill/ ← 配套 skill（指导 LLM 用法）
│
└── references/              ← 实战沉淀（分镜 / 范式 / Bug 4 / 任务管理 / 上传）
```

---

## 🔧 5 步快速安装

详见 [INSTALL.md](./INSTALL.md)：

```bash
# 1. 克隆
git clone https://github.com/leonluo2008-ops/seedance2.0-tool.git
cd seedance2.0-tool

# 2. 装依赖（hermes-agent 仓库 venv）
uv pip install --python ${PATH_TO_HERMES_VENV}/bin/python httpx python-dotenv mcp

# 3. 配环境变量
cp .env.example .env
nano .env  # 填 ARK_API_KEY

# 4. 验证（0 元 list 端点）
python3 -c "
import sys; sys.path.insert(0, 'spikes/001-mcp-uguu-server')
from dotenv import load_dotenv; load_dotenv('.env')
import mcp_server; import asyncio
r = asyncio.run(mcp_server._ark_request_async('GET', f'{mcp_server.ARK_BASE_URL}?page_size=1', None, 30))
print(f'API key OK, total tasks: {r[\"total\"]}')"

# 5. 跑一个 4s 视频
python3 seedance.py create --prompt "A cat walks in a garden" --duration 4 --wait --download /tmp/test.mp4
```

---

## 🚀 3 种使用方式

### 方式 1：CLI（最快上手）

```bash
# 提交 + 等待 + 下载（一行搞定）
python3 seedance.py create \
  --prompt "宇航员在太空中行走，电影质感" \
  --ref-images ./character.png \
  --duration 5 --ratio 16:9 \
  --wait --download ./output.mp4

# 查询任务
python3 seedance.py status cgt-20260611163730-k9n65

# 仅等待已提交任务
python3 seedance.py wait cgt-20260611163730-k9n65 --download ./clip.mp4
```

**完整参数表** → [QUICKSTART.md §CLI 完整参数](./QUICKSTART.md)

### 方式 2：MCP server（给 LLM 调）

MCP 暴露 6 个工具（前缀 `mcp_seedance_`）：

| 工具意图 | 扣费 | 何时用 |
|---------|------|--------|
| **0 元连通性验证** | ❌ | 第一次调 / key 失效怀疑 |
| **提交视频生成** | ✅ | 单个 4-15s 视频 |
| **查询任务状态** | ❌ | 已知 task_id |
| **同步等待+下载** | ❌ | 单段场景（避免自己写轮询）|
| **本地缓存查询** | ❌ | 24h 内复用 task |
| **缓存命中下载** | ❌ | 不调 API 重下 |

**MCP server 启动**：
```bash
# 直接跑（调试）
python3 spikes/001-mcp-uguu-server/mcp_server.py

# 注册到 hermes config.yaml
# 详见 TROUBLESHOOTING.md §MCP 注册
```

**配套 skill**：`seedance-mcp-conductor`（已 symlink 到 `~/.hermes/skills/creative/seedance-mcp-conductor/`）—— 告诉 LLM 什么时候用、怎么用、**不该**怎么用 6 个工具。

### 方式 3：Python import（自建 agent）

```python
import sys
sys.path.insert(0, '/path/to/seedance2.0-tool')
import seedance_uploads as U

# 同步上传
url = U.resolve_url('./local.jpg', 'image')
# → https://n.uguu.se/xxx.jpg

# 同步调 API
result = U.ark_request('POST', U.ARK_BASE_URL, {
    'model': U.DEFAULT_MODEL,
    'content': [{'type': 'text', 'text': '...'}, {'type': 'image_url', 'image_url': {'url': url}}],
    'duration': 4, 'ratio': '16:9',
})
task_id = result['id']

# ⚠️ 2026-06-13 起本地缓存已删：无需 U.cache_task 调用
# 需要查历史任务 → `seedance.py list --page-size N` 走官方 list 端点
```

---

## 🌐 代理 & 网络注意事项

**uguu.se 不走代理**（走代理会 SSL EOF）。代码内置 `seedance_uploads._build_opener` 自动按 host 决定。

```bash
# 推荐：把代理设到 ark 域名（让 uguu.se 走直连）
export no_proxy="uguu.se,n.uguu.se,o.uguu.se"
export http_proxy="http://127.0.0.1:7897"
export https_proxy="http://127.0.0.1:7897"
```

**常见 3 个网络错**（详见 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)）：
- 🔴 `SSL: UNEXPECTED_EOF_WHILE_READING` → 走代理访问 uguu.se
- 🟠 `API key format is incorrect` → .env 被 hermes redact，重新填真值
- 🟡 `task not found` → 24h 后 URL 过期，调官方 `GET /api/v3/contents/generations/tasks/{id}` 拿新 URL

---

## 🛡️ 范式红线（绘本/漫剧场景必看）

| ❌ 错 | ✅ 对 | 原因 |
|-------|-------|------|
| 一次提交 ≥3 段 | 3 段分批 | 单 agent 持有 ≤3 running |
| duration 7.5 / "6s" | 整数 4-15 | API 硬限制 |
| `watermark: true` | `none` / `False` | 绘本不要 AI 水印 |
| `--image` + `--last-frame` | `--ref-images1.jpg 2.jpg` | 首尾帧范式绘本翻车 |
| 跳过 vision 自检 | 4 帧抽帧 + 6 翻车征兆 | 翻车 = 文字消失/角色突变 |
| 同 prompt 重提 | `seedance.py list` + `seedance.py status <id>` 查历史 | 已扣费 = 已扣费 |

详见 [SKILL.md §范式禁令](./SKILL.md)。

---

## 📜 License

Apache-2.0

## 🤝 贡献

每个 spike 目录是**独立 PR**——便于 review / 回滚。

## 🔗 相关仓库

- `picturebook-video`：绘本视频工作流（Step0-7 调度）
- `hermes-agent`：本地 agent 平台
