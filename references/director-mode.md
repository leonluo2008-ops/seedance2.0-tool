# Seedance 2.0 导演模式 · 深度指南

> 本文档整理导演模式（Director Mode / Multi-shot Storytelling）的完整使用指南，包括提示词结构、@-Tags 语法、7个实战模板。
> CLI 工具调用方式见 SKILL.md 主文件。

---

## 什么是导演模式

Seedance 2.0 的导演模式（Multi-shot Storytelling）是其核心差异化能力：
**一个 prompt 生成多个连续分镜，角色/场景/运镜全程锁定，自动转场，无需手动剪辑。**

与普通单镜头生成的本质区别：把视频创作从「描述画面」变成「指挥镜头」。

**核心心法**：Seedance 2.0 不是绘图工具，是虚拟导演。需要的不 是"美丽的描述"，而是**分镜脚本**。像导演一样思考——摄像机在哪？走多快？近景还是远景？光线从哪来？

---

## 四模态输入

| 模态 | 上限 | 作用 |
|------|------|------|
| 文本（Text） | 1 | 定义剧情走向、镜头运动、转场节奏 |
| 图片（Image） | ≤9 | 锁定角色外观、场景背景、首帧/尾帧 |
| 视频（Video） | ≤3 | 动作参考、运镜模板 |
| 音频（Audio） | ≤3 | 台词节奏、BGM 情绪、背景音效 |

**输入限制：**
| 类型 | 数量上限 | 单文件大小 |
|------|---------|-----------|
| 图片 | ≤9 | ≤30MB |
| 视频 | ≤3（总时长 2-15s） | ≤50MB |
| 音频 | ≤3（总时长 ≤15s） | ≤15MB |

---

## 核心能力详解

### 多镜头叙事一致性
- 模型在生成多组分镜时通过共享 Attention 机制保持特征一致
- 角色五官、服装细节、环境光照全程锁定
- 支持激烈动作戏（飞身踢腿、快速换位）下的"锁脸"

### 导演级运镜控制
- 支持推/拉/摇/移/跟/环绕/升降等电影级镜头
- 单场景内多主体差异化调度
- 电影级转场逻辑（淡入淡出、跳切等）

### 原生口型同步
- 帧级音画对齐（毫秒级精度）
- 支持 10+ 语言
- 音频可来自参考音频文件，模型自动匹配口型

### 物理规律建模
- 改善穿模、反物理悬浮
- 布料流体、光影变化更真实
- 减少"穿墙而过"等穿帮镜头

---

## 提示词结构（六要素顺序）

严格按此顺序书写，模型训练数据按此顺序组织。顺序混乱会导致模型权重分配错位。

| 顺序 | 要素 | 作用 | 示例 |
|---|---|---|---|
| 1 | **Subject（主体）** | 焦点是谁/什么 | `A female warrior in black tactical bodysuit` |
| 2 | **Action（动作）** | 具体在做什么 | `delivers a powerful roundhouse kick, then transitions into precise handgun fire` |
| 3 | **Environment（环境）** | 在哪发生 | `abandoned neon-lit industrial factory` |
| 4 | **Camera（运镜）** | 镜头怎么动 | `dramatic side-angle tracking shot with dynamic camera shake` |
| 5 | **Style（风格）** | 视觉美学 | `cinematic action movie style like John Wick` |
| 6 | **Lighting/Mood（光/氛围）** | 光线和情绪 | `golden hour backlighting mixed with blue neon` |

**四步法（快速上手版）**：
1. 说清楚主体（谁/什么）
2. 描述场景（环境、时间、情绪）
3. 描述镜头运动（推、拉、跟、摇）
4. 控制节奏（动作快慢、情绪递进）

---

## @-Tags 精确语法

上传文件后，系统自动命名 `@Image1, @Image2, @Video1` 等。在 prompt 中用自然语言为每个文件分配角色。

### 常用 @ 指令

