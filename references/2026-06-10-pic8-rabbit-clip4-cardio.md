# Pic8 Rabbit Clip4 实战沉淀（2026-06-10 · 音频调试 + 状态查询反模式）

> **触发场景**：绘本 Clip 跑出来没声音 / 状态查询一直显示 running 不确定是否完成 / 想确认任务是真的卡死还是正常生成
>
> **3 个核心教训**：
> 1. **BGM ≠ 音效**（用户红线）
> 2. **状态查询反模式**（`updated_at == created_at` ≠ 卡死）
> 3. **生成时长可到 20 分钟**（不要被 2-5 分钟的"常见时长"误导）

---

## 1. BGM vs 音效 · 用户红线

**用户原话**：
> "不要乱发挥，不生成 BGM 是红线，是底线。**我刚问的是没有音效，所以你应该关注音效的生成。不是生成 BGM**"

**Pic8 Rabbit Clip4 v1 翻车**：
- prompt 末尾写"全程画面...无背景音乐"+ 又写"无任何背景音乐"
- 双重否定 + 加 BGM 描述 = seedance 整体静默
- 结果：视频成功生成 + **完全无声**

**修复（v2 prompt）**：
```
保留 TTS 音轨占位，时长匹配旁白朗读时长（8 秒）。
全程无背景音乐、无旁白人声、无哼唱、无歌唱。
音效：每个英文单词（it、bit、sit、kit、fit）出现瞬间各伴随<短促清脆的叮 一响>，5 词共 5 次清脆叮咚音效，节奏贴合单词浮现节奏。
末帧 5 词并排时伴随<一阵轻快的鸟叫声 渐弱>。
画面保持无字幕、无水印、无 Logo。
```

**关键点**：
- ✅ `全程无背景音乐、无旁白人声、无哼唱、无歌唱` —— 这 4 个"无"是绘本场景允许的
- ✅ 音效用 `<...>` 包裹（官方特殊字符规范，doc2 §440）
- ✅ CLI 参数 `--generate-audio true` 仍要开（让 seedance 生成音效）
- ❌ 不要写 BGM 描述（"钢琴 + pizzicato 90 BPM"）—— 触发 BGM 红线

---

## 2. 状态查询反模式（Pic8 Rabbit 反复踩）

### 2.1 错的方式

**反模式 A · 看 updated_at 判断卡死**：

```python
# 错误判读
if status == 'running' and updated_at == created_at:
    print('任务卡死！')  # ← 错！
```

**真相**：Ark API 的 `updated_at` 只在**状态机转移时刷新**（queued → running → succeeded/failed）。running 阶段内部不刷新 `updated_at` 是**官方设计**，不代表卡死。

**反模式 B · 用 `seedance.py wait` 阻塞 + 设硬超时**：

```bash
# 错误用法
seedance.py wait $TASK_ID --download ./out.mp4  # ← 默认 600s timeout
```

**问题**：
- shell 管道 + grep 抓 status 时字段可能被截断
- 180s/600s 硬 timeout → 长生成任务（14s 视频可达 19+ 分钟）被强制 timeout
- 客户端 timeout ≠ 服务端失败（Pic2/2026-06-07 三元组绑定教训同类坑）

### 2.2 对的方式

**正确模式 · execute_code + urllib 直查**：

```python
import os, json, urllib.request, time

env = {}
with open('/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

task_id = 'cgt-XXXXXXXX-XXXX'

# 直接 REST 查询（不走 seedance.py wrapper）
req = urllib.request.Request(
    f'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}',
    headers={'Authorization': f'Bearer {env["ARK_API_KEY"]}'}
)
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())

# 唯一权威字段
status = d.get('status')  # running / queued / succeeded / failed
print(f'status: {status}')

# succeeded 后才有 video_url
if status == 'succeeded':
    video_url = d['content']['video_url']
    # 立刻下载（24h 过期）
    with urllib.request.urlopen(video_url, timeout=120) as r:
        with open('./clip.mp4', 'wb') as f:
            f.write(r.read())
```

**轮询规则**：
- 间隔 15-30 秒
- **不**设硬超时（允许 30+ 分钟）
- 看到 `status=succeeded` 立即下载
- 看到 `status=failed` 立即报告 + 看 `error` 字段

### 2.3 真假"卡死"信号

