"""
spike 003: 并发任务测试（0 成本版 · 修订）
=============================================

修订动机：用户反馈「不要总是提交任务，每次提交都是成本」。
本测试**只**真跑 1 次（baseline 4s 480p），其余并发场景用 mock / 本地时间模拟。

测 2 件事：
1. asyncio.gather + 同步 urllib 是否真并发（5 个 noop vs 5 个真实 API）
2. 服务端 3 并发限制验证：只查 list 端点，不发新任务

修订记录：
- 2026-06-13 删除"本地缓存并发写"测试（test 2）—— cache 已废
"""
import asyncio
import sys
import json
import time
import threading
from pathlib import Path

sys.path.insert(0, '/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/spikes/001-mcp-uguu-server')
import mcp_server


# ===== Test 1: asyncio.gather + 同步 urllib 真并发性（用 0 成本验证）=====
async def noop():
    """0 成本异步空操作"""
    await asyncio.sleep(0.001)
    return 'ok'


async def test_concurrency_is_real():
    """asyncio.gather 本身是真并发（0 成本 noop 验证）"""
    print("=== Test 1: asyncio.gather 真并发性（0 成本）===")
    # 1a) 5 个 noop 应该 < 0.01s 完成
    t0 = time.time()
    results = await asyncio.gather(*[noop() for _ in range(5)])
    noop_time = time.time() - t0
    print(f"  5 个 noop: {noop_time*1000:.1f}ms（应该 < 50ms）")
    assert noop_time < 0.05, "asyncio 本身坏掉了"

    # 1b) 5 个 list 端点（0 元）— 用 asyncio.to_thread 包同步 urllib
    #     关键：urllib.request.urlopen 是同步 IO，**async def** 包装没用
    #     → 必须 asyncio.to_thread 才能真并发
    t0 = time.time()
    results = await asyncio.gather(*[
        asyncio.to_thread(
            mcp_server._ark_request_sync,
            "GET", f"{mcp_server.ARK_BASE_URL}?page_size=1", None, 15,
        )
        for _ in range(5)
    ])
    list_time = time.time() - t0
    print(f"  5 个 list 端点 (asyncio.to_thread, 0 元): {list_time:.2f}s")
    if list_time < 2.0:
        verdict = "✅ 真并发（5 个 ~150ms 并发完成）"
    else:
        verdict = "⚠️ 可能假并发 / 网络慢"
    print(f"  {verdict}")
    return list_time


# ===== Test 3: 服务端 3 并发限制（不提交，只查 list 端点）=====
async def test_service_3_concurrent_limit_via_list():
    """看 list 端点有多少 running 任务，判断是否撞 3 上限"""
    print()
    print("=== Test 3: 服务端当前 running 任务数（只查 list 0 元）===")
    result = mcp_server._ark_request("GET", f"{mcp_server.ARK_BASE_URL}?page_size=20", timeout=15)
    items = result.get('items', [])
    total = result.get('total', 0)
    running = [it for it in items if it['status'] == 'running']
    queued = [it for it in items if it['status'] == 'queued']
    print(f"  list 端点 total: {total}")
    print(f"  最近 20 条里: running={len(running)}, queued={len(queued)}")
    if running:
        for it in running[:5]:
            print(f"    - {it['id']} status={it['status']} created_at={it.get('created_at')}")
    return len(running)


