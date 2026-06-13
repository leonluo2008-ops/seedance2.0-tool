---
name: seedance2.0-tool
description: "调用 Volcengine Seedance 2.0 模型生成视频的 skill。支持图片参考、视频参考、音频参考、文生视频等多种模式。通过 uguu.se 图床上传本地文件（替代原 chevereto，2026-06-11 spike 006 改造），返回公网 URL 给 Seedance API。CLI 入口：python3 seedance.py create / status / wait。MCP 入口：mcp_seedance_* 工具（自动注册）。触发词：seedance、视频生成、seedance2.0、生成视频、视频模型、文生视频"
---

# Seedance 2.0 Tool Skill

调用 Volcengine Seedance 2.0 API 生成视频。支持图片参考、视频参考、文生视频、动作模仿、角色替换等多种场景。

## ⭐ 必读 references（按问题类别快速定位）

| 类别 | 参考文档 | 触发场景 |
|------|---------|---------|
| **API bug 修复**（5 个已知）| `references/audio-bugs-and-hosting.md` | duration 不生效 / audio role 缺失 / 顶层 vs 嵌套 schema / BASE_URL 调试 / SSL EOF |
| **公网 URL 决策树** | `references/audio-bugs-and-hosting.md` §"mp3 音频必须走公网直链" | 绘本 BGM 上传选 uguu.se / 飞书（**chevereto 已废 2026-06-11**）|
| **官方文档研究 v1** | `references/seedance-official-docs-research-2026-06-04.md` | 找 v14 范式 / 5 条铁律 / v12 范式 5 根因 |
| **官方文档研究 v2** ⭐ 2026-06-10 新增 | `references/seedance-official-docs-research-2026-06-10.md` | **镜头设计方法 + 好提示词写法专项**：分镜时序 4 逻辑 / 特殊字符规范 / 1 运镜红线 / 实战案例 / 按事件拆 / 情绪字典 / 延长画质劣化防御 |
| **Pic8 Rabbit Clip4 实战沉淀** ⭐ 2026-06-10 | `references/2026-06-10-pic8-rabbit-clip4-cardio.md` | **BGM vs 音效红线** / **状态查询反模式**（updated_at ≠ 卡死）/ 20 分钟生成时长预期 / 调用链 bug 全景 / **§8 Rabbit 翻车全链**（v6 整段不分镜翻车 + 5s 5 镜头翻车 + v15 导演思维版验证）/ **§8.2 镜头数算法**（5s=2-3 / 12s=4-5 / 14s=5-6 实战验证）|
| **绘本视频工作流** | `references/picturebook-video-workflow.md` + `picturebook-video` skill | 绘本 prompt 写法 + 范式决策树 |
| **分镜设计规范 v15 导演思维版** ⭐ 2026-06-10 Rabbit 验证 | `../picturebook-video/references/分镜设计规范-v15director.md` | **任何 seedance 2.0 绘本 prompt 写法的单一权威入口**：6 段骨架 + 镜头数算法 + 4 逻辑 + 运镜术语库 + 动作量化 + Rabbit newclip1 v2 验证模板（**v6 旧版"整段不分镜"是翻车坑，新规范要求多镜头时间线分镜**） |
| **Clip 衔接** | `references/clip-continuity.md` | 多 Clip 拼接，尾帧接力 |
| **导演模式** | `references/director-mode.md` | 通用分镜脚本设计 |
| **任务管理铁律** ⭐ 2026-06-05 + 06-10 双增 | `references/task-management-and-cost.md` | task ID 必存 + wait 打断校验 + ark list 救援 + 任务成本意识（**批量提交必读**）+ **§10 批量并发调度（3 并发上限 + 异步等待可执行模板）** ⭐ 2026-06-10 Pic10 Hamster 实战 |
| **批量 Clip 交付前验证 SOP** ⭐ 2026-06-07 新增 | `references/batch-clip-delivery-verification.md` | 客户端报错≠服务端失败 / 三元组绑定 / 绘本原图错位 / vision 语义核对（**pic2 8 Clip 实战沉淀**）|
| **API Key 连接验证** ⭐ 2026-06-07 新增 | `references/api-connection-check.md` | 用户问"检查 K 是否有效" → 0 元 30 秒 list 端点（**不**调 create 扣费）|
| **长旁白单图多 Clip 拆分** ⭐ 2026-06-05 新增 | `references/长旁白单图多clip拆分-v15.1.md` | 朗读 + 留白 > 15s 上限时必走（语义块拆分 + 末帧 = 朗读+静默）|
| **Git 操作红线** ⭐ 2026-06-10 新增 | `references/git-操作红线-2026-06.md` | **任何 skill 仓库 git 操作前必读**：5 条红线（不擅自 init + force push 必问 + .env 排除 + 独立仓库别搞混 + Co-Authored-By 必带）+ 5 问自检清单。**2026-06-10 实战沉淀**（我自己踩 force push 覆盖 seedance2.0-tool main 历史的坑）|

---

## 交付规范 ⭐

> ⚠️ **检查点 1/2：创建前确认参数**
> 执行 `create` 前，必须向用户确认以下参数（即使用户没明确说也要读出来）：
> - **画幅**：`--ratio`（默认 16:9，用户没说则默认）
> - **时长**：`--duration`（默认 5s，建议 4-9s 体验最佳）—— **必须 ≥4 且 ≤15**（API 硬限制 [4,15]）
> - **模型**：`doubao-seedance-2-0-fast`（默认）或 `doubao-seedance-2-0`（高质量慢）
> - **水印**：`--watermark`（**绘本场景必须显式 `false`**，seedance.py 默认 `true` 会带 AI 水印）

> ⚠️ **绘本场景 `--watermark false` 必加（2026-06-03 Ok 好的绘本踩坑）**：
> - seedance.py `--watermark` 默认值 = `true`（带 AI 标识水印）
> - 绘本是给家长/孩子看的产品级视频，AI 水印 = 交付物缺陷
> - **绘本场景所有 create 命令必须显式 `--watermark false`**
> - 跨绘本系列同理（批量、clip 多时都不能漏）
> - 完整默认值表见 `picturebook-video/SKILL.md` Phase 8 参数默认值区

### ⚠️ "首帧" ≠ "首尾帧范式"（2026-06-10 Hamster 用户强纠错）：
- 内部术语"以参考图作为首帧"= 思路起点（看图设计 prompt）= ✅ 必用
- seedance API `--image` + `--last-frame` = 首尾帧范式（锁住首尾两帧）= ❌ 绘本场景禁用

### v14 范式 4 段式 prompt（绘本场景必用 · 2026-06-11 grey 绘本 7 clip 实战沉淀）⭐⭐⭐

> **触发场景**：任何绘本 prompt 写完提交前 / 多镜头分镜 prompt 拼接前 / 跑 v15 范式前
> **来源**：seedance 官方 doc2 + 2026-06-11 grey 绘本 7 clip × 4s 真实跑通验证

**4 段式结构**（必齐全，**不**省略）：

```
[主体定义段]      ← 必填（每张图都定义）
[分镜描述段]      ← 必填（每个镜头绑到对应图）
[风格 + 约束段]  ← 必填（防风格漂移 + 末尾约束 4 词）
[音频参考段]      ← 必填（BGM/音效参考 + 必无 BGM）
```

**完整模板**（grey 绘本 clip 1：标题+云，4s 16:9）：

```
[主体定义段]
将图片1中的彩色大字母 GRAY（橙蓝红黄）+ 灰色纸团 + 银色星星定义为标题主体A。
将图片2中的灰色几何云朵 + 浅蓝天空定义为云朵主体B。

[分镜描述段]
镜头1（0-4s）：中景正面平视，缓慢推近 5%，主体A标题居中，主体B云朵从底部淡入，摇摄 3% 给飘动感。

[风格 + 约束段]
整体保持 2D paper collage style，与图片1、2 画风高度一致。
保持无字幕、无水印、无 Logo，无人声/无歌唱/无配音、无朗读。
音效只保留环境细节：纸页翻动、轻微风声等短促物理声。

[音频参考段]
无背景音乐。末尾伴随<一阵轻柔的微风声 渐弱>，给标题页"轻收"感。
```

**5 个关键铁律（v14 范式）**：

| # | 铁律 | 违反症状 |
|---|------|---------|
| 1 | **每张图都做"主体定义"** | 模型不知道图里有什么 → 自由发挥 |
| 2 | **多图必每张定义** | 主体"漂"到 prompt 描述的其他东西上 |
| 3 | **每个镜头显式"主体X@图片N"绑定** | 多图元素互窜 |
| 4 | **风格词用官方原话**（如 "2D paper collage style"）| 自由发挥被模型漂移到其他风格 |
| 5 | **末尾约束 4 词必加**（无人声/无歌唱/无配音/无朗读）| 莫名说话声（Hamster 实战验证）|

**末尾约束 4 词标准模板**（绘本场景每段必加）：

```
保持无字幕、无水印、无 Logo，无人声/无歌唱/无配音、无朗读。
音效只保留环境细节：风声、纸页翻动、动物叫声等短促物理声。
全程无背景音乐、无旁白人声、无哼唱。
```

**多图参考 vs 首尾帧范式**：

| | `--ref-images 1.jpg 2.jpg`（v14 多图参考）| `--image 1.jpg --last-frame 2.jpg`（v7/v8 首尾帧）|
|---|---|---|
| **适用** | **绘本（v1.0.0 默认）**| 单 Clip 场景（v3/v8 范式）|
| **绘本默认** | ✅ | ❌（v7 范式已删）|

**反模式**：
- ❌ 简化版"无 BGM"（Seedance 可能误读 → 莫名说话声）
- ❌ "无旁白人声"（口语化 → Seedance 理解为人声要存在但不带旁白）
- ❌ 末尾约束段漏写"无人声"（Seedance 看到音效词激活音频生成自动填补）
- ❌ 7 段 prompt 只写一次末尾约束（**不**共享 = 每段**必**重复）
- ❌ 4 段式偷懒只写 2 段 = 模型自由发挥 = 翻车

**判断口诀**：
- ✅ 末尾约束 4 词 = 必填（每段**必**重复，**不**共享）
- ✅ 主体定义 = 每张图**必**做（不只图1）
- ✅ 多图参考 = `--ref-images`（**不**用首尾帧）
- ❌ 4 段式 = 偷懒只写 2 段 = 模型自由发挥 = 翻车

### ⚠️ 红线（v1）· 已发任务 = 已扣费 = 绝不可重跑（2026-06-11 grey 绘本实战沉淀）⭐⭐⭐

> **用户原话**（2026-06-11 grey 绘本 clip 2 实战）：
> - "**停！**"（主 agent 重跑前台时被强打断）
> - "**不要重跑前台，已提交的任务，只要有了 task id 就表示扣费**"
> - "**你检查 API 用法，使用 task id 去查询状态，并下载视频**"

**铁律（新增，2026-06-11）**：

| 反模式（禁止） | 正解（必走） |
|---|---|
| ❌ 重跑前台 `subprocess.run(create + --wait)` | ✅ 只跑 `create`（拿 task_id），**不**用 `--wait` |
| ❌ 看到 status=running 就慌，想"再发一个确保成功" | ✅ 用 `urllib.request.Request` 查 status，running 是正常的 |
| ❌ 客户端报错 = 任务没跑成 | ✅ task_id 拿到了 = 已扣费 = 必查 + 下载，**不**重发 |
| ❌ 觉得"这次可能没扣费所以重发" | ✅ **任何** task_id = 必扣费，**永远不**重发同一绘本的任务 |

**正解流程**：

```python
import json, urllib.request, time
req = urllib.request.Request(
    f'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{TASK_ID}',
    headers={'Authorization': f'Bearer {ARK_API_KEY}'}
)
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
status = d.get('status')  # queued / running / succeeded / failed

if status == 'succeeded':
    video_url = d.get('content', {}).get('video_url')
    urllib.request.urlretrieve(video_url, OUTPUT_PATH)  # 24h 有效
elif status == 'running':
    time.sleep(15)  # 等，**不**重发
elif status == 'failed':
    print(json.dumps(d, indent=2))  # 0 元诊断
elif status == 'queued':
    time.sleep(15)  # 排队中，**不**重发
```

**判断口诀**：
- ✅ "task_id 拿到 = 已扣费" = **必走查 status + 单独 download**
- ❌ "重发任务能解决任何问题" = **错**（重发 = 重复扣费 + 不一定解决问题）
- ❌ "客户端 timeout = 任务失败" = **错**（status 才是唯一权威）
- ✅ 任何 `create` 命令 = 不带 `--wait`（前台阻塞 = 变相"想重跑"风险）

**反例（grey clip 2 实战）**：
- 主 agent 跑了 `seedance.py create --wait` 阻塞 90s + 看输出
- 用户打断："**停！**已扣费 = 不重跑"
- 主 agent 改用 `urllib.request.Request` 查 status = succeeded（1m48s）→ 单独 download = 2.0 MB
- **0 元重跑** + 视频拿到

