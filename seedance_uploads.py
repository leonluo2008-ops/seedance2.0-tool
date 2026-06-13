"""
seedance_uploads.py · 共享业务函数库
====================================

抽离自 mcp_server.py + seedance.py 老的 chevereto 代码。

**单真源原则**：seedance.py（老 CLI） + mcp_server.py（MCP server）
两个入口都 import 本模块 —— 任何上传/解析/Ark 请求逻辑改一处即可。

## 函数清单

上传层：
  - upload_to_uguu(local_path, mime_type) 同步版（urllib）
  - upload_to_uguu_async(local_path, mime_type) 异步版（httpx, 真并发）
  - resolve_url(input_str, kind) 同步解析
  - resolve_url_async(input_str, kind) 异步解析
  - resolve_all_inputs_async(args) 并发上传所有本地文件

API 层：
  - get_ark_key() 读 ARK_API_KEY
  - ark_request(method, url, data, timeout) 同步（urllib）
  - ark_request_async(method, url, data, timeout) 异步（httpx）
  - get_http_client() 懒加载 httpx 客户端

构造层：
  - build_content(args, resolved_urls=None) 构造 Ark content 数组
  - build_body(args, resolved_urls=None) 构造 Ark body（含 watermark 字符串→bool 映射）

下载层：
  - download_video(url, output_path) 同步下载（urllib）

环境变量：
  - ARK_API_KEY         必填，火山引擎鉴权

变更记录：
  - 2026-06-13 删除本地 cache 机制（cache_task / read_cache / parse_url_expires / check_url_expired /
    CACHE_DIR / CACHE_FILE / CACHE_TTL_FALLBACK_SEC 全部移除）
    官方文档（volcengine.com/docs/82379/1520757）仅 2 个权威端点，本地 cache 无存在必要
  - 2026-06-11 v1.0 从 mcp_server.py + seedance.py 抽出
"""
import os
import sys
import json
import time
import asyncio
import hashlib
import ssl
import urllib.request
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # 同步版（seedance.py 老 CLI）不需要 httpx


# ===== 常量 =====

ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
UGUU_UPLOAD_URL = "https://uguu.se/upload.php"
DEFAULT_MODEL = "doubao-seedance-2-0-fast-260128"
UA = "SeedanceMCP/0.1.0"

# CACHE_DIR / CACHE_FILE / CACHE_TTL_FALLBACK_SEC 已删（2026-06-13 移除本地 cache 机制）
# 官方文档（volcengine.com/docs/82379/1520757）仅提供 2 个权威端点，不需要本地 cache


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


def _build_opener(url: str = ""):
    """按 URL host 决定是否走代理。返回 None = 让调用方走 urlopen(req, context=...) 路径。

    已知坑（spike 006 沉淀）：
    - HTTPSHandler(context=...) 在 Python 3.11.15 跟 uguu.se 握手会 SSL EOF
    - urlopen(req, context=ssl.create_default_context()) 正常
    - 所以**所有路径**都让调用方走 urlopen，opener 只为走代理 ark API 用
    """
    proxy_url = ""
    for env_k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(env_k, "").strip()
        if v:
            proxy_url = v
            break

    if not proxy_url:
        return None

    if "uguu.se" in url:
        return None  # uguu.se 走代理会 SSL EOF

    # 火山引擎 / 其他走代理
    proxy_handler = urllib.request.ProxyHandler({
        "http": proxy_url,
        "https": proxy_url,
    })
    return urllib.request.build_opener(proxy_handler)


def _smart_urlopen(req, timeout: int = 60, context=None):
    """智能 urlopen：按 host 选 proxy + 显式 ssl context（解决 uguu.se SSL EOF 坑）。"""
    if context is None:
        context = ssl.create_default_context()
    opener = _build_opener(req.full_url)
    if opener is not None:
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=context)


# ===== uguu 上传（同步）=====

def upload_to_uguu(local_path: str, mime_type: str) -> str:
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
    opener = _build_opener(UGUU_UPLOAD_URL)
    if opener is not None:
        with opener.open(req, timeout=120) as r:
            resp = json.loads(r.read())
    else:
        # 不挂代理：传 ProxyHandler({}) 强制不走 env proxy（避开 SSL EOF）+ 显式 ssl context
        ctx = ssl.create_default_context()
        no_proxy_opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),  # 显式空 proxy，覆盖 env
            urllib.request.HTTPSHandler(context=ctx),
        )
        with no_proxy_opener.open(req, timeout=120) as r:
            resp = json.loads(r.read())

    if not resp.get("success"):
        raise RuntimeError(f"uguu upload failed: {resp}")
    return resp["files"][0]["url"]


