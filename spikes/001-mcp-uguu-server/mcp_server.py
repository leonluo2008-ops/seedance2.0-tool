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


# ===== 业务函数委托给 seedance_uploads（单真源）=====
# 所有上传 / Ark API / 缓存 / body 构造逻辑都在 ../seedance_uploads.py
# 本文件只在 MCP protocol 层面加壳（list_tools / call_tool）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import seedance_uploads as U  # noqa: E402


def _ensure_cache_dir():
    return U._ensure_cache_dir()


def _parse_url_expires(video_url: str) -> int:
    return U.parse_url_expires(video_url)


def _cache_task(task_id: str, status: str, video_url: "str | None" = None, **extra):
    return U.cache_task(task_id, status, video_url=video_url, **extra)


def _read_cache(limit: int = 50) -> list:
    return U.read_cache(limit)


def _check_url_expired(video_url: str) -> bool:
    return U.check_url_expired(video_url)


def _upload_to_uguu(local_path: str, mime_type: str) -> str:
    return U.upload_to_uguu(local_path, mime_type)


def _resolve_url(input_str: str, kind: str) -> str:
    return U.resolve_url(input_str, kind)


async def _upload_to_uguu_async(local_path: str, mime_type: str) -> str:
    return await U.upload_to_uguu_async(local_path, mime_type)


async def _resolve_url_async(input_str: str, kind: str) -> str:
    return await U.resolve_url_async(input_str, kind)


async def _resolve_all_inputs_async(args: dict) -> dict:
    return await U.resolve_all_inputs_async(args)


def _get_ark_key() -> str:
    return U.get_ark_key()


def _ark_request(method: str, url: str, data: dict = None, timeout: int = 60) -> dict:
    return U.ark_request(method, url, data, timeout)


async def _get_http_client() -> "httpx.AsyncClient":
    return await U.get_http_client()


async def _ark_request_async(method: str, url: str, data: dict = None, timeout: int = 60) -> dict:
    return await U.ark_request_async(method, url, data, timeout)


def _build_content(args: dict, resolved_urls: dict = None) -> list:
    return U.build_content(args, resolved_urls=resolved_urls)


def _build_body(args: dict, resolved_urls: dict = None) -> dict:
    return U.build_body(args, resolved_urls=resolved_urls)

# mcp SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# ===== 配置（保留别名，引用 seedance_uploads 单真源）=====
# ⚠️ 这些常量名保留供 list_tools / call_tool 内部 reference，
# 真源在 ../seedance_uploads.py。
ARK_BASE_URL = U.ARK_BASE_URL
UGUU_UPLOAD_URL = U.UGUU_UPLOAD_URL
DEFAULT_MODEL = U.DEFAULT_MODEL
UA = U.UA


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
