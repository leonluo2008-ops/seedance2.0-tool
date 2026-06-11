#!/usr/bin/env python3
"""
Seedance 2.0 Tool - 视频生成工具 CLI（统一图床：uguu.se）

调用 Volcengine Seedance 2.0 API，**唯一图床 = uguu.se**（不再用 chevereto）。

**单真源原则**：本文件只保留 CLI 入口；上传 / Ark API / 任务缓存 / body 构造
全部抽到 seedance_uploads.py。改上传/缓存逻辑请改 seedance_uploads.py。

用法：
    python3 seedance.py create --ref-images ./character.png \
        --prompt "使用图片1的角色..." --duration 5 --ratio 1:1 --wait --download ./output

环境变量：
    ARK_API_KEY         : Volcengine Ark API Key（必填）
    SEEDANCE_CACHE_DIR  : 本地任务缓存目录（可选，默认 ~/.cache/seedance-mcp）

变更记录：
- 2026-06-11 v1.0 迁移到 uguu.se + httpx async + 任务缓存
  - 删 5 个 chevereto 函数（upload_to_chevereto / upload_image / upload_video / resolve_image_url / resolve_video_url）
  - 删 .env 必填 CHEVERETO_API_KEY
  - 底层调 seedance_uploads.py（业务函数库）
  - watermark 默认改 None（绘本场景专精）
  - generate_audio 默认 False（绘本无 BGM）
  - seed/camera_fixed/draft/return_last_frame/service_tier 全部顶层（**不**嵌套 parameters）
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# 共享业务函数库（单真源）
import seedance_uploads as U

# 老 seedance.py 兼容别名
DEFAULT_MODEL = U.DEFAULT_MODEL
BASE_URL = U.ARK_BASE_URL
parse_bool = lambda v: (v.lower() in ("true", "1", "yes")) if isinstance(v, str) else bool(v)


# ============ CLI 命令 ============

def cmd_create(args):
    """创建视频生成任务（保留 CLI 入口行为，老用户兼容）。"""
    # 用 seedance_uploads.build_body 构造请求体（共享逻辑，单真源）
    body_args = {
        "prompt": args.prompt,
        "ref_images": args.ref_images or [],
        "image": getattr(args, "image", None),
        "last_frame": getattr(args, "last_frame", None),
        "video_refs": args.video_refs or [],
        "audio_refs": args.audio or [],
        "draft_task_id": getattr(args, "draft_task_id", None),
        "duration": args.duration,
        "ratio": args.ratio,
        "watermark": getattr(args, "watermark", None),  # 字符串 'none'/'platform'/'seedance_ai'，build_body 内部映射
        "generate_audio": getattr(args, "generate_audio", None),
        "resolution": args.resolution,
        "model": args.model,
        "seed": getattr(args, "seed", None),
        "camera_fixed": getattr(args, "camera_fixed", None),
        "draft": getattr(args, "draft", None),
        "return_last_frame": getattr(args, "return_last_frame", None),
        "service_tier": getattr(args, "service_tier", None),
    }

    # 同步上传所有本地文件 → resolved_urls（保留老 CLI 同步语义）
    try:
        resolved_urls = {}
        for kind, key in [("image", "ref_images"), ("image", "image"), ("image", "last_frame"),
                          ("video", "video_refs"), ("audio", "audio_refs")]:
            v = body_args.get(key)
            if not v:
                continue
            items = v if isinstance(v, list) else [v]
            for item in items:
                if item in resolved_urls:
                    continue
                resolved_urls[item] = U.resolve_url(item, kind)
    except Exception as e:
        print(f"Error: file resolution failed: {e}", file=sys.stderr)
        sys.exit(1)

    # watermark 字符串兼容：老 seedance.py 接受 true/false，mcp 接受 'none'/'platform'/'seedance_ai'
    # 这里加映射：true → 'seedance_ai'（保持老行为），false → 'none'（绘本正确）
    if isinstance(body_args["watermark"], bool):
        body_args["watermark"] = "seedance_ai" if body_args["watermark"] else "none"

    try:
        body = U.build_body(body_args, resolved_urls=resolved_urls)
    except Exception as e:
        print(f"Error: build body failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Creating task with model {args.model}...")
    print("BODY:", json.dumps(body, ensure_ascii=False)[:2000])

    try:
        result = U.ark_request("POST", BASE_URL, body)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    task_id = result.get("id")
    if not task_id:
        print(f"Error: No task ID in response: {result}", file=sys.stderr)
        sys.exit(1)

    print(f"Task ID: {task_id}")

    # 写本地缓存（spike 002 升级：跨 session 可查）
    U.cache_task(
        task_id=task_id, status=result.get("status", "queued"),
        duration=body["duration"], ratio=body["ratio"], resolution=body.get("resolution"),
        model=body["model"], source="seedance_cli",
    )

    if args.wait:
        print("Waiting for completion...")
        result = wait_for_completion(task_id)

        if args.download:
            video_url = result.get("content", {}).get("video_url")
            if video_url:
                if U.download_video(video_url, args.download):
                    print(f"  Downloaded: {args.download}")
                else:
                    print(f"Warning: download failed", file=sys.stderr)
            else:
                print("Warning: No video_url in result", file=sys.stderr)
                print(json.dumps(result, indent=2, ensure_ascii=False))

        # 成功后更新缓存（含 video_url + TTL）
        video_url = result.get("content", {}).get("video_url")
        U.cache_task(
            task_id=task_id, status=result.get("status", "succeeded"),
            video_url=video_url,
            duration=result.get("duration"), ratio=result.get("ratio"),
            resolution=result.get("resolution"),
            local_path=args.download if args.download else None,
        )

        print(f"\n✅ Task completed: {task_id}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n✅ Task created: {task_id}")
        print("Use 'seedance.py status <task_id>' to check progress.")


def cmd_status(args):
    """查询任务状态"""
    try:
        result = U.ark_request("GET", f"{BASE_URL}/{args.task_id}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # 写缓存
    U.cache_task(
        task_id=args.task_id, status=result.get("status", "unknown"),
        video_url=result.get("content", {}).get("video_url"),
        duration=result.get("duration"), ratio=result.get("ratio"),
        resolution=result.get("resolution"),
    )


def cmd_wait(args):
    """等待任务完成并下载"""
    print(f"Waiting for task {args.task_id}...")
    result = wait_for_completion(args.task_id)

    if args.download:
        video_url = result.get("content", {}).get("video_url")
        if video_url:
            if U.download_video(video_url, args.download):
                print(f"  Downloaded: {args.download}")
            else:
                print(f"Warning: download failed", file=sys.stderr)

    print(json.dumps(result, indent=2, ensure_ascii=False))


def wait_for_completion(task_id: str, poll_interval: int = 15, timeout: int = 600) -> dict:
    """轮询等待任务完成（同步版，给老 CLI 用）。"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = U.ark_request("GET", f"{BASE_URL}/{task_id}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        status = result.get("status", "")

        if status == "succeeded":
            return result
        elif status == "failed":
            print(f"Task failed: {result.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)
        elif status in ("running", "pending"):
            print(f"  Status: {status}...", flush=True)
            time.sleep(poll_interval)
        else:
            print(f"Unknown status: {status}", file=sys.stderr)
            sys.exit(1)

    print("Timeout waiting for task completion.", file=sys.stderr)
    sys.exit(1)


# ============ 主入口 ============

def main():
    # 自动加载 .env 文件
    from dotenv import load_dotenv
    script_dir = Path(__file__).resolve().parent
    for candidate in [script_dir, script_dir.parent, Path.cwd()]:
        env_path = candidate / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            break

    # 必填环境变量校验
    if not os.environ.get("ARK_API_KEY"):
        print("Error: ARK_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with: export ARK_API_KEY='your-ark-api-key'", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Seedance 2.0 Tool - 视频生成工具（统一图床：uguu.se）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 seedance.py create --ref-images char.png --prompt "使用图片1的角色..." --duration 5 --ratio 1:1 --wait --download ./output

Environment variables:
  ARK_API_KEY         : Volcengine Ark API Key（必填）
  SEEDANCE_CACHE_DIR  : 本地任务缓存目录（可选，默认 ~/.cache/seedance-mcp）
""")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    create_parser = subparsers.add_parser("create", help="创建视频生成任务")
    create_parser.add_argument("--ref-images", nargs="+", help="参考图片路径或URL（角色参考）")
    create_parser.add_argument("--image", "-i", help="首帧图片路径或URL")
    create_parser.add_argument("--last-frame", help="尾帧图片路径或URL")
    create_parser.add_argument("--video-refs", nargs="+", help="参考视频路径或URL")
    create_parser.add_argument("--audio", nargs="+", help="参考音频路径或URL")
    create_parser.add_argument("--draft-task-id", help="草稿任务ID（从草稿生成正式视频）")
    create_parser.add_argument("--prompt", "-p", help="文字提示词")
    create_parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"模型ID（默认: {DEFAULT_MODEL}）")
    create_parser.add_argument("--ratio", default="16:9", help="画幅（1:1/16:9/4:3/9:16/21:9/adaptive）")
    create_parser.add_argument("--duration", type=int, default=5, help="视频时长（秒，4-15，或-1自动）")
    create_parser.add_argument("--resolution", default="720p", help="分辨率（480p/720p/1080p）")
    create_parser.add_argument("--seed", type=int, help="随机种子（-1=随机，用于复现）")
    create_parser.add_argument("--camera-fixed", type=parse_bool, help="固定镜头位置（true/false）")
    # watermark 老 CLI 兼容：true/false → 内部映射 'none'/'seedance_ai'/'platform'
    create_parser.add_argument("--watermark", type=parse_bool, default=False,
                               help="是否带 AI 水印（true/false，**默认 false**）—— 绘本场景必传 false")
    create_parser.add_argument("--generate-audio", type=parse_bool, help="生成音频（true/false）")
    create_parser.add_argument("--draft", type=parse_bool, help="草稿/预览模式（true/false）")
    create_parser.add_argument("--return-last-frame", type=parse_bool, help="返回尾帧图片URL（true/false）")
    create_parser.add_argument("--service-tier", choices=["default", "flex"], help="服务层级（flex=离线便宜50%%）")
    create_parser.add_argument("--wait", "-w", action="store_true", help="等待生成完成")
    create_parser.add_argument("--download", help="下载到的本地路径")
    create_parser.set_defaults(func=cmd_create)

    status_parser = subparsers.add_parser("status", help="查询任务状态")
    status_parser.add_argument("task_id", help="任务ID")
    status_parser.set_defaults(func=cmd_status)

    wait_parser = subparsers.add_parser("wait", help="等待任务完成")
    wait_parser.add_argument("task_id", help="任务ID")
    wait_parser.add_argument("--download", help="下载到的本地路径")
    wait_parser.set_defaults(func=cmd_wait)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