| 想要的效果 | prompt 里这么写 |
|---|---|
| 设置视频第一帧 | `@Image1 as the first frame` |
| 锁定角色外观 | `@Image1 for character appearance` 或 `@Image1's character as the subject` |
| 视觉风格参考 | `@Image1 as style reference` |
| 场景背景 | `scene references @Image2` |
| 复制镜头运动 | `reference @Video1's camera movements and transitions` |
| 复制动作编排 | `reference @Video1's action choreography` |
| 替换视频中的人物 | `Replace the person in @Video1 with @Image1` |
| 背景音乐 | `BGM references @Audio1` |
| 音效参考 | `sound effects reference @Video3's audio` |
| 多帧连续镜头 | `@Image1 through @Image5`（模型理解为顺序帧） |
| 视频节奏/韵律 | `video rhythm references @Video1` |
| 视觉效果模板 | `completely reference @Video1's effects and transitions` |

**组合示例**：
```
@Image1's character as the subject, reference @Video1's camera movement
and action choreography, BGM references @Audio1, scene references @Image2
```

**原则**：越具体越好。`@Image1 as reference` 不如 `@Image1 as character's face and clothing`。

---

## 多镜头时间线写法

多个不同镜头在一个视频里，用时间轴分段指定：

```
[00–05s] Shot 1: 特写 — 女孩脸部表情，紧张
[05–10s] Shot 2: 全景 — 她冲出工厂大门
[10–15s] Shot 3: 升格 — 爆炸，火光充满画面
```

模型按时间顺序生成连续镜头，不会乱跳。

---

## 运镜术语（直接抄进 prompt）

模型看过大量电影素材，认识以下术语：

**镜头运动**
- `tracking shot` — 摄像机跟随主体移动
- `dolly zoom` — 后退+镜头推进（眩晕效果/希区柯克变焦）
- `shallow depth of field` — 背景虚化
- `anamorphic lens` — 宽银幕镜头（带典型光晕）
- `golden hour backlighting` — 日落逆光
- `360° rotation` — 360度旋转
- `steady tracking shot` — 平稳跟拍
- `push in / pull out` — 推进/拉远
- `whip pan` — 快速摇镜
- `crane shot` — 升降镜头

**景别**
- `Extreme close-up` — 特写（眼睛、嘴巴等细节）
- `Close-up` — 脸部特写
- `Medium close-up` — 头部+肩部
- `Medium shot` — 腰部以上
- `Full shot` — 全身
- `Wide / Establishing shot` — 环境全景
- `Bird's eye` — 俯视镜头
- `First-person POV` — 主观镜头

---

## 实战提示词模板（7个已验证示例）

使用前替换 `@Image1, @Image2` 等为实际上传文件的编号。

### ① 电影感动作场景
```
@Image1 as first frame and character reference, @Image2 as environment style.
A female warrior in black tactical bodysuit stands in the center of an abandoned
neon-lit industrial factory. She delivers a powerful roundhouse kick sending an enemy
flying, then seamlessly transitions into precise one-handed handgun fire with bright
muzzle flashes. Dramatic side-angle tracking shot with dynamic camera shake,
cinematic action movie style like John Wick, realistic physics and gravity,
golden hour backlighting mixed with blue neon, 1080p, ultra-smooth motion.
```
> ⚠️ **注意**：当前线上 API 中 `first_frame` 和 `reference_image` 互斥，上述 `@Image1 as first frame and character reference` 语法会触发 API 报错。如需同时锁定首帧和角色外观，需要制作「角色+构图」合并的首帧图。
要点：第一帧用图锁定起始姿势；写 `realistic physics and gravity` 否则打斗像飘着；暖冷混合光线增加对比。