def resolve_url(input_str: str, kind: str) -> str:
    """解析输入（同步版）：URL 直返，本地路径上传 uguu。
    kind: image / video / audio（仅用于语义，无逻辑影响）
    """
    if input_str.startswith(("http://", "https://", "data:")):
        return input_str
    ext = Path(input_str).suffix.lower()
    mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
    return upload_to_uguu(input_str, mime)


# ===== uguu 上传（异步 / httpx）=====

_http_client: "httpx.AsyncClient | None" = None


async def get_http_client():
    """懒加载 httpx 客户端（spike 004：常驻，**不**每个请求新建）。"""
    global _http_client
    if httpx is None:
        raise RuntimeError("httpx not installed; pip install httpx")
    if _http_client is None:
        _http_client = httpx.AsyncClient(  # type: ignore
            timeout=httpx.Timeout(timeout=60.0, connect=10.0),  # type: ignore
            headers={"User-Agent": UA},
        )
    return _http_client


async def upload_to_uguu_async(local_path: str, mime_type: str) -> str:
    """异步版 uguu 上传（spike 004：用 httpx 替代 urllib + subprocess）。

    跟 upload_to_uguu 行为一致：
    - 任何类型 mime 都行
    - 单文件 100MB 上限
    - 返回 n.uguu.se 永久公网直链
    """
    if httpx is None:
        raise RuntimeError("httpx not installed; pip install httpx")

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

    client = await get_http_client()  # type: ignore
    try:
        resp = await client.post(  # type: ignore
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
    except httpx.HTTPStatusError as e:  # type: ignore
        raise RuntimeError(f"uguu upload HTTP {e.response.status_code}: {e.response.text[:200]}")
    except httpx.TimeoutException as e:  # type: ignore
        raise RuntimeError(f"uguu upload timeout: {e}")
    except httpx.RequestError as e:  # type: ignore
        raise RuntimeError(f"uguu upload request error: {e}")

    if not result.get("success"):
        raise RuntimeError(f"uguu upload failed: {result}")
    return result["files"][0]["url"]


async def resolve_url_async(input_str: str, kind: str) -> str:
    """解析输入（异步版）：URL 直返，本地路径 async 上传 uguu。"""
    if input_str.startswith(("http://", "https://", "data:")):
        return input_str
    ext = Path(input_str).suffix.lower()
    mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
    return await upload_to_uguu_async(input_str, mime)


async def resolve_all_inputs_async(args: dict) -> dict:
    """并发上传所有本地文件到 uguu，返回 {原始 input_str: uguu_url} 映射。

    已经被 build_content 内部用，**不**阻塞事件循环。
    """
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
    results = await asyncio.gather(*[resolve_url_async(p, k) for p, k in unique])
    for (p, k), url in zip(unique, results):
        seen[p] = url
    return seen


# ===== 火山引擎 API =====

def get_ark_key() -> str:
    """读 ARK_API_KEY。失败抛 RuntimeError（不 sys.exit，让调用方处理）。"""
    key = os.environ.get("ARK_API_KEY")
    if not key:
        raise RuntimeError("ARK_API_KEY env var not set")
    return key


def ark_request(method: str, url: str, data: dict = None, timeout: int = 60) -> dict:
    """调火山引擎 API（同步）。失败抛 RuntimeError（**不** sys.exit）。"""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {get_ark_key()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
    opener = _build_opener(url)
    try:
        if opener is not None:
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        # 不挂代理：传 ProxyHandler({}) 强制不走 env proxy + 显式 ssl context
        ctx = ssl.create_default_context()
        no_proxy_opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),  # 显式空 proxy，覆盖 env
            urllib.request.HTTPSHandler(context=ctx),
        )
        with no_proxy_opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        try:
            err = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            err = body
        raise RuntimeError(f"API Error (HTTP {e.code}): {err}")
    except Exception as e:
        raise RuntimeError(f"API Error: {e}")

