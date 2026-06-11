"""
spike 004: 验证 httpx 改造后 call_tool 真异步
==============================================

对比 spike 003 4a（同步 urllib = 5.00s），spike 004 应该 ~1.00s。
"""
import asyncio
import sys
import time
import json

sys.path.insert(0, '/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/spikes/001-mcp-uguu-server')
import mcp_server


async def test_call_tool_real_concurrent():
    """5 个并发调 call_tool（**走真 httpx async**），预期 ~1-2s"""
    print("=== 5 个并发 call_tool（httpx 真异步）===")
    # 用 URL 跳过 uguu 上传（避免 mock 不到 _upload_to_uguu_async）
    BASE = {
        'prompt': 'spike 004 test',
        'ref_images': ['https://n.uguu.se/fake-spike004.jpg'],  # 假 URL 跳过 uguu
        'duration': 4, 'ratio': '16:9', 'watermark': 'none',
        'generate_audio': False, 'resolution': '480p',
    }
    t0 = time.time()
    results = await asyncio.gather(*[
        mcp_server.call_tool('generate_video', BASE) for _ in range(5)
    ])
    elapsed = time.time() - t0
    print(f"  5 个 call_tool: {elapsed:.2f}s")
    print(f"  (spike 003 4a 同步版: 5.00s | 4b/4c async baseline: 1.00s)")
    if elapsed < 2.5:
        print(f"  ✅ 真并发达成（{elapsed:.2f}s < 2.5s）")
    else:
        print(f"  ⚠️ 比 baseline 慢（{elapsed:.2f}s ≥ 2.5s）")

    # 看缓存里有多少 cgt 任务（说明提交了几个）
    import json
    from pathlib import Path
    cache = Path('/home/luo/.cache/seedance-mcp/tasks.jsonl')
    if cache.exists():
        with open(cache) as f:
            lines = f.readlines()
        spike004_tasks = [json.loads(l) for l in lines
                          if 'spike-004' in l or (json.loads(l).get('source') == 'generate_video' and json.loads(l).get('cached_at', 0) > time.time() - 60)]
        print(f"  缓存里最近 60s 任务数: {len(spike004_tasks)}")
        for t in spike004_tasks[:3]:
            print(f"    {t['task_id']} {t.get('status')}")

    # 清理 client + 缓存
    if mcp_server._http_client:
        await mcp_server._http_client.aclose()
    if mcp_server.CACHE_FILE.exists():
        with open(mcp_server.CACHE_FILE) as f:
            lines = f.readlines()
        with open(mcp_server.CACHE_FILE, 'w') as f:
            for line in lines:
                if 'mock-task-' not in line and 'spike-004' not in line:
                    f.write(line)


async def test_resolve_all_inputs_concurrent():
    """5 个并发调 _resolve_all_inputs_async，传相同本地路径"""
    print()
    print("=== _resolve_all_inputs_async 真并发（3 个相同路径）===")
    args = {
        'ref_images': [
            '/home/luo/.hermes/profiles/huiben/work/20260610-rabbit-input/3.jpg',
            '/home/luo/.hermes/profiles/huiben/work/20260610-rabbit-input/3.jpg',
            '/home/luo/.hermes/profiles/huiben/work/20260610-rabbit-input/3.jpg',
        ],
    }
    t0 = time.time()
    result = await mcp_server._resolve_all_inputs_async(args)
    elapsed = time.time() - t0
    print(f"  3 个相同路径（dedup 后 1 个真上传）: {elapsed:.2f}s")
    print(f"  resolved_urls: {result}")
    if elapsed < 5.0:
        print(f"  ✅ 合理（1 个真上传 ~2s + 网络延迟）")


async def main():
    print("=" * 50)
    print("spike 004: 验证 httpx 改造后真并发")
    print("=" * 50)
    await test_call_tool_real_concurrent()
    await test_resolve_all_inputs_concurrent()
    print()
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
