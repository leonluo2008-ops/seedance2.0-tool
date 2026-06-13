# TROUBLESHOOTING.md · 4 常见错 + 修复

> 80% 的问题能在这 4 个里找到答案。

---

## 🔴 错 1 · `SSL: UNEXPECTED_EOF_WHILE_READING`

**症状**：

```
urllib.error.URLError: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1016)>
```

**根因**：**走公司代理访问 uguu.se 会 SSL EOF**。Python urllib 在 uguu.se 这个 endpoint 跟公司代理的 SSL 握手不兼容。

**修复**：

```bash
# 1. 在 shell 加 no_proxy 排除 uguu.se
export no_proxy="uguu.se,n.uguu.se,o.uguu.se"
export NO_PROXY="uguu.se,n.uguu.se,o.uguu.se"

# 2. 保留 ark 走代理（公司代理对 ark.cn-beijing.volces.com 友好）
export http_proxy="http://127.0.0.1:7897"
export https_proxy="http://127.0.0.1:7897"
```

或者直接 unset 代理（如果本机能直连 uguu.se）：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
```

**代码侧**：已内置自动判断——`seedance_uploads._build_opener(url)` 按 host 决定是否走代理，**uguu.se 永远走直连**。

**验证**：

```bash
unset http_proxy https_proxy
python3 -c "
import sys
sys.path.insert(0, '/path/to/seedance2.0-tool')
import seedance_uploads as U
print(U.resolve_url('/path/to/any.jpg', 'image'))
"
# 期望：https://n.uguu.se/xxx.jpg（无 SSL EOF）
```

---

## 🟠 错 2 · `API key format is incorrect` / `ARK_API_KEY env var not set`

**症状**：

```
RuntimeError: ARK_API_KEY env var not set
# 或
API Error (HTTP 401): The API key format is incorrect.
```

**根因 A**：`.env` 文件没填 / 路径不对。

**修复 A**：

```bash
# 1. 确认 .env 存在 + 路径对
ls -la /path/to/seedance2.0-tool/.env

# 2. 确认 key 真值（非占位）
cat .env
# 应该看到：ARK_API_KEY=314953...f591
# 不是：ARK_API_KEY=your-volcengine-ark-api-key
# 不是：ARK_API_KEY=314953...n  ← 这是 hermes 自动 redact 痕迹，要重新填

# 3. 验证 .env 加载顺序
python3 -c "
import sys
sys.path.insert(0, '/path/to/seedance2.0-tool/spikes/001-mcp-uguu-server')
from dotenv import load_dotenv
load_dotenv('/path/to/seedance2.0-tool/.env')
import os
print('ARK_API_KEY prefix:', os.environ.get('ARK_API_KEY', '')[:10] + '...')
"
```

**根因 B**：hermes 在某些 agent 平台自动 redact `.env` 写入（**保护机制**——避免 agent 生成时泄露真值）。

**修复 B**：直接在服务器上 `nano .env` 编辑，**粘贴真值**，**不要**通过 agent 写。

```bash
nano /path/to/seedance2.0-tool/.env
# 把 ARK_API_KEY=314953...n 改成 ARK_API_KEY=<完整真值>
# Ctrl+O 保存，Ctrl+X 退出
```

**根因 C**：环境变量没传给子进程（hermes config 没配 env 段）。

**修复 C**：

```yaml
# hermes config.yaml
mcp_servers:
  seedance:
    command: ["python3", "/path/to/seedance2.0-tool/spikes/001-mcp-uguu-server/mcp_server.py"]
    env:
      ARK_API_KEY: "your-real-key"  # 直接在这里写
```

---

## 🟡 错 3 · `task not found` / `URL expired`

**症状**：

```
API Error (HTTP 404): task not found
# 或
# 等 24h 后下不到 video_url
```

**根因 A**：task_id 输错了 / 任务被删了。

**修复 A**：用本地缓存查：

```python
import seedance_uploads as U
cache = U.read_cache(limit=20)
for r in cache:
    print(r['task_id'], r['status'], r.get('video_url', 'no-url')[:80])
```

**根因 B**：video_url 过期（X-Tos-Expires=86400s，24h 后失效）。

**修复 B**：

```python
# 2026-06-13 本地缓存已删：直接调官方 ark 端点拿新 URL
import asyncio
import mcp_server

async def fix(task_id: str):
    # 调官方 API（直连 ark.cn-beijing.volces.com，不依赖本地 cache）
    r = await mcp_server._ark_request_async('GET', f"{mcp_server.ARK_BASE_URL}/{task_id}")
    if r['status'] == 'succeeded':
        new_url = r['content']['video_url']
        print(f"new URL: {new_url[:80]}")
        return new_url
    else:
        print(f"task 当前状态: {r['status']}")
        return None

