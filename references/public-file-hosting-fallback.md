# 公网文件 URL 兜底路线（2026-06-04 沉淀）

> **触发场景**：seedance.py 调 Seedance API 时，本地文件必须先上传到公网可访问的 URL。**chevereto + 飞书云盘是首选，但有些场景会失败**——本节是兜底路线。

## 🎯 决策树（按优先级）

```
本地文件（图片/视频/音频）需要公网 URL 给 Seedance
│
├─ 1. chevereto 自建图床
│    ├─ 是图片？ ✅ 上传 OK
│    ├─ 是视频？ ✅ 上传 OK（强制 type=video/mp4）
│    └─ 是 mp3/wav 音频？ ❌ code 610 mime 白名单
│
├─ 2. 飞书云盘（aistar-work.feishu.cn）
│    └─ 任意文件？ ❌ Seedance 服务端需登录态，URL 不可达
│
├─ 3. 火山引擎 TOS 公共读桶（ark-project.tos-cn-beijing.volces.com）
│    └─ 任意文件？ ✅ 但需要自己有 bucket + 上传权限
│
├─ 4. 【兜底】公网免费图床
│    ├─ uguu.se ✅ 已测，mp3 直链永久（163KB 测试通过，6.84s mp3 OK）
│    ├─ catbox.moe ⚠️ 偶发 Broken pipe
│    ├─ 0x0.st ❌ 503 关停（2026-06 AI botnet spam）
│    ├─ file.io ❌ 返回 Gatsby HTML 包装页（不是直链）
│    └─ transfer.sh ⚠️ 未测，临时用
│
└─ 5. 阿里 OSS / 腾讯 COS / GitHub raw.githubusercontent.com
     └─ ✅ 永久稳定，但需要自己的 bucket/repo
```

### ⚠️ chevereto 二次上传同一文件：code 101 重复上传绕过

**症状**（2026-06-04 Good Morning 绘本实测）：
```
HTTP 400: {"status_code":400,"error":{"message":"重复上传","code":101}}
```

**根因**：chevereto 用**文件二进制 SHA-256 哈希**判重，**不靠文件名**。
- 改文件名（`img1.jpg` → `v12-img1.jpg`）→ ❌ 仍被拒
- 改 EXIF metadata → ⚠️ 哈希仍会撞

**唯一靠谱绕过**：在 JPEG 文件的 **EOI marker（`FFD9`）之后**追加**唯一二进制数据**。JPEG 解码器**忽略 EOI 后的字节**，但哈希变了。

**实测代码**（Python）：

```python
import urllib.request, ssl, json
ctx = ssl.create_default_context()
API_URL = "https://chevereto.aistar.work/api/1/upload"
API_KEY = "<your-key>"

for i in [1, 2, 3, 4]:
    img_path = f"/path/to/img{i}.jpg"
    with open(img_path, "rb") as f:
        file_data = f.read()
    
    # 找 JPEG EOI marker (FFD9) 位置
    eoi_pos = file_data.rfind(b'\xff\xd9')
    # 在 EOI 后插入 JPEG COM marker (FFFE) + 唯一内容
    # COM marker: 2 bytes marker + 2 bytes length + 内容
    unique_comment = b'\xff\xfe' + (f'v12{i}'.encode() + b'\x00').ljust(50, b'\x00')[:50]
    modified_data = file_data[:eoi_pos+2] + unique_comment + file_data[eoi_pos+2:]
    
    boundary = "----hermesboundary12345"
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="source"; filename="v12-img{i}.jpg"\r\n'.encode())
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
    img_url = resp["image"]["url"]
    print(f"图 {i}: {img_url}")
```

**关键点**：
- JPEG EOI 是 `FF D9`（hex），找最后一个（rfind）
- COM marker 是 `FF FE` + 2 字节 length + 内容
- **不破坏 JPEG 解码**（解码器看到 EOI 就停）
- **不破坏 chevereto 缩略图生成**（chevereto 用 libvips 重新解码）
- 实测：127596 → 127648 bytes（图 1），图正常显示 ✅

**适用范围**：
- ✅ 改 jpg 内容 + 重新上传（绘本 A/B 测试、迭代上传同图）
- ❌ 不适用于 png（PNG 末尾是 IEND，需要不同处理）

**反模式**：
- ❌ 改文件名（`img1.jpg` → `v12-img1.jpg`）—— 哈希一样，101 仍被拒
- ❌ 加 `?v=2` query string —— 上传是 POST file body 不是 URL，query 无效
- ❌ 重新生成图片（用 PIL 加水印等）—— 浪费 + chevereto 重新解码慢

## 🧪 实测矩阵（2026-06-04）