### ② 病毒式循环满足视频
```
@Image1 as the product (first and last frame).
A perfect sphere of liquid mercury sits on a mirror surface in a minimalist studio.
It slowly deforms under invisible force into a perfect cube, then smoothly morphs
back into a sphere. Reflections shift realistically, extreme macro close-up,
seamless loop-ready motion, ASMR-satisfying aesthetic, clean white background
with soft directional lighting, high-end commercial style.
```
要点：同一张图同时作为首帧和尾帧，保证无缝循环；`ASMR-satisfying aesthetic` 是算法关键词；反射写清楚，循环视频里反射做砸了特别明显。

### ③ 情感故事（多镜头）
```
@Image1 as main character appearance, @Image2 as location style.
A young man (@Image1) comes home tired after work, walks down a warm hallway,
stops at the door, takes a deep breath and smiles. Close-up of his face relaxing,
then his daughter and dog run to hug him. One continuous tracking shot,
cozy home interior, cinematic family drama style like "The Pursuit of Happyness",
soft natural window light, gentle camera movement, native warm ambient sound.
```
要点：角色绑定 `@Image1` 保证面部一致；`one continuous tracking shot` 要求平滑跟随不剪辑；`native warm ambient sound` 让模型自己生成脚步声、开门声。

### ④ 高端产品广告
```
@Image1 as the watch (product reference).
Premium wristwatch floats and slowly rotates in mid-air against pure black background.
Water droplets suspended around it catch dramatic spotlight like diamonds. Extreme macro
details on every texture and reflection, high-end jewelry commercial aesthetic,
ultra-smooth 360° rotation, Apple-level cinematic quality.
```
要点：产品悬浮+旋转不需要手或支架；`Apple-level cinematic quality` 是质量基准词，模型理解这意味着什么。

### ⑤ 超现实梦境
```
@Image1 as person, @Image2 as doorway style.
A person walks through a normal doorway and steps into an impossible M.C. Escher
landscape where staircases go upside down and gravity shifts. Floating dust particles
catch golden light shafts, smooth steady tracking shot following the walker,
dreamlike ethereal atmosphere, Christopher Nolan's Inception meets Studio Ghibli style.
```
要点：直接提艺术家名字（Escher、Nolan、宫崎骏）模型能理解风格；`gravity shifts` 是打破物理规则的许可，不写这个模型会按真实物理来。

### ⑥ 前后对比 Transformation
```
@Image1 as starting object, @Image2 as final object.
Split-screen: left side shows ordinary plain coffee mug on desk, right side
dramatically transforms the same mug into an ornate golden chalice with jewels and
glowing effects. Satisfying swipe transition, dramatic before-after reveal,
clean studio lighting, viral transformation trend style, fast-paced editing.
```
要点：分屏布局；`satisfying swipe transition` 不是硬切而是平滑过渡；`viral transformation trend style` 让模型知道当前社交流行的风格。

### ⑦ 赛车/动作多镜头时间线
```
Style: Hollywood professional racing movie (Le Mans style), cinematic night, heavy rain.
[00–05s] Veteran driver in helmet looks focused, rain lashes windshield.
[05–10s] Rival car next to him, adrenaline in eyes.
[10–15s] Green light — both cars accelerate on wet track, water sprays into camera,
motion blur on stadium lights.
```
要点：时间轴分三段，镜头节奏从静到动递进；指定 `heavy rain` `motion blur` 等物理细节；结尾镜头朝赛车方向抬，视觉冲击感强。

---

## 爆款算法关键词

放在 prompt 末尾能提升平台推荐率：

- `seamless loop-ready motion` — 可无缝循环
- `ASMR-satisfying aesthetic` — 舒缓催眠感
- `before-after transformation` — 前后对比
- `fast-paced editing` — 快节奏剪辑
- `viral transformation trend style` — 社交流行趋势风格
- `beat-synced transitions` — 节奏卡点转场

**必须避免的词**：`"有点""大概""某种""美丽的"` — 模型无法猜测。`Beautiful light` 什么都不是，`soft golden hour backlighting` 是明确指令。

---

## 素材准备清单

