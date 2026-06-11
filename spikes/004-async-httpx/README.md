# spike 004: httpx.AsyncClient 真异步改造

> ⏰ **截至 2026-06-11 spike 004 + 006 全部完成**（含 spike 006 委托层瘦身：mcp_server.py 业务函数委托给 seedance_uploads.py）。本文档 line 引用已不准（委托后行号变化），仅作历史决策记录。

> **For Hermes:** 本 spike 是单文件重写（mcp_server.py 改 ~5 个调用点），不分 subagent 派发，自己干 + 频繁 commit。

## 目标

把 spike 001-003 的 MCP server 从「**假并发**（同步 urllib 阻塞事件循环）」升级到「**真异步**（httpx.AsyncClient + asyncio.gather）」。

预期收益：
- 5 个并发 generate_video：从 25s 降到 ~5s（= 单 API 时长）
- 批量 N 段绘本场景（Hamster 8 段）能真并发跑

## 不做（明确划线）

- ❌ 不动 seedance.py（生产代码不动，spike 内部重写）
- ❌ 不加 batch_generate_videos 工具（用户没要求，spike 005 范围）
- ❌ 不改 spike 001-003 已 e2e 跑通的功能（4 个工具 inputSchema、watermark 枚举、任务管理、TTL 自适应）
- ❌ 不跨 profile 启用 MCP（用户没要求）
- ❌ 不删 chevereto 残留（spike 005 范围）

## 现状盘点

mcp_server.py 当前 `_ark_request` 是同步函数（line 217-226）：

```python
def _ark_request(method, url, data=None, timeout=60) -> dict:
    req = urllib.request.Request(url, method=method)
    req.add_header(...)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8"))
```

调用点（5 处）：generate_video / check_task / wait_and_download (1) / verify_api_key / download_cached fallback (1) —— 实际 line 469, 497, 534, 582, 624。

## 拆解

| # | 任务 | 验证 |
|---|------|------|
| 1 | 装 httpx 依赖 | `import httpx` 成功 |
| 2 | 写 `_ark_request_async` 用 httpx.AsyncClient | 单元测试：单次调用能返回 dict |
| 3 | 重构 upload_to_uguu → 异步版本 `_upload_to_uguu_async` | uguu 上传 130KB jpg 拿到 n.uguu.se URL |
| 4 | 把 call_tool 内 5 处同步调用改异步 | Test 4 重跑：5 个并发从 5.00s 降到 ~1.00s |
| 5 | 端到端回归：4 个原工具 + 2 个新工具（list_recent_tasks / download_cached）| 至少跑 1 个 generate_video + 1 个 wait_and_download 全 e2e |

## 关键设计决策

### 决策 1：httpx vs aiohttp

| 维度 | httpx | aiohttp |
|------|-------|---------|
| API 风格 | requests 风格，**学习成本 0** | aiohttp 风格，需重学 |
| 同步兼容 | 同一个 client **可以**同步用（httpx.Client）| 不可 |
| 测试支持 | 内置 MockTransport | 需装 aiohttp.test_utils |
| 维护活跃度 | 高（encode/httpx 团队）| 高（aio-libs/team） |
| 已装 | ❌ 没装 | ❌ 没装 |

**选 httpx**——跟现有 `urllib` 习惯接近，迁移成本最低。

### 决策 2：客户端生命周期

**MCP server 是常驻进程**（native-mcp skill 确认），httpx.AsyncClient 也应该常驻：

```python
# 模块级 client（懒加载）
_http_client: Optional[httpx.AsyncClient] = None

async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={"User-Agent": UA},
        )
    return _http_client
```

**不**每个请求新建 client（性能差）。**也不**用 `async with AsyncClient()` 块（每个 call 都建/拆）。

### 决策 3：超时配置

参考现有 `urllib` 行为：
- `connect` timeout: 10s（之前没显式，urllib 默认 无限）
- `read` timeout: 视调用类型（generate_video 60s / check_task 30s / list 15s）

```python
httpx.Timeout(
    timeout=60.0,      # 默认 60s
    connect=10.0,      # DNS+TCP 握手
)
```

**per-call override**：保留 `timeout` 参数（5 个调用点各传不同值）。

### 决策 4：uguu 上传同步转异步

当前 uguu 上传用 `subprocess.run(["curl", ...])`（绕 Cloudflare）。但：
- `curl` 命令行是**子进程**，**没法** async 直接调用
- 需要 httpx + 同步上传（httpx 可以同步，但只对**单次**调用）

**方案**：uguu 上传也用 httpx.AsyncClient（multipart），**不**再走 curl 子进程：

```python
async def _upload_to_uguu_async(local_path: str, mime_type: str) -> str:
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(f"file not found: {local_path}")
    
    with open(p, "rb") as f:
        file_data = f.read()
    
    # multipart 构造（跟之前一样）
    boundary = "----hermesmcpboundary"
    body = b"".join([...])  # 之前的代码
    
    client = await _get_http_client()
    resp = await client.post(
        UGUI_UPLOAD_URL,
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "curl/8.0"},
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"uguu upload failed: {result}")
    return result["files"][0]["url"]
```

**保留同步版本 `_upload_to_uguu`**（spike 内部测试用），新加 async 版本。

### 决策 5：本地缓存并发写

`asyncio.to_thread(_cache_task, ...)` 已经在 spike 003 验证过 OK（10 个并发 0 丢失）。**保持不变**。

### 决策 6：error handling

httpx 抛 `httpx.HTTPStatusError` / `httpx.RequestError` / `httpx.TimeoutException`，跟 urllib 的 `urllib.error.HTTPError` / `urllib.error.URLError` **不一样**。需要在 `_ark_request_async` 内部**统一** try/except，**转成 RuntimeError** 抛出（call_tool 顶层有 `except Exception` 兜底）。

