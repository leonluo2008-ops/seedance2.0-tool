---
name: seedance2.0-tool
description: "调用 Volcengine Seedance 2.0 模型生成视频的 OpenClaw Skill。⚠️ 仅使用 Seedance 2.0 系列模型（doubao-seedance-2-0-fast-260128 / doubao-seedance-2-0-260128），禁止使用 Seedance 1.0 系列模型。支持图片参考、视频参考、音频参考、文生视频等多种模式。通过 Chevereto 图床中转上传本地文件（绕过 Cloudflare 拦截），返回公网 URL 给 Seedance API。触发词：seedance、视频生成、seedance2.0、生成视频、视频模型、文生视频"
---

# Seedance 2.0 Tool Skill

调用 Volcengine Seedance 2.0 API 生成视频。支持图片参考、视频参考、文生视频、动作模仿、角色替换等多种场景。

## 交付规范 ⭐

视频生成完成后，必须将生成的视频文件发送给用户（通过对话所在渠道的工具发送实际文件，禁止只发链接或文字描述）。

```python
# 飞书发送示例
message(
    action="send",
    channel="feishu",
    media="/home/luo/.openclaw/media/outbound/生成视频.mp4",
    caption="生成完成"
)
```

告知用户任务 ID 供追溯。

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
  --ratio 16:9 \
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

### 场景 3 vs 场景 4 快速区分

| 你的需求 | 用哪个场景 | 参数 |
|---------|-----------|------|
| 保留视频动作，换一个新角色的脸/外观 | 场景3 动作模仿 | `--ref-images` 角色图 |
| 保留场景背景，换视频里的动作编排 | 场景4 动作复刻 | `--image` 场景图 |

### 3. 动作模仿（角色替换）⭐ 最常用

**用途**：保留视频动作，更换角色外观。角色A → 角色B，执行视频里同样的动作。

> ✅ **执行前确认**：请确认你已提供：
> - 角色参考图（`--ref-images`）：要出现的新角色外观
> - 视频参考（`--video-refs`）：要模仿的动作编排
> - 画幅和时长参数

```bash
python3 seedance.py create \
  --ref-images ./character.png \
  --video-refs ./motion.mp4 \
  --prompt "@Image1's character mimics @Video1's action choreography, pure white background, <用户指定画幅>" \
  --duration 5 \
  --ratio <用户指定画幅> \
  --wait \
  --download ./output
```

> ⚠️ **画幅限制**：使用视频参考时，API 可能以参考视频的原生画幅为主，`--ratio` 参数不保证生效。如需精准控制画幅，建议使用纯文字（文生视频）或纯图片参考（首帧控制）。

### 4. 动作复刻（场景不变，换动作）

**用途**：保留场景图，更换视频动作。场景不变，视频里的动作替换为新的动作编排。