### 必须准备
- 🎯 **主体图片**：角色正脸/全身，用于锁定外观（至少1张）
- 🎬 **首帧图片**：你想视频第一帧长什么样（推荐准备）
- ✍️ **prompt**：按六要素结构写的分镜脚本

### 可选准备
- 🌄 **风格参考图**：想要的视觉风格/色调/光感
- 📹 **运镜参考视频**：录一段镜头运动，模型会复制
- 🎵 **音频文件**：MP3，最长15秒（特定BGM或音效）
- 🖼️ **尾帧图片**：视频最后一帧长什么样

### 推荐工作流（省成本）
先用 Seedance 1.5 或图片生成模式测试 prompt 的构图和逻辑，确认分镜没问题再正式生成 Seedance 2.0。

---

## API 接入方式

### DeepInfra（推荐，稳定）
- 地址：`https://deepinfra.com/ByteDance/Seedance-2.0`
- 定价（480p/780p）：$4.3/M tokens（含视频），$7/M（不含）
- 定价（1080p）：$4.7/M（含视频），$7.7/M（不含）
- 支持 Demo 试用

### Atlas Cloud（第三方聚合）
- 提供 Seedance 2.0 统一 API + 300+ 其他 AI 模型
- 支持多镜头场景续接
- 地址：`https://www.atlascloud.ai`

### 即梦 AI（字节官方网页端）
- 支持导演模式全部功能
- 缺点：算力排队，生成有概率波动

---

## 竞品对比（官方参数）

| | Seedance 2.0 | 可灵 3.0 | Sora 2 |
|--|---|---|---|
| 最长时长 | 10秒/镜头 | 短视频 | 20秒 |
| 多镜头 | ✅ 自动转场 | 需手动拼接 | 部分支持 |
| 角色一致性 | ⚠️ 实测结论：reference_image **无法**锁定角色外貌 | 中等 | 中等 |
| 口型同步 | 原生支持10+语言 | 需额外处理 | 需额外处理 |
| 音频生成 | 原生同步音效+音乐 | 部分支持 | 部分支持 |
| 四模态输入 | ✅ | ❌ | ❌ |

> ⚠️ **实测提醒（2026-05-22）**：传入角色参考图（托比：黄色安全帽+方脸小眼）+ 分镜图，生成结果为黑发护目镜卡通人，与角色图完全不像。`reference_image` 只能提供风格/场景参考，不能保持角色特征一致性。官方 skill 文档描述的"锁脸能力强"在当前线上 API 中**未经实测验证**。

---

## 对绘本视频的价值评估

| 需求 | Seedance 2.0 匹配度 |
|------|-------------------|
| 多镜头连续叙事 | ✅✅ 核心能力 |
| 角色一致性（角色外观不变） | ✅✅ 锁脸能力强 |
| 口型同步（对话/旁白） | ✅ 原生支持 |
| 运镜控制（推拉摇移） | ✅ 导演级控制 |
| 音频+画面同步 | ✅ 原生支持 |
| 短片段稳定性 | ✅ 适合 |
| 长镜头成功率 | ⚠️ 有概率波动 |

**适用场景：** 绘本角色连续动作故事、角色对话场景、多镜头分镜叙事
**不适用：** 超长镜头（>20s 连续）、需要 100% 确定性输出的场景

---

## 典型绘本视频工作流

1. **角色锁定**：上传角色设定图（9张参考图中的主角色）
2. **动作编排**：上传参考视频定义动作节奏
3. **分镜设计**：一个 prompt 写多个分镜（如 0-5s 开场、5-10s 发展、10-15s 高潮）
4. **音频同步**：上传旁白/BGM，模型自动匹配口型和节奏
5. **运镜描述**：在 prompt 中写明镜头运动（推近/拉远/环绕）

---

## 一句话总结

导演模式 = **四模态同时输入 → 多镜头自动生成 → 角色/运镜/口型全程锁定**，是当前最接近"导演工具"的 AI 视频生成方案。