**grey 绘本 7 clip 实战数据**（v14 范式 + 末尾约束 4 词 + 整数档 4s 全部跑通）：

| clip | 主体 | task_id | 实际时长 | 文件大小 | 耗时 |
|---|---|---|---|---|---|
| 1 | 标题+云 | cgt-20260611150833-5gml8 | 4.086s | 1.6 MB | 1m48s |
| 2 | 象 | cgt-20260611151218-l99bk | 4.086s | 2.0 MB | 1m49s |
| 3 | 鼠 | cgt-20260611151957-gwh7l | 4.086s | 1.7 MB | 3m8s 批 |
| 4 | 包 | cgt-20260611151957-7m92k | 4.086s | 2.1 MB | 批 |
| 5 | 鲸 | cgt-20260611151957-l48dt | 4.096s | 2.1 MB | 批 |
| 6 | 石群 | cgt-20260611152005-scnh7 | 4.086s | 1.3 MB | 批 |
| 7 | 总结 | cgt-20260611152005-b2gx8 | 4.086s | 1.2 MB | 批 |

**总实际时长 28.61s ≈ TTS 28s ✅（误差 0.6s = 帧级差异）**

### ⚠️ 红线（v1）· 已发任务 = 已扣费 = 绝不可重跑（2026-06-11 grey 绘本实战沉淀）⭐⭐⭐

> **用户原话**（2026-06-11 grey 绘本 clip 2 实战）：
> - "**停！**"（主 agent 重跑前台时被强打断）
> - "**不要重跑前台，已提交的任务，只要有了 task id 就表示扣费**"
> - "**你检查 API 用法，使用 task id 去查询状态，并下载视频**"

**铁律（新增，2026-06-11）**：

| 反模式（禁止） | 正解（必走） |
|---|---|
| ❌ 重跑前台 `subprocess.run(create + --wait)` | ✅ 只跑 `create`（拿 task_id），**不**用 `--wait` |
| ❌ 看到 status=running 就慌，想"再发一个确保成功" | ✅ 用 `urllib.request.Request` 查 status，running 是正常的 |
| ❌ 客户端报错 = 任务没跑成 | ✅ task_id 拿到了 = 已扣费 = 必查 + 下载，**不**重发 |
| ❌ 觉得"这次可能没扣费所以重发" | ✅ **任何** task_id = 必扣费，**永远不**重发同一绘本的任务 |

**正解流程**（任何"看到 status ≠ succeeded 或 0 视频文件"时）：

```python
import json, urllib.request, time
# 1. 用 task_id 查 status（status 是唯一权威字段）
req = urllib.request.Request(
    f'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{TASK_ID}',
    headers={'Authorization': f'Bearer {ARK_API_KEY}'}
)
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
status = d.get('status')  # queued / running / succeeded / failed

# 2. status 决定动作
if status == 'succeeded':
    video_url = d.get('content', {}).get('video_url')
    # 下载（24h 有效）
    urllib.request.urlretrieve(video_url, OUTPUT_PATH)
elif status == 'running':
    time.sleep(15)  # 等，**不**重发
elif status == 'failed':
    print(json.dumps(d, indent=2))  # 0 元诊断
elif status == 'queued':
    time.sleep(15)  # 排队中，**不**重发
```

**判断口诀**：
- ✅ "task_id 拿到 = 已扣费" = **必走查 status + 单独 download**
- ❌ "重发任务能解决任何问题" = **错**（重发 = 重复扣费 + 不一定解决问题）
- ❌ "客户端 timeout = 任务失败" = **错**（status 才是唯一权威）
- ✅ 任何 `create` 命令 = 不带 `--wait`（前台阻塞 = 变相"想重跑"风险）

**反例（grey clip 2 实战）**：
- 主 agent 跑了 `seedance.py create --wait` 阻塞 90s + 看输出
- 用户打断："**停！**已扣费 = 不重跑"
- 主 agent 改用 `urllib.request.Request` 查 status = succeeded（1m48s）→ 单独 download = 2.0 MB
- **0 元重跑** + 视频拿到


> - **判断口诀**：看到"首帧"= 思路（看图）/ 看到"首尾帧"= 参数（禁用）
> - 触发场景：任何"看图设计" / "推断情节" 的话术出现 = ✅ 思路；任何"锁帧过渡" / "中间插值" 的话术出现 = ❌ 走错范式
> - 反模式：把"以参考图为基准"误读为"用 `--image` 钉死构图"（= 走 v7 范式 = 禁用）→ 必用 `--ref-images` 多图参考

> ⚠️ **`--duration` 4-15s 全支持 · 不擅自设上限（2026-06-05 Cat AT 家族踩坑 · 用户纠错）**：
> - seedance API `--duration` 范围 **[4, 15]** 秒，**或 -1**（模型自动判断）
> - **12s / 13s / 14s 都合规**，不是"最长 4s/8s/10s"
> - 用户原话："一直都说 clip 时长为 4-15s"——**4-15s 都支持是常识**
> - ❌ 拍脑袋猜"12s 是最长"会被打脸（Cat 4a 我就猜错被骂"你TM哪来这么多问题"）
> - ✅ 拿不准时**查文档 / 问用户**，不凭直觉编时长上限
> - **触发场景**：用户指定时长 / 多镜头分镜 / 朗读长旁白需要长 clip

> ⚠️ **官方"好提示词写法" 3 条 P0 铁律（2026-06-10 调研沉淀 · 绘本 prompt 必看）**：
> 来源：`references/seedance-official-docs-research-2026-06-10.md`（doc2 §440 特殊字符 / §4 运镜写法 / §2 分镜时序）
>
> 1. **特殊字符规范**（doc2 §440 · 零成本高回报）：
>    | 信息类型 | 符号 | 示例 |
>    |---|---|---|
>    | 音乐 | `（）` | （背景中播放着快节奏的摇滚乐） |
>    | 音效 | `<>` | `<远处传来鸟叫声>` |
>    | 台词 | `{}` | {你好，世界} |
>    | 字幕 | `【】` | 【第一章：启程】 |
>    - ❌ 我们之前完全没用这套符号——音效/BGM/台词全混在自然语言里
>    - ✅ 立即可改：所有 BGM 写 `（...）`，所有音效写 `<...>`，绘本朗读台词写 `{...}`
>
> 2. **1 个镜头只 1 种运镜**（doc2 §4 红线）：
>    - "**一个镜头里尽量只指定 1 种运镜方式，不要同时要求推拉摇移，会增加画面的不稳定性**"
>    - ❌ 反模式："镜头缓慢推近+向右横移+轻微旋转"
>    - ✅ 正解："镜头缓慢推近" / 需要切换用"镜头切至..."
>
> 3. **每个镜头 4 逻辑齐全**（doc2 §2 分镜时序）：
>    - **运镜或镜头切换方式** + **主体动作与表情** + **位置或空间变化** + **音频信息**
>    - ❌ 我们经常缺"音频内联"——音频单独成段写在末尾
>    - ✅ 正解：每个镜头自带 BGM 描述 `（...）` + 音效 `<...>`
>
> **触发场景**：任何绘本 prompt 写完提交前 / 跑 v15 范式前 / 多镜头分镜 prompt 拼接前

> ⚠️ **BGM vs 音效铁律 · 2026-06-10 用户红线（绘本场景）**：
> 用户原话："不要乱发挥，不生成 BGM 是红线，是底线。**我刚问的是没有音效，所以你应该关注音效的生成。不是生成 BGM**"
>
> - **BGM（背景音乐）= 绘本场景红线，禁止生成**
> - **音效（短促声音事件）=绘本场景允许且应生成**
> - 官方特殊字符规范：音效用 `<...>`（如 `<远处传来鸟叫声>` / `<短促清脆的叮 一响>`）
> - 触发条件：用户说"加入音效" / "加上声音" / "视频没声音" →**只加音效，不加 BGM**
> - 反模式（绘本场景）：prompt 写"全程使用钢琴 + pizzicato 作为背景音乐"= 触发 BGM 红线
> - 正解：prompt 写"每个英文单词出现瞬间各伴随<短促清脆的叮 一响>"="<远处传来鸟叫声 渐弱>"
> - 同时：CLI 参数 `--generate-audio true` 仍要开（让 seedance 生成音效），但 prompt 里**只**写音效事件，不写 BGM 持续段落
> - 反模式 2（更隐蔽）：prompt 里既写 BGM 又写"无背景音乐"=seedance 理解为"刻意静音"= 完全无音频

视频生成完成后，必须将生成的视频文件发送给用户（通过对话所在渠道的工具发送实际文件，禁止只发链接或文字描述）。

> ⚠️ **元偏好 · 铁律定义与精简标准（2026-06-10 用户红线）**：
> 用户原话（明确纠错 · 升 SKILL 必查项）："**铁律的定义是红线、底线，绝对不能逾越的原则。那么说它应该是精简少，而不是数量这么多。**"
>
> **铁律定义（适用于所有 skill，不只本 skill）**：
> - ✅ **铁律 = 红线 / 底线 / 不能逾越的原则**——违反 = 必然翻车 / 必然破坏产品 / 必然失败
> - ❌ **不是** = 流程建议 / 方法论 / 范式 / 技巧 / 模板 / 计算公式 / 调试经验 / 历史教训
>
> **精简标准**（每条铁律提交前必问）：
> 1. **违反 = 翻车吗？**（红线的本质）
> 2. **能合并到其他铁律吗？**（重复定义 = 删）
> 3. **能降级到 references 或 SKILL.md 正文吗？**（不是红线就降级）
> 4. **有官方文档原话支持吗？**（官方说"必须/不能" = 红线；官方说"建议/推荐" = 降级）
>
> **判断流程**：
> - 用户说"加铁律"时 → 先问"违反会怎样" → 不能回答 = 不是铁律
> - skill 维护者加新铁律时 → 必跑上面 4 问 → 不通过 = 不加
>
> **Pic8 Rabbit 实战反模式**：当前 SKILL.md 有 65 条"铁律"清单 = **太多** = 失控。本次精简后保留 **12-13 条真铁律**（A 类红线），其余 35 条降级到 references（流程/方法），18 条删除（反模式/历史/已修复）。
> **触发场景**：任何 skill 维护时新建"铁律"前 / 整理"铁律清单"时。
>
> **官方文档原话作为权威来源**（用户元偏好）："**你应该在 seedance 的原始文档中去寻找一些好的设计方法、好的提示词写法**"——任何"prompt 写法/技术规范"类规则必先查官方 doc2/doc3，找到官方依据才写，找不到标注"未验证"。

