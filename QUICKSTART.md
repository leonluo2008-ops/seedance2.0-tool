# QUICKSTART.md · 3 个最快跑通示例

> 已完成 [INSTALL.md](./INSTALL.md)？OK。下面 3 个示例**任选一个**跑通就 OK。

---

## 示例 1 · CLI（5 分钟上手）

最简单：纯命令行提交 + 等待 + 下载。

```bash
# 文生视频（无参考图）
python3 seedance.py create \
  --prompt "宇航员在太空中行走，电影质感，缓慢镜头" \
  --duration 5 \
  --ratio 16:9 \
  --wait \
  --download ./astronaut.mp4

# 图生视频（角色参考）
python3 seedance.py create \
  --ref-images ./character.png \
  --prompt "Character walks through a magical forest, soft lighting" \
  --duration 6 \
  --ratio 16:9 \
  --wait \
  --download ./forest.mp4
```

### CLI 完整参数表

| 参数 | 说明 | 默认 |
|------|------|------|
| `--prompt` / `-p` | 文字提示词（必填，除非有其他内容源）| - |
| `--ref-images` | 参考图片（可多个，本地路径或 URL）| - |
| `--image` / `-i` | 首帧图片 | - |
| `--last-frame` | 尾帧图片（绘本场景**禁用**）| - |
| `--video-refs` | 参考视频（动作模仿）| - |
| `--audio` | 参考音频（绘本 BGM）| - |
| `--draft-task-id` | 草稿任务 ID（从草稿生成正式视频）| - |
| `--model` / `-m` | 模型 ID | `doubao-seedance-2-0-fast-260128` |
| `--ratio` | 画幅 | `16:9` |
| `--duration` | 时长（**整数 4-15**）| `5` |
| `--resolution` | 分辨率 | `720p` |
| `--watermark` | **绘本必传 false** | `false` |
| `--generate-audio` | 生成音频 | 默认 false（绘本无 BGM）|
| `--seed` | 随机种子（-1=随机）| -1 |
| `--service-tier` | `default` / `flex` | `default` |
| `--wait` / `-w` | 等待生成完成 | false |
| `--download` | 下载到的本地路径 | - |

### CLI 子命令

```bash
python3 seedance.py create [options]   # 提交 + 可选 wait + 可选 download
python3 seedance.py status <task_id>   # 查询状态（实时）
python3 seedance.py wait <task_id> --download ./out.mp4  # 仅等待 + 下载
```

---

## 示例 2 · MCP server（5 分钟上手）

最 LLM 友好：把 6 个工具暴露给 agent。

```bash
# 1. 启动 MCP server（stdio 模式）
python3 spikes/001-mcp-uguu-server/mcp_server.py

# 2. 在你的 agent 平台注册
# Hermes config.yaml:
#   mcp_servers:
#     seedance:
#       command: ["python3", "/path/to/seedance2.0-tool/spikes/001-mcp-uguu-server/mcp_server.py"]
#       env:
#         ARK_API_KEY: "your-key"
```

### 6 个 MCP 工具（自动注册为 `mcp_seedance_*`）

| 工具意图 | 扣费 | 何时用 |
|---------|------|--------|
| **0 元连通性验证** | ❌ | 第一次调 / key 失效怀疑 |
| **提交视频生成** | ✅ 真扣费 | 单个 4-15s 视频 |
| **查询任务状态** | ❌ | 已知 task_id，看是否 succeeded |
| **同步等待+下载** | ❌ | 单段场景（避免自己写轮询）|
| **本地缓存查询** | ❌ | 24h 内复用 task |
| **缓存命中下载** | ❌ | 不调 API 重下 |

### 配套 skill（v0.1）

`seedance-mcp-conductor` 已 symlink 到 `~/.hermes/skills/creative/seedance-mcp-conductor/`。

LLM 同时拿到 skill + 工具 = 知道什么时候用 + 怎么用 + **不该**怎么用 6 个工具。

---

## 示例 3 · Python import（5 分钟上手）

最灵活：自建 agent / 工作流脚本。

```python
import sys
sys.path.insert(0, '/path/to/seedance2.0-tool')

import seedance_uploads as U

# 1. 上传本地文件到 uguu.se（永久公网直链）
image_url = U.resolve_url('./local-character.jpg', 'image')
# → 'https://n.uguu.se/xxx.jpg'

# 2. 构造 body（含 ref_images + prompt + duration）
body = U.build_body({
    "prompt": "A cute cartoon character walks in a garden",
    "ref_images": [image_url],
    "duration": 4,
    "ratio": "16:9",
    "watermark": "none",  # 绘本无水印
    "generate_audio": False,  # 绘本无 BGM
    "resolution": "480p",
    "model": U.DEFAULT_MODEL,
})

# 3. 调 Ark API 提交
result = U.ark_request("POST", U.ARK_BASE_URL, body)
task_id = result["id"]
print(f"Task ID: {task_id}")

# 4. 写本地缓存（铁律 30 升级：已发任务 = 已扣费，本地必有记录）
U.cache_task(
    task_id=task_id, status=result.get("status", "queued"),
    duration=4, ratio="16:9", resolution="480p",
    model=U.DEFAULT_MODEL, source="my_agent",
)

# 5. 轮询 + 下载（自己写或用 wait_and_download 异步版）
import time
while True:
    r = U.ark_request("GET", f"{U.ARK_BASE_URL}/{task_id}")
    if r["status"] == "succeeded":
        video_url = r["content"]["video_url"]
        U.download_video(video_url, "./out.mp4")
        break
    elif r["status"] == "failed":
        raise RuntimeError(f"task failed: {r.get('error')}")
    time.sleep(15)
```

---

## 🎯 3 种方式对比

| 维度 | CLI | MCP | Python import |
|------|-----|-----|---------------|
| **上手难度** | ⭐ 最易 | ⭐⭐ 中 | ⭐⭐⭐ 灵活 |
| **适合场景** | 临时跑 1 段 / 调试 | LLM agent 集成 | 自建工作流 / 批量 |
| **状态查询** | 子命令 | 工具 | 自己写 |
| **缓存** | 自动 | 自动 | 自己调 `cache_task()` |
| **轮询** | `--wait` 自动 | `wait_and_download` 工具 | 自己 `time.sleep` |

## 🔥 下一个

- 想看**完整工作流**（绘本 Step0-7 调度）→ 跳 [../picturebook-video/SKILL.md](../picturebook-video/SKILL.md)
- 遇到错 → [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 看实战沉淀（94KB）→ [SKILL.md](./SKILL.md)
