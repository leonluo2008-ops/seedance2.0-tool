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
import asyncio
import re
import hashlib
import urllib.request
import ssl
import subprocess
import httpx
from pathlib import Path
from typing import Any

# ===== 任务本地缓存（铁律 30 升级：append-only JSONL + 平台 URL TTL 同步）=====
# 缓存文件位置：MCP server 持久目录，跨 session/重启可查
# 写入时机：generate_video 成功 / check_task 拿到 succeeded / wait_and_download 完成
# TTL 策略：从 video_url 的 X-Tos-Expires 字段读，**不**硬编码 24h（未来平台改 1h 自动适配）
CACHE_DIR = Path(os.environ.get("SEEDANCE_CACHE_DIR", "/home/luo/.cache/seedance-mcp"))
CACHE_FILE = CACHE_DIR / "tasks.jsonl"
CACHE_TTL_FALLBACK_SEC = 24 * 3600  # 平台 URL TTL 字段缺失时的兜底（24h）


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _parse_url_expires(video_url: str) -> int:
    """从 video_url query string 解析 X-Tos-Expires（秒）。
    失败时返回 fallback 24h。"""
    if not video_url:
        return CACHE_TTL_FALLBACK_SEC
    m = re.search(r'X-Tos-Expires=(\d+)', video_url)
    if m:
        try:
            return int(m.group(1) or 0) or CACHE_TTL_FALLBACK_SEC
        except (ValueError, TypeError):
            pass
    return CACHE_TTL_FALLBACK_SEC


