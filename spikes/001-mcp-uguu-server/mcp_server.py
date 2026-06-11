"""
spike 001: MCP server for seedance2.0-tool
==========================================

⚠️ THROWAWAY SPIKE CODE — 不直接合并到 seedance.py
   跑通后清理阶段会重构：上传函数抽到 seedance_uploads.py，再让 seedance.py + mcp_server.py 都 import

Tools exposed (auto-registered as mcp_seedance_* by Hermes):
- generate_video      提交任务，返回 task_id
- check_task          查询任务状态
- wait_and_download   同步等待 + 自动下载（绘本单 clip 场景）
- verify_api_key      0 元 list 端点检测

设计原则（来自 SKILL.md 实战沉淀）：
- duration [4, 15] 硬限制（inputSchema 强制）
- watermark 默认 false（绘本场景专精，原 seedance.py 默认 true 是坑）
- duration 必须是整数（避开 argparse '7.5' → invalid int 坑）
- 已发任务 = 已扣费 = 绝不重提交（check_task docstring 必含警示）

环境变量（必填）：
- ARK_API_KEY   火山引擎 Ark API Key
"""
import os
import sys
import json
import time
import hashlib
import urllib.request
import ssl
import subprocess
from pathlib import Path
from typing import Any

# mcp SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# ===== 配置 =====
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
UGUU_UPLOAD_URL = "https://uguu.se/upload.php"
DEFAULT_MODEL = "doubao-seedance-2-0-fast-260128"
UA = "SeedanceMCP/0.1.0"

# ===== uguu 上传（spike 内部版）=====
# 完整版未来抽到 seedance_uploads.py
# 当前 spike 复刻自 scripts/uguu_ark_fallback.py + references/public-file-hosting-fallback.md

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
}


