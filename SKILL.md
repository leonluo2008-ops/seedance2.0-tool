---
name: seedance2.0-tool
description: "调用 Volcengine Seedance 2.0 模型生成视频的 OpenClaw Skill。支持图片参考、视频参考、音频参考、文生视频等多种模式。通过 Chevereto 图床中转上传本地文件（绕过 Cloudflare 拦截），返回公网 URL 给 Seedance API。触发词：seedance、视频生成、seedance2.0、生成视频、视频模型、文生视频"
---

# Seedance 2.0 Tool Skill

调用 Volcengine Seedance 2.0 API 生成视频。支持图片参考、视频参考、文生视频、角色替换等多种场景。

## 环境准备

### 必填环境变量

```bash
export ARK_API_KEY="your-volcengine-ark-api-key"
export CHEVERETO_API_KEY="your-chevereto-api-key"
```

- **ARK_API_KEY**: 火山引擎 Ark API Key，从 [火山方舟控制台](https://console.volcengine.com/ark) 获取
- **CHEVERETO_API_KEY**: Chevereto 图床 API Key，用于上传本地文件到公网

### Chevereto 图床说明

本地文件（图片、视频）必须上传到公网 URL 才能传给 Seedance API。本 skill 使用 Chevereto 图床中转：

- 上传 endpoint: `https://chevereto.aistar.work/api/1/upload`
- 上传方式: `curl subprocess`（绕过 Cloudflare 对 urllib/requests 的拦截）
- 视频 MIME: 必须显式指定 `type=video/mp4`
- 返回: Chevereto API 直接返回的 URL（HTTP 协议，原样使用，不修改）

## 核心用法

### 1. 文生视频（纯文字）

```bash
python3 seedance.py create \
  --prompt "宇航员在太空中行走，漂浮感，电影质感" \
  --duration 5 \
  --ratio 1:1 \
  --wait \
  --download ./output
```

### 2. 图片 + 文字（首帧控制）

```bash
python3 seedance.py create \
  --image ./hero.png \
  --prompt "英雄转身，气势磅礴" \
  --ratio adaptive \
  --wait
```

### 3. 角色替换（图片参考 + 视频参考）⭐ 最常用

```bash
python3 seedance.py create \
  --ref-images ./character.png \
  --video-ref ./motion.mp4 \
  --prompt "使用图片1的角色，替换视频1中的角色，纯白色背景，表情自然流畅" \
  --duration 5 \
  --ratio 1:1 \
  --wait \
  --download ./output
```

### 4. 动作复刻（场景图 + 视频参考）

```bash
python3 seedance.py create \
  --image ./scene.jpg \
  --video-ref ./ref.mp4 \
  --prompt "动作复刻，保持场景一致性" \
  --wait
```

### 5. 音频参考（音画同步）

```bash
python3 seedance.py create \
  --audio ./bgm.mp3 \
  --prompt "配合音乐节奏的画面" \
  --duration 10 \
  --wait
```

## 完整参数说明

### 输入控制

| 参数 | 短选项 | 说明 | 示例 |
|------|--------|------|------|
| `--prompt` | `-p` | 文字提示词，描述视频内容 | `"宇航员在太空行走"` |
| `--image` | `-i` | 首帧图片（URL 或本地路径） | `./hero.png` |
| `--last-frame` | - | 尾帧图片（URL 或本地路径） | `./end.png` |
| `--ref-images` | - | 参考图片列表（角色参考，role=reference_image） | `./char.png` |
| `--video-ref` | - | 参考视频（本地路径自动上传 Chevereto） | `./motion.mp4` |
| `--audio` | - | 参考音频（URL 或本地路径） | `./bgm.mp3` |
| `--draft-task-id` | - | 草稿任务 ID（从草稿生成正式视频） | `task_xxx` |

### 模型控制

| 参数 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `--model` | 模型 ID | `doubao-seedance-2-0-fast-260128`（Fast）/ `doubao-seedance-2-0-260128`（高质量） | `doubao-seedance-2-0-fast-260128` |
| `--ratio` | 画幅比例 | `16:9` / `4:3` / `1:1` / `3:4` / `9:16` / `21:9` / `adaptive` | `1:1` |
| `--duration` | 视频时长（秒） | `4-15`，或 `-1`（模型自动判断） | `5` |
| `--resolution` | 输出分辨率 | `480p` / `720p` / `1080p` | `720p` |
| `--seed` | 随机种子 | 整数，`-1` 表示随机 | `-1` |

### 高级参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--camera-fixed` | 固定镜头位置 | `true` / `false` |
| `--watermark` | 添加水印 | `true`（默认）/ `false` |
| `--generate-audio` | 生成音频 | `true` / `false` |
| `--draft` | 草稿/预览模式（1.5 Pro） | `true` / `false` |
| `--return-last-frame` | 返回尾帧图片 URL | `true` / `false` |
| `--service-tier` | 服务层级 | `default`（在线）/ `flex`（离线，便宜 50%） |
| `--frames` | 精确帧数（1.0 模型） | `25+4n`，范围 29-289 |
| `--execution-expires-after` | 任务超时（秒） | `3600-259200` |
| `--callback-url` | 回调 Webhook URL | `https://example.com/webhook` |

### 执行控制

| 参数 | 说明 |
|------|------|
| `--wait` / `-w` | 创建后等待生成完成 |
| `--interval` | 轮询间隔秒数（默认 15） |
| `--download` | 下载目录（默认当前目录） |

## 工作流程

```
1. 解析参数
   └── 本地文件 → 通过 Chevereto API 上传 → 获得公网 URL
   └── 公网 URL → 直接使用，不上传

2. 构建请求体
   └── model: 模型 ID
   └── content: prompt + 各类参考（图片/视频/音频）
   └── parameters: ratio / duration / resolution / seed / ...

3. 发送创建请求
   └── POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks

4. 轮询等待（可选）
   └── GET /{task_id} 每 15 秒一次
   └── 状态: pending → running → succeeded / failed

5. 下载结果（如指定 --download）
   └── 从响应中提取 video_url
   └── 用 urllib 下载到本地
```

## 边界条件

### 文件上传

- 本地图片: 自动识别后缀（png→image/png, jpg→image/jpeg），上传 Chevereto
- 本地视频: 强制 `type=video/mp4`，绕过 Chevereto 的 MIME 识别 bug
- 公网 URL: 直接传递给 API，不上传
- 文件大小: 图片≤30MB，视频≤50MB

### 错误处理

| 错误 | 处理方式 |
|------|---------|
| `ARK_API_KEY` 未设置 | 打印错误信息并退出 |
| `CHEVERETO_API_KEY` 未设置 | 打印错误信息并退出 |
| Chevereto API 返回非 200 | 打印 status_txt 并退出 |
| 任务 failed | 打印错误信息并退出 |
| 轮询超时（默认 600s） | 打印超时并退出 |

## 子命令

```bash
# 创建视频任务
python3 seedance.py create [options]

# 查询任务状态
python3 seedance.py status <task_id>

# 等待任务完成
python3 seedance.py wait <task_id> [--download ./dir]

# 列出任务
python3 seedance.py list [--status succeeded] [--page 1]

# 删除任务
python3 seedance.py delete <task_id>
```

## 技术细节

### API Endpoint

```
POST   https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks
GET    https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}
```

### Chevereto 上传（curl subprocess）

```python
subprocess.run([
    "curl", "-s", "-X", "POST",
    "https://chevereto.aistar.work/api/1/upload",
    "-F", f"source=@{path};type={mime_type}",
    "-F", f"key={api_key}",
], capture_output=True)
```

### 为什么用 curl 而非 urllib

Cloudflare 会拦截来自数据中心 IP 的 urllib/requests 请求（ASN block 1010）。curl 来自用户环境，绕过此限制。
