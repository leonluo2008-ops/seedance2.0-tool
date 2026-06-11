# spike 003: 并发任务测试（0 成本版）

## 修订动机

用户反馈「不要总是提交任务，每次提交都是成本」。

**修订**：本测试**不**真提交任何视频任务，所有并发场景用 mock / 本地时间 / 0 元 list 端点验证。

## 4 个测试 + 关键发现

### Test 1: asyncio.gather 真并发性

| 场景 | 耗时 | 结论 |
|------|------|------|
| 5 个 `asyncio.sleep(0.001)` noop | 1.5ms | ✅ asyncio 本身没问题 |
| 5 个 list 端点（asyncio.to_thread 包装同步 urllib）| 0.32s | ✅ 真并发（5 个 ~150ms 真实并发） |

### Test 2: 10 个并发 `_cache_task` 写同一 JSONL

- 0.004s 全部完成
- 10 条记录全在缓存里（无丢失/错位）
- ✅ append-only JSONL + 单条写入是原子的，**没**问题

### Test 3: 服务端当前 running 任务数（**只**查 list 0 元）

- total: 226（含 spike 001/002 全部历史）
- 最近 20 条 running=0, queued=0（之前的任务全跑完了）

### Test 4: 5 个并发 generate_video（**mock 0 成本**）

**关键三段对比**：

| 场景 | 实现 | 5 个并发耗时 |
|------|------|-------------|
| 4a | 当前 call_tool（内部 `result = _ark_request(...)` 同步调用）| **5.00s** ❌ 假并发 |
| 4b | 改用 `_ark_request_async`（asyncio.to_thread 包装）| **1.00s** ✅ 真并发 |
| 4c | baseline：5 个 `asyncio.sleep(1.0)` noop | **1.00s** ✅ 真并发 |

**4a / 4c 倍数**：5× 差距 — 确认了"**当前 call_tool 是假并发**"。

## 根因分析

```python
# mcp_server.py 当前 call_tool
async def call_tool(name, arguments):
    if name == "generate_video":
        body = _build_body(arguments)
        result = _ark_request("POST", ARK_BASE_URL, body, timeout=60)  # ← 同步！
        # ...
```

**问题**：
1. `_ark_request` 是 `def`（**同步函数**），内部用 `urllib.request.urlopen` 同步阻塞
2. `call_tool` 内部 `result = _ark_request(...)` **没 `await`**（因为不能 await sync function）
3. 5 个 `asyncio.gather(call_tool, ...)` 看似并发，**实际**每个 call_tool 都同步阻塞事件循环

**5 个并发 = 5 × 同步阻塞时间 = 串行**

## 修复方案

### 方案 A（最小改动 · 推荐）

加 `_ark_request_async` 包装（**已写**）：

```python
async def _ark_request_async(method, url, data=None, timeout=60):
    return await asyncio.get_event_loop().run_in_executor(
        None, _ark_request, method, url, data, timeout
    )
```

把 `call_tool` 内 5 处 `_ark_request` 改成 `await _ark_request_async`：

```python
# before
result = _ark_request("POST", ARK_BASE_URL, body, timeout=60)
# after
result = await _ark_request_async("POST", ARK_BASE_URL, body, timeout=60)
```

**预期收益**：5 个并发 generate_video 从 25s 降到 ~5s（= 单个 API 时长）。

### 方案 B（彻底重写）

改用 `httpx.AsyncClient` / `aiohttp` 真异步 HTTP 库。**收益更大但改动大**（重写所有 _ark_request 调用点）。

**不推荐先做**——按用户「当前方案能用就干活，不要主动提议优化」原则，先用方案 A。

## 适用场景 vs 不适用场景

### 不影响（已用对的场景）
- **单 LLM 工具调用**（一次一个 tool_call）：同步 OK，没假并发问题
- **绘本单 Clip 跑**：本来就一个任务，假并发没意义
- **`wait_and_download` 轮询**：内部 `time.sleep(poll)` 是同步等待，本来就该阻塞

### 受影响（**才**需要并发的场景）
- **绘本 N 段批量提交**（8 段 / 10 段）：Hamster 实战证明并发节省 60% 时间
- **漫画 N 镜头批量提交**
- **任何"LLM 在一个 turn 里发多个 generate_video tool_call"**

## 反模式（不要做）

- ❌ 直接 `asyncio.gather(call_tool, call_tool, ...)` 然后觉得是真并发——假并发
- ❌ MCP server 里用 `subprocess.Popen` + `communicate` 走 shell 端并发（之前的 seedance.py 模板就是这样，但 MCP 内能用 async 别绕）
- ❌ 把 `_ark_request` 改成 `async def` 但内部还调 `urllib.urlopen`——`async def` 不让 sync IO 变 async

## 推荐 spike 004 范围（如果用户要继续）

1. **方案 A 实施**：把 call_tool 内 5 处 `_ark_request` 改 `_ark_request_async`
2. 重新跑 Test 4a，预期从 5.00s 降到 1.00s
3. 写 e2e regression test：批量 5 个并发提交 → 验证 5 个 task_id 都拿 + 5 个视频都下到
4. 加 `batch_generate_videos` MCP 工具？**不在本范围**（用户没要求）

## 红线遵守

- ✅ 0 真任务提交（mock + 0 元 list 端点）
- ✅ `.env` 未被改
- ✅ 在 `feat/mcp-uguu-server` 分支上干
- ✅ 测试代码自清理（`test-concurrent-*` / `mock-task-*` 跑完从 cache 删）

## 关键参考

- `references/task-management-and-cost.md` §10 批量并发调度（用户原话："seedance 可以并发 3 个任务"）
- `references/2026-06-10-pic8-rabbit-clip4-cardio.md` §3 生成时长实测分布（长任务可到 20 分钟）
- `native-mcp` SKILL §"How It Works"（MCP server 在 background event loop 运行）