async def ark_request_async(method: str, url: str, data: dict = None, timeout: int = 60) -> dict:
    """异步版调火山引擎 API（httpx）。"""
    if httpx is None:
        raise RuntimeError("httpx not installed; pip install httpx")
    if httpx is None:
        raise RuntimeError("httpx not installed; pip install httpx")
    client = await get_http_client()  # type: ignore
    headers = {
        "Authorization": f"Bearer {get_ark_key()}",
        "Content-Type": "application/json",
    }
    try:
        resp = await client.request(
            method, url,
            json=data,
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:  # type: ignore
        body = e.response.text[:500] if e.response else ""
        try:
            err = e.response.json().get("error", {}).get("message", body)
        except Exception:
            err = body
        raise RuntimeError(f"API Error (HTTP {e.response.status_code}): {err}")
    except httpx.TimeoutException as e:  # type: ignore
        raise RuntimeError(f"API timeout after {timeout}s: {e}")
    except httpx.RequestError as e:  # type: ignore
        raise RuntimeError(f"API request error: {e}")


# ===== Ark content + body 构造 =====

def build_content(args: dict, resolved_urls: dict = None) -> list:
    """从工具入参构建 Ark content 数组。

    resolved_urls: dict，key 是原始 input_str（路径或 URL），value 是已上传的 uguu URL
                   —— 让调用方异步上传完后传进来，避免 build_content 内部 IO 阻塞
    """
    resolved_urls = resolved_urls or {}

    def _r(input_str: str, kind: str) -> str:
        """从 resolved_urls 取已上传 URL；缺失则回退到 input_str（**仅**对已是 URL 的情况）"""
        if input_str in resolved_urls:
            return resolved_urls[input_str]
        if input_str.startswith(("http://", "https://", "data:")):
            return input_str
        raise RuntimeError(f"resolved_urls 缺 {input_str}（{kind}），必须先上传")

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


def build_body(args: dict, resolved_urls: dict = None) -> dict:
    """构建 Ark API 请求体。

    关键差异（vs 老 seedance.py）：
    - duration 默认 5（绘本场景推荐）
    - watermark 默认 false（绘本场景专精；老 seedance.py 默认 true 是坑）
    - watermark 字符串枚举（'none'/'platform'/'seedance_ai'）→ bool 映射
    - generate_audio 默认 false（绘本无 BGM）
    - seed/camera_fixed/draft/return_last_frame/service_tier 全部顶层（**不**嵌套 parameters）
    """
    body = {
        "model": args.get("model", DEFAULT_MODEL),
        "content": build_content(args, resolved_urls=resolved_urls),
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
        body["generate_audio"] = False
    if args.get("resolution"):
        body["resolution"] = args["resolution"]

    # 官方 schema 是顶层扁平结构（audio-bugs-and-hosting.md Bug 4 沉淀）
    for k in ("seed", "camera_fixed", "draft", "return_last_frame"):
        if args.get(k) is not None:
            body[k] = args[k]
    if args.get("service_tier"):
        body["service_tier"] = args["service_tier"]
    return body


# ===== 视频下载 =====

def download_video(url: str, output_path: str) -> bool:
    """同步下载视频（urllib）。"""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        opener = _build_opener(url)
        if opener is not None:
            with opener.open(req, timeout=120) as resp:
                content_type = resp.headers.get("Content-Type", "")
                ext = ".mp4"
                if "video/mp4" in content_type:
                    ext = ".mp4"
                elif "video/webm" in content_type:
                    ext = ".webm"

                out_p = Path(output_path)
                if out_p.suffix not in (".mp4", ".webm", ".mov"):
                    output_path = str(out_p.with_suffix(ext))

                with open(output_path, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                return True
        # 不挂代理：传 ProxyHandler({}) 强制不走 env proxy + 显式 ssl context
        ctx = ssl.create_default_context()
        no_proxy_opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ctx),
        )
        with no_proxy_opener.open(req, timeout=120) as resp:
            content_type = resp.headers.get("Content-Type", "")
            ext = ".mp4"
            if "video/mp4" in content_type:
                ext = ".mp4"
            elif "video/webm" in content_type:
                ext = ".webm"

            out_p = Path(output_path)
            if out_p.suffix not in (".mp4", ".webm", ".mov"):
                output_path = str(out_p.with_suffix(ext))

            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"  Download failed: {e}", file=sys.stderr)
        return False


async def download_video_async(url: str, output_path: str) -> bool:
    """异步下载视频（httpx）。"""
    if httpx is None:
        raise RuntimeError("httpx not installed; pip install httpx")
    client = await get_http_client()  # type: ignore
    try:
        resp = await client.get(url, timeout=120)  # type: ignore
        resp.raise_for_status()
        data = resp.content
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  Download failed: {e}", file=sys.stderr)
        return False


# ===== 进程退出时关闭 httpx 客户端 =====

async def close_http_client():
    """关闭常驻 httpx 客户端。main() 退出前调。"""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
