# INSTALL.md · 5 步安装

> **前提**：你已经有 hermes-agent 仓库 + Python 3.11+ + venv（`${PATH_TO_HERMES_VENV}` 是你的 venv 路径，比如 `~/.hermes/hermes-agent/venv`）。

## Step 1 · 克隆仓库

```bash
git clone https://github.com/leonluo2008-ops/seedance2.0-tool.git
cd seedance2.0-tool
```

仓库是**独立**的（不嵌套在 hermes-agent 或 picturebook-video 里）—— 5 个 spike 各占一个目录，便于独立 review。

## Step 2 · 装 Python 依赖

```bash
# 装到 hermes venv（不新建 venv，跟其他 skill 共享）
uv pip install --python ${PATH_TO_HERMES_VENV}/bin/python httpx python-dotenv mcp
```

| 包 | 必填 | 用途 |
|----|------|------|
| `httpx` | ✅ | MCP server 异步 HTTP 客户端 |
| `python-dotenv` | ✅ | 读 `.env` 文件 |
| `mcp` | ✅ | MCP server stdio 协议 |
| `argparse` | 内置 | seedance.py CLI 解析 |

## Step 3 · 配环境变量

```bash
cp .env.example .env
nano .env  # 或 vim / VSCode
```

**`.env` 文件**（**只**需要 1 个 key）：

```bash
# 必填：Volcengine Ark API Key
# 获取地址：https://console.volcengine.com/ark
ARK_API_KEY=你的真实_key

# ⚠️ 2026-06-13 起本地缓存已删，SEEDANCE_CACHE_DIR 环境变量不再需要
```

**⚠️ 不要 commit `.env` 到 git**（仓库 `.gitignore` 已配）。

## Step 4 · 验证（0 元 list 端点）

```bash
cd /path/to/seedance2.0-tool
python3 -c "
import sys
sys.path.insert(0, 'spikes/001-mcp-uguu-server')
from dotenv import load_dotenv
load_dotenv('.env')

import mcp_server
import asyncio

async def verify():
    r = await mcp_server._ark_request_async('GET', f'{mcp_server.ARK_BASE_URL}?page_size=1', None, 30)
    print(f'✅ API key OK, total tasks: {r[\"total\"]}')

asyncio.run(verify())
"
```

**期望输出**：`✅ API key OK, total tasks: <数字>`

**如果报错**：
- 🔴 `ARK_API_KEY env var not set` → Step 3 没配对
- 🔴 `401 The API key format is incorrect` → .env 里的 key 是占位符（hermes redact 痕迹），手动填真值
- 🔴 `SSL: UNEXPECTED_EOF_WHILE_READING` → 走代理访问 uguu.se，看 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

## Step 5 · 跑一个测试视频

```bash
python3 seedance.py create \
  --prompt "A cat walks in a garden, soft watercolor style" \
  --duration 4 \
  --wait \
  --download /tmp/test.mp4
```

**期望**：
1. 打印 `Task ID: cgt-...`
2. 等待 30-60s
3. 下载到 `/tmp/test.mp4`
4. `ffprobe /tmp/test.mp4` 看到 `Duration: 00:00:04.04`

**如果报错**：
- 🟠 `task failed` → 看 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) §任务失败
- 🟡 `URL expired` → 24h 后重新调 `seedance.py status <task_id>` 拿新 URL

## 🎉 完成！

**3 种使用方式**（详见 [README.md](./README.md) §3 种使用方式）：

```bash
# CLI
python3 seedance.py create --prompt "..." --duration 4

# MCP server
python3 spikes/001-mcp-uguu-server/mcp_server.py

# Python import
import seedance_uploads as U
url = U.resolve_url('./local.jpg', 'image')
```

## 📦 可选 · 安装 conductor skill

`seedance-mcp-conductor` skill（v0.1）已 symlink 到：

```
~/.hermes/skills/creative/seedance-mcp-conductor
```

**真源**：`spikes/005-mcp-conductor-skill/SKILL.md`（在 seedance2.0-tool 仓库内）

**symlink 检查**：

```bash
ls -la ~/.hermes/skills/creative/seedance-mcp-conductor
# 应该指向：.../seedance2.0-tool/spikes/005-mcp-conductor-skill
```

如果 symlink 丢了：

```bash
ln -s /path/to/seedance2.0-tool/spikes/005-mcp-conductor-skill \
      ~/.hermes/skills/creative/seedance-mcp-conductor
```

**验证 skill 可加载**：

```bash
# 用 hermes 的 skill_view 工具（如果你有）或者：
cat ~/.hermes/skills/creative/seedance-mcp-conductor/SKILL.md | head -20
```
