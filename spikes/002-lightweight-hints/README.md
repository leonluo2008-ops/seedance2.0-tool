# spike 002: 轻量参数提示 + 任务管理

## 目标

把 spike 001 的 4 个执行工具扩展到 6 个，新增任务管理 + 平台 video_url TTL 自适应保留策略。

## 完成

| 任务 | 状态 | 实证 |
|------|------|------|
| 1. watermark enum 化（绘本/通用/强制水印 3 选 1）| ✅ | inputSchema 验证通过，4 个映射全对 |
| 2. generate_video description 加"绘本/通用/硬限制"3 段 | ✅ | description 174 → 580 字符 |
| 3. 边界测试 5 组 8 断言 | ✅ | 全部通过 |
| 4. 真实 e2e 8s 480p 16:9 | ✅ | duration=8.041s（顶层 schema 修对，**不**塞 parameters 嵌套）|
| 5. **任务管理（list_recent_tasks + download_cached）** | ✅ | e2e 全跑通 |

## 任务管理核心设计

### TTL 策略：**跟平台对齐，不硬编码**

```python
# 从 video_url query string 自动读 X-Tos-Expires
def _parse_url_expires(video_url) -> int:
    m = re.search(r'X-Tos-Expires=(\d+)', video_url)
    return int(m.group(1)) if m else 24*3600  # 兜底 24h
```

**当前**：X-Tos-Expires=86400（24h）
**未来**：平台改 1h → 自动同步，本地 cache 标 `url_expired_by_local_clock=true`

### 本地缓存位置

```
/home/luo/.cache/seedance-mcp/tasks.jsonl  (append-only)
```

可被 `SEEDANCE_CACHE_DIR` env 覆盖。append-only JSONL 简化并发/恢复。

### 写入时机（铁律 30 升级）

| 触发 | 写入内容 |
|------|---------|
| `generate_video` 提交成功 | task_id + status=queued + body 参数（duration/ratio/resolution/model）|
| `check_task` 拿到响应 | task_id + status + video_url + url_ttl_sec + url_expires_at |
| `wait_and_download` 完成 | 同上 + local_path + size_bytes + md5 |
| **任务 failed 也写** | "已发任务 = 已扣费"，避免 agent 误判为没跑过 |

### 6 个工具汇总

| 工具 | 调 API? | 用途 |
|------|---------|------|
| `generate_video` | ✅ POST create | 提交任务 |
| `check_task` | ✅ GET task | 实时查状态 + 写缓存 |
| `wait_and_download` | ✅ GET task poll | 同步等 + 下载 + 写缓存 |
| `verify_api_key` | ✅ GET list 1条 | 0 元验 key |
| **`list_recent_tasks`** | ❌ 读本地 | 0 元查历史 task_id（铁律 30 升级：跨 session 可查）|
| **`download_cached`** | ⚠️ 仅 fallback 时 | 用缓存 URL 下载（自动 fallback 到 check_task）|

## 实战成果

```
$ python mcp_server.py list_recent_tasks
{
  "count": 1,
  "cache_file": "/home/luo/.cache/seedance-mcp/tasks.jsonl",
  "tasks": [
    {
      "task_id": "cgt-20260611165547-dxt99",
      "status": "succeeded",
      "cached_at_iso": "2026-06-11T09:01:23Z",
      "url_ttl_sec": 86400,
      "url_expires_at_iso": "2026-06-12T09:01:23Z",
      "url_expired_by_local_clock": false,
      "duration": 8,
      "ratio": "16:9",
      "resolution": "480p"
    }
  ]
}

$ python mcp_server.py download_cached
{
  "task_id": "cgt-20260611165547-dxt99",
  "output_path": "/tmp/spike-002-cached.mp4",
  "size_bytes": 1436126,
  "md5": "929d11cc8bd289b8bde827269659f997",
  "url_ttl_sec": 86400,
  "url_was_expired_before_download": false,
  "api_fallback_used": false  ← 没调 API，纯缓存下载
}
```

ffprobe: duration=8.041s ✅

## 已知改进点（spike 003+ 范围）

- ❌ 缓存文件没自动 prune（append-only，几个月后会大）—— 加 7 天/30 天 prune job
- ❌ 多个 profile 共用一个 `~/.cache/seedance-mcp/`——后续按 profile 隔离（参考 hermes-multi-agent 多 profile 架构）
- ❌ list_recent_tasks 不调 API 但也不调 list 端点，所以"**不是我提交的**"任务看不到——这是**设计**：本地缓存是"我的任务",list 端点是"平台所有任务"
- ❌ failed 任务重试策略没实现（避免重复扣费，需要先看是不是 24h 内视频还能拿）
