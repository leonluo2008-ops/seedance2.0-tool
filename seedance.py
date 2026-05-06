#!/usr/bin/env python3
"""
Seedance 2.0 Tool - 纯视频生成工具

支持多种文件托管后端（chevereto / nginx-docker / http-url）
默认使用 chevereto API 上传文件。

用法：
    python3 seedance.py create --ref-image ./char.png --video-ref ./motion.mp4 \\
        --prompt "使用图片1的角色，替换视频1中的角色，纯白色背景" \\
        --duration 5 --ratio 1:1 --wait --download ./output

文件托管后端（--upload-backend）：
    chevereto     : Chevereto API（默认，需配置 CHEVERETO_API_KEY）
    nginx-docker  : docker cp 到 nginx 容器（当前 OpenClaw 方式）
    http-url      : 直接使用公网 URL，不上传
"""

import argparse
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ============ 配置 ============

DEFAULT_MODEL = "doubao-seedance-2-0-fast-260128"
NGINX_HOST = "img.aistar.work"
NGINX_VIDEO_PATH = "/www/video/"
NGINX_IMAGE_PATH = "/www/image/"
NGINX_CONTAINER = "1Panel-openresty-kfra"
CHEVERETO_HOST = "http://127.0.0.1:8080"


def get_api_key() -> str:
    key = os.environ.get("ARK_API_KEY")
    if not key:
        print("Error: ARK_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with: export ARK_API_KEY='your-api-key-here'", file=sys.stderr)
        sys.exit(1)
    return key


def get_chevereto_key() -> str:
    key = os.environ.get("CHEVERETO_API_KEY")
    if not key:
        print("Error: CHEVERETO_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with: export CHEVERETO_API_KEY='your-chevereto-api-key'", file=sys.stderr)
        sys.exit(1)
    return key


# ============ 文件托管后端 ============

class Uploader:
    """文件托管后端基类"""
    
    def upload_image(self, file_path: str) -> str:
        """上传图片，返回公网 URL"""
        raise NotImplementedError
    
    def upload_video(self, file_path: str) -> str:
        """上传视频，返回公网 URL"""
        raise NotImplementedError