```python
async def _ark_request_async(method, url, data=None, timeout=60):
    client = await _get_http_client()
    try:
        resp = await client.request(
            method, url,
            json=data,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        # 跟原来 urllib 行为一致：print 到 stderr + sys.exit(1)
        # 但 call_tool 顶层是 except Exception，不会 sys.exit，所以改成 raise
        body = e.response.text[:500] if e.response else ""
        try:
            err = e.response.json().get("error", {}).get("message", body)
        except Exception:
            err = body
        raise RuntimeError(f"API Error (HTTP {e.response.status_code}): {err}")
    except httpx.TimeoutException as e:
        raise RuntimeError(f"API timeout after {timeout}s: {e}")
    except httpx.RequestError as e:
        raise RuntimeError(f"API request error: {e}")
```

## 实施步骤（5 个任务，每步 2-5 分钟）

### Task 1: 装 httpx

**Files:** mcp_server.py (import 段)

**步骤**：
1. `uv pip install --python /home/luo/.hermes/hermes-agent/venv/bin/python httpx`（挂代理）
2. 验证 `import httpx` 不报错

**验证**：
```python
import httpx
print(httpx.__version__)
# 期望: 0.x.y
```

### Task 2: 写 _ark_request_async（httpx 版）

**Files:** mcp_server.py (line 217 后)

**步骤**：
1. 加 `import httpx`
2. 写 `_get_http_client()` 懒加载
3. 写 `_ark_request_async(method, url, data, timeout)`
4. 写最小测试：调 list 端点拿 total

**验证**：
```python
import asyncio
async def t():
    r = await mcp_server._ark_request_async("GET", f"{mcp_server.ARK_BASE_URL}?page_size=1", None, 15)
    assert "items" in r
    print(f"total: {r['total']}")
asyncio.run(t())
# 期望: 打印 total（不为 0）
```

### Task 3: 重构 uguu 上传为 async

**Files:** mcp_server.py (line 84 后)

**步骤**：
1. 加 `_upload_to_uguu_async(local_path, mime_type)` 用 httpx.AsyncClient
2. 加 `_resolve_url_async(input_str, kind)` 替换调用
3. 测试：传 130KB jpg，拿到 n.uguu.se URL

**验证**：
```python
import asyncio
async def t():
    url = await mcp_server._resolve_url_async('/home/luo/.hermes/profiles/huiben/work/20260610-rabbit-input/3.jpg', 'image')
    print(f"uguu URL: {url}")
asyncio.run(t())
# 期望: https://n.uguu.se/xxx.jpg
```

### Task 4: call_tool 内 5 处同步调用改异步

**Files:** mcp_server.py (line 469, 497, 534, 582, 624)

**步骤**：
1. 改 `result = _ark_request(...)` → `result = await _ark_request_async(...)`（5 处）
2. 改 `_resolve_url(...)` → `await _resolve_url_async(...)`（在 `_build_content` 内被调 5 处）
3. 重新跑 Test 4：预期 5.00s → 1.00s

**验证**：
```python
# 跑 spike 003 的 test_concurrent.py，期望：
# 4a 当前 call_tool: 从 5.00s 降到 ~1.00s
```

### Task 5: 端到端回归

**Files:** 无新文件

**步骤**：
1. 跑一次 generate_video (4s 480p 16:9) — 验证 uguu 上传 + API 提交 + 缓存写入
2. 跑一次 wait_and_download — 验证下载 + 缓存写入
3. 跑 list_recent_tasks — 验证缓存读
4. 跑一次 verify_api_key — 验 key

**验证**：
- generate_video: task_id 立刻返回
- wait_and_download: 输出文件 685KB 左右，md5 跟服务端一致
- list_recent_tasks: count >= 1
- verify_api_key: valid=True

## Commit 策略

| Task | Commit 消息 |
|------|-------------|
| 1 | `chore(deps): add httpx 0.x.y` |
| 2 | `feat(mcp): add _ark_request_async (httpx)` |
| 3 | `feat(mcp): add _upload_to_uguu_async + _resolve_url_async` |
| 4 | `refactor(mcp): 5 处 _ark_request 改 _ark_request_async (真并发)` |
| 5 | `test(e2e): 4 工具回归跑通`（5 测试一起 commit）|

## 红线检查

- ✅ 不改 seedance.py
- ✅ 不动 .env
- ✅ 在 feat/mcp-uguu-server 分支干（不碰 main）
- ✅ 每次 commit 带 Co-Authored-By
- ✅ 任务步骤 2-5 分钟（writing-plans skill 规定）
- ✅ 不真提交多任务（0 成本 mock 测试为主）
- ✅ httpx 装在 hermes venv（不是 spike 文件夹，venv 共享）

## 风险评估

| 风险 | 概率 | 应对 |
|------|------|------|
| httpx 装失败（GFW / pip 限速）| 中 | 挂代理重试，跟 proxy-ironclad 铁律一致 |
| multipart 编码 bug（uguu）| 中 | 保留同步版本对比测试 |
| httpx vs urllib 行为差异（json 序列化、headers、redirects）| 中 | 跑 4 工具 e2e 验证 |
| 异步 context（httpx.AsyncClient 在 MCP 长进程里是否要 close）| 低 | 常驻 client 不关（OS 进程退出时自动 cleanup） |

## 不在 spike 004 范围（spike 005+ 后续）

- 重构 seedance.py 上传函数到独立模块
- 删 chevereto 残留 / uguu_ark_fallback.py
- 跨 profile 启用 MCP
- 加 batch_generate_videos 工具
- 加 aiofiles 异步文件读（uguu 上传用 bytes 已经够）
