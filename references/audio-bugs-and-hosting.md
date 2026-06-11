# 音频相关错误（2026-04 沉淀 · 必读）⭐⭐⭐

> ⚠️ **本文件中的 chevereto 章节（Bug 2 / 二次上传 / 音频）已废弃**（spike 006 · 2026-06-11）：
> - chevereto 图床已**全量**替换为 uguu.se（匿名、无 key、白名单不限）
> - seedance.py 内部上传函数 = `seedance_uploads.upload_to_uguu`
> - **保留**这些章节作为**历史**（Bug 2 的 http→https 修复仍通用 / Bug 4 的 duration 顶层 schema 仍适用）
> - **不**再适用于"修复 chevereto"为目的的实操——**改用 uguu.se**

## 关键背景：seedance.py 请求体 schema（2026-06-04 实测踩坑后强制规范）

**官方请求体**（来源：1-教程 末段 + 3-视频生成教程 §请求体格式）：

```json
{
  "model": "doubao-seedance-2-0-...",
  "content": [...],          ← 文字 + 各类参考（图片/视频/音频）
  "ratio": "16:9",           ← ✅ 顶层（不是 content.parameters）
  "duration": 5,             ← ✅ 顶层
  "resolution": "720p",      ← ✅ 顶层
  "watermark": true,         ← ✅ 顶层
  "generate_audio": true,    ← ✅ 顶层
  "seed": 11,                ← ✅ 顶层（可选）
  "camera_fixed": false,     ← ✅ 顶层（可选）
  "draft": false,            ← ✅ 顶层（可选）
  "return_last_frame": true, ← ✅ 顶层（可选）
  "service_tier": "default"  ← ✅ 顶层（可选）
}
```

> ⚠️ **没有 `parameters` 嵌套对象**——这是 seedance.py 早期版本的错误（用了 OpenAI 兼容的 parameters 嵌套）。**实际官方 API schema 是顶层扁平结构**。

**调试时验证 body 实际发了什么**（必跑）：

```python
# 在 cmd_create 里加 print 调试
print("BODY:", json.dumps(body, indent=2, ensure_ascii=False))
```

## 已知 seedance.py 4 个 bug + 修复

### Bug 1：audio_url 缺 `role: reference_audio`（已修复）

**症状**：传 `--audio ./bgm.mp3` 时 API 返回 400：
```
InvalidParameter: The parameter `content` specified in the request is not valid:
reference media mode requires audio role to be reference_audio.
```

**根因**：seedance.py 原代码：
```python
content.append({"type": "audio_url", "audio_url": {"url": resolve_audio_url(audio)}})  # 缺 role
```

**修复**（已合并到 seedance.py）：
```python
content.append({
    "type": "audio_url",
    "audio_url": {"url": resolve_audio_url(audio)},
    "role": "reference_audio"
})
```

### Bug 2：chevereto 上传后 URL 是 http，Seedance 访问失败（已修复）

**症状**：图片上传 chevereto 后 API 返回 400 `InvalidParameter`，但 API 端能访问（手动 curl https chevereto 200 OK）。

**根因**：
- chevereto API 返回 `http://chevereto.aistar.work/...`（HTTP）
- Seedance 服务端在火山引擎内网，走 HTTP 时 DNS 可能解析到本机 IP（不可达）
- 改为 HTTPS 走 Cloudflare → Seedance 内网可访问

**修复**（已实施于 2026-06-04）：
```python
# 上传图片/视频后强制把 http://chevereto.* 替换为 https://
if url.startswith("http://chevereto."):
    url = url.replace("http://", "https://", 1)
```

### Bug 3：BASE_URL 硬编码，无法用本地代理调试（已修复）

**症状**：调试 seedance.py 时想抓包分析请求 body，无法替换 BASE_URL 走代理。

**根因**：BASE_URL 硬编码 `https://ark.cn-beijing.volces.com/...`，无 env 覆盖。

**修复**（已合并到 seedance.py）：
```python
BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks")
```

调试时设 env：`ARK_BASE_URL=http://127.0.0.1:18765/api/v3/contents/generations/tasks`，本地代理拦截 + forward 真 API + 记录 headers/body。

