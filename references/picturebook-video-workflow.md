# 绘本视频工作流（静态图 → 动画视频）

> **适用场景**：用户已有 N 张静态绘本图 + 对应旁白，需要转成动画视频。
> **核心约束**：每个 AI 生成的 Clip 必须在 4-15 秒之间；衔接设计必须在生成前完成，不能事后补救。
> **Skill 依赖**：调用 `seedance2.0-tool` 生成视频，调用 `picturebook-creator` 生成绘本图片。

---

## 两种路径对比

| 阶段 | 官方 SOP（Phase 0-9） | 绘本场景（简化路径） |
|------|---------------------|-------------------|
| Phase 0-3 | 创意→大纲→剧本 | **跳过**：旁白即剧本 |
| Phase 4 | 素材挖掘 | **跳过**：图片已处理好角色/风格一致性 |
| Phase 5 | 分镜设计（4步） | **做**：script-chunk + shots-timing + shots-assembly + scene-reflection |
| Phase 6 | 需求确认 | 用户自确认 |
| Phase 7 | 参考素材生成 | **跳过**：图片已处理好一致性 |
| Phase 8 | 分镜生视频 | **做**：video-prompt + 并行生成 |
| Phase 9 | 视频剪辑 | **做**：ffmpeg 拼接 + BGM 合并 |

**核心结论**：从 Phase 8 开始执行，跳过 Phase 4/7（图片已完成一致性处理）。

---

## 完整工作流 Step by Step

### Step 1：图片分析（Vision）

**必须先做，不能跳过。**

对每一张图片执行：
```
分析内容：场景、人物、构图、色彩、氛围、关键元素
输出：图片分析摘要（用于后续 prompt 匹配）
```

> ⚠️ **教训**：绝对不能用旁白反推画面描述。图片里有什么才能写什么，硬加图片没有的内容会导致视频生成结果不符预期。

---

### Step 2：旁白与图片匹配

把每段旁白匹配到对应的图片上（不是按序号硬套）。

匹配原则：
- 看图片实际场景是否贴合旁白内容
- 同一场景顺序连接自然
- 避免"图说不到一块"的情况

输出：匹配表（图片→旁白）

---

### Step 3：分镜计时（shots-timing）

基于即梦 SOP 的 shots-timing 规则：

| 类型 | 计算方式 |
|------|---------|
| 台词镜头 | 字数 × 0.3 秒/字 |
| 最低保底 | 每镜 ≥1 秒 |
| Clip 硬约束 | 4秒 ≤ 每 Clip ≤ 15秒 |

---

### Step 4：Clip 合并（shots-assembly）

将分镜合并为 4-15 秒的 Clip。

每个 Clip 必须包含三段衔接设计（**核心，生成前必须写好**）：

```
Clip N
├─ 开头：承接 Clip N-1 结尾 → 【具体动作描述】
├─ 中段：【当前场景核心动作】
└─ 结尾：【出动作】→ 下一 Clip N+1 开头要从这个动作接
```

---

### Step 5：连贯性校验（scene-reflection）

检查每个 Clip 之间的：
- 人物外观一致性
- 场景/道具一致性
- 光影/色调一致性
- 逻辑连贯性

输出修复后的 Clip 表 + 一致性注意事项。

---

### Step 6：生成 Prompt（video-prompt）

每个 Clip 的 Prompt 必须包含：
1. **主体定义**（v13 新增）：`将图片1中的[主角核心特征]定义为主角`（官方 §1 定义主体）
2. **参考主体引用**：`<主体N>@<图片N>` 显式绑定（官方 §1 注意）
3. **场景描述**：描述当前 Clip 所在场景，要求保持与图片一致
4. **分镜动作描述**：按时间线写 `[00-02.5s]` + 镜头描述
5. **衔接描述**：prompt 开头写「承接上一 Clip 结尾：【具体动作】」
6. **风格一致性说明**（v13 强化）：用官方推荐风格词（"2D paper collage style" / "3D国风漫画"）而不是模糊形容

> ⚠️ **v13 范式必读（2026-06-04 用户纠错沉淀）**：v11-β/v12 prompt 与参考图"语义冲突"会导致参考图完全失效。完整 5 个官方依据修复点见 `references/seedance-official-docs-research-2026-06-04.md` §13。