```bash
python3 seedance.py create \
  --image ./scene.jpg \
  --video-refs ./ref.mp4 \
  --prompt "@Image1's action choreography, @Image2 as the scene background, cinematic quality" \
  --duration 5 \
  --ratio 16:9 \
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

> ⚠️ 音频时长上限 15s，超过会被截断或报错。

## 完整参数说明

### 输入控制

| 参数 | 短选项 | 说明 | 示例 |
|------|--------|------|------|
| `--prompt` | `-p` | 文字提示词，描述视频内容 | `"宇航员在太空行走"` |
| `--image` | `-i` | 首帧图片（URL 或本地路径） | `./hero.png` |
| `--last-frame` | - | 尾帧图片（URL 或本地路径） | `./end.png` |
| `--ref-images` | （无） | 参考图片列表（角色参考，role=reference_image） | `./char.png` |
| `--video-refs` | （无） | 参考视频（本地路径自动上传 Chevereto，支持多个） | `./motion.mp4` |
| `--audio` | - | 参考音频（URL 或本地路径） | `./bgm.mp3` |
| `--draft-task-id` | - | 草稿任务 ID（从草稿生成正式视频） | `task_xxx` |

### 模型控制

> ⚠️ **模型限制**：本 skill **仅使用 Seedance 2.0 系列模型**，禁止使用 Seedance 1.0 系列模型。禁止使用 seedance-2-0-pro 系列模型。

| 参数 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `--model` | 模型 ID | `doubao-seedance-2-0-fast-260128`（Fast，速度优先）/ `doubao-seedance-2-0-260128`（高质量，质量优先） | `doubao-seedance-2-0-fast-260128` |
| `--ratio` | 画幅比例 | `16:9` / `4:3` / `1:1` / `3:4` / `9:16` / `21:9` / `adaptive` | `16:9`（⚠️ 使用视频参考时可能不生效） |
| `--duration` | 视频时长（秒） | `4-15`，或 `-1`（模型自动判断） | `5` |
| `--resolution` | 输出分辨率 | `480p` / `720p` / `1080p` | `720p` |
| `--seed` | 随机种子 | 整数，`-1` 表示随机 | `-1` |

> ⚠️ **首帧图生视频跳变**（画面拉伸/压缩）：将 `ratio` 设置为 `adaptive`，或将输入图片裁剪为与目标 ratio 一致的宽高比。

> ⚠️ **视频 URL 有效期仅 24 小时**，超过需转存。推荐配置火山引擎 TOS 数据订阅自动转存。

### 高级参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--camera-fixed` | 固定镜头位置 | `true` / `false` |
| `--watermark` | 添加水印 | `true`（默认）/ `false` |
| `--generate-audio` | 音视频联合生成（Seedance 2.0 原生能力） | `true` / `false` |
| `--draft` | 草稿/预览模式 | `true` / `false` |
| `--return-last-frame` | 返回尾帧图片 URL | `true` / `false` |
| `--service-tier` | 服务层级 | `default`（在线）/ `flex`（离线，便宜 50%） |
| `--execution-expires-after` | 任务超时（秒） | `3600-259200` |
| `--callback-url` | 回调 Webhook URL | `https://example.com/webhook` |
| `tools: [{"type": "web_search"}]` | 联网搜索（仅纯文本模式） | 自动搜索互联网内容 |

### 执行控制

| 参数 | 说明 |
|------|------|
| `--wait` / `-w` | 创建后等待生成完成 |
| `--interval` | 轮询间隔秒数（默认 15） |
| `--download` | 下载目录（默认当前目录） |
| `--force` / `-y` | 跳过确认步骤，直接执行。**Agent 场景专用**：当 Agent（game-keyframe 或其他调用方）已完成用户确认，可传此参数跳过 SKILL.md 中的确认步骤，直接调用 API 执行。允许多个 Agent 并发调用此参数 |

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
   └── 响应结构：`result["content"]["video_url"]`
   └── 用 urllib 下载到本地
```

## 边界条件

### 参数组合预校验

| 参数组合 | 冲突 | 处理 |
|---------|------|------|
| `--ref-images` + `--image` 同时使用 | 两者都生成 `reference_image` 和 `first_frame` | 警告：优先使用 `--ref-images`（角色替换），`--image` 被忽略 |
| `--ref-images` + `--video-refs` | 正常组合 | 无冲突 |
| 只有 `--ref-images` 无 `--video-refs` | 缺少动作参考 | 警告：行为变为"图生视频"（首帧控制）而非动作模仿 |
| 只有 `--video-refs` 无 `--ref-images` | 缺少角色参考 | 警告：prompt 必须包含主体描述 |

### 文件上传

- 本地图片: 自动识别后缀（png→image/png, jpg→image/jpeg），上传 Chevereto
- 本地视频: 强制 `type=video/mp4`，绕过 Chevereto 的 MIME 识别 bug
- 公网 URL: 直接传递给 API，不上传
- 文件大小: 图片≤30MB，视频≤50MB

### 缺素材时的引导

| 用户说 | 识别为 | 引导用户 |
|--------|--------|---------|
| 只有文字描述 | 文生视频 | 正常执行，无需补充素材 |
| "把这张图生成视频" + 图 | 首帧控制 | 确认是否需要动作参考，如否则用场景2执行 |
| "角色替换" + 图+视频 | 动作模仿 | 正常执行 |
| "角色替换" + 只有图 | 缺素材 | 提示："请提供动作参考视频" |
| "角色替换" + 只有视频 | 缺素材 | 提示："请提供角色参考图" |
| 图+视频+音频 | 组合场景 | 可叠加使用，注意各素材数量上限（图片≤9，视频≤3，音频≤3） |
| 视频+音频 | 组合场景 | 可叠加，音频时长≤15s |
| 图片+音频 | 组合场景 | 可叠加，无时长限制 |

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
```