| 信号 | 真假 | 应对 |
|---|---|---|
| `status=running` + `updated_at==created_at` | **假阳性**（API 设计如此） | 继续等 |
| `status=queued` 超过 5 分钟 | **真异常**（服务队列卡住） | 重提交 |
| API 返回 `InvalidAction.RunningTaskDeletion` | **假阳性**（官方不允许取消 running task） | 改 DELETE → 改 wait until succeeded |
| 20+ 分钟仍 running（无 queued） | **可能正常**（复杂 prompt 长生成） | 看同类 task 历史耗时作参考 |
| `execution_expires_after=172800`（48h）| 任务最长存活 48 小时 | 超时 = 自动 expired |

---

## 3. 生成时长实测分布（Pic8 Rabbit 期间观察）

| Task | 时长 | 备注 |
|---|---|---|
| `qg6cg`（Rabbit Clip4 v1，14s，audio=false）| **19 分 26 秒** | 第一次跑 + 我以为是卡死 |
| `r7vxs`（Rabbit Clip4 v2，14s，audio=true）| **预计 ~20 分钟** | 加音效版，正在跑 |
| `94bcs`（早些其他任务）| 2 分 12 秒 | 简单场景 |
| `pqqg5` | 4 分 31 秒 | 标准时长 |
| `n8nk7` | 4 分 23 秒 | 标准时长 |
| `bh95f` | 3 分 51 秒 | 标准时长 |

**规律**：
- 简单任务（图生视频 + 短时长）：2-5 分钟
- 复杂任务（14s + 多图参考 + 自带音频设计 + 长 prompt）：**15-20 分钟**
- 绘本 Clip 默认走复杂任务 → **必须接受 15-25 分钟级别**

---

## 4. seedance.py 调用链 bug 全景（2026-06-10 总结）

| Bug | 现象 | 修复 |
|---|---|---|
| 1. `seedance.py status` 输出被 shell 管道截断 | `status=running` 但后面字段丢失 | 改 execute_code + urllib 直查 |
| 2. `seedance.py wait` 阻塞 + 强制 timeout | 180s/600s 后 timeout 但 task 实际还在跑 | 长任务不用 wait，改轮询 |
| 3. `updated_at` 字段在 running 阶段不刷新 | 误判"卡死" | 只看 `status` |
| 4. 长 prompt（>2K 字符）耗时显著长 | 14s 视频跑 19+ 分钟 | 接受现实，提前预计 20 分钟 |
| 5. `execution_expires_after=172800`（48h）无提示 | 任务过期前无通知 | 自行记录 created_at + 48h 截止 |

---

## 5. Pic8 Rabbit Clip4 时间线（事实）

```
09:22  Rabbit 兔子.zip 收到 → 解压 → 8 张 jpg + GBK乱码 readme.txt
09:23  翻译 readme.txt = UTF-8"找一找，兔子 rabbit 藏在哪里？..."
09:25  vision 看 1.jpg（封面）+ 8.jpg（尾页）=纸艺拼贴 + 温暖收势
09:32  用户给 8 段旁白（领读 + IT 家族集合）
09:34  按铁律 #91 走兜底公式 1.4 词/秒算时长
09:35  Step1 6必问 → 5 Clip 方案（11/12/12/14/6s = 55s 总）
09:36  用户纠错：图 7 单独 14s Clip（图 8 收势压到 6s）
09:38  提交 task qg6cg（generate_audio=false，audio 关闭）
09:38-09:55 wait 超时 + 反复查 status=running + updated_at 停 = 误判卡死
10:16  用户问"画面是否遵循规则"→ 已 succeeded，但我在 09:55 误删任务（其实没删成功）
11:xx  用户亲自查 API → succeeded → 下载 clip4.mp4（无音频版）
12:xx  用户问"没有声音是什么原因"
12:xx  我错误归因为 BGM 缺失（实际是 generate_audio=false CLI 参数 + prompt 兜底句双重否定）
12:xx  用户强烈纠错"不是 BGM 是音效" → 写 BGM vs 音效铁律
13:xx  提交 task r7vxs（v2 prompt，generate_audio=true + 音效事件）
13:xx  轮询 status=running + updated_at 没动 → 误判"卡死"
13:xx  用户纠错"你肯定弄错命令了"
13:xx  查官方 doc3 line286-1458 → 确认：updated_at 设计就是状态转移才刷新 + 不能 cancel running
13:xx  接受 r7vxs 还要等 ~10 分钟
```

---

## 6. 立刻可落地的修复（Pic8 Rabbit 跑完后）

