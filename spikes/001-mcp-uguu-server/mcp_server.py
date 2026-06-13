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

# ===== 业务函数委托给 seedance_uploads（单真源）=====
# 所有上传 / Ark API / body 构造逻辑都在 ../seedance_uploads.py
# 本文件只在 MCP protocol 层面加壳（list_tools / call_tool）
# 2026-06-13 移除本地 cache（cache_task / parse_url_expires / read_cache / _ensure_cache_dir / _check_url_expired）
# 全部缓存相关函数已删，调用方改用官方 ark list 端点
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import seedance_uploads as U  # noqa: E402


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
                "**【参数透传铁律 · 2026-06-11 用户红线】**\n"
                "MCP 工具**绝不强制覆盖 agent 传过来的参数**。逻辑：\n"
                "  - agent **传了值** → **严格用 agent 的值**（即使违反默认推荐，比如 generate_audio=True 给绘本场景）\n"
                "  - agent **没传** → 走 inputSchema 的 default（绘本默认无 BGM / 无水印）\n"
                "判断条件用 `if X in args`，**不**用 `args.get(X, default)`——区分『没传』和『传了 None』。\n"
                "目的：绘本有声绘本 / 社媒视频 / 用户临时改需求，agent 都能精准控制。\n\n"
                "[绘本/动画场景推荐参数]\n"
                "  - watermark: 'none'（默认，无 AI 水印）\n"
                "  - duration: 按镜头数算法（5s=2-3 镜 / 8s=3-4 镜 / 12s=4-5 镜 / 14s=5-6 镜）\n"
                "  - ratio: '16:9'（横屏绘本）/ '9:16'（抖音/小红书竖屏）\n"
                "  - generate_audio: false（绘本默认无 BGM，避免莫名说话声；**有声绘本场景**agent 传 true）\n"
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
        # ⚠️ 2026-06-13 删除 list_recent_tasks + download_cached 工具（基于本地 cache，
        # cache 已删，工具失效）。如需"列最近任务"功能，后续调官方 list 端点
        # (`seedance.py list` 或 MCP 加新工具)
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
            # ⚠️ 2026-06-13 移除 _cache_task 调用：本地 cache 已删，需要查历史 = 走官方 list 端点
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
            # 标准化输出（2026-06-13 移除 url_ttl_sec / url_expired_by_local_clock：
            # 这俩依赖 parse_url_expires / check_url_expired（已删）。需要时 client 自己判断 URL 是否过期）
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
                out["_note"] = "video_url 24h 有效，及时下载。过期调 check_task 拿新 URL。"
            if result.get("error"):
                out["error"] = result["error"]
            # ⚠️ 2026-06-13 移除 _cache_task 调用
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
                    # ⚠️ 2026-06-13 移除 _cache_task 调用（wait_and_download 完成后不再写 cache）
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
                    # ⚠️ 2026-06-13 移除 _cache_task 调用（失败也不再写 cache）
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