# ===== Test 4: 模拟 LLM 一次发 5 个 tool_call（0 成本 mock）=====
async def test_simulated_5_concurrent_agents():
    """模拟 5 个 LLM 客户端同时调 5 个 generate_video（mock 掉 _ark_request，0 成本）"""
    print()
    print("=== Test 4: 模拟 5 个并发 agent 调 generate_video（mock 0 成本）===")
    # 保存原 _ark_request
    orig_request = mcp_server._ark_request
    call_count = [0]
    call_lock = threading.Lock()
    call_timestamps = []

    def mock_request(method, url, data=None, timeout=60):
        """mock 一个**同步**阻塞 1 秒的 _ark_request（模拟真实 urllib）"""
        with call_lock:
            call_count[0] += 1
            idx = call_count[0]
            call_timestamps.append(time.time())
        # 同步 sleep 1 秒（真实 urllib.urlopen 也是同步阻塞）
        time.sleep(1.0)
        return {
            "id": f"mock-task-{idx:03d}",
            "status": "queued",
            "created_at": int(time.time()),
        }

    # **必须**同时 mock 两个名字
    mcp_server._ark_request = mock_request
    mcp_server._ark_request_sync = mock_request
    try:
        # 关键：用 URL 跳过 uguu 上传（直接传 URL 给 _resolve_url，**不**触发 _upload_to_uguu）
        BASE = {
            'prompt': 'mock test',
            'ref_images': ['https://n.uguu.se/fake-mock.jpg'],  # 假 URL 跳过 uguu
            'duration': 4, 'ratio': '16:9', 'watermark': 'none',
            'generate_audio': False, 'resolution': '480p',
        }

        # === 4a: 当前实现（call_tool 内部直接调同步 _ark_request）→ 应该假并发 ===
        t0 = time.time()
        results = await asyncio.gather(*[mcp_server.call_tool('generate_video', BASE) for _ in range(5)])
        elapsed_naive = time.time() - t0
        print(f"  4a) 当前 call_tool（同步 _ark_request）: {elapsed_naive:.2f}s, call_count={call_count[0]}")
        if elapsed_naive < 2.0:
            print(f"      ✅ 真并发（意外？）")
        else:
            print(f"      ❌ **假并发** — 当前实现 ~ 串行（5s = 5 × 1s）")
            print(f"      修复方向：把 call_tool 内的 _ark_request 换成 _ark_request_async（asyncio.to_thread）")

        # 清理缓存
        if mcp_server.CACHE_FILE.exists():
            with open(mcp_server.CACHE_FILE) as f:
                lines = f.readlines()
            with open(mcp_server.CACHE_FILE, 'w') as f:
                for line in lines:
                    if 'mock-task-' not in line:
                        f.write(line)

        # === 4b: 改用 _ark_request_async（asyncio.to_thread 包装）→ 应该真并发 ===
        call_count[0] = 0  # 重置
        async def fake_call_tool_with_async():
            """模拟 call_tool 但用 _ark_request_async"""
            return await mcp_server._ark_request_async("POST", mcp_server.ARK_BASE_URL, BASE, 60)
        t0 = time.time()
        results = await asyncio.gather(*[fake_call_tool_with_async() for _ in range(5)])
        elapsed_async = time.time() - t0
        print(f"  4b) 直接 asyncio.gather + _ark_request_async: {elapsed_async:.2f}s, call_count={call_count[0]}")
        if elapsed_async < 2.0:
            print(f"      ✅ 真并发（修复方向验证通过）")
        else:
            print(f"      ⚠️ 仍 ~ 串行（可能 thread pool 太小）")

        # === 4c: 对比 noop（无 API 调用，纯 asyncio 延迟）===
        async def noop():
            await asyncio.sleep(1.0)
            return "ok"
        t0 = time.time()
        results = await asyncio.gather(*[noop() for _ in range(5)])
        elapsed_noop = time.time() - t0
        print(f"  4c) 5 个 1s asyncio.sleep: {elapsed_noop:.2f}s（真并发 baseline）")
        print()
        print(f"  总结：4a={elapsed_naive:.2f}s | 4b={elapsed_async:.2f}s | 4c={elapsed_noop:.2f}s")
        if elapsed_naive > 4 * elapsed_async:
            print(f"  ✅ **当前实现是假并发**（4a ~ 5s，4b/c ~ 1s）")
        else:
            print(f"  ⚠️ 4a 没那么慢（可能 ~ 4s，但比 4b/c 慢几倍）")
    finally:
        mcp_server._ark_request = orig_request
        mcp_server._ark_request_sync = orig_request


async def main():
    print("=" * 50)
    print("spike 003: 并发任务测试（0 成本版）")
    print("=" * 50)
    print()

    # Test 1
    await test_concurrency_is_real()

    # Test 2 已删（2026-06-13 · cache 已废）

    # Test 3
    await test_service_3_concurrent_limit_via_list()

    # Test 4
    await test_simulated_5_concurrent_agents()

    print()
    print("=" * 50)
    print("✅ 0 成本版 spike 003 完成（只跑了几个 list 端点查询）")


if __name__ == "__main__":
    asyncio.run(main())