def _cache_task(task_id: str, status: str, video_url: "str | None" = None, **extra):
    """写一条任务到本地 JSONL 缓存。
    字段：task_id / status / video_url / url_ttl_sec / cached_at / url_expires_at / extras
    """
    _ensure_cache_dir()
    now = int(time.time())
    record = {
        "task_id": task_id,
        "status": status,
        "cached_at": now,
        "cached_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        **extra,
    }
    if video_url:
        ttl = _parse_url_expires(video_url)
        record["video_url"] = video_url
        record["url_ttl_sec"] = ttl
        record["url_expires_at"] = now + ttl
        record["url_expires_at_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + ttl)
        )
    # append-only, 一行一记录
    with open(CACHE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _read_cache(limit: int = 50) -> list:
    """读本地缓存（最新 limit 条）。相同 task_id 取最后一条（去重）。"""
    if not CACHE_FILE.exists():
        return []
    seen = {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            seen[rec["task_id"]] = rec
    # 按 cached_at 倒序
    return sorted(seen.values(), key=lambda r: r.get("cached_at", 0), reverse=True)[:limit]


def _check_url_expired(video_url: str) -> bool:
    """检查 video_url 是否已过期（用本地时间，不调 API）。"""
    if not video_url:
        return True
    ttl = _parse_url_expires(video_url)
    # video_url 里的 X-Tos-Date 是签名时刻，但我们关心"现在距离签名过了多久"
    # 简化：直接比较 ttl 秒数（保守——如果签发到现在已超 ttl，就当过期）
    # 实际更准应该用 X-Tos-Date + X-Tos-Expires
    m_date = re.search(r'X-Tos-Date=(\d{8}T\d{6}Z)', video_url)
    if m_date:
        try:
            signed_at = time.mktime(time.strptime(m_date.group(1), "%Y%m%dT%H%M%SZ"))
            return (time.time() - signed_at) > ttl
        except ValueError:
            pass
    # 兜底：保守认为已过期
    return True

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
    """解析输入：URL 直返，本地路径上传 uguu（同步，保留兼容）。
    kind: image / video / audio
    """
    if input_str.startswith(("http://", "https://", "data:")):
        return input_str
    # 本地文件
    ext = Path(input_str).suffix.lower()
    mime = _MIME_BY_EXT.get(ext, f"application/octet-stream")
    return _upload_to_uguu(input_str, mime)


async def _upload_to_uguu_async(local_path: str, mime_type: str) -> str:
    """异步版 uguu 上传（spike 004：用 httpx 替代 urllib + subprocess）。

    跟 _upload_to_uguu 行为一致：
    - 任何类型 mime 都行（uguu 没 chevereto 白名单）
    - 单文件 100MB 上限
    - 返回 n.uguu.se 永久公网直链
    """
    p = Path(local_path)
    if not p.exists():
        raise FileNotFoundError(f"file not found: {local_path}")

    file_size = p.stat().st_size
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

    client = await _get_http_client()
    try:
        resp = await client.post(
            UGUU_UPLOAD_URL,
            content=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "curl/8.0",  # 沿用 sync 版的 UA（uguu 识别）
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"uguu upload HTTP {e.response.status_code}: {e.response.text[:200]}")
    except httpx.TimeoutException as e:
        raise RuntimeError(f"uguu upload timeout: {e}")
    except httpx.RequestError as e:
        raise RuntimeError(f"uguu upload request error: {e}")

    if not result.get("success"):
        raise RuntimeError(f"uguu upload failed: {result}")
    return result["files"][0]["url"]


async def _resolve_url_async(input_str: str, kind: str) -> str:
    """解析输入（异步版）：URL 直返，本地路径 async 上传 uguu。
    kind: image / video / audio
    """
    if input_str.startswith(("http://", "https://", "data:")):
        return input_str
    ext = Path(input_str).suffix.lower()
    mime = _MIME_BY_EXT.get(ext, f"application/octet-stream")
    return await _upload_to_uguu_async(input_str, mime)


async def _resolve_all_inputs_async(args: dict) -> dict:
    """并发上传所有本地文件到 uguu，返回 {原始 input_str: uguu_url} 映射。
    已经被 _build_content 内部用，**不**阻塞事件循环。
    """
    # 收集所有需要上传的本地路径（URL 直接跳过）
    paths_to_upload = []
    for key, kind in [
        ("ref_images", "image"),
        ("image", "image"),
        ("last_frame", "image"),
        ("video_refs", "video"),
        ("audio_refs", "audio"),
    ]:
        v = args.get(key)
        if not v:
            continue
        items = v if isinstance(v, list) else [v]
        for item in items:
            if not item.startswith(("http://", "https://", "data:")):
                paths_to_upload.append((item, kind))

    if not paths_to_upload:
        return {}

    # 并发上传（不同路径可并行；同一路径 dedup）
    seen = {}
    unique = list({p: k for p, k in paths_to_upload}.items())
    results = await asyncio.gather(*[_resolve_url_async(p, k) for p, k in unique])
    for (p, k), url in zip(unique, results):
        seen[p] = url
    return seen


# ===== 火山引擎 API =====
def _get_ark_key() -> str:
    key = os.environ.get("ARK_API_KEY")
    if not key:
        raise RuntimeError("ARK_API_KEY env var not set")
    return key


def _ark_request(method: str, url: str, data: dict = None, timeout: int = 60) -> dict:
    """调火山引擎 API（同步，保留兼容）。"""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {_get_ark_key()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8"))


# 别名 + 常驻 httpx 客户端（spike 004：真异步 IO）
_ark_request_sync = _ark_request
_http_client: "httpx.AsyncClient | None" = None


async def _get_http_client() -> httpx.AsyncClient:
    """懒加载 httpx 客户端（MCP server 常驻，**不**每个请求新建）。"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=60.0, connect=10.0),
            headers={"User-Agent": UA},
        )
    return _http_client


async def _ark_request_async(method: str, url: str, data: dict = None, timeout: int = 60) -> dict:
    """异步版调火山引擎 API（httpx）。

    跟同步版 _ark_request 行为一致：
    - Authorization Bearer ARK_API_KEY
    - Content-Type application/json
    - 失败抛 RuntimeError（不 sys.exit，因为 call_tool 顶层 except）
    """
    client = await _get_http_client()
    headers = {
        "Authorization": f"Bearer {_get_ark_key()}",
        "Content-Type": "application/json",
    }
    try:
        resp = await client.request(
            method, url,
            json=data,  # httpx 自动 json 序列化（替代手动 json.dumps）
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
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


def _build_content(args: dict, resolved_urls: dict = None) -> list:
    """从 MCP 工具入参构建 Ark content 数组。
    复刻 seedance.py cmd_create 的 content 构造逻辑。

    resolved_urls: dict，key 是原始 input_str（路径或 URL），value 是已上传的 uguu URL
                   —— 让 call_tool 异步上传完后传进来，避免 _build_content 内部 IO 阻塞
    """
    resolved_urls = resolved_urls or {}

    def _r(input_str: str, kind: str) -> str:
        """从 resolved_urls 取已上传 URL；缺失则回退到 input_str（**仅**对已是 URL 的情况）"""
        if input_str in resolved_urls:
            return resolved_urls[input_str]
        # ⚠️ 兜底：传入的 resolved_urls 漏了，但 input_str 是 URL（不会触发 uguu）
        if input_str.startswith(("http://", "https://", "data:")):
            return input_str
        # 这种情况应该是 call_tool 漏上传，**不**兜底（让用户看到错误）
        raise RuntimeError(f"resolved_urls 缺 {input_str}（{kind}），call_tool 必须先上传")

    content = []

    if args.get("draft_task_id"):
        content.append({"type": "draft_task", "draft_task": {"id": args["draft_task_id"]}})
    else:
        if args.get("prompt"):
            content.append({"type": "text", "text": args["prompt"]})

        for img in args.get("ref_images") or []:
            content.append({
                "type": "image_url",
                "image_url": {"url": _r(img, "image")},
                "role": "reference_image",
            })

        if args.get("image"):
            content.append({
                "type": "image_url",
                "image_url": {"url": _r(args["image"], "image")},
                "role": "first_frame",
            })
        if args.get("last_frame"):
            content.append({
                "type": "image_url",
                "image_url": {"url": _r(args["last_frame"], "image")},
                "role": "last_frame",
            })

        for vid in args.get("video_refs") or []:
            content.append({
                "type": "video_url",
                "video_url": {"url": _r(vid, "video")},
                "role": "reference_video",
            })

        for aud in args.get("audio_refs") or []:
            content.append({
                "type": "audio_url",
                "audio_url": {"url": _r(aud, "audio")},
                "role": "reference_audio",
            })

    if not content:
        raise ValueError("must provide at least one of: prompt, ref_images, image, video_refs, audio_refs, draft_task_id")
    return content


def _build_body(args: dict, resolved_urls: dict = None) -> dict:
    """构建 Ark API 请求体。复刻 seedance.py cmd_create 的 body 构造。
    关键差异：duration 默认 5（绘本场景推荐）；watermark 默认 false（绘本场景专精）

    resolved_urls: 透传给 _build_content（避免重复上传）
    """
    body = {
        "model": args.get("model", DEFAULT_MODEL),
        "content": _build_content(args, resolved_urls=resolved_urls),
        "duration": args["duration"],
        "ratio": args.get("ratio", "16:9"),
    }
    # watermark 字符串枚举 → API bool 字段映射
    # 'none' / 'platform' → false（不加 AI 水印）
    # 'seedance_ai' → true（加 Seedance 官方 AI 标识）
    watermark = args.get("watermark", "none")
    if watermark == "seedance_ai":
        body["watermark"] = True
    elif watermark in ("none", "platform"):
        body["watermark"] = False
    # generate_audio 绘本默认 false（避免莫名说话声）
    if "generate_audio" in args:
        body["generate_audio"] = args["generate_audio"]
    else:
        body["generate_audio"] = False  # 绘本场景默认
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
                "提交 Seedance 2.0 视频生成任务，立即返回 task_id。"
                "已发任务 = 已扣费，绝不重提交。推荐用 wait_and_download 同步等待。\n\n"
                "[绘本/动画场景推荐参数]\n"
                "  - watermark: 'none'（默认，无 AI 水印）\n"
                "  - duration: 按镜头数算法（5s=2-3 镜 / 8s=3-4 镜 / 12s=4-5 镜 / 14s=5-6 镜）\n"
                "  - ratio: '16:9'（横屏绘本）/ '9:16'（抖音/小红书竖屏）\n"
                "  - generate_audio: false（绘本默认无 BGM，避免莫名说话声）\n"
                "  - prompt: 必带末尾约束段（无人声/无歌唱/无配音/无朗读）\n"
                "  - 多图参考用 ref_images（不 image+last_frame，绘本首尾帧范式禁用）\n\n"
                "[通用/社媒场景推荐参数]\n"
                "  - watermark: 'platform'（不加 AI 水印，自己后期加平台水印）\n"
                "  - duration: 8-12s（社媒最佳）\n"
                "  - ratio: '9:16'（抖音/小红书）/ '1:1'（朋友圈）\n"
                "  - generate_audio: 默认即可（社媒视频通常自带 BGM）\n\n"
                "⚠️ 硬限制\n"
                "  - duration 必在 [4, 15]（API 拒绝范围外）\n"
                "  - duration 必为整数（避开 argparse '7.5' → invalid int 老坑）\n"
                "  - 已发任务 = 已扣费，绝不重提交同 task_id"
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
                                 "description": "API 硬限制 [4,15] 秒。绘本按镜头数算法选（5s=2-3 / 8s=3-4 / 12s=4-5 / 14s=5-6）"},
                    "ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
                              "default": "16:9",
                              "description": "画幅。绘本 16:9 / 抖音 9:16 / 朋友圈 1:1"},
                    "watermark": {
                        "type": "string",
                        "enum": ["none", "platform", "seedance_ai"],
                        "default": "none",
                        "description": (
                            "水印策略：\n"
                            "  - 'none'（默认，绘本/动画）— 不加任何水印\n"
                            "  - 'platform'（通用/社媒）— 不加 AI 水印，自己后期加平台水印\n"
                            "  - 'seedance_ai'（测试/审计）— 加 Seedance 官方 AI 标识"
                        ),
                    },
                    "generate_audio": {
                        "type": "boolean",
                        "default": False,
                        "description": "绘本场景必传 false（避免莫名说话声）；社媒场景可不传（默认走模型策略）",
                    },
                    "resolution": {"type": "string", "enum": ["480p", "720p", "1080p"], "default": "720p",
                                   "description": "spike 用 480p 省钱；生产用 720p"},
                    "model": {"type": "string", "default": DEFAULT_MODEL,
                              "description": "doubao-seedance-2-0-fast（默认）/ doubao-seedance-2-0（高质量慢）"},
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
        types.Tool(
            name="list_recent_tasks",
            description=(
                "查询本地缓存的历史任务（不调 API，0 元）。\n"
                "⚠️ 已发任务 = 已扣费，绝不重提交。本工具用于查过往 task_id。\n\n"
                "TTL 策略：本地缓存的视频 URL 保留期 **跟平台一致** —— "
                "从 video_url 的 X-Tos-Expires 字段读取（当前 86400s = 24h），"
                "如果未来平台改 1h，本工具自动同步。\n\n"
                "返回字段：\n"
                "  - task_id / status / cached_at\n"
                "  - video_url / url_ttl_sec / url_expires_at / url_expired_by_local_clock\n"
                "  - local_path（如果之前 wait_and_download 过）\n"
                "  - duration / ratio / resolution / model"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20, "maximum": 100,
                              "description": "返回最近 N 条"},
                    "include_expired_urls": {"type": "boolean", "default": True,
                                             "description": "是否包含 url_expired_by_local_clock=true 的记录"},
                },
            },
        ),
        types.Tool(
            name="download_cached",
            description=(
                "用本地缓存的 video_url 下载（不调 list 端点）。\n"
                "⚠️ URL 可能已过期——若已过期自动 fallback 到 check_task 重新拿新 URL。\n"
                "推荐用法：先 list_recent_tasks → 拿 task_id → download_cached"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "从 list_recent_tasks 拿到的 task_id"},
                    "output_path": {"type": "string", "description": "本地保存路径（.mp4）"},
                },
                "required": ["task_id", "output_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "generate_video":
            # ⚠️ 先并发上传所有本地文件到 uguu（spike 004：真异步）
            resolved_urls = await _resolve_all_inputs_async(arguments)
            body = _build_body(arguments, resolved_urls=resolved_urls)
            result = await _ark_request_async("POST", ARK_BASE_URL, body, timeout=60)
            task_id = result.get("id")
            if not task_id:
                raise RuntimeError(f"no task_id in response: {result}")
            # ⚠️ 写本地缓存（铁律 30 升级：已发任务 = 已扣费，本地必须有记录）
            _cache_task(
                task_id=task_id,
                status=result.get("status", "queued"),
                duration=body["duration"],
                ratio=body["ratio"],
                resolution=body.get("resolution"),
                model=body["model"],
                source="generate_video",
            )
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
            result = await _ark_request_async("GET", f"{ARK_BASE_URL}/{task_id}", timeout=30)
            # 标准化输出
            out = {
                "task_id": task_id,
                "status": result.get("status"),
                "created_at": result.get("created_at"),
                "updated_at": result.get("updated_at"),
            }
            content = result.get("content") or {}
            video_url = content.get("video_url")
            if video_url:
                out["video_url"] = video_url
                ttl = _parse_url_expires(video_url)
                out["url_ttl_sec"] = ttl
                out["url_expired_by_local_clock"] = _check_url_expired(video_url)
                out["_note"] = f"video_url TTL={ttl}s（来自 X-Tos-Expires），及时下载。"
            if result.get("error"):
                out["error"] = result["error"]
            # ⚠️ 写本地缓存（铁律 30 升级：跨 session 可查）
            _cache_task(
                task_id=task_id,
                status=result.get("status", "unknown"),
                video_url=video_url,
                duration=result.get("duration"),
                ratio=result.get("ratio"),
                resolution=result.get("resolution"),
            )
            return [types.TextContent(type="text", text=json.dumps(out, ensure_ascii=False, indent=2))]

        elif name == "wait_and_download":
            task_id = arguments["task_id"]
            output_path = arguments["output_path"]
            timeout = arguments.get("timeout_sec", 300)
            poll = arguments.get("poll_interval_sec", 15)
            deadline = time.time() + timeout

            while time.time() < deadline:
                result = await _ark_request_async("GET", f"{ARK_BASE_URL}/{task_id}", timeout=30)
                status = result.get("status")
                if status == "succeeded":
                    video_url = result.get("content", {}).get("video_url")
                    if not video_url:
                        raise RuntimeError(f"succeeded but no video_url: {result}")
                    # 下载（用 httpx async，替代 sync urllib）
                    client = await _get_http_client()
                    dl_resp = await client.get(video_url, timeout=120)
                    dl_resp.raise_for_status()
                    data = dl_resp.content
                    out_p = Path(output_path)
                    out_p.parent.mkdir(parents=True, exist_ok=True)
                    with open(out_p, "wb") as f:
                        f.write(data)
                    # ⚠️ 写本地缓存（铁律 30 升级）
                    _cache_task(
                        task_id=task_id,
                        status="succeeded",
                        video_url=video_url,
                        duration=result.get("duration"),
                        ratio=result.get("ratio"),
                        resolution=result.get("resolution"),
                        local_path=str(out_p),
                        size_bytes=len(data),
                        md5=hashlib.md5(data).hexdigest(),
                    )
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({
                            "task_id": task_id,
                            "status": "succeeded",
                            "output_path": str(out_p),
                            "size_bytes": len(data),
                            "md5": hashlib.md5(data).hexdigest(),
                            "url_ttl_sec": _parse_url_expires(video_url),
                        }, ensure_ascii=False, indent=2),
                    )]
                elif status == "failed":
                    err = result.get("error", {})
                    # 失败也写缓存（"已发任务 = 已扣费"，不要让 agent 误以为没跑过）
                    _cache_task(task_id=task_id, status="failed", error=err)
                    raise RuntimeError(f"task failed: {err}")
                time.sleep(poll)
            raise RuntimeError(f"timeout after {timeout}s")

        elif name == "verify_api_key":
            # ⚠️ 官方 list 端点参数是 page_size（不是 limit）—— 来源：api-connection-check.md 方法 A
            try:
                result = await _ark_request_async("GET", f"{ARK_BASE_URL}?page_size=1", timeout=15)
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

        elif name == "list_recent_tasks":
            limit = arguments.get("limit", 20)
            include_expired = arguments.get("include_expired_urls", True)
            records = _read_cache(limit=limit)
            if not include_expired:
                records = [r for r in records if not r.get("url_expired_by_local_clock", False)]
            # 标准化 + 加过期标记
            for r in records:
                if r.get("video_url"):
                    r["url_expired_by_local_clock"] = _check_url_expired(r["video_url"])
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "count": len(records),
                    "cache_file": str(CACHE_FILE),
                    "tasks": records,
                }, ensure_ascii=False, indent=2),
            )]

        elif name == "download_cached":
            task_id = arguments["task_id"]
            output_path = arguments["output_path"]
            # 从缓存拿 video_url
            cache = {r["task_id"]: r for r in _read_cache(limit=200)}
            rec = cache.get(task_id)
            video_url = rec.get("video_url") if rec else None
            url_expired = _check_url_expired(video_url) if video_url else True

            # fallback：如果缓存没有 / URL 已过期 → 调 check_task 拿新 URL
            if not video_url or url_expired:
                result = await _ark_request_async("GET", f"{ARK_BASE_URL}/{task_id}", timeout=30)
                video_url = result.get("content", {}).get("video_url")
                if not video_url:
                    raise RuntimeError(f"task {task_id} 无 video_url（可能仍 running/failed: {result.get('status')}）")
                # 更新缓存
                _cache_task(
                    task_id=task_id,
                    status=result.get("status", "unknown"),
                    video_url=video_url,
                    duration=result.get("duration"),
                    ratio=result.get("ratio"),
                    resolution=result.get("resolution"),
                )
                fallback_used = True
            else:
                fallback_used = False

            # 下载（用 httpx async，替代 sync urllib）
            client = await _get_http_client()
            dl_resp = await client.get(video_url, timeout=120)
            dl_resp.raise_for_status()
            data = dl_resp.content
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "wb") as f:
                f.write(data)
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "task_id": task_id,
                    "output_path": str(out_p),
                    "size_bytes": len(data),
                    "md5": hashlib.md5(data).hexdigest(),
                    "url_ttl_sec": _parse_url_expires(video_url),
                    "url_was_expired_before_download": url_expired,
                    "api_fallback_used": fallback_used,
                    "_note": "url 过期时已自动 fallback 到 check_task 拿新 URL。",
                }, ensure_ascii=False, indent=2),
            )]

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
