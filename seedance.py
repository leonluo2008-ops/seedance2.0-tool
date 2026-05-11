#!/usr/bin/env python3
"""
Seedance 2.0 Tool - 纯视频生成工具（唯一图床：Chevereto）

调用 Volcengine Seedance 2.0 API，仅支持 Chevereto 图床上传。

用法：
    python3 seedance.py create --ref-images ./character.png --video-refs ./motion.mp4 \
        --prompt "使用图片1的角色，替换视频1中的角色，纯白色背景" \
        --duration 5 --ratio 1:1 --wait --download ./output

环境变量：
    ARK_API_KEY         : Volcengine Ark API Key（必填）
    CHEVERETO_API_KEY   : Chevereto 图床 API Key（必填）
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv


def parse_bool(v):
    """Parse boolean CLI argument (true/false/1/0)."""
    if isinstance(v, bool):
        return v
    if v.lower() in ("true", "1", "yes"):
        return True
    if v.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean expected, got '{v}'")

# ============ 配置 ============

# ⚠️ 仅使用 Seedance 2.0 系列模型，禁止 1.0 系列和 2.0-pro 系列
DEFAULT_MODEL = "doubao-seedance-2-0-fast-260128"
SUPPORTED_MODELS = [
    "doubao-seedance-2-0-fast-260128",   # Fast 模式，速度优先
    "doubao-seedance-2-0-260128",        # 高质量模式，质量优先
]
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
CHEVERETO_API_URL = "https://chevereto.aistar.work/api/1/upload"


def get_api_key() -> str:
    key = os.environ.get("ARK_API_KEY")
    if not key:
        print("Error: ARK_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with: export ARK_API_KEY='your-ark-api-key'", file=sys.stderr)
        sys.exit(1)
    return key


def get_chevereto_key() -> str:
    key = os.environ.get("CHEVERETO_API_KEY")
    if not key:
        print("Error: CHEVERETO_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with: export CHEVERETO_API_KEY='your-chevereto-api-key'", file=sys.stderr)
        sys.exit(1)
    return key


# ============ Chevereto 图床上传（curl 绕过 Cloudflare）============

def upload_to_chevereto(local_path: str, mime_type: str) -> str:
    """
    上传本地文件到 Chevereto 图床，返回公开 URL（HTTP）。
    mime_type 示例：'video/mp4', 'image/png', 'image/jpeg'
    使用 curl 绕过 Cloudflare 对 urllib/requests 的拦截。
    """
    p = Path(local_path)
    if not p.exists():
        print(f"Error: File not found: {local_path}", file=sys.stderr)
        sys.exit(1)

    file_size = p.stat().st_size
    max_size = 50 * 1024 * 1024 if mime_type.startswith("video") else 30 * 1024 * 1024
    if file_size > max_size:
        print(f"Error: File too large ({file_size / 1024 / 1024:.1f} MB). Max {max_size // 1024 // 1024} MB.", file=sys.stderr)
        sys.exit(1)

    api_key = get_chevereto_key()
    print(f"  Uploading to Chevereto ({p.name}, {file_size / 1024 / 1024:.1f} MB)...", end=" ", flush=True)

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                CHEVERETO_API_URL,
                "-F", f"source=@{p};type={mime_type}",
                "-F", f"key={api_key}",
            ],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"\nError: curl failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        response = json.loads(result.stdout)
        if response.get("status_code") != 200:
            print(f"\nError: Chevereto API error: {response.get('status_txt')} (code {response.get('status_code')})", file=sys.stderr)
            sys.exit(1)

        url = response.get("image", {}).get("url", "")
        if not url:
            print(f"\nError: Chevereto response missing URL: {response}", file=sys.stderr)
            sys.exit(1)

        print("✓")
        return url

    except subprocess.TimeoutExpired:
        print("Error: Upload timed out after 60s", file=sys.stderr)
        sys.exit(1)


def upload_image(file_path: str) -> str:
    """上传图片到 Chevereto，返回公网 URL"""
    suffix = Path(file_path).suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    return upload_to_chevereto(file_path, mime_type)


def upload_video(file_path: str) -> str:
    """上传视频到 Chevereto，返回公网 URL。视频必须显式指定 type=video/mp4。"""
    return upload_to_chevereto(file_path, "video/mp4")


def resolve_image_url(image_input: str) -> str:
    """解析图片输入：URL 直接返回，本地文件上传 Chevereto"""
    if image_input.startswith(("http://", "https://", "data:")):
        return image_input
    return upload_image(image_input)


def resolve_video_url(video_input: str) -> str:
    """解析视频输入：URL 直接返回，本地文件上传 Chevereto"""
    if video_input.startswith(("http://", "https://")):
        return video_input
    return upload_video(video_input)


def resolve_audio_url(audio_input: str) -> str:
    """解析音频输入：URL 直接返回，本地文件上传 Chevereto。"""
    if audio_input.startswith(("http://", "https://", "data:")):
        return audio_input
    suffix = Path(audio_input).suffix.lower()
    mime_type = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
        ".m4a": "audio/mp4",
    }.get(suffix, "application/octet-stream")
    return upload_to_chevereto(audio_input, mime_type)


# ============ 工具函数 ============

def verify_url_accessible(url: str, timeout: int = 10) -> bool:
    """验证 URL 是否可访问（HEAD 请求）"""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def api_request(method: str, url: str, data: dict = None, timeout: int = 120) -> dict:
    """Make an API request and return parsed JSON response."""
    api_key = get_api_key()

    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "SeedanceTool/1.0")

    if data:
        req.data = json.dumps(data).encode("utf-8")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_body)
            print(f"API Error (HTTP {e.code}): {error_json.get('error', {}).get('message', error_body[:500])}", file=sys.stderr)
        except Exception:
            print(f"API Error (HTTP {e.code}): {error_body[:500]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)


def wait_for_completion(task_id: str, poll_interval: int = 15, timeout: int = 600) -> dict:
    """轮询等待任务完成"""
    start = time.time()
    while time.time() - start < timeout:
        result = api_request("GET", f"{BASE_URL}/{task_id}")
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


def download_video(url: str, output_path: str) -> bool:
    """下载视频文件"""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "SeedanceTool/1.0")
        with urllib.request.urlopen(req, timeout=60) as resp:
            content_type = resp.headers.get("Content-Type", "")
            ext = ".mp4"
            if "video/mp4" in content_type:
                ext = ".mp4"
            elif "video/webm" in content_type:
                ext = ".webm"

            if Path(output_path).suffix not in (".mp4", ".webm", ".mov"):
                output_path = str(Path(output_path).with_suffix(ext))

            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

            print(f"  Downloaded: {output_path}")
            return True
    except Exception as e:
        print(f"  Download failed: {e}", file=sys.stderr)
        return False


# ============ CLI 命令 ============

def cmd_create(args):
    """创建视频生成任务"""
    content = []

    # 草稿模式：直接用 draft_task_id 生成正式视频
    if getattr(args, "draft_task_id", None):
        content.append({"type": "draft_task", "draft_task": {"id": args.draft_task_id}})
    else:
        if getattr(args, "prompt", None):
            content.append({"type": "text", "text": args.prompt})

        # 参考图片（角色参考）
        ref_images = getattr(args, "ref_images", None) or []
        for img in ref_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": resolve_image_url(img)},
                "role": "reference_image"
            })

        # 首帧/尾帧图片（与参考图片二选一）
        if getattr(args, "image", None):
            img_url = resolve_image_url(args.image)
            content.append({"type": "image_url", "image_url": {"url": img_url}, "role": "first_frame"})
            if getattr(args, "last_frame", None):
                content.append({"type": "image_url", "image_url": {"url": resolve_image_url(args.last_frame)}, "role": "last_frame"})

        # 参考视频
        video_refs = getattr(args, "video_refs", None) or []
        for vid in video_refs:
            content.append({
                "type": "video_url",
                "video_url": {"url": resolve_video_url(vid)},
                "role": "reference_video"
            })

        # 参考音频
        audio_refs = getattr(args, "audio", None) or []
        for audio in audio_refs:
            content.append({"type": "audio_url", "audio_url": {"url": resolve_audio_url(audio)}})

    if not content:
        print("Error: Must provide --prompt, --image, --ref-images, --video-refs, --audio, or --draft-task-id.", file=sys.stderr)
        sys.exit(1)

    # 构建请求体（duration/ratio/resolution/watermark 为顶层字段，非 parameters 内）
    body = {
        "model": args.model,
        "content": content,
        "duration": args.duration,
        "resolution": args.resolution,
        "ratio": args.ratio,
        "watermark": args.watermark,
    }

    # 可选高级参数
    if getattr(args, "seed", None) is not None:
        body["seed"] = args.seed
    if getattr(args, "camera_fixed", None) is not None:
        body["camera_fixed"] = args.camera_fixed
    if getattr(args, "generate_audio", None) is not None:
        body["generate_audio"] = args.generate_audio
    if getattr(args, "draft", None) is not None:
        body["draft"] = args.draft
    if getattr(args, "return_last_frame", None) is not None:
        body["return_last_frame"] = args.return_last_frame
    if getattr(args, "service_tier", None):
        body["service_tier"] = args.service_tier

    print(f"Creating task with model {args.model}...")
    result = api_request("POST", f"{BASE_URL}", body)

    task_id = result.get("id")
    if not task_id:
        print(f"Error: No task ID in response: {result}", file=sys.stderr)
        sys.exit(1)

    print(f"Task ID: {task_id}")

    if args.wait:
        print("Waiting for completion...")
        result = wait_for_completion(task_id)

        if args.download:
            video_url = result.get("content", {}).get("video_url")
            if video_url:
                download_video(video_url, args.download)
            else:
                print("Warning: No video_url in result", file=sys.stderr)
                print(json.dumps(result, indent=2, ensure_ascii=False))

        print(f"\n✅ Task completed: {task_id}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n✅ Task created: {task_id}")
        print("Use 'seedance.py status <task_id>' to check progress.")


def cmd_status(args):
    """查询任务状态"""
    result = api_request("GET", f"{BASE_URL}/{args.task_id}")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_wait(args):
    """等待任务完成并下载"""
    print(f"Waiting for task {args.task_id}...")
    result = wait_for_completion(args.task_id)

    if args.download:
        video_url = result.get("content", {}).get("video_url")
        if video_url:
            download_video(video_url, args.download)

    print(json.dumps(result, indent=2, ensure_ascii=False))


# ============ 主入口 ============

def main():
    # 自动加载 .env 文件（从脚本所在目录向上查找）
    script_dir = Path(__file__).resolve().parent
    for candidate in [script_dir, script_dir.parent, Path.cwd()]:
        env_path = candidate / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            break

    parser = argparse.ArgumentParser(
        description="Seedance 2.0 Tool - 视频生成工具（唯一图床：Chevereto）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 seedance.py create --ref-images char.png --video-refs motion.mp4 \
      --prompt "使用图片1的角色，替换视频1中的角色，纯白色背景" \
      --duration 5 --ratio 1:1 --wait --download ./output

Environment variables:
  ARK_API_KEY        : Volcengine Ark API Key（必填）
  CHEVERETO_API_KEY  : Chevereto 图床 API Key（必填）
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    create_parser = subparsers.add_parser("create", help="创建视频生成任务")
    create_parser.add_argument("--ref-images", nargs="+", help="参考图片路径或URL（角色参考）")
    create_parser.add_argument("--image", "-i", help="首帧图片路径或URL")
    create_parser.add_argument("--last-frame", help="尾帧图片路径或URL")
    create_parser.add_argument("--video-refs", nargs="+", help="参考视频路径或URL")
    create_parser.add_argument("--audio", nargs="+", help="参考音频路径或URL")
    create_parser.add_argument("--draft-task-id", help="草稿任务ID（从草稿生成正式视频）")
    create_parser.add_argument("--prompt", "-p", help="文字提示词")
    create_parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"模型ID（默认: {DEFAULT_MODEL}，仅支持Seedance 2.0系列）")
    create_parser.add_argument("--ratio", default="16:9", help="画幅（1:1/16:9/4:3/9:16/21:9/adaptive）")
    create_parser.add_argument("--duration", type=int, default=5, help="视频时长（秒，4-15，或-1自动）")
    create_parser.add_argument("--resolution", default="480p", help="分辨率（480p/720p/1080p）")
    create_parser.add_argument("--seed", type=int, help="随机种子（-1=随机，用于复现）")
    create_parser.add_argument("--camera-fixed", type=parse_bool, help="固定镜头位置（true/false）")
    create_parser.add_argument("--watermark", type=parse_bool, default=True, help="添加水印（true/false，默认true）")
    create_parser.add_argument("--generate-audio", type=parse_bool, help="生成音频（true/false）")
    create_parser.add_argument("--draft", type=parse_bool, help="草稿/预览模式（true/false）")
    create_parser.add_argument("--return-last-frame", type=parse_bool, help="返回尾帧图片URL（true/false）")
    create_parser.add_argument("--service-tier", choices=["default", "flex"], help="服务层级（flex=离线便宜50%%）")
    create_parser.add_argument("--wait", "-w", action="store_true", help="等待生成完成")
    create_parser.add_argument("--download", help="下载到的本地路径")
    create_parser.add_argument("--force", "-y", action="store_true", help="跳过确认步骤，直接执行（Agent 场景使用）")
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