> ⚠️ **BGM vs 音效铁律 · 2026-06-10 用户红线（绘本场景）**：
> 用户原话："不要乱发挥，**不生成 BGM 是红线，是底线**。我刚问的是没有音效，所以你应该关注音效的生成。不是生成 BGM。"
>
> - **BGM（背景音乐 / 持续音乐）= 绘本场景红线，禁止生成**——除非用户明确要 BGM
> - **音效（短促声音事件 · swoosh / 叮 / tap / 鸟叫）= 绘本场景允许且应生成**——用户说"加音效" = 加这个
> - 官方特殊字符规范：音效用 `<...>`（如 `<远处传来鸟叫声>` / `<短促清脆的叮 一响>`）；BGM 用 `（...）`（如 `（钢琴 + 弦乐持续 90 BPM）`）
> - **触发条件**：用户说"加入音效"/"加上声音"/"视频没声音" → **只加音效，不加 BGM**
> - **反模式 1**（绘本场景）：prompt 写"全程使用钢琴 + pizzicato 作为背景音乐" = 触发 BGM 红线
> - **反模式 2**（更隐蔽）：prompt 里既写 BGM 又写"无背景音乐" = seedance 理解为"刻意静音" = 完全无音频
> - **反模式 3**（最常见）：`--generate-audio false` + prompt 完全不提音效 = 视频零音频（Pic8 Rabbit Clip4 v1 案例）
> - **正解**：CLI `--generate-audio true`（让 seedance 生成音效）+ prompt 写具体音效事件 `<短促清脆的叮 一响>`，**不写 BGM 持续段落**
>
> **Pic8 Rabbit Clip4 v1 → v2 修复**：
> - v1（失败）：`--generate-audio false` + prompt 写"无任何背景音乐、无旁白人声、无哼唱" → 视频零音频
> - v2（成功）：`--generate-audio true` + prompt 加"每个英文单词出现瞬间各伴随<短促清脆的叮 一响>，末帧伴随<一阵轻快的鸟叫声 渐弱>" + 删"无背景音乐" → AAC 立体声 14.07s ✓
>
> ---
>
> ⚠️ **末尾约束段必用官方原话 4 词"无人声/无歌唱/无配音/无朗读"（2026-06-10 Hamster 用户反馈"莫名说话声"沉淀 · 必读）**：
>
> **用户反馈原文**（Hamster Clip 2 v2 端到端跑通后）："**视频里出现了莫名的说话声，也不是 'hamster' 这一类的核心词领读**"
>
> **官方文档原话**（`references/seedance-official-docs-research-2026-06-10.md` line 534 · doc2 §16）："保持无字幕、无水印、无 Logo，**无人声/无歌唱/无配音**"
>
> **4 个问题点**（P0×2 + P1×2）：
> - **P0-1**：末约束段弱约束 = "无旁白人声"等口语化 → seedance 理解为人声要存在但不带旁白 = 误读
> - **P0-2**：末约束段漏写"无人声" → seedance 看到"音效/吱/TTS"等声音词 → 模型激活音频生成 → 自动填补"人声"（不是 hamster 等核心词）
> - **P1-1**：主体行为描述可能被误读为"对话"（"对镜头说/对观众说"等措辞 = 触发对话信号）
> - **P1-2**：音效描述太具体化（"撒娇/满足/紧张"等情绪词）→ seedance 自我补全"人声撒娇"
>
> **修复方向**（3 个关键修改 · Hamster Clip 2 修复范本）：
> ```diff
> - 全程无背景音乐、无旁白人声、无哼唱、无歌唱。保留 TTS 音轨占位，时长匹配旁白朗读时长（2 秒）。
> + 保持无字幕、无水印、无 Logo，无人声、无歌唱、无配音、无朗读。
> + 音效只保留环境细节：风声、纸页翻动、仓鼠吱声等短促物理声。
> ```
> ```diff
> - <一声轻柔的微风>
> + <一声轻柔的微风声>
> ```
> ```diff
> - <一声细软的"吱"叫，像小宠物的撒娇>
> + <一声短促的吱声>
> ```
>
> **末尾约束段标准模板**（绘本场景统一使用）：
> ```
> 保持无字幕、无水印、无 Logo，无人声、无歌唱、无配音、无朗读。
> 音效只保留环境细节：风声、纸页翻动、动物叫声等短促物理声。
> 全程无背景音乐、无旁白人声、无哼唱。
> ```
>
> **官方特殊字符规范**（doc2 line 380-386 · 零容忍踩坑）：
> - `()` 音乐 / `<>` 音效 / `{}` 台词（seedance 默认对 `{}` 生成"台词"人声）/ `【】` 字幕
> - 绘本 = 领读型 / 认字型 = **不**用 `{}`（无台词）· 凡 `{}` 必删除或改用 `<>`（音效）
> - 音效**不**写"情绪化人声"（撒娇/满足/紧张/温柔）· 只写物理音（风声/纸页翻动/吱声）
> - prompt 里的"TTS 音轨占位"等元术语**必放末尾约束段**（不当镜头描述）· 避免被误读为"要生成 TTS 语音"
>
> **触发场景**：任何绘本 prompt 写完提交前 / 看到用户反馈"莫名说话声/嘈杂人声/不属于旁白的人声"时 / 跑 v15 范式前 / 多镜头分镜 prompt 拼接前
>
> **完整诊断 + 修复 + 反模式库**见 `picturebook-video/references/2026-06-10-hamster-v15-end-to-end-validation.md` §8（Hamster 实战 §8 音频末尾约束官方原话修复库）

> ⚠️ **官方"好提示词写法" 3 条 P0 铁律（2026-06-10 调研沉淀 · 绘本 prompt 必看）**：
> 来源：`references/seedance-official-docs-research-2026-06-10.md`（doc2 §440 特殊字符 / §4 运镜写法 / §2 分镜时序）
>
> 1. **特殊字符规范**（doc2 §440 · 零成本高回报）：
>    | 信息类型 | 符号 | 示例 |
>    |---|---|---|
>    | 音乐 | `（）` | （背景中播放着快节奏的摇滚乐） |
>    | 音效 | `<>` | `<远处传来鸟叫声>` |
>    | 台词 | `{}` | {你好，世界} |
>    | 字幕 | `【】` | 【第一章：启程】 |
>    - ❌ 我们之前完全没用这套符号——音效/BGM/台词全混在自然语言里
>    - ✅ 立即可改：所有 BGM 写 `（...）`，所有音效写 `<...>`，绘本朗读台词写 `{...}`
>
> 2. **1 个镜头只 1 种运镜**（doc2 §4 红线）：
>    - "**一个镜头里尽量只指定 1 种运镜方式，不要同时要求推拉摇移，会增加画面的不稳定性**"
>    - ❌ 反模式："镜头缓慢推近+向右横移+轻微旋转"
>    - ✅ 正解："镜头缓慢推近" / 需要切换用"镜头切至..."
>
> 3. **每个镜头 4 逻辑齐全**（doc2 §2 分镜时序）：
>    - **运镜或镜头切换方式** + **主体动作与表情** + **位置或空间变化** + **音频信息**
>    - ❌ 我们经常缺"音频内联"——音频单独成段写在末尾
>    - ✅ 正解：每个镜头自带 BGM 描述 `（...）` + 音效 `<...>`
>
> **触发场景**：任何绘本 prompt 写完提交前 / 跑 v15 范式前 / 多镜头分镜 prompt 拼接前

> ⚠️ **重要：`--download` 是「完整文件路径」，不是「目录」**。脚本把 `--download` 的值直接当文件名使用（不拼接 task_id）。多任务并发时**必须每个任务用不同路径**，否则会互相覆盖。
>
> 推荐做法：每个任务传独立文件名，例如 `--download /path/clip1.mp4`、`--download /path/clip2.mp4`。
>
> 错误示例（并发场景）：所有任务都传 `--download /path/output`，结果全部写入 `/path/output`（无扩展名），需要重命名。

> ⚠️ **批量并发调度 · 3 并发上限（2026-06-10 Hamster 8 段实战沉淀 · 调度规则）**：
> - **API 限制**：seedance 单用户**最多 3 个任务并发**（用户 2026-06-10 原话："seedance 可以并发 3 个任务"）
> - **绘本 N 段拆分**：N 段拆为 ceil(N/3) 批，**每批 ≤3 个**（例：8 段 = 3+3+2 批 / 5 段 = 3+2 批）
> - **默认走并发，禁走串行**：绘本/漫剧"批量跑 N 个 Clip"场景，**不**用 `for ... subprocess.run` 串行（绘本 8 段 18 分钟 vs 3+2 并发 7 分钟，**节省 60%**）
> - **可执行模板**（`execute_code + subprocess.Popen + communicate()` 异步等所有）：见 `references/task-management-and-cost.md` §10
> - **红线**（违反翻车而非"慢"）：① `--download` 路径冲突（互相覆盖）② 错开 < 1 秒（API 限流）③ `timeout` 太短（假阳性失败）
> - **触发场景**：任何绘本 N 段 / 漫剧 N 段 / 多角度产品图 / 同主题多版本批量提交前
>
> - ❌ 用 `for ... subprocess.run` 串行 / 用 `nohup &` 后台失联 / 把"批量"等同于"串行"
>
> **Pic10 Hamster 8 段并发实战数据**：3+2 并发总耗时 7 分 18 秒（vs 串行预估 18 分钟），节省 11 分钟。

> ⚠️ **🛑 任务创建=已扣费 · 禁止重跑（2026-06-11 grey 绘本实战沉淀 · 红线级）**：
>
> **用户原话**："**不要重跑前台，已提交的任务，只要有了task id就表示扣费，你检查API用法，使用task id去查询状态，并下载视频**"
>
> **铁律**：
> 1. **任何 seedance 任务 `create` 调用成功 = 已扣费**（无论后续 `wait` 状态如何）
> 2. **重跑 `create` = 重复扣费**（无任何价值，task 不会"消失"或"修复"）
> 3. **正确操作 = 用 `task_id` 查 status + 读 `content.video_url` + 下载 + 发用户**
>
> **错误的重跑模式**（v1.0.0 显式禁止）：
> - ❌ "wait 60s 还没出来" → 重跑 create（**重复扣费**）
> - ❌ "好像 shell 挂了" → 重跑 create（先 list 端点核对，**不**重跑）
> - ❌ "我想看 status" → 重跑 create（用 task_id 查，**不**重跑）
> - ❌ "上一批 stdout 没拿到" → 重跑 create（用 task_id 补，**不**重跑）
>
> **正确的 follow-up 模式**（`execute_code + urllib + json.dumps`）：
> ```python
> import os, json, urllib.request
> env = {}
> with open('/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env') as f:
>     for line in f:
>         line = line.strip()
>         if line and not line.startswith('#') and '=' in line:
>             k, v = line.split('=', 1)
>             env[k.strip()] = v.strip()
>
> task_id = 'cgt-XXXXXXXX'
> req = urllib.request.Request(
>     f'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}',
>     headers={'Authorization': f'Bearer {env["ARK_API_KEY"]}'}
> )
> with urllib.request.urlopen(req, timeout=30) as r:
>     d = json.loads(r.read())
> print('status:', d.get('status'))
> print('video_url:', d.get('content', {}).get('video_url'))
> ```
>
> **Pic11 grey 7 clip 实战数据**（2026-06-11）：
> - 批量创建 7 个 task 耗时 36 秒（拿到所有 task_id）
> - 3+2 分批轮询 188 秒（3 分 8 秒）= 全部 succeeded
> - 7 个视频下载耗时 3 秒
> - **0 元重跑** = 用 task_id 全程 follow-up
> - 平均生成时长 = 1-2 分钟/clip（fast 模型 4s 短档）
```python
# 飞书发送示例（--download 是完整文件路径，需自己起名）
# 生成后从该路径读取视频并通过 send_message 发送
# 示例：--download /home/luo/cactus-pic-vid/output/clip1.mp4
```

告知用户任务 ID 供追溯。

## 环境准备

### Key 配置（`.env` 文件）⭐

Key 存储在 skill 目录的 `.env` 文件中，**不要放在 `~/.bashrc`**——subprocess 调用不会继承 bashrc 环境变量，会导致 `ARK_API_KEY not set` 错误。

skill 目录已有 `.env` 文件（已配置），无需额外操作。如需更新 key，直接编辑：

```bash
~/.hermes/skills/seedance2.0-tool/.env
```

```bash
# 文件内容格式
ARK_API_KEY=your-volcengine-ark-api-key
CHEVERETO_API_KEY=your-chevereto-api-key
```