> ⚠️ `--list` / `--delete` 子命令尚未实现，如有需要请在 seedance.py 中补充。

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

## 用户提示词翻译规则

当用户用自然语言描述视频需求时，将其翻译为 Seedance 2.0 可理解的提示词。

### 翻译对照表

| 用户意图 | 翻译结果 |
|---------|---------|
| 模仿/复刻动作 | `@Image1's character mimics @Video1's action choreography` |
| 纯白背景 | `pure white background` |
| 1:1 画幅 | `1:1 aspect ratio` |
| 16:9 画幅 | `16:9 aspect ratio` |
| 角色外观 | `@Image1's character as the subject` |
| 镜头跟随 | `reference @Video1's camera movement` |
| 电影感/质感 | `cinematic quality, film grain, shallow depth of field` |
| 全身/半身 | `full shot` / `medium close-up` |
| 平滑过渡 | `smooth beat-synced transitions` |

> **注意**：`@` 后面必须用英文占位符（@Image1、@Video1），中文标签模型不认。

### 翻译示例

| 用户说 | 翻译后 |
|--------|--------|
| 我要让这只猫模仿视频里的动作，纯白背景，1:1画幅 | `@Image1's character mimics @Video1's action choreography, pure white background, 1:1 aspect ratio` |
| 生成一个科幻风格的城市景观 | `sci-fi city landscape, futuristic architecture, cinematic quality, wide establishing shot` |
| 产品展示视频，15秒 | `0-5s: Product enters frame with dynamic rotation` / `6-10s: Close-up on details` / `11-15s: Hero shot with brand tagline` |

## 提示词编写指南（@ 参考系统）

Seedance 2.0 使用 `@` 符号为每个素材分配角色，这是最核心的提示词技巧。

### 输入限制

| 类型 | 数量上限 | 格式 | 单文件大小 |
|------|---------|------|-----------|
| 图片 | ≤9 | jpeg, png, webp, bmp, tiff, gif | ≤30MB |
| 视频 | ≤3 | mp4, mov | ≤50MB，总时长 2-15s |
| 音频 | ≤3 | mp3, wav | ≤15MB，总时长 ≤15s |
| **合计** | **≤12** | — | — |

> ⚠️ 禁止上传真实人脸图片（平台合规限制）

### @ 参考系统语法

```plaintext
@Image1 @Image2 @Image3 ...
@Video1 @Video2 @Video3
@Audio1 @Audio2 @Audio3
```

每个素材必须明确声明用途：

| 用途 | 示例语法 |
|------|---------|
| 首帧 | `@Image1 as the first frame` |
| 尾帧 | `@Image2 as the last frame` |
| 角色外观 | `@Image1's character as the subject` |
| 场景背景 | `scene references @Image3` |
| 镜头运动 | `reference @Video1's camera movement` |
| 动作编排 | `reference @Video1's action choreography` |
| 视觉效果 | `completely reference @Video1's effects and transitions` |
| 节奏/韵律 | `video rhythm references @Video1` |
| 背景音乐 | `BGM references @Audio1` |
| 音效 | `sound effects reference @Video3's audio` |