**导演模式时间线写法（模式 B）**：
```
[00-02.5s] Shot 1: 承接上一Clip，火把从右侧进入，小女孩接过火把
[02.5-05s] Shot 2: 小女孩举火炬率队列出发，夕阳下行进
[05-07.5s] Shot 3: 镜头推进小女孩眼神POV，回首望身后
Style: flat 2D cartoon illustration, warm lighting, consistent ethnic characters.
```

**尾帧接力写法（模式 C）**：
- 在 prompt 开头明确写：「承接 Clip N 结尾：火把从画面右侧进入」
- 下一 Clip 生成时用 `--last-frame` 传入上一 Clip 的尾帧图

---

### Step 7：并行生成所有 Clip

所有 Clip **一次性并行提交**，不串行。

```bash
python3 seedance.py create \
  --image /path/to/image_N.jpg \
  --prompt "..." \
  --duration 8 \
  --ratio 16:9 \
  --model doubao-seedance-2-0-fast-260128 \
  --return-last-frame \
  --wait \
  --download /path/to/output_dir
```

> ⚠️ **`--duration` 参数必须是整数**，浮点数（如 `7.5`）会导致 CLI 报错：`invalid int value: '7.5'`。向上取整到最近的整数。

---

### Step 8：ffmpeg 拼接 + BGM 合并

```bash
# 1. 列出所有生成的 clip 文件（按顺序）
ls torch_festival/output/*.mp4 > clips.txt

# 2. 生成拼接文件
cat clips.txt | while read f; do echo "file '$f'"; done > concat.txt

# 3. ffmpeg 拼接
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy concat_raw.mp4

# 4. 合并 BGM（自动延长 BGM 匹配视频总时长）
ffmpeg -y -i concat_raw.mp4 -i "bgm.mp3" -shortest -c:v copy -c:a aac output_final.mp4
```

---

## 三种衔接模式

| 模式 | 做法 | 适用 |
|------|------|------|
| **模式 A：独立 Clip** | 每个 clip 单独生成，无衔接设计 | ❌ 问题根源，不推荐 |
| **模式 B：导演时间线** | 一个 prompt 写多段 `[00-05s] Shot 1` + `[05-10s] Shot 2` | ✅ 单次 ≤15s，内部自动衔接 |
| **模式 C：尾帧接力** | Clip N 尾帧用 `--return-last-frame` → 作为 Clip N+1 的 `--last-frame` 驱动 | ✅ 超时长时跨 Clip 物理连贯 |

**推荐：模式 B + C 结合** —— 每个 prompt 内部用时间线写法（模式 B），段间用尾帧接力（模式 C）。

---

## 关键教训（从实战中提取）

### 1. 衔接必须在生成前设计
不能在 clip 生成完后再想办法拼接，必须在分镜阶段就设计好「出/入动作」。

### 2. duration 参数必须是整数
`--duration 7.5` 会报错：`argument --duration: invalid int value: '7.5'`。向上取整到最近的整数。

### 3. 旁白按 0.3 秒/字计算
用户确认这是正确标准，不是估算。计算后合并为 Clip 时必须满足 4-15 秒硬约束。

### 4. 并行生成，不串行
同一阶段多个生成任务，必须一次性并行提交，不串行分批。

### 5. 交付必须发实际文件
生成完成后必须将视频文件发送给用户，不能只发链接或文字描述。

### 6. 图片分析不能省略
之前犯过这个错误：没有分析图片就凭旁白设计画面描述，结果与图片实际内容不符。**正确做法**：先 vision 分析每张图，再写 prompt。

---

## 工作流速查

```
已有：静态图（1.jpg~10.jpg）+ 旁白 Excel + BGM MP3

Step 1 → 分析每张图片（vision）
Step 2 → 旁白与图片匹配
Step 3 → shots-timing 计算时长
Step 4 → shots-assembly 合并 Clip + 衔接设计
Step 5 → scene-reflection 连贯性校验
Step 6 → video-prompt 生成并行任务
Step 7 → Seedance 并行生成所有 Clip（模式B+模式C）
Step 8 → ffmpeg 拼接 + BGM 合并
```

---

## 即梦 API 限制速查

| 参数 | 限制 |
|------|------|
| 单次生成时长 | 4-15s（超出报错） |
| 导演时间线上限 | ~15s（一个 prompt 内可写多段时间线） |
| 总时长 67s 如何处理 | 分 4-5 个 prompt，每个内部用时间线，段间尾帧接力 |