### Bug 4：duration/ratio/resolution/watermark/generate_audio 放在 body.parameters 嵌套里 → API 找不到（已修复 · 2026-06-04 重大发现）

> ⚠️ **本 bug 影响**：`--duration` 传任何值都被忽略，**API 永远返回默认 5s**。用户原话"全部时长都是5s，没有根据我们规划的时长来生成"。

**症状**（2026-06-04 Good Morning 绘本实测）：用户传 `--duration 8`，任务 `result["duration"] = 5`（不是 8）。**全部 4 个 clip 都 5s**——用户拍板"先看 v12 效果再批量"时还没发现，**批量跑完才发现全 5s**。

**根因**：seedance.py 早期版本把 `duration/ratio/resolution` 等放在 `body.parameters` 嵌套里（沿用 OpenAI 兼容 schema），但**官方 Seedance API 是顶层扁平 schema**。API 收到 `parameters.duration` 但 schema 里没有 `parameters` 字段 → 用了模型默认 5s。

**修复**（已合并到 seedance.py，2026-06-04）：
```python
# 修复前（错）：duration 在 parameters 嵌套
body = {
    "model": args.model,
    "content": content,
    "parameters": {                          # ❌ 错误：用了 OpenAI 嵌套
        "duration": args.duration,
        "resolution": args.resolution,
        "ratio": args.ratio,
    }
}
# 可选参数继续写 body["parameters"][k] = v
# ...

# 修复后（对）：duration/ratio/resolution/watermark/generate_audio 全部在 body 顶层
body = {
    "model": args.model,
    "content": content,
    "ratio": args.ratio,                    # ✅ 顶层
    "duration": args.duration,              # ✅ 顶层
    "resolution": args.resolution,          # ✅ 顶层
}
if getattr(args, "watermark", None) is not None:
    body["watermark"] = args.watermark      # ✅ 顶层
if getattr(args, "generate_audio", None) is not None:
    body["generate_audio"] = args.generate_audio    # ✅ 顶层
if getattr(args, "seed", None) is not None:
    body["seed"] = args.seed                # ✅ 顶层
if getattr(args, "camera_fixed", None) is not None:
    body["camera_fixed"] = args.camera_fixed
if getattr(args, "draft", None) is not None:
    body["draft"] = args.draft
if getattr(args, "return_last_frame", None) is not None:
    body["return_last_frame"] = args.return_last_frame
if getattr(args, "service_tier", None):
    body["service_tier"] = args.service_tier
```

**修复后实测**（2026-06-04 Good Morning v14 范式批量）：
- clip 1: `--duration 7` → result `7.06s` ✅
- clip 2: `--duration 8` → result `8.06s` ✅
- clip 3: `--duration 9` → result `9.10s` ✅
- clip 4: `--duration 9` → result `9.06s` ✅

**自检必加项**（v14 build script 后续增强用）：
```python
# 跑完检查 result["duration"] 是否 == 用户传 --duration
if result["duration"] != expected_dur:
    print(f"⚠️ duration mismatch: 期望 {expected_dur}s 实际 {result['duration']}s")
    print("→ 检查 seedance.py cmd_create 函数 body 结构（duration 必须顶层）")
```

### Bug 5（待办）：seedance.py 不检查任务创建时的 HTTP 错误

**症状**：seedance.py 调 API 拿 400 错误（带 `{"error": {...}}` body），**没检查 status code**，直接把 `result.get("id")` 当作成功（None），但 `if not task_id` 也不会触发（如果 error body 里有 id 字段会误判成功）。

**修复建议**（待办）：在 `api_request` 函数里加 HTTP status 检查，返回前确保 `response.status == 200`。

> **调试工作流**（已沉淀）：遇到 `InvalidParameter` 模糊错误时：
> 1. 在 cmd_create 里加 `print("BODY:", json.dumps(body))` 看实际发的请求
> 2. 用 `ARK_BASE_URL` env + 本地 HTTP 代理拦截 + 转发到真 API
> 3. 对比 seedance.py 实际 body 和手写 API 成功的 body 差异
> 4. 修 seedance.py 源码（不要修调用方绕过去）

---

## chevereto 二次上传同图 code 101 绕过（2026-06-04 沉淀）