| URL 提供方 | 测的文件类型 | Seedance 端能访问？ | 备注 |
|-----------|------------|------------------|------|
| **chevereto https** (aistar.work) | mp4 / jpg | ✅ | 首选；http 必须改 https |
| **chevereto https** | mp3 | ❌ | code 610 mime 白名单 |
| 飞书云盘 (aistar-work.feishu.cn) | mp3 / mp4 | ❌ | 需登录态 |
| **uguu.se** (n.uguu.se) | mp3 | ✅（已用 mp3 URL 跑通 Seedance 任务 cgt-20260604130735-cpn5v + cgt-20260604141858-24cmt）| **本会话两次实测通过** |
| ark-project.tos-cn-beijing.volces.com | mp3 | ✅ | 官方测试音频 |
| 0x0.st | mp3 | - | 已关停 |
| catbox.moe | mp3 | - | Broken pipe |
| file.io | mp3 | - | 返回 Gatsby HTML，不是直链 |
| uguu.se | jpg | ✅（需验）| 同 multipart API |

## 🛠️ uguu.se 上传代码（Python urllib 版）

> **为什么用 urllib 不用 curl？** uguu.se 没 Cloudflare 拦截，urllib 干净。chevereto 必须用 curl（Cloudflare ASN 拦截 urllib）。

```python
import urllib.request, ssl

ctx = ssl.create_default_context()
MP3_PATH = "/path/to/audio.mp3"

with open(MP3_PATH, "rb") as f:
    file_data = f.read()

boundary = "----hermesboundary12345"
parts = []
parts.append(f"--{boundary}\r\n".encode())
parts.append(b'Content-Disposition: form-data; name="files[]"; filename="audio.mp3"\r\n')
parts.append(b"Content-Type: audio/mpeg\r\n\r\n")
parts.append(file_data)
parts.append(b"\r\n")
parts.append(f"--{boundary}--\r\n".encode())
body = b"".join(parts)

req = urllib.request.Request(
    "https://uguu.se/upload.php",
    data=body,
    headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "User-Agent": "curl/8.0",
    },
    method="POST",
)
r = urllib.request.urlopen(req, timeout=120, context=ctx)
# 响应: {"success": true, "files": [{"url": "https://n.uguu.se/xxxxx.mp3", ...}]}
import json
resp = json.loads(r.read())
print(resp["files"][0]["url"])
```

**关键字段**：
- 端点：`https://uguu.se/upload.php`
- multipart field 名：`files[]`（**带方括号**！不是 `file`）
- 响应：JSON，提取 `files[0].url`
- 直链域名：`n.uguu.se`

## 🛠️ 0x0.st 备用代码（如果 uguu 抽风）

> ⚠️ 0x0.st 2026-06 因 AI botnet spam 关停，恢复无 ETA。**不推荐**，留作应急。

```python
# 0x0.st 旧 API（已失效，参考用）
# multipart field: file
# 端点: https://0x0.st
# 响应: 纯文本 URL
```

## 🛠️ GitHub raw URL 路线（永久稳定）

> **本会话已测过坑**——GitHub Gist 存 mp3 有 base64 编码问题。下面是**正确的 binary 上传方式**：

### 路线 A：GitHub Gist API（**有坑**）

```python
# 错误方式：直接传 base64 文本，raw_url 返回的是 base64 文本不是真 mp3
b64 = base64.b64encode(mp3_data).decode()
payload = {
    "public": True,
    "files": {"audio.mp3": {"content": b64, "encoding": "base64"}}
}
# raw_url 返回 text/plain，下载到的是 base64 文本
```

### 路线 B：GitHub Repository Contents API + raw.githubusercontent.com（✅ 推荐）

```python
# 用 Contents API 推 binary，response.raw_url 是真 mp3
# 端点: PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}
# 注意：Contents API 也要 base64，但要加 encoding 字段告诉 GitHub 解码
```

**结论**：GitHub raw 路线**麻烦且坑多**，**绘本项目推荐 uguu.se 兜底**。

## 📋 决策建议（绘本项目场景）

| 文件类型 | 首选 | 兜底 |
|---------|------|------|
| 绘本图片（jpg/png） | chevereto https | uguu.se |
| 绘本视频（mp4） | chevereto https | uguu.se |
| 绘本音频（mp3） | **uguu.se** | 阿里 OSS / GitHub raw |

**绘本 BGM 路线（v12 范式）** 完整流程：
1. ffmpeg 切分整段 mp3 → 4 段 ≤15s
2. **uguu.se 上传 4 段 mp3** → 拿 4 个 n.uguu.se 公网直链
3. seedance.py 调 Seedance，4 段 mp3 URL 喂给 4 个 clip

## 🔗 相关

- 完整 BGM 集成流程见 `references/paradigm-v12-external-bgm.md`
- chevereto 错误排查见 `references/troubleshooting.md`
- 官方文档调研笔记（API 4 种组合 + 音频限制）见 `references/seedance-official-docs-research-2026-06-04.md`