### 6.1 skill 仓更新（已完成）
- ✅ seedance2.0-tool §交付规范加 BGM vs 音效红线
- ✅ seedance2.0-tool §任务管理加状态查询反模式 + 长生成预期
- ✅ 本文档写入 references/

### 6.2 picturebook-video 待办（未做）
- ❌ v15/v6/v15.1 模板 prompt 写法升级（调研笔记 §16.1）
- ❌ 子 agent C SKILL.md 同步升级
- ❌ fill_v15_template.py 同步升级

### 6.3 工具封装（用户提议 · 未启动）
- 用户 2026-06-10 原话："从昨晚开始，你就不能很正常的使用 seedance 生成视频，我感觉现在的调用方式不稳定，是否可以考虑封装成工具？"
- **方案 A**：升级 seedance.py wrapper（最小改动 · 1-2 天）
- **方案 B**：完整重写 async + 队列 + 事件驱动（中等改动 · 3-5 天）
- **方案 C**：先 A 救火，B 设计文档同步沉淀

---

## 7. 一句话 TL;DR

**BGM ≠ 音效 · updated_at ≠ 卡死信号 · 复杂 prompt 长 20 分钟属正常**。

---

## 8. Rabbit 翻车全链 · v6 错误范本 + v15 导演思维版验证（2026-06-10 · ⭐必看）

> **触发场景**：用户反馈"镜头呆板/单镜头/简单推镜头" / "只有 5 秒慢推，文字一动不动" / 写任何 seedance 2.0 绘本 prompt 之前

### 8.1 翻车链（v6 错误范本）

1. **v6 整段不分镜版被误用为通用范本**（Pic8 Rabbit newclip1 v1，2026-06-10 13:00 提交）
   - 7 个新 Clip prompt = `@image1 + 风格 + 整段主题 + 音频约束 + 画面禁令`（**没有多镜头分镜**）
   - 7 个视频 = 5 秒慢推 + 单镜头 + 文字一动不动
   - 用户原话："**生成这一批视频，使用了之前过时的镜头画面设计方式，导致了镜头非常的呆板，缺乏动感，没有故事性，非常垃圾，只有简单的推镜头，而且只有单镜头，这根本不能用！**"
   - 用户原话："**V15 系列里面对镜头语言的设计就非常的好，你只要把 V15 里面关于镜头设计的东西，结合官方文档正确的写法，修正声音、音效，等一系列的东西**"

2. **5s 5 镜头 = 每镜头 1s 翻车**（Pic8 Rabbit newclip1 v1.5，2026-06-10 13:55 提交）
   - 第一个修正版：5 个镜头（建立/角色/事件/过渡/收势）
   - 用户原话："**镜头数量应该结合旁白内容，参考图，clip 时长合理配置，5s 时长，你的镜头数量明显过多**"
   - 修复：5s = 2-3 镜头（1.5+1.5+2s 节奏）

3. **v15 导演思维版验证通过**（Pic8 Rabbit newclip1 v2，2026-06-10 13:58 提交）
   - 5s · 3 镜头（建立/单词动作/收势）· 1657 字符
   - task_id `cgt-20260610135836-mchbt` · 5 分钟跑完 · md5 bdd229bd5c995fd13abd43857280057a
   - 用户反馈："**这次的画面明显好于之前**" ✅
   - **沉淀为新规范** [`分镜设计规范-v15director.md`](../../picturebook-video/references/分镜设计规范-v15director.md) v1.0.0

### 8.2 镜头数算法（v15 实战验证 · 5 个时长档）

| 时长 | 旁白密度 | 推荐镜头数 | 节奏公式 |
|---|---|---|---|
| **5s** | 1 短句（5-7 字） | **2-3 镜头** | 1.5s 建立 + 1.5s 单词动作 + 2s 收势 |
| **8s** | 1 短句 | 3-4 镜头 | 2s 建立 + 1s 跃入 + 3-4s 单词 + 1s 收势 |
| **12s** | 3 词家族 | 5 镜头 | 2-1-3-3-3（Cat 4a v3 标版） |
| **14s** | 5 词家族 | 5-6 镜头 | 2-1-3-3-3-3（Pic4 v2 标版） |
| **15s** | 6+ 词 | 6-7 镜头 | 2-1-3-3-3-3-...（Pic7 Horse OR 家族实测） |

**判定口诀**：
- **建立镜头 = 1**（必加，交代场景）
- **单词/事件镜头 = N**（每词/每事件 1 镜头，2-3s/镜头）
- **收势镜头 = 1**（必加，定格末态）
- **总镜头数 ≤ 时长 ÷ 1.5s**（每镜头至少 1.5s，少于则糊）