def _upload_to_uguu(local_path: str, mime_type: str) -> str:
    """上传本地文件到 uguu.se，返回 n.uguu.se 永久公网直链。
    任何类型的 mime 都行（uguu 没 chevereto 那种白名单限制）。
    """
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(f"file not found: {local_path}")

    file_size = p.stat().st_size
    # uguu 单文件 100MB 限制（实测值，留 5% buffer 写到 95MB 报错）
    if file_size > 100 * 1024 * 1024:
        raise ValueError(f"file too large ({file_size/1024/1024:.1f}MB), uguu limit 100MB")

    with open(p, "rb") as f:
        file_data = f.read()

    boundary = "----hermesmcpboundary"
    parts = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="files[]"; filename="{p.name}"\r\n'.encode(),
        f"Content-Type: {mime_type}\r\n\r\n".encode(),
        file_data, b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)

    req = urllib.request.Request(
        UGUU_UPLOAD_URL, data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "curl/8.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
        resp = json.loads(r.read())

    if not resp.get("success"):
        raise RuntimeError(f"uguu upload failed: {resp}")
    return resp["files"][0]["url"]


def _resolve_url(input_str: str, kind: str) -> str:
    """解析输入：URL 直返，本地路径上传 uguu。
    kind: image / video / audio
    """
    if input_str.startswith(("http://", "https://", "data:")):
        return input_str
    # 本地文件
    ext = Path(input_str).suffix.lower()
    mime = _MIME_BY_EXT.get(ext, f"application/octet-stream")
    return _upload_to_uguu(input_str, mime)


# ===== 火山引擎 API =====
def _get_ark_key() -> str:
    key = os.environ.get("ARK_API_KEY")
    if not key:
        raise RuntimeError("ARK_API_KEY env var not set")
    return key


def _ark_request(method: str, url: str, data: dict = None, timeout: int = 60) -> dict:
    """调火山引擎 API。"""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {_get_ark_key()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8"))


def _build_content(args: dict) -> list:
    """从 MCP 工具入参构建 Ark content 数组。
    复刻 seedance.py cmd_create 的 content 构造逻辑。
    """
    content = []

    if args.get("draft_task_id"):
        content.append({"type": "draft_task", "draft_task": {"id": args["draft_task_id"]}})
    else:
        if args.get("prompt"):
            content.append({"type": "text", "text": args["prompt"]})

        for img in args.get("ref_images") or []:
            content.append({
                "type": "image_url",
                "image_url": {"url": _resolve_url(img, "image")},
                "role": "reference_image",
            })

        if args.get("image"):
            content.append({
                "type": "image_url",
                "image_url": {"url": _resolve_url(args["image"], "image")},
                "role": "first_frame",
            })
        if args.get("last_frame"):
            content.append({
                "type": "image_url",
                "image_url": {"url": _resolve_url(args["last_frame"], "image")},
                "role": "last_frame",
            })

        for vid in args.get("video_refs") or []:
            content.append({
                "type": "video_url",
                "video_url": {"url": _resolve_url(vid, "video")},
                "role": "reference_video",
            })

        for aud in args.get("audio_refs") or []:
            content.append({
                "type": "audio_url",
                "audio_url": {"url": _resolve_url(aud, "audio")},
                "role": "reference_audio",
            })

    if not content:
        raise ValueError("must provide at least one of: prompt, ref_images, image, video_refs, audio_refs, draft_task_id")
    return content


def _build_body(args: dict) -> dict:
    """构建 Ark API 请求体。复刻 seedance.py cmd_create 的 body 构造。
    关键差异：duration 默认 5（绘本场景推荐）；watermark 默认 false（绘本场景专精）
    """
    body = {
        "model": args.get("model", DEFAULT_MODEL),
        "content": _build_content(args),
        "duration": args["duration"],
        "ratio": args.get("ratio", "16:9"),
    }
    if args.get("watermark") is not None:
        body["watermark"] = args["watermark"]
    if args.get("generate_audio") is not None:
        body["generate_audio"] = args["generate_audio"]
    if args.get("resolution"):
        body["resolution"] = args["resolution"]

    # ⚠️ 关键：官方 schema 是顶层扁平结构（audio-bugs-and-hosting.md Bug 4 沉淀）
    # seed/camera_fixed/draft/return_last_frame/service_tier 全部顶层，**不**嵌套 parameters
    # 早期 seedance.py 错用 OpenAI 兼容的 parameters 嵌套 → API 静默忽略这些字段
    for k in ("seed", "camera_fixed", "draft", "return_last_frame"):
        if args.get(k) is not None:
            body[k] = args[k]
    if args.get("service_tier"):
        body["service_tier"] = args["service_tier"]
    return body


# ===== MCP Server =====
server = Server("seedance")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="generate_video",
            description=(
                "提交 Seedance 2.0 视频生成任务，立即返回 task_id。\n"
                "已发任务 = 已扣费，绝不重提交。\n"
                "推荐用 wait_and_download 同步等待。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "文字提示词（v14 4 段式 / v15 导演版）"},
                    "ref_images": {"type": "array", "items": {"type": "string"},
                                   "description": "参考图片（角色参考）。本地路径或 URL。"},
                    "image": {"type": "string", "description": "首帧图片（first_frame）"},
                    "last_frame": {"type": "string", "description": "尾帧图片（绘本场景禁用）"},
                    "video_refs": {"type": "array", "items": {"type": "string"},
                                   "description": "参考视频（动作模仿）"},
                    "audio_refs": {"type": "array", "items": {"type": "string"},
                                   "description": "参考音频（绘本 BGM）"},
                    "duration": {"type": "integer", "minimum": 4, "maximum": 15,
                                 "description": "API 硬限制 [4,15] 秒。-1 = 自动"},
                    "ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
                              "default": "16:9"},
                    "watermark": {"type": "boolean", "default": False,
                                  "description": "绘本场景必传 false（默认 false）"},
                    "resolution": {"type": "string", "enum": ["480p", "720p", "1080p"], "default": "720p"},
                    "model": {"type": "string", "default": DEFAULT_MODEL,
                              "description": "doubao-seedance-2-0-fast（默认）/ doubao-seedance-2-0（高质量慢）"},
                    "generate_audio": {"type": "boolean"},
                    "seed": {"type": "integer", "description": "随机种子（-1=随机，复现用）"},
                    "camera_fixed": {"type": "boolean"},
                    "service_tier": {"type": "string", "enum": ["default", "flex"]},
                },
                "required": ["duration"],
            },
        ),
        types.Tool(
            name="check_task",
            description=(
                "查询任务状态（queued/running/succeeded/failed）。\n"
                "⚠️ 已发任务 = 已扣费，绝不重提交同 task_id。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string", "description": "Seedance 任务 ID（cgt- 开头）"}},
                "required": ["task_id"],
            },
        ),
        types.Tool(
            name="wait_and_download",
            description="同步等待任务完成 + 自动下载到本地（绘本单 clip 场景用）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "output_path": {"type": "string", "description": "本地保存路径（.mp4）"},
                    "timeout_sec": {"type": "integer", "default": 300, "maximum": 600},
                    "poll_interval_sec": {"type": "integer", "default": 15},
                },
                "required": ["task_id", "output_path"],
            },
        ),
        types.Tool(
            name="verify_api_key",
            description="0 元 list 端点检测 API key 有效性（不扣费）。",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "generate_video":
            body = _build_body(arguments)
            result = _ark_request("POST", ARK_BASE_URL, body, timeout=60)
            task_id = result.get("id")
            if not task_id:
                raise RuntimeError(f"no task_id in response: {result}")
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "task_id": task_id,
                    "status": result.get("status", "queued"),
                    "model": body["model"],
                    "duration": body["duration"],
                    "ratio": body["ratio"],
                    "_note": "task submitted. 已扣费。use check_task to query status.",
                }, ensure_ascii=False, indent=2),
            )]

        elif name == "check_task":
            task_id = arguments["task_id"]
            result = _ark_request("GET", f"{ARK_BASE_URL}/{task_id}", timeout=30)
            # 标准化输出
            out = {
                "task_id": task_id,
                "status": result.get("status"),
                "created_at": result.get("created_at"),
                "updated_at": result.get("updated_at"),
            }
            content = result.get("content") or {}
            if "video_url" in content:
                out["video_url"] = content["video_url"]
                out["_note"] = "video_url 24h 内有效，及时下载。"
            if result.get("error"):
                out["error"] = result["error"]
            return [types.TextContent(type="text", text=json.dumps(out, ensure_ascii=False, indent=2))]

        elif name == "wait_and_download":
            task_id = arguments["task_id"]
            output_path = arguments["output_path"]
            timeout = arguments.get("timeout_sec", 300)
            poll = arguments.get("poll_interval_sec", 15)
            deadline = time.time() + timeout

            while time.time() < deadline:
                result = _ark_request("GET", f"{ARK_BASE_URL}/{task_id}", timeout=30)
                status = result.get("status")
                if status == "succeeded":
                    video_url = result.get("content", {}).get("video_url")
                    if not video_url:
                        raise RuntimeError(f"succeeded but no video_url: {result}")
                    # 下载
                    req = urllib.request.Request(video_url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
                        data = r.read()
                    out_p = Path(output_path)
                    out_p.parent.mkdir(parents=True, exist_ok=True)
                    with open(out_p, "wb") as f:
                        f.write(data)
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({
                            "task_id": task_id,
                            "status": "succeeded",
                            "output_path": str(out_p),
                            "size_bytes": len(data),
                            "md5": hashlib.md5(data).hexdigest(),
                        }, ensure_ascii=False, indent=2),
                    )]
                elif status == "failed":
                    err = result.get("error", {})
                    raise RuntimeError(f"task failed: {err}")
                time.sleep(poll)
            raise RuntimeError(f"timeout after {timeout}s")

        elif name == "verify_api_key":
            # ⚠️ 官方 list 端点参数是 page_size（不是 limit）—— 来源：api-connection-check.md 方法 A
            try:
                result = _ark_request("GET", f"{ARK_BASE_URL}?page_size=1", timeout=15)
                return [types.TextContent(type="text", text=json.dumps({
                    "valid": True,
                    "key_prefix": _get_ark_key()[:8] + "...",
                    "response_keys": list(result.keys()) if isinstance(result, dict) else str(type(result)),
                }, ensure_ascii=False, indent=2))]
            except Exception as e:
                return [types.TextContent(type="text", text=json.dumps({
                    "valid": False,
                    "error": str(e),
                }, ensure_ascii=False, indent=2))]

        else:
            raise ValueError(f"unknown tool: {name}")

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(e), "tool": name, "arguments": arguments}, ensure_ascii=False, indent=2),
        )]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