class CheveretoUploader(Uploader):
    """Chevereto API 上传后端"""
    
    def __init__(self, host: str = CHEVERETO_HOST):
        self.host = host
        self.api_key = get_chevereto_key()
    
    def upload_image(self, file_path: str) -> str:
        return self._upload(file_path, "image")
    
    def upload_video(self, file_path: str) -> str:
        return self._upload(file_path, "video")
    
    def _upload(self, file_path: str, media_type: str) -> str:
        p = Path(file_path)
        if not p.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        
        print(f"  Uploading to Chevereto ({p.name})...", end=" ", flush=True)
        
        try:
            import requests
        except ImportError:
            print("\nError: requests library required for Chevereto uploader.", file=sys.stderr)
            print("  Install with: pip install requests", file=sys.stderr)
            sys.exit(1)
        
        try:
            with open(p, "rb") as f:
                files = {"source": (p.name, f, self._guess_mime(p))}
                data = {"key": self.api_key}
                resp = requests.post(
                    f"{self.host}/api/1/upload",
                    files=files,
                    data=data,
                    timeout=60
                )
            result = resp.json()
            
            if result.get("status_code") == 200:
                url = result["image"]["url"]
                print("✓")
                return url
            else:
                print(f"\nError: Chevereto upload failed: {result.get('error', {}).get('message', 'Unknown error')}")
                sys.exit(1)
        except Exception as e:
            print(f"\nError: Chevereto upload failed: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _guess_mime(self, p: Path) -> str:
        mime, _ = mimetypes.guess_type(str(p))
        return mime or f"{media_type}/octet-stream"


class NginxDockerUploader(Uploader):
    """docker cp 到 nginx 容器后端（当前 OpenClaw 使用的方式）"""
    
    def __init__(self, host: str = NGINX_HOST, container: str = NGINX_CONTAINER):
        self.host = host
        self.container = container
    
    def upload_image(self, file_path: str) -> str:
        return self._upload(file_path, "image")
    
    def upload_video(self, file_path: str) -> str:
        return self._upload(file_path, "video")
    
    def _upload(self, file_path: str, media_type: str) -> str:
        p = Path(file_path)
        if not p.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        
        file_size = p.stat().st_size
        max_size = 50 * 1024 * 1024 if media_type == "video" else 30 * 1024 * 1024
        if file_size > max_size:
            print(f"Error: File too large ({file_size / 1024 / 1024:.1f} MB). Max {max_size // 1024 // 1024} MB.", file=sys.stderr)
            sys.exit(1)
        
        md5_hash = hashlib.md5(p.read_bytes()).hexdigest()[:12]
        safe_name = f"{md5_hash}_{p.name}"
        
        if media_type == "image":
            container_dest = f"/www/image/{safe_name}"
            public_url = f"https://{self.host}/image/{safe_name}"
        else:
            container_dest = f"/www/video/{safe_name}"
            public_url = f"https://{self.host}/video/{safe_name}"
        
        print(f"  Uploading to nginx ({self.container}:{container_dest})...", end=" ", flush=True)
        
        try:
            subprocess.run(["docker", "exec", self.container, "mkdir", "-p", f"/www/{media_type}/"], check=True, capture_output=True)
            subprocess.run(["docker", "cp", str(p.absolute()), f"{self.container}:{container_dest}"], check=True, capture_output=True)
            subprocess.run(["docker", "exec", self.container, "chmod", "644", container_dest], check=True, capture_output=True)
        except FileNotFoundError:
            print("\nError: docker command not found.", file=sys.stderr)
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            print(f"\nError: docker exec failed: {stderr}", file=sys.stderr)
            sys.exit(1)
        
        print("✓")
        return public_url


class HttpUrlUploader(Uploader):
    """直接使用公网 URL，不上传"""
    
    def upload_image(self, file_path: str) -> str:
        if file_path.startswith(("http://", "https://")):
            return file_path
        print("Error: HttpUrlUploader requires a URL, not a local file.", file=sys.stderr)
        sys.exit(1)
    
    def upload_video(self, file_path: str) -> str:
        if file_path.startswith(("http://", "https://")):
            return file_path
        print("Error: HttpUrlUploader requires a URL, not a local file.", file=sys.stderr)
        sys.exit(1)


def create_uploader(backend: str) -> Uploader:
    if backend == "chevereto":
        return CheveretoUploader()
    elif backend == "nginx-docker":
        return NginxDockerUploader()
    elif backend == "http-url":
        return HttpUrlUploader()
    else:
        print(f"Error: Unknown upload backend: {backend}", file=sys.stderr)
        sys.exit(1)


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


def resolve_image_url(uploader: Uploader, image_input: str) -> str:
    """解析图片输入：URL 直接返回，本地文件上传"""
    if image_input.startswith(("http://", "https://")):
        return image_input
    if image_input.startswith("data:"):
        return image_input
    return uploader.upload_image(image_input)


def resolve_video_url(uploader: Uploader, video_input: str) -> str:
    """解析视频输入：URL 直接返回，本地文件上传"""
    if video_input.startswith(("http://", "https://")):
        return video_input
    return uploader.upload_video(video_input)


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
    base_url = "https://ark.cn-beijing.volces.com/api/v3/bots/bot-..."  # placeholder
    
    start = time.time()
    while time.time() - start < timeout:
        result = api_request("GET", f"{base_url}/tasks/{task_id}")
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
    uploader = create_uploader(args.upload_backend)
    
    # 解析输入
    ref_image_urls = []
    if args.ref_images:
        for img in args.ref_images:
            ref_image_urls.append(resolve_image_url(uploader, img))
    
    video_ref_urls = []
    if args.video_refs:
        for vid in args.video_refs:
            video_ref_urls.append(resolve_video_url(uploader, vid))
    
    audio_urls = []
    if args.audios:
        for aud in args.audios:
            if aud.startswith(("http://", "https://")):
                audio_urls.append(aud)
            else:
                # TODO: 实现音频上传
                print(f"Warning: Audio upload not yet implemented, treating as URL: {aud}", file=sys.stderr)
                audio_urls.append(aud)
    
    # 构建请求
    content = []
    if args.prompt:
        content.append({"type": "text", "text": args.prompt})
    
    for url in ref_image_urls:
        content.append({
            "type": "image_url",
            "image_url": {"url": url},
            "role": "reference_image"
        })
    
    for url in video_ref_urls:
        content.append({
            "type": "video_url",
            "video_url": {"url": url},
            "role": "reference_video"
        })
    
    for url in audio_urls:
        content.append({
            "type": "audio_url",
            "audio_url": {"url": url}
        })
    
    if not content:
        print("Error: Must provide --prompt, --ref-images, --video-ref, or --audio.", file=sys.stderr)
        sys.exit(1)
    
    body = {
        "model": args.model,
        "content": content,
        "parameters": {
            "duration": args.duration,
            "resolution": args.resolution,
            "ratio": args.ratio,
        }
    }
    
    # 发送请求
    base_url = "https://ark.cn-beijing.volces.com/api/v3/bots/bot-..."  # placeholder
    print(f"Creating task with model {args.model}...")
    result = api_request("POST", f"{base_url}/tasks", body)
    
    task_id = result.get("id")
    if not task_id:
        print(f"Error: No task ID in response: {result}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Task ID: {task_id}")
    
    if args.wait:
        print("Waiting for completion...")
        result = wait_for_completion(task_id)
        
        if args.download:
            video_url = result.get("data", {}).get("video_url")
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
    base_url = "https://ark.cn-beijing.volces.com/api/v3/bots/bot-..."
    result = api_request("GET", f"{base_url}/tasks/{args.task_id}")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_wait(args):
    """等待任务完成并下载"""
    print(f"Waiting for task {args.task_id}...")
    result = wait_for_completion(args.task_id)
    
    if args.download:
        video_url = result.get("data", {}).get("video_url")
        if video_url:
            download_video(video_url, args.download)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(
        description="Seedance 2.0 Tool - 视频生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 角色替换（使用 chevereto 上传）
  python3 seedance.py create --ref-image char.png --video-ref motion.mp4 \\
      --prompt "使用图片1的角色，替换视频1中的角色" \\
      --duration 5 --ratio 1:1 --upload-backend chevereto --wait --download ./output

  # 直接使用公网 URL（不上传）
  python3 seedance.py create --ref-image https://example.com/char.png \\
      --video-ref https://example.com/motion.mp4 \\
      --prompt "..." --wait

Environment variables:
  ARK_API_KEY        : Volcengine Ark API Key（必填）
  CHEVERETO_API_KEY  : Chevereto API Key（chevereto 后端必填）
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # create 命令
    create_parser = subparsers.add_parser("create", help="创建视频生成任务")
    create_parser.add_argument("--ref-images", nargs="+", help="参考图片路径或URL")
    create_parser.add_argument("--video-refs", nargs="+", help="参考视频路径或URL")
    create_parser.add_argument("--audios", nargs="+", help="参考音频路径或URL")
    create_parser.add_argument("--prompt", help="提示词")
    create_parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型ID（默认: {DEFAULT_MODEL}）")
    create_parser.add_argument("--duration", type=int, default=5, help="视频时长（秒）")
    create_parser.add_argument("--resolution", default="720p", help="分辨率（720p/1080p）")
    create_parser.add_argument("--ratio", default="1:1", help="画幅（1:1/16:9/9:16）")
    create_parser.add_argument("--upload-backend", default="chevereto",
        choices=["chevereto", "nginx-docker", "http-url"],
        help="文件托管后端（默认: chevereto）")
    create_parser.add_argument("--wait", action="store_true", help="等待生成完成")
    create_parser.add_argument("--download", help="下载到的本地路径")
    create_parser.set_defaults(func=cmd_create)
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查询任务状态")
    status_parser.add_argument("task_id", help="任务ID")
    status_parser.set_defaults(func=cmd_status)
    
    # wait 命令
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