### 8.3 v6 旧版 vs v15 导演思维版核心差异

| 维度 | v6 旧版（❌ Rabbit 翻车）| v15 导演思维版（✅ Rabbit 验证）|
|---|---|---|
| 镜头结构 | "整段不分镜"= 5 秒慢推单镜头 | 6 段骨架 · 多镜头时间线分镜 |
| 镜头数 | 1 镜头 = 5 秒单一运镜 | 5s=2-3 / 12s=4-5 / 14s=5-6 |
| 运镜 | "镜头缓慢平稳推进" = 死板 | 1 镜头 1 种运镜（推/拉/切/跟/摇/移 自由组合）|
| 4 逻辑齐全 | ❌ 缺音频内联 + 缺动作量化 | ✅ 运镜+动作+位置+音频内联 |
| 动作量化 | 缺（"兔子动了"）| 必加（"缓缓抬手到胸口高度"）|
| 情绪具象化 | 缺（happy/sad 抽象词）| 必加（"胡须轻颤"代替"好奇"）|
| 主体标签 | 无（"小兔子"）| 必加（`<主角小兔>` 标签，doc2 §4.2 命名精神）|
| 音效 | 集中末尾兜底句 | 每个镜头内联 `<...>`（doc2 §440 特殊字符）|

### 8.4 净化决策（2026-06-10 用户原话）

- **用户原话**："**以后 clip 分镜规范以本轮设计实测的结构为准，移除其它版本，避免污染**"
- **5 个老 references 彻底删除**（无 .deprecated 备份）：
  - `picturebook-video/references/v6-5段骨架-模板.md`
  - `picturebook-video/references/v15-4段骨架-模板.md`
  - `picturebook-video/references/2026-06-07-pic4-no-v6-final.md`
  - `picturebook-video/references/2026-06-07-pic4-no-v5-rhythm-formula.md`
  - `seedance2.0-tool/references/v6-v15-导演思维+多镜头设计-2026-06-10.md`
- **唯一权威**：[`分镜设计规范-v15director.md`](../../picturebook-video/references/分镜设计规范-v15director.md) v1.0.0
- **元偏好沉淀**：picturebook-video SKILL.md 元偏好区加"**用户说'删' = 真删 · 不擅自备份到 .deprecated 目录**"反模式

### 8.5 Rabbit 完整 prompt 模板（v15 导演思维版 · 1657 字符 · 5s · 3 镜头）

```
@image1 as the only visual reference for the entire video, children's picture book 2D paper-cut collage style, soft pastel palette of mint green, cream, white, and warm yellow, paper texture and torn edges clearly visible.

主体定义：将图片1中的小兔子定义为<主角小兔>。

整段视频呈现"找一找"主题。旁白朗读："小兔子 rabbit，藏在哪里？"。参考图原有的"rabbit"与"兔子"字样作为画面元素自然融入场景，不重新生成任何新文字。

镜头 1（建立 · 0-1.5s）：中景拉远定格，画面中央的草丛只露出<主角小兔>的两只长耳朵，纸艺拼贴的质感和纸纹清晰可见，<远处有微风轻轻吹过的声音>。
镜头 2（单词动作 · 1.5-3s）：镜头切到侧面中景特写，<主角小兔>缓缓从草丛里探出半个脑袋，胡须轻颤，眼睛眨了两下，<一声轻巧的"叮"，像铃铛一响>。
镜头 3（收势 · 3-5s）：缓推回到正面中景，<主角小兔>从草丛完全钻出坐在花田中央，前爪轻轻放下，<主角小兔>抬头望向镜头方向微笑，<远处鸟叫声渐弱>，画面定格在<主角小兔>微笑的最后一帧。

全程无背景音乐、无旁白人声、无哼唱、无歌唱。保留 TTS 音轨占位，时长匹配旁白朗读时长（5 秒）。
画面保持无字幕、无水印、无 Logo。镜头全程严格遵守"1 镜头 1 种运镜"红线（不堆叠推拉摇移）。

This is a storyboard reference image sequence, designed for picture book reading - viewers should clearly see the rabbit scene unfold with gentle micro-animations, holding the final pose for natural reading rhythm.
```

### 8.6 一句话 TL;DR

**v6 整段不分镜 = 翻车坑 · v15 导演思维版 = 唯一权威 · 镜头数 = 时长 ÷ 1.5s 上限**。