- **ARK_API_KEY**: 火山引擎 Ark API Key，从 [火山方舟控制台](https://console.volcengine.com/ark) 获取
- **CHEVERETO_API_KEY**: Chevereto 图床 API Key，用于上传本地文件到公网

> **为什么不用 `~/.bashrc`？** seedance.py 通过 `subprocess` 调用 curl 时不会加载用户 shell 的环境变量，`.env` 文件由 Python `python-dotenv` 自动加载，是跨所有调用路径的可靠方案。

### Chevereto 图床说明

本地文件（图片、视频）必须上传到公网 URL 才能传给 Seedance API。本 skill 使用 Chevereto 图床中转：

- 上传 endpoint: `https://chevereto.aistar.work/api/1/upload`
- 上传方式: `curl subprocess`（绕过 Cloudflare 对 urllib/requests 的拦截）
- 视频 MIME: 必须显式指定 `type=video/mp4`
- 返回: Chevereto API 直接返回的 URL（HTTP 协议，原样使用，不修改）

> ⚠️ **chevereto 不支持音频**（默认 mime 白名单只接 image/*）—— mp3 必须用 uguu.se 替代（见 `references/audio-bugs-and-hosting.md` §"mp3 音频必须走公网直链"）。

## MCP 工具（首选 · 替代 seedance.py CLI）⭐⭐⭐ 2026-06-11 接入

**MCP server 自动把以下 4 个工具注册为 `mcp_seedance_*` 前缀**（绘本 agent 工具列表里直接可见）：

| 工具 | 用途 | 替代 seedance.py 子命令 | 触发词 |
|------|------|------------------------|--------|
| `mcp_seedance_generate_video` | 提交任务，返回 task_id | `seedance.py create`（不传 `--wait`）| "生成视频" / "跑一段" / "提交任务" |
| `mcp_seedance_check_task` | 查询任务状态（**已发任务 = 已扣费 = 绝不重提交**）| `seedance.py status <task_id>` | "查任务" / "看进度" |
| `mcp_seedance_wait_and_download` | 同步等待 + 自动下载（绘本单 clip 场景）| `seedance.py wait` + `seedance.py download` | "等完成" / "拿到视频" |
| `mcp_seedance_verify_api_key` | 0 元 list 端点检测（key 验通）| （无 CLI 等价）| "验 key" / "key 有效吗" |

**调用规则（绘本 agent 必守 · 来自 conductor skill v0.1）**：

- **duration 必须是整数**（避开 argparse `"7.5"` → `invalid int` 坑；inputSchema 强制 `type: integer`）
- **duration [4, 15] 硬限制**（API 物理上限，inputSchema 写死）
- **watermark 默认 `"none"`**（绘本场景专精；原 seedance.py 默认 true 是坑，**绝对不要**覆盖为平台水印）
- **generate_audio 默认 `False`**（绘本场景无声更纯净；如需 BGM 显式传 `True`）
- **resolution 默认 `"720p"`**（spike 阶段 `480p` 验证；生产用 720p）
- **model 默认 `doubao-seedance-2-0-fast-260128`**（性价比；如需高质量传 `doubao-seedance-2-0-260128`）
- **ratio 默认 `16:9`**（绘本横版）
- **参数透传铁律**：MCP server 用 `if "X" in args` 而非 `args.get("X", default)`——agent 传什么用什么，agent 没传才用 MCP 默认值。**绝不要**在 MCP server 里把 agent 传的 None 隐式吞掉

**当前 MCP server 状态（2026-06-11 Cherry 报告后 · 绘本 agent 必看）**：

✅ **已就绪**：
- MCP server 代码：`spikes/001-mcp-uguu-server/mcp_server.py`（**注意**在 spike 目录里、不是仓库根）
- 业务函数（单真源）：`seedance_uploads.py`（648 行，与 seedance.py 共享）
- Python 依赖：`mcp 1.27.0` 已在 `/home/luo/.hermes/hermes-agent/venv/lib/python3.11/site-packages/`
- 注册位置：`~/.hermes/profiles/huiben/config.yaml` `mcp_servers.seedance` 段（profile 级生效）
- 重启 hermes 后工具列表重载可见

⚠️ **前置条件**：
- **绘本 agent 实际使用的仓**是 profile 仓：`~/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/`
- **必须切到 `feat/mcp-uguu-server` 分支**（`a9cdd34` 才有 mcp_server.py + seedance_uploads.py）
- **main 分支 = 生产版本，absolute NO merge**（用户红线 2026-06-11）
- ARK_API_KEY 自动从 skill 仓 `.env` 文件加载（不通过 config.yaml 注入）

**回退路径（仅 MCP 不可用时）**：
- uguu.se 图床 + curl ark API（`scripts/uguu_ark_fallback.py` 是当前回退实现，参考 `references/public-file-hosting-fallback.md`）
- Cherry 绘本 4/4 视频用此路径成功生成（task_id 在 `~/.hermes/profiles/huiben/work/20260611-cherry-input/task_ids.json`）

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

> ⚠️ **没有 `--prompt-file` 参数（2026-06-10 Pic10 Hamster 实战踩坑）**：
> - seedance.py **只接受** `--prompt "<string>"`（argparse `-p`），**不接受** `--prompt-file path/to/file.txt`
> - 错误调用：`--prompt-file /path/clip3-prompt.txt` → `error: unrecognized arguments: --prompt-file /path/clip3-prompt.txt`
> - **正确做法**（prompt 在文件里时）：
>   - **方案 1（推荐）**：用 `execute_code` + `subprocess.run([..., '--prompt', prompt_text, ...])` 列表传字符串（**避免** shell 转义 1500+ 字符的 prompt）
>   - **方案 2**：shell `cat` 转义：`--prompt "$(cat /path/clip3-prompt.txt)"`（注意中文/引号/反斜杠的 shell 转义陷阱）
> - **绘本项目最佳实践**：每段 prompt 写到 `clips/clipN-prompt.txt` → 提交任务用方案 1（subprocess 列表）→ 避免 0.5% 概率的转义翻车

### 2. 图片 + 文字（首帧控制）

```bash
python3 seedance.py create \
  --image ./hero.png \
  --prompt "英雄转身，气势磅礴" \
  --ratio adaptive \
  --wait
```

### 2b. 首尾帧控制（v3/v8 范式 · 单 Clip 场景）⚠️ 注意：绘本默认**不是**这个

> ⚠️ **2026-06-03 用户纠错（Chat 聊天绘本实测）**：
> - 用户原话："大哥，你别搞错了，我用的不是首尾帧，绝对不是首尾帧"
> - **绘本默认范式是 v10**（多帧参考 + 跨 Clip 共享 BGM 主题），**不是首尾帧**
> - 首尾帧（`--image` + `--last-frame`）只用于 v3/v8 范式的**单 Clip**场景
> - 详见 `picturebook-video/SKILL.md` §"🎯 绘本动画视频范式选择决策树"（v10 升级为默认）

**用途**（v3/v8 范式 · 单 Clip 场景）：用「图 A → 图 B」驱动**单个** Clip 视频，A 是首帧、B 是尾帧，中间由 prompt 引导运镜/过渡。**不适用整本绘本**（整本绘本用 v9/v10 多帧参考）。

```bash
python3 seedance.py create \
  --image ./1.jpg \
  --last-frame ./2.jpg \
  --prompt "Camera starts on @Image1 ... transitions to @Image2 ... Final frame: camera locks, no fade, no dissolve" \
  --duration 8 \
  --ratio 16:9 \
  --wait
```

**与 `--ref-images` 的本质区别**：

| | `--image` + `--last-frame`（首尾帧） | `--ref-images`（多帧参考）|
|---|---|---|
| **参数语义** | `first_frame` + `last_frame` 锁住首/尾两帧 | `reference_image` 多图风格/场景参考（**不锁帧**）|
| **中间过程** | 由 prompt 引导运镜/过渡 | 由 prompt 时序窗（`from 0.0s to 4.0s @Image1 ...`）驱动 |
| **适用范式** | v3/v8 单 Clip（红苹果/Cactus/Red）| **v9/v10 整本绘本**（Eat 吃/Chat 聊天领读型）|
| **绘本默认** | ❌ | ✅ **绘本默认走 v10（多帧参考）**|
| **互斥** | API 拒绝同时使用 |

**Prompt 写法要点**（首尾帧范式 · v3/v8）：
- 描述运镜过程：「Camera starts on X, slowly pushes in, transitions via warm glow, reveals Y, holds」
- **必须显式收势**：「Final frame: camera locks completely, image becomes still, no fade, no dissolve, holds to the last frame」
- 风格锁定写在末尾：「Children's picture book illustration style, flat cartoon with thick black outlines」

**完整 v3/v8 vs v9/v10 范式决策树**（绘本场景必看）见 `picturebook-video/SKILL.md` §"🎯 绘本动画视频范式选择决策树"。

> **2026-06-03 Chat 聊天绘本踩坑教训**：搜索 seedance.py create 命令时，如果 hit 到本节（旧版没标"v3/v8 单 Clip 限定"的）→ 会误用首尾帧调 v10。**修复**：本节已加 ⚠️ 警告 + 指向 picturebook-video 决策树。

### 场景 3 vs 场景 4 快速区分

| 你的需求 | 用哪个场景 | 参数 |
|---------|-----------|------|
| 保留视频动作，换一个新角色的脸/外观 | 场景3 动作模仿 | `--ref-images` 角色图 |
| 保留场景背景，换视频里的动作编排 | 场景4 动作复刻 | `--image` 场景图 |

### 3. 动作模仿（角色替换）⭐ 最常用

**用途**：保留视频动作，更换角色外观。角色A → 角色B，执行视频里同样的动作。

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

### 5. 音频参考（音画同步）⭐ 2026-06-04 完整跑通

> **本节是绘本/动画项目 BGM 集成的工业级做法**。背景音乐走音频参考模式比让 Seedance 自带生成更可控（你可以选自己剪映里调好的 BGM）。

```bash
python3 seedance.py create \
  --audio ./bgm.mp3 \
  --prompt "全程使用音频1作为背景音乐。..." \
  --duration 10 \
  --generate-audio true \
  --wait
```

#### 5.1 官方支持的多模态组合（2026-06-04 官方文档确认）

| 组合 | 适用场景 | prompt 关键句 |
|------|---------|--------------|
| **图片 + 音频** | 静态图 + BGM（绘本场景）| "全程使用音频1作为背景音乐。" |
| 图片 + 视频 | 视频主体换图（动作迁移）| "参考视频1的运镜方式，生成图片1..." |
| 视频 + 音频 | 视频配音/换 BGM | "参考音频1的音色生成..." |
| 图片 + 视频 + 音频 | 复杂多模态 | 三者结合 |

#### 5.2 音频官方限制（必须遵守，否则 InvalidParameter）

| 限制 | 值 | 来源 |
|------|---|------|
| 单音频时长 | **[2, 15] 秒** | 官方文档 §音频要求 |
| 最多音频数 | **3 段** | 官方文档 |
| 所有音频总时长 | **≤ 15 秒** | 官方文档 |
| 格式 | wav / mp3 | 官方文档 |
| 单文件大小 | ≤ 15 MB | 官方文档 |
| 请求体大小 | ≤ 64 MB | 官方文档 |
| 传入方式 | URL / Base64 / 素材 ID | 官方文档 |

> **绘本项目适配**：32 秒绘本音频必须切分成 ≤15 秒的多段（最多 3 段），然后多段都传 `--audio` 多次。

#### 5.3 音频 URL 必须公网可达（2026-06-04 踩坑 · 重要）

> ⚠️ **飞书云盘 / 私有图床 URL 在 Seedance 服务端会 404 失败**——这些 URL 在你的浏览器能打开，但 Seedance 服务器（火山引擎内网）访问不到。

**实测对比**：

| URL 类型 | Seedance 服务端能访问？ | 实测 |
|---------|---------------------|------|
| `https://ark-project.tos-cn-beijing.volces.com/...`（TOS 公共读）| ✅ | succeeded |
| `https://chevereto.aistar.work/...`（自建图床）| ✅（需 https）| succeeded |
| `https://aistar-work.feishu.cn/file/...`（飞书云盘）| ❌ 需要登录态 | failed InvalidParameter |
| `http://chevereto.aistar.work/...`（HTTP）| ⚠️ 火山内网可能走不通 | 改 https 后成功 |

**修复方案**（已实测）：
1. **chevereto http→https 修复**：seedance.py 自动把 `http://chevereto.*` 替换为 `https://`
2. **公网 URL 推荐用**：火山 TOS 公共读桶 / GitHub raw.githubusercontent.com / 阿里 OSS / 腾讯 COS
3. **不要用**：飞书云盘 URL（需登录态）、公司内网图床、CDN 但需要鉴权的 URL

#### 5.4 完整成功请求体示例（绘本 BGM 场景）

```json
{
  "model": "doubao-seedance-2-0-fast-260128",
  "content": [
    {"type": "text", "text": "全程使用音频1作为背景音乐。A small teddy bear..."},
    {"type": "image_url", "image_url": {"url": "https://ark-project.../image.jpg"}, "role": "reference_image"},
    {"type": "audio_url", "audio_url": {"url": "https://ark-project.../bgm.mp3"}, "role": "reference_audio"}
  ],
  "duration": 7,
  "ratio": "16:9",
  "watermark": false,
  "generate_audio": true
}
```

**实测 task**：`cgt-20260604130735-cpn5v`（绘本 clip1，7s，status=succeeded，seed=39914）

#### 5.5 音频参考的两种语义

| 语义 | prompt 写法 | 用途 |
|------|------------|------|
| **音色参考**（TTS 替代）| "使用@音频1低厚温润带细碎颗粒感中年男声的音色说{台词}" | 角色配音 |
| **BGM 背景音乐**（绘本场景）| "全程使用音频1作为背景音乐。" | 绘本/动画 BGM |

**官方示例**（果茶广告）：
> "全程使用音频1作为背景音乐。第一人称视角果茶宣传广告..."

#### 5.6 音频切分工具（绘本项目必用）

绘本 32s 音频 → 切分到 ≤15s 段：

```bash
# 探测总时长
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 audio.mp3

# 按 8s 切分（适合绘本单 clip ≤10s 场景）
ffmpeg -y -ss 0 -i audio.mp3 -t 8 -c copy audio_clip1.mp3
ffmpeg -y -ss 8 -i audio.mp3 -t 8 -c copy audio_clip2.mp3
ffmpeg -y -ss 16 -i audio.mp3 -t 8 -c copy audio_clip3.mp3
ffmpeg -y -ss 24 -i audio.mp3 -t 8 -c copy audio_clip4.mp3
```

详细切分策略（按字数比例 vs 按静音点）见 `picturebook-video/SKILL.md` v12 章节。

### 5.7 音频"参考" vs "原样播放"（v12 范式用户反馈沉淀 · 2026-06-04）

> **用户实测反馈**：
> - "BGM 配乐与上传的音频相符" ✅ → Seedance 拿上传音频的"风格/音色"作参考，**自行生成** BGM
> - "音频包含了人声，但生成的视频里没有人声" ❌ → **音频参考默认是音色参考语义，不是原样播放**

**绘本场景两种路线**：

| 用户需求 | 路线 | 关键参数 |
|---------|------|---------|
| **只要 BGM**（绘本 BGM 控制）| `v12 audio-driven` | `--audio` + `--generate-audio true` + prompt "全程使用音频1作为背景音乐" |
| **要人声 + BGM**（含 TTS 朗读）| `v13 prompt + 后期 ffmpeg 替换音频轨` | **不传 `--audio`**（让 Seedance 自带 BGM）+ 后期 ffmpeg 替换原 mp3 |

**后期 ffmpeg 替换音频轨**（让用户原 mp3 真正进视频）：

```bash
ffmpeg -y -i generated_video.mp4 -i original_audio.mp3 \
  -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 \
  final_video_with_user_audio.mp4
```

**完整决策树** + 听感解释见 `references/seedance-official-docs-research-2026-06-04.md` §14。

#### 5.8 uguu.se 同时支持图片托管（2026-06-04 Good Night 绘本实测 · chevereto 不可用兜底）⭐ 新增

> **触发场景**：chevereto API key 不可用（占位符 / 失效 / 不想配置），但用户给了一批本地图片（绘本 8 张 jpg），需要拿到公网直链喂给 Seedance。

**操作步骤**（已实测，2026-06-04 Good Night 绘本 8 张图 100% 成功）：

```bash
# 1) 上传单张图片（multipart, files[] 带方括号）
curl -sS -F "files[]=@1.jpg" https://uguu.se/upload
# 响应: {"success": true, "files": [{"url": "https://o.uguu.se/xxx.jpg", ...}]}

# 2) 批量上传 8 张
for i in 1 2 3 4 5 6 7 8; do
  curl -sS -F "files[]=@${i}.jpg" https://uguu.se/upload
done

# 3) HTTP 200 验证（可选）
for url in $(cat urls.txt); do
  curl -sI "$url" -o /dev/null -w "%{http_code} $url\n"
done
```

**关键点**：
- 端点：`https://uguu.se/upload`（**不是** `/upload.php`，实测以 `/upload` 为准）
- multipart field：**`files[]`**（**带方括号**！）
- 响应：JSON 里 `files[].url` 是公网直链
- 直链域名：`n.uguu.se` / `d.uguu.se` / `h.uguu.se` / `o.uguu.se`（按 hash 分片，**全部 HTTPS 永久有效**）
- 不需要 API key（匿名）
- 支持 jpg/png/gif/webp/mp3/wav/ogg/视频（**一站式**——绘本图片 + BGM 都能用同一个服务）

**与 chevereto 对比**：

| 维度 | chevereto | uguu.se |
|------|-----------|---------|
| 需 API key | ✅ | ❌ 匿名 |
| 支持 jpg/png | ✅ | ✅ |
| 支持 mp3 | ❌ code 610 | ✅ |
| 直链稳定性 | 私有实例看运营 | ✅ 永久 |
| Seedance 可达 | ✅（需 https）| ✅ |
| 速度 | 私有服务器 | ✅ CDN |

**绘本项目推荐**：**uguu.se 作为默认一站式托管**（图片 + BGM 都能用，匿名无需 key）。chevereto 仅在"用户有 chevereto 私有实例"或"需要用户管理后台"时用。

**反模式**：
- ❌ 把 uguu.se 当主参考写入"必须用 chevereto"提示——会误导下次会话
- ❌ 上传失败时不验证 HTTP 200 → 拿到 404 URL 喂给 Seedance → 任务 400 失败

**实测产物**（2026-06-04 Good Night 绘本）：8 张图 uguu.se 全部 HTTP 200 直链，2-3s 上传完成，已为下一步 Seedance 视频生成任务就绪。

---

## 6. 参考图失效修复（v13/v14 范式）⭐ 2026-06-04 绘本实测沉淀
> **本节是绘本项目最新最优实践**——v12 audio-driven 跑通后画面"参考图完全没生效"的根因 + 5 个官方依据修复。
> **触发场景**：跑完 video 后画面与参考图明显不符（角色错、场景错、风格错），且 v11-β/v12 prompt 写法都试过不行。
> **完整诊断 + prompt 模板**：见 `references/seedance-official-docs-research-2026-06-04.md` §13/§15。

### 6.1 现象（v12 audio-driven clip 1 实测）

| 元素 | 绘本原图 | v12 实际生成 |
|------|---------|------------|
| 主角 | 🐻 棕色小熊 | 🐰 白兔子 |
| 场景 | 🌳 户外清晨 | 🛏️ 室内卧室 |
| 风格 | 2D 纸艺拼贴 | 3D 毛毡 |

### 6.2 5 个根因（官方依据）

| # | 根因 | 官方原话 | 来源 |
|---|------|---------|------|
| 1 | prompt 与参考图"语义冲突" | "避免语义冲突（如同一主体出现矛盾特征）" | 2-提示词 §1 注意 |
| 2 | 未用 "图片 N" / "主体 N@图片 N" 语法 | "参考`<图片N>`中的`<主体N>`，生成..." | 2-提示词 §基础公式 |
| 3 | 未做 "主体定义" | "将`<图片N>`中的`[主体核心特征]`定义为`<主体N>`" | 2-提示词 §1 定义主体 |
| 4 | 素材顺序不优化 | "越需要精准参考的素材，放在提示词中越靠前的位置" | 2-提示词 §1 注意 |
| 5 | 撞上"风格漂移" | "加入明确的风格约束词，例如'2D日漫风格'、'3D国风漫画'" | 2-提示词 §风格漂移 |

### 6.3 v13 范式 5 个修正点（v12 失败后必加）

```diff
- "A small bunny peeks out from behind a colorful blanket in a warm sunlit bedroom"
+ "将图片1中的小熊定义为主角小熊。... 主角小熊@图片1 站在绿色草地上..."
+ "参考图片1的整体画面构图与纸艺拼贴风格"
+ "整体保持 2D 纸艺拼贴风格（2D paper collage style）"
+ "参考音频1中的钢琴 + pizzicato 弦乐作为背景音乐"
+ "镜头1: ... 镜头2: ..."
```

**完整 v13 prompt 模板**：见 `references/seedance-official-docs-research-2026-06-04.md` §13.3（实测任务 `cgt-20260604144202-zqprm` 跑通）。

### 6.4 v14 范式 4 段式 prompt（v13 升级 · 单 clip 跨多图必用）⭐ 2026-06-04 里程碑

> **v13 修了"角色对位"，但只看到图1的元素，没看到图2**。**v14 = v13 + 显式把每个镜头绑到对应图**。

**4 段式 prompt 模板**：

```
[主体定义段]  ← 必填（每张图都定义）
将图片1中的 X 定义为主体A。
将图片2中的 Y 定义为主体B，将图片2中的 Z 定义为主体C。

[分镜描述段]  ← 必填（每个镜头绑到对应图）
镜头1：场景为图片1的 [场景描述]。主体A@图片1 [动作]。
镜头2：场景为图片2的 [场景描述]。主体B@图片2 [动作]，
       主体C@图片2 [动作]。

[风格 + 约束段]  ← 必填（防风格漂移）
整体保持 2D paper collage style，与图片1、2 的画风高度一致。
保持无字幕、无水印、无 Logo，无人声/无歌唱/无配音。

[音频参考段]  ← 必填（BGM 调性参考）
参考音频1中的 [乐器/调性] 作为背景音乐，
在整个视频中以相同的 [情绪] BGM 调性播放，
平缓过渡到下一段。镜头N结尾不收势，
BGM continues softly into the next moment。
```

**5 条铁律**：

| # | 铁律 | 失败症状 |
|---|------|---------|
| 1 | **每张图都做"主体定义"** | 模型不知道图里有什么 → 自由发挥 |
| 2 | **`<主体N>@<图片N>` 显式绑定** | 主体"漂"到 prompt 描述的其他东西上 |
| 3 | **每个镜头显式"场景为图片N的 XX"** | 多张图的场景元素互窜 |
| 4 | **风格词用官方原话** | 自由发挥被模型漂移到其他风格 |
| 5 | **BGM 用 prompt 写"参考音频1中的..."** | Seedance 不调用音频参考 |

**v14 API 必填参数**（与 v13 区别）：
- `--ref-images 1.jpg 2.jpg`（**v14 必传 ≥2 张**）
- `--audio https://n.uguu.se/xxx.mp3`（**v14 必传**外部 mp3 URL）
- `--prompt "<4 段式 prompt>"`
- `--watermark false` + `--generate-audio true`（同 v13）
- `--duration 7/8/9/9`（**实测 7/8/9/9s 完整跑通——duration 字段必须在 body 顶层**）

**实测 v14 跑通**：Good Morning 绘本 4 个 clip 全部一次跑通（任务 ID `cgt-20260604145154-8bq8w` / `cgt-20260604151253-wbbvf` / `cgt-20260604151549-5pxk2` / `cgt-20260604151842-s64zv`），**总耗时 ~10 分钟**。**修复 duration 字段位置 bug 后 7/8/9/9s 完整实测通过**（任务 ID `cgt-20260604153857-tfj4w` / `cgt-20260604153415-2gnq2` / `cgt-20260604153856-c2hgt` / `cgt-20260604153856-b2c6g`）。

**完整 v14 文档** + 4 个 clip 批量 prompt 范本 + 失败模式排查：`picturebook-video/references/paradigm-v14-multi-image-shots-bgm.md`

### 6.5 升级到 v14 vs v13 决策

| 场景 | 范式 |
|------|------|
| 单图单 clip | v13 即可 |
| **单 clip 跨多张图（绘本主场景）** | **v14** ✅ |
| 单图 + 外部 mp3 驱动 | v12 即可（v14 的前身）|
| v14 跑 4 个 clip 验证 | ✅ 已实测一次跑通 |

### 6.6 用户工作流铁律（2026-06-04 纠错沉淀）

> **用户原话**："你要从官方文档里好好查找有价值的信息来修正，不能乱猜。"

- ❌ 凭印象 / 猜 / 编的 prompt 修复规则 → 失败
- ✅ 任何"为什么 v11-β/v12/v13 没生效"的修复 → **必须先回官方文档**找依据（`references/seedance-official-docs-research-2026-06-04.md` 是 L1 信息源）
- ✅ 没找到官方依据的修复 → 不动手，**先告诉用户"文档没说，先验证"**

### 6.7 何时升级到"大头特写图"？

| 场景 | 是否需要升级 |
|------|------------|
| 角色单一（绘本主角 1 只小熊）+ 全身照清晰 | ❌ v14 prompt 修正 + 参考图已足够 |
| v14 prompt 仍角色错位 | ✅ 先生成"主角大头特写图"再重跑 |
| 角色 4+ 个 | ✅ 必升级（官方"参考人物过多"明确支持不住） |

## 完整参数说明

### 输入控制

| 参数 | 短选项 | 说明 | 示例 |
|------|--------|------|------|
| `--prompt` | `-p` | 文字提示词，描述视频内容 | `"宇航员在太空行走"` |
| `--image` | `-i` | 首帧图片（URL 或本地路径） | `./hero.png` |
| `--last-frame` | - | 尾帧图片（URL 或本地路径） | `./end.png` |
| `--ref-images` | （无） | 参考图片列表（角色参考，role=reference_image） | `./char.png` |

> ⚠️ **`--ref-images` 行为说明**：
> - 多张 ref_images 可以同时传入（如角色图 + 分镜图），API 不会报错
> - **但 `reference_image` 无法锁定角色外观一致性**：传入托比角色图，生成结果仍会是随机卡通形象，与原角色图不符。`reference_image` 只能提供**风格/场景参考**，不能保持角色特征。如需角色一致性，需要换方案（如先单独生成首帧再用首帧驱动）。
> - `--image`（first_frame）和 `--ref-images` **互斥**：同时使用会触发 API 报错 `first/last frame content cannot be mixed with reference media content`
| `--video-refs` | （无） | 参考视频（本地路径自动上传 Chevereto，支持多个） | `./motion.mp4` |
| `--audio` | - | 参考音频（URL 或本地路径） | `./bgm.mp3` |
| `--draft-task-id` | - | 草稿任务 ID（从草稿生成正式视频） | `task_xxx` |

### 模型控制

| 参数 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `--model` | 模型 ID | `doubao-seedance-2-0-fast-260128`（Fast）/ `doubao-seedance-2-0-260128`（高质量） | `doubao-seedance-2-0-fast-260128` |
| `--ratio` | 画幅比例 | `16:9` / `4:3` / `1:1` / `3:4` / `9:16` / `21:9` / `adaptive` | `16:9`（⚠️ 使用视频参考时可能不生效） |
| `--duration` | 视频时长（秒） | `4-15`，或 `-1`（模型自动判断） | `5` ⚠️ **必须顶层（修复前会被忽略）** |
| `--resolution` | 输出分辨率 | `480p` / `720p` / `1080p` | `720p` | ⚠️ CLI 保留，但 API 不接受此参数，实际输出由模型决定 |
| `--seed` | 随机种子 | 整数，`-1` 表示随机 | `-1` |

### 高级参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--camera-fixed` | 固定镜头位置 | `true` / `false` |
| `--watermark` | 添加水印 | `true`（默认）/ `false` |
| `--generate-audio` | 生成音频 | `true` / `false` |
| `--draft` | 草稿/预览模式（1.5 Pro） | `true` / `false` |
| `--return-last-frame` | 返回尾帧图片 URL | 不接受参数，argparse 会报错 `expected one argument`，使用 `--return-last-frame true` | 不接受参数 |
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

2. 构建请求体（**所有非 content 字段都在 body 顶层**，不要嵌套 parameters）
   └── model: 模型 ID
   └── content: prompt + 各类参考（图片/视频/音频）
   └── duration: 视频时长（顶层）
   └── ratio: 画幅比例（顶层）
   └── watermark: 水印（顶层，默认 true）
   └── generate_audio: 生成音频（顶层）
   └── seed/camera_fixed/draft/return_last_frame/service_tier（顶层，可选）
   └── ⚠️ 注意：`resolution` 不是 API 有效参数，会被忽略

3. 发送创建请求
   └── POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks
   └── 获得 task_id，立即告知用户

4. 状态机轮询
   ┌──────────┐  15s   ┌──────────┐  15s   ┌────────────┐
   │ pending  │───────→│ running  │───────→│ succeeded  │
   └──────────┘        └──────────┘        └────────────┘
        │                  │                     │
        │                  │                     ↓
        │                  │              下载视频文件
        │                  │              发送给用户
        │                  ↓
        │           ┌────────────┐
        └──────────→│  failed    │ → 打印错误信息，告知用户
                    └────────────┘

5. 下载结果（如指定 `--download <path>`）
   └── 响应结构：`result["content"]["video_url"]`
   └── 写入 `--download` 指定的**完整文件路径**（不拼接 task_id）
```

> ⚠️ **检查点 2/2：下载后确认**
> 下载完成后，确认文件存在（`ls -lh <path>/seedance_{task_id}.mp4`）再发送给用户。
> 如果 `wait` 超时但任务实际已成功（后台 server 端已完成），用 `status <task_id>` 确认状态后，手动 `wait --download <path>` 重试下载，**不要重新创建任务**。

## 边界条件

### ⚠️ 调用路径坑：Hermes 下 `~` 双重展开（2026-06-02 实测）

在 hermes agent 里 `python3 ~/.hermes/skills/.../seedance.py` 会展开成 `~/.hermes/profiles/huiben/home/.hermes/skills/...`（profile 目录 + 误加的 home 子目录 + 原始路径），导致 `No such file or directory`。**修复**：一律用**绝对路径**：

```bash
python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py create ...
```

同 trap 也适用于所有 `~/.hermes/...` 开头的命令。**先 `which` 验证路径再调用**。

### 参数组合预校验
| 参数组合 | 冲突 | 处理 |
|---------|------|------|
| `--ref-images` + `--image` 同时使用 | 两者都生成 `reference_image` 和 `first_frame` | ❌ API 直接拒绝：`"first/last frame content cannot be mixed with reference media content"`. 两个场景互斥，只能二选一 |
| `--ref-images` + `--video-refs` | 正常组合 | 无冲突 |
| 只有 `--ref-images` 无 `--video-refs` | 缺少动作参考 | 行为变为"图生视频"（首帧控制）而非动作模仿 |
| 只有 `--video-refs` 无 `--ref-images` | 缺少角色参考 | prompt 必须包含主体描述 |
| 多张 `--ref-images`（角色图+分镜图） | 角色一致性无法保证 | 传入多张 ref_images 不会报错，但 `reference_image` 无法锁定角色外观，只能提供风格/场景参考 |
| 视频参考 `--ratio` 控制 | 画幅可能不生效 | 使用视频参考时以参考视频原生画幅为主 |

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
| 任务 failed | 打印错误信息并退出。用 `seedance.py status <task_id>` 确认错误详情。 |
| 轮询超时（默认 600s） | `wait` 命令在 600s 未完成会报错退出。如果任务实际已完成（后台 server 端正常），直接用 `status <task_id>` 确认状态，再用 `wait --download <path>` 重新等待下载即可，无需重新创建任务。 |

### ⚠️ 音频相关错误（2026-06-04 沉淀 · 必读）

**完整 4 个 bug + 修复 + 调试工作流**：见 `references/audio-bugs-and-hosting.md`。**快速速查**：

| Bug | 症状 | 根因 | 修复 | Commit |
|-----|------|------|------|--------|
| 1. audio role 缺失 | API 400 "reference media mode requires audio role to be reference_audio" | seedance.py 原代码没加 role | 加 `"role": "reference_audio"` | ✅ 已修 |
| 2. chevereto HTTP 不可达 | API 400 但手动 curl https chevereto 200 OK | chevereto 返回 http → 火山内网走不通 | seedance.py 自动 http→https | ✅ 已修 |
| 3. BASE_URL 硬编码 | 无法本地代理调试 | 无 env 覆盖 | 加 `ARK_BASE_URL` env | ✅ 已修 |
| **4. duration 字段位置错** | **`--duration 8` 实际生成 5s** | **seedance.py 把 duration 放 `body.parameters` 嵌套，官方 API 是顶层** | **修复 cmd_create，duration/ratio/resolution/watermark/generate_audio 全部移到 body 顶层** | ✅ **commit ef983c5** |

> **快速验证** body 是否正确：在 cmd_create 里加 `print("BODY:", json.dumps(body, indent=2))` 看实际发的请求。
>
> **4 个 bug 全部已修**（commit ef983c5 · 2026-06-04）—— 任何"audio / duration / chevereto 不可达"问题先确认用户用的是 patch 后的 seedance.py（`/home/luo/seedance2.0-tool/seedance.py`），别在已修 bug 上二次踩坑。

### Pitfall: 已扣费任务 = 用 task_id 查+下载，不许重跑前台（2026-06-11 grey 绘本实战 · 必看）⭐⭐⭐

> **本节是 seedance 调度流程的"扣费后行为"红线**——和 §1 (task_id 必存) + §10 (并发调度) 同级铁律。

**触发条件**：`seedance.py create` 已成功执行 + 拿到 task_id 之后。

**根因**（2026-06-11 grey 绘本 clip 1 实战）：
- 我用 `seedance.py create --wait --download <path>` 在前台跑
- 用户喊"停！"并指出"已提交的任务只要有了 task id 就表示扣费"
- `create` 那一刻就扣费，`--wait` 只是额外阻塞前台等结果，**不是必要的扣费动作**
- 但用户想让我"用 task id 去查询状态，并下载视频"——这才是创建后的正确流程

**反模式**：

```bash
# ❌ 反模式 1：前台阻塞等（已经扣费了，不必要）
TASK_ID=$(python3 seedance.py create --ref-images ... --wait --download ./out.mp4 2>&1 | grep "Task ID" | awk '{print $3}')
# 问题：--wait 在前台等 1-15 分钟，agent 不能做别的事
# 而且 stdout 里 task_id 容易被截断（shell 管道风险）
# 用户原话："不要重跑前台，已提交的任务，只要有了task id就表示扣费"

# ❌ 反模式 2：拿不到 task_id 就重提交
# 万一 grep 截断了 / stdout 没打印 task_id / agent 异常退出
# 错误做法：再调一次 create 拿新 task_id → 重复扣费
# 正确做法：用 ark list 端点（§3）查最近任务找回旧 task_id
```

**正确做法（5 步）**：

```bash
# Step 1：创建任务（不加 --wait = 不前台阻塞 = 立刻拿 task_id 返回）
TASK_ID=$(python3 ~/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py create \
  --ref-images <url1> <url2> \
  --prompt "<v14 4 段式 prompt>" \
  --duration 4 --ratio 16:9 \
  --model doubao-seedance-2-0-fast-260128 \
  --watermark false --generate-audio true \
  --download <output_path> \
  2>&1 | grep "Task ID:" | awk '{print $3}')
echo "task_id = $TASK_ID"

# Step 2：存 task_id 兜底（参考 §1 + §10.5）
echo -e "${TASK_ID}\tclip<N>\t<output_path>\t$(date +%H:%M:%S)" >> task_ids.tsv

# Step 3：轮询状态（用 urllib + json.loads，不走 shell 管道，参考 §1 + status 状态读取陷阱 Pitfall）
python3 << EOF
import os, json, urllib.request, time
env = {}
with open(os.path.expanduser('~/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env')) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

API_KEY = env['ARK_API_KEY']
TASK_ID = '$TASK_ID'
start = time.time()
while time.time() - start < 600:  # 10 分钟上限
    req = urllib.request.Request(
        f'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{TASK_ID}',
        headers={'Authorization': f'Bearer {API_KEY}'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    if d.get('status') == 'succeeded':
        video_url = d['content']['video_url']
        urllib.request.urlretrieve(video_url, '<output_path>')
        print(f'✅ downloaded: <output_path>')
        break
    elif d.get('status') == 'failed':
        print(f'❌ failed: {d}')
        break
    time.sleep(15)
EOF

# Step 4：校验文件存在 + 大小 > 0（参考 §9 4 必查）
ls -lh <output_path>

# Step 5：ffprobe 实测时长（绘本场景必做，参考 picturebook-video skill Step 6.0 ffprobe SOP）
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  <output_path>
```

**反模式 vs 正确做法 · 决策表**：

| 场景 | 决策 | 原因 |
|---|---|---|
| 第一次创建 + 马上要结果 | 用 `--wait`（前台阻塞）| 简单直接，1-2 分钟能出 |
| 已创建 + 想拿 status | ❌ **不重跑前台** | 重复扣费 |
| 已创建 + 想下载 | 用 task_id + urllib 轮询 + urllib 下载 | 0 元 |
| 批量并发 | §10 模板（subprocess.Popen + 独立 download 路径） | 节省 60% 时间 |
| 想知道进度 | urllib 轮询（不用 --wait）| 0 元 + 不阻塞 |

**触发场景**：
- 任何 `seedance.py create` 之后 + 想拿结果的所有场景
- 任何 agent / sub-agent / 脚本里调 seedance 之后想确认完成度
- 任何用户问"任务完成了吗" / "视频在哪" / "为什么不下载"

**用户原话**（2026-06-11 grey 绘本实战）："不要重跑前台，已提交的任务，只要有了task id就表示扣费，你检查API用法，使用task id去查询状态，并下载视频"

**关联铁律**：
- §1 task_id 必存（基础）—— 本节是 §1 之后的下一步
- §10 并发调度（batch 场景）—— 本节是单任务场景的对应
- §3 ark list 端点救援（task_id 丢失时）

---

### Pitfall: status 状态读取陷阱（2026-06-10 Rabbit Clip4 实测 · 必看）⭐⭐⭐

**症状**：用 `seedance.py status <task_id>` 或 shell `curl + python3 管道 + grep` 查 task 状态时，**可能拿到不完整 JSON 看不到 status 字段**。本会话 Rabbit Clip4 `cgt-20260610093758-qg6cg` 真实状态 = `succeeded`（有 video_url 可下载），但 shell 管道版本 status 字段可能被截断或 grep 漏掉，**误判为 "running 死锁"**。

**根因**（2026-06-10 实测）：
- `seedance.py status` CLI 输出走 argparse formatter，**可能不带 status 字段明文**
- shell `curl | python3 -c "...d.get('status')..."` 管道里 `python3 -c` 的引号转义在某些 shell 下会截断 JSON
- `grep "Task ID"` 抓 task_id 的常见模式**只看 created_at 之前字段**

**修复方向**（**Rabbit Clip4 实测验证过**）：
1. **状态查询必用 `execute_code` + python urllib + json.dumps**（不走 shell 管道）：
   ```python
   import os, json, urllib.request
   env = {}
   with open('/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env') as f:
       for line in f:
           line = line.strip()
           if line and not line.startswith('#') and '=' in line:
               k, v = line.split('=', 1)
               env[k.strip()] = v.strip()
   
   task_id = 'cgt-XXXXXXXX'
   req = urllib.request.Request(
       f'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}',
       headers={'Authorization': f'Bearer {env["ARK_API_KEY"]}'}
   )
   with urllib.request.urlopen(req, timeout=30) as r:
       d = json.loads(r.read())
   print('status:', d.get('status'))
   print('video_url:', d.get('content', {}).get('video_url'))
   ```
2. **查 video_url 之前必查 status**（`status != succeeded` 时 `content.video_url` 必然是 None/缺失，不是 URL 失效）
3. **`updated_at` 不动 ≠ 任务死锁**——Rabbit Clip4 实测：updated_at 1781055488（创建时间）→ 之后变 1781056653（成功后）= 静止 20 分钟内是正常的（seedance 14s 720p 视频生成约 15-25 分钟），**不要立刻报"卡死"**
4. **真卡死判据**：`status=running` 持续 > 30 分钟 + `updated_at` 始终未变 + DELETE 返回 `InvalidAction.RunningTaskDeletion` = **3 个条件全中才标 orphan**

**判断口诀**：
- ❌ shell 管道 + grep 拼装查 status = 信息截断风险
- ✅ execute_code + python urllib + json.dumps = 完整 dump status / video_url / updated_at / seed / duration 一次拿全
- ⏱️ `updated_at` 静止 ≤ 30 分钟 = 正常生成中
- 🚨 `updated_at` 静止 > 30 分钟 + status 仍 running + DELETE 拒 = 真死锁

**触发场景**：任何 seedance 任务查 status / 下载 video / 排查 "running 死锁" 怀疑时。

### ⚠️ chevereto 二次上传同图 code 101 绕过（2026-06-04 沉淀）

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

**完整文档**：见 `references/audio-bugs-and-hosting.md` §"chevereto 二次上传同图 code 101 绕过"。

### ⚠️ mp3 音频必须走公网直链（chevereto 不接音频）

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

**完整决策树 + 实测矩阵**：见 `references/audio-bugs-and-hosting.md` §"mp3 音频必须走公网直链"。

### Key 找不到的排查路径

如果遇到 `ARK_API_KEY not set`：

1. 确认 `.env` 文件存在于 `~/.hermes/skills/seedance2.0-tool/.env`
2. 确认文件内有正确的 `ARK_API_KEY=...` 行（无引号）
3. `seedance.py` 通过 `load_dotenv()` 自动加载 `.env`，无需手动 source

**不要**在 `~/.bashrc` 中 export key——subprocess 不会继承 bashrc 环境变量。

## 子命令

> ⚠️ **跑前必先 `create --help`（2026-06-05 Cat 绘本踩坑 · 铁律 #35）**：
> - seedance.py CLI 是**子命令结构** `create / status / wait`——**不**是直接接所有参数
> - 错误调用（直接传 model/ratio/duration）→ `error: argument command: invalid choice`
> - **正确流程**：先 `seedance.py create --help` 看参数 → 再拼命令
> - 完整 SKILL.md 里的样例命令是 `create` 子命令版（不是直接参数版）

```bash
# 跑前必查（1 秒成本，避免 4 次报错起步）
python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py create --help 2>&1 | head -30

# 创建视频任务
python3 seedance.py create [options]

# 查询任务状态（含长跑 hint · 不判卡死 — 30 分钟阈值）
python3 seedance.py status <task_id>

# 列出最近 N 条任务（含长跑标记 · 不判卡死）
python3 seedance.py list [--page-size 10]

# 等待任务完成
python3 seedance.py wait <task_id> [--download <path>]
```

> ✅ **2026-06-13 新增 list 子命令**：CLI 历史上缺 `list`，2026-06-13 用 `cmd_list` 补上（含长跑标记列）。`list` 是排查"任务为什么没完成"的**首选入口**——同批次任务状态一眼对比，比单点 `status` 信息密度高得多。
>
> **长跑 hint 行为**（2026-06-13）：`status` 子命令在 `status=running/pending` + `updated_at==created_at`（API 设计如此）+ **超过 30 分钟**时打 💡 hint，**不**断言卡死；提示内容是建议跑 `list` 看相邻任务对比。这跟 2026-06-10 实战沉淀的"`updated_at` 不动 ≠ 卡死"铁律完全一致——30 分钟阈值就是按 qg6cg 19 分钟 + 余裕定的。

**救命通道 · ark REST list 端点**（task ID 丢失时使用）：

```bash
source /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env

# 拉最近 20 个任务
curl -sS -H "Authorization: Bearer $ARK_API_KEY" \
  "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks?page_size=20" \
  > /tmp/ark_tasks.json

# 解析后批量下载 video_url（不重提交 task = 0 元）
python3 << 'EOF'
import json, urllib.request
d = json.load(open('/tmp/ark_tasks.json'))
for item in d['items']:
    if item['id'] in {'cgt-...', 'cgt-...'}:  # 按你记得的 ID 过滤
        urllib.request.urlretrieve(item['content']['video_url'], f'./out_{item["id"]}.mp4')
EOF
```

**关键限制**：
- `page_size` 20，看不到所有历史任务
- 必须按 `created_at` 时间窗口过滤
- `video_url` 24h 过期 → **立刻下载**
- **不替代铁律 30**（task ID 必存是首选预防）

**完整任务管理铁律**：见 `references/task-management-and-cost.md`（task ID 必存 + wait 打断校验 + ark list 救援 + 任务成本意识）。

> ⚠️ **状态查询反模式 · 2026-06-10 实战沉淀（Pic8 Rabbit Clip4）**：**`updated_at == created_at` ≠ 任务卡死**。这是 Ark API 设计——`updated_at` 只在**状态机转移时刷新**（queued → running → succeeded / failed），running 阶段内部不刷新。
>
> **错误判读**（Pic8 Rabbit v1+ v2 都踩过）：
> - 看 `status=running` + `updated_at == created_at` → 误判"任务死锁"
> - 看 `wait` 子命令 180s timeout → 误判"卡死"
> - 看 `video_url=None` → 误判"失败"
>
> **正确判读**：
> - 唯一权威字段是 **`status`**（running / queued / succeeded / failed）
> - `updated_at` 只在状态转移时刷新，running 阶段不变化是**正常**
> - 长生成耗时是**正常的**——实测范围 2-20 分钟，复杂 prompt（14s + audio + 多图参考）可达 19+ 分钟（qg6cg 案例）
> - **真正的死锁信号**：`status=queued` 超过 5 分钟没变 OR API 返回 InvalidAction.RunningTaskDeletion 持续 30 分钟
>
> **正确轮询模式**（**不**用 shell + `seedance.py wait`）：
> 1. 用 execute_code + urllib 直接调 `GET /api/v3/contents/generations/tasks/{id}`（带 Bearer）
> 2. 轮询间隔 15-30 秒，**不**设硬超时（允许 30+ 分钟）
> 3. 看到 `status=succeeded` 立即读 `content.video_url` + 下载（24h 过期）
>
> **反模式（铁律）**：
> - ❌ 用 `seedance.py status <task_id>` + shell 管道 → 状态字段可能截断
> - ❌ 用 `--wait` 阻塞 180s/600s → 强制 timeout = 假阳性"失败"
> - ❌ 看 `updated_at` 没动就报"卡死" → 真假阳性反复出错
> - ✅ 唯一信源：`status` 字段 + 24h 内的 video_url

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

## 导演模式 · 深度指南

> **完整导演模式使用指南见 [`references/director-mode.md`](references/director-mode.md)`**
> **绘本/图片书视频工作流见 [`references/picturebook-video-workflow.md`](references/picturebook-video-workflow.md)`**（静态绘本图+旁白→动画视频，含Clip衔接设计）
> 以下是快速参考摘要，详细内容（含7个实战模板）请查看完整文档。

### 核心心法

Seedance 2.0 不是绘图工具，是**虚拟导演**。需要的不 是"美丽的描述"，而是**分镜脚本**。像导演一样思考——摄像机在哪？走多快？近景还是远景？光线从哪来？

### 提示词六要素顺序

| 顺序 | 要素 | 示例 |
|---|---|---|
| 1 | Subject（主体） | `A female warrior in black tactical bodysuit` |
| 2 | Action（动作） | `delivers a powerful roundhouse kick` |
| 3 | Environment（环境） | `abandoned neon-lit industrial factory` |
|  | Camera（运镜） | `dramatic side-angle tracking shot` |
| 5 | Style（风格） | `cinematic action movie style like John Wick` |
| 6 | Lighting/Mood（光/氛围） | `golden hour backlighting mixed with blue neon` |

### @-Tags 常用指令

| 想要的效果 | prompt 里这么写 |
|---|---|
| 设置视频第一帧 | `@Image1 as the first frame` |
| 锁定角色外观 | `@Image1's character as the subject` |
| 复制镜头运动 | `reference @Video1's camera movements and transitions` |
| 复制动作编排 | `reference @Video1's action choreography` |
| 替换视频中的人物 | `Replace the person in @Video1 with @Image1` |
| 背景音乐 | `BGM references @Audio1` |

### 爆款关键词

- `seamless loop-ready motion` — 无缝循环
- `ASMR-satisfying aesthetic` — 舒缓催眠感
- `split-synced transitions` — 节奏卡点转场

### 必须避免的词

`"有点""大概""某种""美丽的"` — 模型无法猜测。`Beautiful light` 什么都不是，`soft golden hour backlighting` 是明确指令。

## ⚠️ 任务管理铁律（2026-06-05 Say 说绘本踩坑沉淀 · 必读）⭐⭐

> **Say 说绘本 10 Clip 批量提交 4 个核心问题**：
> 1. task ID 没存（`tail -1` 抓丢）→ **6 个 ID 全丢**
> 2. wait 被中断 → 退出码非 0 但任务 succeeded，没补校验
> 3. seedance.py 无 `list` 子命令 → 想找回 ID 没办法
> 4. 重提交 task = **重复扣费**（用户原话"20 元"）
>
> **修复**：**全套铁律 + 救援通道**见 `references/task-management-and-cost.md`（含 7 节：成本意识 / task ID 必存 / wait 打断校验 / ark list 救援 / 默认值表 / 单测门 SOP / 自检清单）。

## 9. 自检清单升级（v2）

**5 必避**（在原 4 必避基础上 + 1）：

- ❌ `for ... do ... done` 串行 + `tail -1` 抓 ID 不存变量
- ❌ 后台 `&` 启动不存 PID/task ID
- ❌ wait 被打断就盲重创建（**先 status 查实际状态**——可能已 succeeded）
- ❌ task ID 丢了直接重提交（**先查 ark list 端点救回**——video_url 24h 有效，0 元重跑）
- ❌ **客户端报错就当服务端没跑成**（**必先 list 端点核对**——2026-06-07 pic2 实战：客户端报"API 401"但服务端 8 个全 succeeded）

## 9.1 红线（v1）· 已发任务 = 已扣费 = 绝不可重跑（2026-06-11 grey 绘本实战沉淀）⭐⭐⭐

> **用户原话**（2026-06-11 grey 绘本 clip 2 实战）：
> - "**停！**"（主 agent 重跑前台时被强打断）
> - "**不要重跑前台，已提交的任务，只要有了 task id 就表示扣费**"
> - "**你检查 API 用法，使用 task id 去查询状态，并下载视频**"

**铁律（新增，2026-06-11）**：

| 反模式（禁止） | 正解（必走） |
|---|---|
| ❌ 重跑前台 `subprocess.run(create + --wait)` | ✅ 只跑 `create`（拿 task_id），**不**用 `--wait` |
| ❌ 看到 status=running 就慌，想"再发一个确保成功" | ✅ 用 `urllib.request.Request` 查 status，running 是正常的 |
| ❌ 客户端报错 = 任务没跑成 | ✅ task_id 拿到了 = 已扣费 = 必查 + 下载，**不**重发 |
| ❌ 觉得"这次可能没扣费所以重发" | ✅ **任何** task_id = 必扣费，**永远不**重发同一绘本的任务 |

**反模式触发条件**：
- 主 agent 调用了 `seedance.py create --wait ... --download <path>` 阻塞前台 → 想"重来" → **错**
- 看到 600s timeout = 想"再发" → **错**（700s timeout 也可能 succeeded）
- 输出没拿到 = 想"再发" → **错**（用 task_id 查 status + 单独 download）

**正解流程**（任何"看到 status ≠ succeeded 或 0 视频文件"时）：

```python
import json, urllib.request, time
# 1. 用 task_id 查 status（status 是唯一权威字段）
req = urllib.request.Request(
    f'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{TASK_ID}',
    headers={'Authorization': f'Bearer {ARK_API_KEY}'}
)
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
status = d.get('status')  # queued / running / succeeded / failed

# 2. status 决定动作
if status == 'succeeded':
    video_url = d.get('content', {}).get('video_url')
    # 下载（24h 有效）
    urllib.request.urlretrieve(video_url, OUTPUT_PATH)
elif status == 'running':
    # 等（**不**重发）
    time.sleep(15)
    # 重新查 status
elif status == 'failed':
    # 看 d['error']，**不**立即重发 = 0 元先诊断
    print(json.dumps(d, indent=2))
elif status == 'queued':
    # 排队中等（**不**重发）
    time.sleep(15)
```

**关键判断口诀**：
- ✅ "task_id 拿到 = 已扣费" = **必走查 status + 单独 download** 路径
- ❌ "重发任务能解决任何问题" = **错**（重发 = 重复扣费 + 不一定解决问题）
- ❌ "客户端 timeout = 任务失败" = **错**（status 才是唯一权威）

**反例（grey clip 2 实战）**：
- 主 agent 跑了 `seedance.py create --wait` 阻塞 90s + 看输出
- 用户打断："**停！**已扣费 = 不重跑"
- 主 agent 改用 `urllib.request.Request` 查 status = succeeded（1m48s）→ 单独 download = 2.0 MB
- **0 元重跑** + 视频拿到

**判断口诀**：
- ✅ 任何已发任务 = 必查 + 下载，**不**重跑
- ✅ 任何 `create` 命令 = 不带 `--wait`（前台阻塞 = 等于变相"想重跑"风险）
- ✅ 任何 status 查询 = urllib 直接调 REST API（不走 shell 管道，避免截断）

**触发场景**：
- 任何 `seedance.py create` 调用后必走此 SOP
- 任何"我看到 600s 超时了 = 失败了" 的判断
- 任何"再发一次确保成功" 的想法



**4 必查**：

- ✅ `wc -l task_ids.txt` == 计划任务数
- ✅ 每个 task 跑完 `wait` 后 `ls -lh` 校验文件存在
- ✅ 交付前所有 task `status` 都 succeeded
- ✅ **批量交付前必做"三元组绑定校验"**：本地文件 md5 ↔ ark list video_url ↔ clip 序号 三者对得上（2026-06-07 pic2 实战：v1-clip5-fixed.mp4 md5 实际是 ark 任务 6 的内容 = 3 错位 + 1 漏下）

### ⚠️ 错位铁律：三元组绑定（2026-06-07 pic2 实战 · 必读）⭐⭐

> **触发场景**：绘本 / 短视频批量跑 N 个 Clip，**用户说"clip X 失败/不对"**但服务端 8 个任务全 succeeded。
>
> **根因**：子 agent D 跑完用 `--download ./v1-clipN-fixed.mp4` 默认按"我跑的序号 N"命名，但**没把 task_id ↔ 本地文件 ↔ 旁白/clip 语义**三者绑定校验。下载时**漏 1 错 3**——md5 一对才看出来。
>
> **实测案例**（pic2 绘本 8 Clip）：
>
> | 本地文件 | md5 | 真实 ark task | 真实内容 |
> |---|---|---|---|
> | v1-clip1-fixed.mp4 | 20898c | drzfn | clip1 ✓ |
> | v1-clip2-fixed.mp4 | 6ce6a4 | 6xz56 | clip2 ✓ |
> | v1-clip3-fixed.mp4 | f3e63a | 48hmb | clip3 ✓ |
> | v1-clip4-fixed.mp4 | 3f67ae | slx57 | clip4 ✓ |
> | v1-clip5-fixed.mp4 | **6a49b4** | = ark clip6 (xnxhz) | **❌ 是 clip6** |
> | v1-clip6-fixed.mp4 | **fa967d** | = ark clip7 (kvj88) | **❌ 是 clip7** |
> | v1-clip7-fixed.mp4 | **8c11ab** | = ark clip8 (bmqml) | **❌ 是 clip8** |
> | (v1-clip8 不存在) | — | — | **❌ 漏下** |
>
> **SOP**（批量跑完必做，0 元）：
>
> ```bash
> # 1. 拉 ark list 端点拿全部 video_url
> source /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env
> curl -sS -H "Authorization: Bearer $ARK_API_KEY" \
>   "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks?page_size=30" \
>   > /tmp/ark_tasks.json
>
> # 2. 按 created_at 排序 + 编号，得到"服务端 clip 顺序"
> python3 << 'EOF'
> import json
> from datetime import datetime, timezone, timedelta
> d = json.load(open('/tmp/ark_tasks.json'))
> items = sorted(d['items'], key=lambda x: x['created_at'])
> # 假设本次任务的提交窗口是 22:00-23:30 CST
> win = [it for it in items if '22:00' <= (datetime.fromtimestamp(it['created_at'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M') <= '23:30']
> for i, it in enumerate(win, 1):
>     print(f"server_clip{i}\t{it['id']}\t{it['content']['video_url'][:60]}...")
> EOF
>
> # 3. 下载全部到 /tmp + 算 md5
> for i in $(seq 1 8); do
>   url=$(python3 -c "...")  # 按 server_clipN 拿 video_url
>   curl -sS -L -o /tmp/batch_$i.mp4 "$url"
> done
> md5sum /tmp/batch_*.mp4 /home/luo/project/v1-clip*-fixed.mp4 | sort
>
> # 4. 三元组核对：本地的 md5 必须能在 /tmp 里找到匹配，反之亦然
> # 不匹配 → 错位 / 漏下 → 重新按 server_clip 顺序覆盖命名
> ```
>
> **铁律**：
> - ✅ 批量跑完**不立刻交付**，先跑三元组校验（5 分钟 0 元，能避免 100% 错位交付）
> - ✅ 客户端报"401/failed"**不直接信**——必先 list 端点核对（24h 内 video_url 都可救）
> - ✅ task_id 持久化文件**不只存 ID**，要存 `task_id\tclip_idx\tlocal_path\t旁白摘要`（一行一组，便于 md5 反查）
> - ❌ "task_id 存了 = 安全"——昨夜就是反例：存了 task_id 但**没和本地文件做绑定**

### 单任务必存 task_id 模板

```bash
# ✅ 正版（每个 task 必用这个模式）
TASK_ID=$(python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py create \
  --ref-images /path/to/img.jpg \
  --prompt "..." \
  --duration 4 --ratio 16:9 --resolution 720P \
  --model doubao-seedance-2-0-fast-260128 \
  --watermark false --generate-audio true \
  --download /path/to/output.mp4 2>&1 | grep "Task ID" | awk '{print $3}')
echo "task_id = $TASK_ID"
echo "$TASK_ID" >> /path/to/project/task_ids.txt

# 阻塞等结果（不后台）
python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py wait $TASK_ID \
  --download /path/to/output.mp4
ls -lh /path/to/output.mp4  # 必校验
```

### 绘本场景默认值（绘本启动必跑 · 4 个值全对才算 OK）

| 参数 | 必设值 | 不设的后果 |
|---|---|---|
| `--watermark` | `false` | 绘本带 AI 水印 = 产品缺陷（2026-06-03 Ok 好的绘本踩坑）|
| `--generate-audio` | `true` | 绘本 ≠ 全静音，需要拟声/环境音（2026-06-02 Red 绘本踩坑）|
| `--ratio` | `16:9` | 短视频平台标准（用户原话"视频比例默认 16:9"）|
| `--duration` | `4-10s` | 4s 硬下限，10s 体验最佳 |

**反模式**：
- ❌ 用 seedance.py 默认值跑绘本 → 水印 + 比例错 + 时长错 4 件事全错
- ❌ 不查绘本原图比例（绘本 1920×1200 = 16:10，但视频模型自动适配 16:9，**不需裁切**）—— 用户原话"你不用看原图，视频模型会自动处理"

### 任务成本意识

- 单任务约 0.1-20 元（按 prompt 复杂度 + 时长 + 分辨率差异大）
- **批量提交前必报总预算**给用户
- 任何"重提交 task"前**必查 ark list 端点**（不查 = 可能重复扣费）

### 交付必发实际文件

视频生成后**必须**通过对话渠道发实际文件（`MEDIA:/path/to/file.mp4` 或 send_message）。只发链接或文字描述"已完成"= 任务失败（用户看不到视频）。

## 工具状态追踪（2026年5月）

| 工具 | 类型 | 状态 | 用途 |
|------|------|------|------|
| seedance2.0-tool | CLI + Skill | 主力 | 豆包即梦 Seedance 2.0 视频生成 |
| seedance2.0（旧） | Skill | 已废弃 | nginx/docker 上传架构，已迁移到 seedance2.0-tool |

**安装验证（2026-05-18）：**
```bash
python3 ~/.hermes/skills/seedance2.0-tool/seedance.py --help
skill_view(name='seedance2.0-tool')
# readiness_status: available
```

**情报追踪标准：**
- 高优先级：新模型、新功能、新 API、@参考系统使用技巧
- 低优先级/跳过：已废弃工具相关内容、非工具性纯理论文章

**完整安装与验证笔记：** `references/skill-install-notes.md`
**导演模式深度指南（含7个模板）：** `references/director-mode.md`
**Clip 衔接问题实战诊断：** `references/clip-continuity.md`
**Key 配置问题排查：** `references/troubleshooting.md`
**🎯 音频相关 bug 完整 4 项 + 公网 URL 决策树（2026-06-04 沉淀）：** `references/audio-bugs-and-hosting.md`
**绘本 v12 范式（外部 BGM）：** `references/paradigm-v12-external-bgm.md`（外部 mp3 走 uguu.se 托管 + chevereto 不接音频的兜底）
**Seedance 2.0 官方文档调研笔记（2026-06-04）：** `references/seedance-official-docs-research-2026-06-04.md`
**v13 范式修复（2026-06-04 实测沉淀）：** 同上 reference §13（参考图失效 5 大根因 + 5 个官方依据修复 + 完整 v13 prompt 模板）
**音频"音色 + 配乐"分离（2026-06-04 用户反馈沉淀）：** 同上 reference §14（v12 audio-driven 默认"参考"不"原样播放" + 后期 ffmpeg 替换音频轨）
**公网文件 URL 兜底路线（chevereto 不支持音频时用 uguu.se）：** `references/public-file-hosting-fallback.md`
**⭐ 任务管理与成本意识（2026-06-05 Say 说绘本踩坑沉淀）：** `references/task-management-and-cost.md`（task ID 必存 + wait 打断校验 + ark list 救援 + 任务成本意识）

## ⚡ 衔接设计：每个 Clip 必须设计「出动作/入动作」

> **教训（2026-05-26 实战）**：火把节 Clip 4-6 各自独立生成，生成时没有设计衔接。模型默认从头开始动作（人物站好、场景静置），导致拼接像 10 张 GIF 随机播放。**衔接必须在生成前设计，不能事后补救。**

### 三种模式

| 模式 | 做法 | 适用 |
|------|------|------|
| **模式 A：独立 Clip** | 每个 clip 单独生成，无衔接设计 | ❌ 问题根源，不推荐 |
| **模式 B：导演时间线** | 一个 prompt 写多段 `[00-05s] Shot 1` + `[05-10s] Shot 2` | ✅ 单次 ≤15s，内部自动衔接 |
| **模式 C：尾帧接力** | Clip N 尾帧用 `--return-last-frame` → 作为 Clip N+1 的 `--last-frame` 驱动 | ✅ 超时长时跨 Clip 物理连贯 |

**推荐：模式 B + C 结合** —— 每个 prompt 内部用时间线写法（模式 B），段间用尾帧接力（模式 C）。

### 分镜脚本必须包含的内容

每个 Clip 的脚本描述必须写清楚三段：

```
Clip N
├─ 开头：承接 Clip N-1 结尾 → 【具体动作/元素】
├─ 中段：【当前场景核心动作】
└─ 结尾：【出动作】→ 下一 Clip N+1 开头要从这个动作接
```

**示例（Clip 4→5）：**
```
Clip 4（庭院日常）
├─ 开头：承接 Clip 3 → 男人拿起松木准备制作火把
├─ 中段：女人制作扫帚，男人削木柴、绑火把、浸松脂
└─ 结尾：女人把火把举起 → 火把头朝右

Clip 5（黄昏出发）
├─ 开头：承接 Clip 4 → 火把从画面右侧进入，小女孩从右侧接过火把
├─ 中段：小女孩举火炬率队列出发，夕阳下行进
└─ 结尾：小女孩回首望身后 → 镜头推进她的眼神 POV
```

### 操作步骤

1. **生成 Clip N 时**：加 `--return-last-frame`，拿到尾帧图
2. **生成 Clip N+1 时**：用尾帧图作为 `--last-frame`，同时在 prompt 开头写「承接上一 Clip 结尾：【具体动作描述】」

**命令示例：**
```bash
# Clip N：生成 + 返回尾帧
python3 seedance.py create \
  --image ./clip{N}_first.png \
  --prompt "[00-07s] 中段动作描述，结尾：角色举起火把朝右" \
  --return-last-frame \
  --duration 8 \
  --ratio 16:9 \
  --wait --download ./output

# Clip N+1：用尾帧接力
python3 seedance.py create \
  --image ./clip{N+1}_first.png \
  --last-frame ./clip{N}_last.png \
  --prompt "承接 Clip N 结尾：火把从右侧进入，角色接过火把..." \
  --duration 8 \
  --ratio 16:9 \
  --wait --download ./output
```

> ⚠️ **一个 prompt 只能放一张尾帧图**。如果 N 个 Clip 接龙，用 N-1 次接力。

### 错误做法（已踩坑）

- ❌ 先批量生成所有 Clip，再想办法拼接 → 必然断裂
- ❌ 每个 Clip prompt 开头都写「画面开始」或「场景静置」→ 模型从头开始，无连续感
- ❌ 尾帧图手动截图上传 → API 要求用 `--return-last-frame` 返回的图