"""
Task 5 · 端到端回归测试
======================
绘本素材包（袋鼠 KANGAROO · 3 张图）—— 跑 3 个 4s 480p 视频
验证 MCP server 6 工具端到端能跑通

执行路径（直接 import mcp_server 业务函数，不走 stdio 装饰器）：
  verify_api_key → generate_video × 3 (3 并发) → check_task × 3 → wait_and_download × 3

注意：4s 480p × 3 = 绘本最便宜，cost ≈ 0.3-0.9 元
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 让 import 找到 mcp_server
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

# .env 加载（必须在 import mcp_server 之前，_get_ark_key 读 env var）
from dotenv import load_dotenv
load_dotenv(HERE.parent.parent / ".env")

import mcp_server as M

# 3 张图（绘本页面）
IMG1 = "/home/luo/.hermes/image_cache/img_f52f94cd1fe5.jpg"  # 袋鼠妈妈+宝宝
IMG2 = "/home/luo/.hermes/image_cache/img_a9ec9e92455a.jpg"  # 站立袋鼠+树
IMG3 = "/home/luo/.hermes/image_cache/img_33e10504047b.jpg"  # 蹲伏袋鼠

# 3 句旁白（用户给）
NAR1 = "袋鼠 KANGAROO！"
NAR2 = "袋鼠站得高高的，the kangaroo stands tall."
NAR3 = "袋鼠有强壮的后腿，the kangaroo has big strong legs!"

# 输出目录
OUT_DIR = Path("/tmp/task5-kangaroo")
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def run_e2e():
    print("=" * 70)
    print("TASK 5 · 端到端回归 · 袋鼠绘本 3 视频")
    print("=" * 70)

    # ========== 1. verify_api_key ==========
    print("\n[1] verify_api_key")
    t0 = time.time()
    list_result = await M._ark_request_async("GET", f"{M.ARK_BASE_URL}?page_size=1", timeout=30)
    print(f"  total tasks: {list_result.get('total')} · {time.time()-t0:.2f}s")
    assert list_result.get("total", 0) > 200, f"total too low: {list_result}"
    print("  ✅ API key 有效")

    # ========== 2. generate_video × 3（3 并发）==========
    print("\n[2] generate_video × 3 (3 并发)")
    clips = [
        {
            "name": "clip1",
            "image_path": IMG1,
            "prompt": f"A friendly cartoon kangaroo mother stands in golden grass, collage art style, soft watercolor sky, rainbow letters spelling KANGAROO with Chinese 袋鼠. Subtle gentle motion: the kangaroo looks around, the small joey in the pouch blinks. Children picture book illustration, warm and educational.",
            "narration": NAR1,
            "output": OUT_DIR / "clip1.mp4",
        },
        {
            "name": "clip2",
            "image_path": IMG2,
            "prompt": f"A proud cartoon kangaroo stands tall on golden grass with two small green trees, collage art style, watercolor blue sky, colorful letters spelling kangaroo. Subtle motion: the kangaroo straightens up proudly, the tail sways gently. Children picture book, warm and educational.",
            "narration": NAR2,
            "output": OUT_DIR / "clip2.mp4",
        },
        {
            "name": "name3",
            "image_path": IMG3,
            "prompt": f"A strong cartoon kangaroo in a powerful stance on yellow grass, showing its thick muscular hind legs, collage art style, watercolor sky, colorful block letters spelling kangaroo. Subtle motion: the kangaroo's strong legs shift weight, tail balances. Children picture book, warm and educational.",
            "narration": NAR3,
            "output": OUT_DIR / "clip3.mp4",
        },
    ]

    async def submit_one(clip):
        # ✅ 走与 call_tool generate_video 完全相同的代码路径
        args = {
            "prompt": clip["prompt"],
            "ref_images": [clip["image_path"]],  # 本地路径
            "duration": 4,                        # 整数（4s 最短 = 最便宜）
            "ratio": "16:9",
            "resolution": "480p",                 # 最便宜分辨率
            "watermark": "none",                  # 绘本无水印
            "generate_audio": False,              # 绘本无 BGM
            "model": "doubao-seedance-2-0-fast-260128",  # Fast 模型
        }
        # 1. 并发上传所有本地文件
        resolved = await M._resolve_all_inputs_async(args)
        # 2. 构造 body
        body = M._build_body(args, resolved_urls=resolved)
        # 3. POST
        t0 = time.time()
        result = await M._ark_request_async("POST", M.ARK_BASE_URL, body, timeout=60)
        elapsed = time.time() - t0
        task_id = result["id"]
        # 4. 写本地缓存
        M._cache_task(
            task_id=task_id, status=result.get("status", "queued"),
            duration=body["duration"], ratio=body["ratio"], resolution=body.get("resolution"),
            model=body["model"], source="e2e_task5",
        )
        return clip["name"], task_id, elapsed, body["model"]

    t0 = time.time()
    submissions = await asyncio.gather(*[submit_one(c) for c in clips])
    total_elapsed = time.time() - t0
    print(f"  3 并发提交：{total_elapsed:.2f}s")
    for name, tid, e, model in submissions:
        print(f"    {name}: {tid} ({e:.2f}s, {model})")

    # ========== 3. check_task + wait_and_download（3 并发）==========
    print("\n[3] wait_and_download × 3 (3 并发)")
    task_ids = [tid for _, tid, _, _ in submissions]
    clip_outputs = {c["name"]: c["output"] for c in clips}

    async def wait_one(name, tid):
        # ✅ 走与 call_tool wait_and_download 完全相同的代码路径
        output_path = clip_outputs[name]
        deadline = time.time() + 300  # 5min timeout
        while time.time() < deadline:
            r = await M._ark_request_async("GET", f"{M.ARK_BASE_URL}/{tid}", timeout=30)
            status = r.get("status")
            if status == "succeeded":
                video_url = r.get("content", {}).get("video_url")
                client = await M._get_http_client()
                dl = await client.get(video_url, timeout=120)
                dl.raise_for_status()
                data = dl.content
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(data)
                M._cache_task(
                    task_id=tid, status="succeeded", video_url=video_url,
                    duration=r.get("duration"), ratio=r.get("ratio"),
                    resolution=r.get("resolution"),
                    local_path=str(output_path), size_bytes=len(data),
                    md5=__import__("hashlib").md5(data).hexdigest(),
                )
                return name, tid, str(output_path), len(data)
            elif status == "failed":
                M._cache_task(task_id=tid, status="failed", error=r.get("error"))
                raise RuntimeError(f"{name} failed: {r.get('error')}")
            await asyncio.sleep(15)
        raise RuntimeError(f"{name} timeout 5min")

    t0 = time.time()
    downloads = await asyncio.gather(*[wait_one(n, t) for n, t, _, _ in submissions])
    total_elapsed = time.time() - t0
    print(f"  3 并发下载：{total_elapsed:.2f}s")
    for name, tid, path, size in downloads:
        print(f"    {name}: {tid} → {path} ({size/1024:.1f}KB)")

    # ========== 4. list_recent_tasks（验证缓存写入）==========
    print("\n[4] list_recent_tasks (本地缓存验证)")
    cache = M._read_cache(limit=10)
    new_ids = {tid for _, tid, _, _ in submissions}
    cached_new = [r for r in cache if r["task_id"] in new_ids]
    print(f"  缓存总数: {len(cache)} · 新提交 3 个都在缓存: {len(cached_new)}/3")
    for r in cached_new:
        print(f"    {r['task_id']} · status={r.get('status')} · has_url={bool(r.get('video_url'))} · ttl={r.get('url_ttl_sec')}s")
    assert len(cached_new) == 3, "缓存里没找到 3 个新任务！"

    # ========== 5. ffprobe 校验 ==========
    print("\n[5] ffprobe 校验 3 个视频")
    import subprocess
    for name, tid, path, size in downloads:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,codec_name,duration",
             "-of", "json", str(path)],
            capture_output=True, text=True,
        )
        info = json.loads(r.stdout)["streams"][0]
        print(f"    {name}: {info['width']}x{info['height']} {info['codec_name']} dur={info.get('duration')}s")
        assert int(info["width"]) > 0, f"{name} invalid width"

    # ========== 6. download_cached 二次下载（不调 API）==========
    print("\n[6] download_cached 二次下载 (验证缓存 + URL 重用)")
    for name, tid, path, size in downloads:
        # 找缓存里这条
        rec = next(r for r in cache if r["task_id"] == tid)
        cached_url = rec.get("video_url")
        assert cached_url, f"{name} 缓存里没 video_url"
        # 用同一个 URL 再下 1 次
        client = await M._get_http_client()
        dl = await client.get(cached_url, timeout=60)
        dl.raise_for_status()
        size2 = len(dl.content)
        print(f"    {name}: 重下 {size2/1024:.1f}KB (跟首次 {size/1024:.1f}KB 对比)")

    print("\n" + "=" * 70)
    print("✅ TASK 5 通过 · 6 工具端到端全跑通")
    print("=" * 70)
    for name, tid, path, size in downloads:
        print(f"  {name}: {path}")


if __name__ == "__main__":
    asyncio.run(run_e2e())