**组合示例：**
```
@Image1's character as the subject, reference @Video1's camera movement
and action choreography, BGM references @Audio1, scene references @Image2
```

### 标准提示词结构

```
[主体/角色设定] + [场景/环境] + [动作/运动描述] + [镜头运动] +
[时间分段] + [转场/特效] + [音频/音效] + [风格/氛围]
```

### 时间分段提示词（视频 > 8s）

```plaintext
0–3s:  [开场场景描述，镜头，动作]
3–6s:  [中间发展]
6–10s: [高潮或关键动作]
10–15s:[结局，结尾镜头]
```

### 镜头术语表

| 术语 | 说明 |
|------|------|
| Push in / Slow push | 镜头推向主体 |
| Pull back | 镜头拉远主体 |
| Pan left/right | 水平摇镜 |
| Tilt up/down | 垂直摇镜 |
| Track / Follow shot | 跟踪拍摄 |
| Orbit / Revolve | 环绕拍摄 |
| One-take / Oner | 单镜连续拍摄 |
| Hitchcock zoom | 移动变焦（推+拉同时） |
| Fisheye lens | 鱼眼镜头 |
| Low angle / High angle | 低角度/高角度 |
| Bird's eye | 俯视镜头 |
| First-person POV | 主观镜头 |
| Whip pan | 快速摇镜 |
| Crane shot | 升降镜头 |

| 景别 | 说明 |
|------|------|
| Extreme close-up | 特写（眼睛、嘴巴等细节） |
| Close-up | 脸部特写 |
| Medium close-up | 头部+肩部 |
| Medium shot | 腰部以上 |
| Full shot | 全身 |
| Wide / Establishing shot | 环境全景 |

### 质量增强词（可附加在提示词末尾）

```plaintext
- Cinematic quality, film grain, shallow depth of field
- 2.35:1 widescreen, 24fps
- Anime style / Photorealistic
- High saturation neon colors, cool-warm contrast
- Tense and suspenseful / Warm and healing / Epic and grand
- Comedy with exaggerated expressions
- Background music: grand and majestic
- Sound effects: footsteps, crowd noise, car sounds
- Beat-synced transitions matching music rhythm
```

### 常见错误

| 错误 | 正确做法 |
|------|---------|
| 只说 `reference @Video1` 不说参考什么 | 明确说 `reference @Video1's camera movement` |
| 使用生僻字、特殊符号 | 优先使用常用字，确保最佳呈现效果 |
| 同时要求固定镜头+环绕镜头 | 同一片段只选一种 |
| 5秒塞太多场景 | 确保物理上可行 |
| 上传5张图但没给每张分配角色 | 每个 @reference 都要有明确用途 |
| 忽略音频设计 | 音效设计大幅提升质量 |
| 忘记匹配时长和复杂度 | 提示词复杂度要和生成时长匹配 |

### 提示词示例：动作模仿

```
@Image1's character mimics @Video1's action choreography, pure white background, <aspect ratio>
```

> **映射规则**：按上传顺序自动对应 — `--ref-images` 第一个文件 = @Image1，`--video-refs` 第一个文件 = @Video1。`@` 后面必须用英文占位符（@Image1、@Video1），不支持中文标签。

### 提示词示例：产品展示

```
0–3s: Product enters frame with dynamic rotation, close-up on surface texture
4–8s: Multiple angle transitions with highlight scanning light effects
9–12s: Product in lifestyle context showing usage scenario
13–15s: Hero shot with brand tagline, background music builds to resolution
Sound: Reference @Audio1's background music, add product interaction sound effects
```

### 为什么用 curl 而非 urllib

Cloudflare 会拦截来自数据中心 IP 的 urllib/requests 请求（ASN block 1010）。curl 来自用户环境，绕过此限制。