**症状**（A/B 测试或迭代上传同一张图时）：
```
HTTP 400: {"status_code":400,"error":{"message":"重复上传","code":101},"status_txt":"Bad Request"}
```

**根因**：chevereto 用**文件二进制 SHA-256 哈希**判重，**不靠文件名**——改文件名无效。

**唯一靠谱绕过**：在 JPEG 文件的 EOI marker（`FF D9`）之后追加**唯一 COM marker（`FF FE`）**。JPEG 解码器忽略 EOI 后的字节，但哈希变了。

**实测代码**：

```python
import urllib.request, ssl, json
ctx = ssl.create_default_context()
API_URL = "https://chevereto.aistar.work/api/1/upload"
API_KEY = "<your-key>"

with open(img_path, "rb") as f:
    file_data = f.read()

# 找 JPEG EOI marker (FFD9) 位置
eoi_pos = file_data.rfind(b'\xff\xd9')
# 在 EOI 后插入 JPEG COM marker (FFFE) + 唯一内容
unique_comment = b'\xff\xfe' + (f'unique{i}'.encode() + b'\x00').ljust(50, b'\x00')[:50]
modified_data = file_data[:eoi_pos+2] + unique_comment + file_data[eoi_pos+2:]

boundary = "----hermesboundary12345"
parts = []
parts.append(f"--{boundary}\r\n".encode())
parts.append(b'Content-Disposition: form-data; name="source"; filename="img.jpg"\r\n')
parts.append(b"Content-Type: image/jpeg\r\n\r\n")
parts.append(modified_data)
parts.append(b"\r\n")
parts.append(f"--{boundary}--\r\n".encode())
body = b"".join(parts)

req = urllib.request.Request(API_URL, data=body, headers={
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    "X-API-Key": API_KEY,
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
    "Referer": "https://chevereto.aistar.work/",
}, method="POST")
r = urllib.request.urlopen(req, timeout=120, context=ctx)
resp = json.loads(r.read())
print(resp["image"]["url"])
```

**反模式**：
- ❌ 改文件名（`img1.jpg` → `v12-img1.jpg`）—— 哈希一样，101 仍被拒
- ❌ 重新生成图片（用 PIL 加水印等）—— 浪费 + chevereto 重新解码慢
- ❌ 加 `?v=2` query string —— 上传是 POST file body 不是 URL，query 无效

**完整文档**：见 `references/public-file-hosting-fallback.md` §"chevereto 二次上传同一文件"。

---

## mp3 音频必须走公网直链（chevereto 不接音频）

**症状**：绘本 v12/v14 范式需要上传 mp3 到公网时：
```
HTTP 400: {"status_code":400,"error":{"message":"Can't get target upload source info","code":610}}
```

**根因**：chevereto v3 默认 mime 白名单**只接 image/**，**mp3 / wav / ogg 全部被拒**（code 610 = "Can't get target upload source info"）。

**修复**（绘本 BGM 场景）：用 **uguu.se** 替代：
- 端点：`https://uguu.se/upload.php`
- multipart field：`files[]`（**带方括号**！）
- 不需要 API key，匿名 POST
- 响应：`{"success": true, "files": [{"url": "https://n.uguu.se/xxx.mp3", "size": ...}]}`
- 直链域名：`n.uguu.se`（不是 `uguu.se`）

**实测**（2026-06-04 Good Morning 绘本）：
- uguu.se 上传 audio_clip1.mp3（164929 bytes, 6.84s, 192kbps stereo）→ 返回 `https://n.uguu.se/fWyAcpcH.mp3`
- 用该 URL + chevereto 图 + v14 prompt → Seedance 任务 `cgt-20260604141858-24cmt` succeeded

**反模式**（chevereto 之外的失败路径）：
- ❌ 飞书云盘 URL（`aistar-work.feishu.cn/file/...`）—— 需登录态，Seedance 服务端不可达
- ❌ GitHub Gist `?base64=true` 解析 —— GitHub 不会自动解码，raw_url 仍返回 base64 文本
- ❌ catbox.moe —— 偶发 Broken pipe
- ❌ 0x0.st —— 已关停（AI botnet spam）
- ❌ file.io —— 返回 Gatsby HTML 包装页，不是直链

**完整决策树 + 实测矩阵**：见 `references/public-file-hosting-fallback.md`。