asyncio.run(fix('cgt-...'))
```

---

## 🟠 错 4 · 任务 failed / `Duration mismatch`

**症状**：

```
Task failed: {"code": "InvalidParameter", "message": "..."}
# 或（更隐蔽）
# 任务 succeeded 但 duration 跟用户传的不一致
```

**根因 A**：参数 schema 不对（4 个最常见）：

| 错 | 对 | API 报错 |
|----|----|----------|
| `"duration": 4.5` | `4` | `duration must be integer` |
| `"duration": 16` | `15` | `duration must be 4-15` |
| `"watermark": "off"` | `"none"` | `watermark must be one of none/platform/seedance_ai` |
| `"ratio": "16:10"` | `"16:9"` | `ratio not supported` |

**修复 A**：

```python
# 严格用 seedance_uploads 的常量
import seedance_uploads as U
U.DEFAULT_MODEL       # 'doubao-seedance-2-0-fast-260128'
U.ARK_BASE_URL        # 完整 endpoint
# 持续时间：int 4-15
# 画幅：16:9 / 9:16 / 1:1 / 4:3 / 3:4 / 21:9 / adaptive
# 水印：'none' / 'platform' / 'seedance_ai'
```

**根因 B**：**所有参数**塞进 `body["parameters"]` 嵌套（OpenAI 兼容风格）—— **Seedance 2.0 是顶层扁平 schema**。

**修复 B**：

```python
# ❌ 错
body = {
    "model": "...",
    "content": [...],
    "parameters": {  # ← 错！Seedance 2.0 不接
        "duration": 4, "ratio": "16:9", "watermark": False,
    }
}

# ✅ 对
body = {
    "model": "...",
    "content": [...],
    "duration": 4,        # 顶层
    "ratio": "16:9",      # 顶层
    "watermark": False,   # 顶层
    "generate_audio": False,  # 顶层
    "resolution": "720p",  # 顶层
    "seed": -1,           # 顶层（可选）
    "camera_fixed": False,  # 顶层（可选）
}
```

**根因 C**：duration 跟用户传的不一致（**最隐蔽的坑**）。

**修复 C**：跑完必 ffprobe 校验：

```bash
ffprobe -v error -show_entries stream=duration -of csv=p=0 /path/to/output.mp4
# 期望：跟你传的 --duration 一致（误差 ±0.1s）
```

如果 ffprobe 显示不是 4.x（如 5.0）→ 说明 seedance API 用了模型默认 → 检查 body 里 duration 是不是顶层（不嵌套）。

---

## 🆘 错 5 · `ModuleNotFoundError: No module named 'seedance_uploads'`

**症状**：

```
ModuleNotFoundError: No module named 'seedance_uploads'
```

**根因**：跑 `mcp_server.py` 时 sys.path 没包含 seedance2.0-tool 根目录。

**修复**：

```bash
# 方案 A：cd 到仓库根再跑
cd /path/to/seedance2.0-tool
python3 spikes/001-mcp-uguu-server/mcp_server.py

# 方案 B：PYTHONPATH 显式
PYTHONPATH=/path/to/seedance2.0-tool python3 spikes/001-mcp-uguu-server/mcp_server.py

# 方案 C：在 hermes config 加 cwd
# mcp_servers.seedance.env.PYTHONPATH = /path/to/seedance2.0-tool
```

---

## 🔍 自检脚本

```bash
cd /path/to/seedance2.0-tool
python3 -c "
import sys
sys.path.insert(0, 'spikes/001-mcp-uguu-server')
from dotenv import load_dotenv
load_dotenv('.env')

import mcp_server
import seedance_uploads as U
import asyncio

async def full_check():
    print('=== 自检 1: 环境 ===')
    import os
    key = os.environ.get('ARK_API_KEY', '')
    print(f'  ARK_API_KEY prefix: {key[:10]}... (len={len(key)})')
    
    print('=== 自检 2: 业务函数 ===')
    print(f'  DEFAULT_MODEL: {U.DEFAULT_MODEL}')
    print(f'  ARK_BASE_URL: {U.ARK_BASE_URL}')
    print(f'  CACHE_DIR: {U.CACHE_DIR}')
    
    print('=== 自检 3: API 连通性 ===')
    r = await mcp_server._ark_request_async('GET', f'{mcp_server.ARK_BASE_URL}?page_size=1', None, 30)
    print(f'  total tasks: {r[\"total\"]}')
    
    print('=== 自检 4: uguu 上传 ===')
    import os
    if os.path.exists('/tmp/test.jpg'):
        url = U.resolve_url('/tmp/test.jpg', 'image')
        print(f'  uploaded: {url[:60]}...')
    else:
        print('  skip (no /tmp/test.jpg)')
    
    print('=== 自检 5: 缓存 ===')
    cache = U.read_cache(5)
    print(f'  cache count: {len(cache)}')

asyncio.run(full_check())
"
```

**期望输出**：

```
=== 自检 1: 环境 ===
  ARK_API_KEY prefix: 3149537... (len=40+)
=== 自检 2: 业务函数 ===
  DEFAULT_MODEL: doubao-seedance-2-0-fast-260128
  ...
✅ 全过
```
