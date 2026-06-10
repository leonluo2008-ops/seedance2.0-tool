# 绘本视频工作流（基于即梦 SOP 简化版）

> 本文档定义从「已有静态绘本图片+旁白」到「视频成片」的完整工作流。
> 适用于：用户已有 10 张静态绘本图 + 对应旁白（Excel/MP3），需快速转视频的场景。

---

## 完整 SOP vs 绘本简化路径对比

| 官方 Phase | 内容 | 绘本场景 |
|-----------|------|---------|
| Phase 0-3 | 创意→大纲→剧本 | **跳过**：旁白即剧本 |
| Phase 4 | 素材挖掘 | **跳过**：图片已处理好角色/风格一致性 |
| Phase 5 | 分镜设计（4步） | **做**：script-chunk + shots-timing + shots-assembly + scene-reflection |
| Phase 6 | 需求确认 | 用户自确认 |
| Phase 7 | 参考素材生成 | **跳过**：图片已处理好一致性 |
| Phase 8 | 分镜生视频 | **做**：video-prompt + 并行生成 |
| Phase 9 | 视频剪辑 | **做**：ffmpeg 拼接 + BGM 合并 |

**核心结论**：从 Phase 8 开始执行，跳过 Phase 4/7（图片已完成一致性处理）。

---

## 工作流 Step by Step

### Step 1：图片分析（Vision）

**必须先做，不能跳过。**

对每一张图片执行：
```
分析内容：场景、人物、构图、色彩、氛围、关键元素
输出：图片分析摘要（用于后续 prompt 匹配）
```

> ⚠️ **教训**：绝对不能用旁白反推画面描述。图片里有什么才能写什么，硬加图片没有的内容会导致视频生成结果不符预期。

### Step 2：旁白与图片匹配

把每段旁白匹配到对应的图片上（不是按序号硬套）。

匹配原则：
- 看图片实际场景是否贴合旁白内容
- 同一场景顺序连接自然
- 避免"图说不到一块"的情况

输出：匹配表（图片→旁白）

### Step 3：分镜计时（shots-timing）

基于即梦 SOP 的 shots-timing 规则：

| 类型 | 计算方式 |
|------|---------|
| 台词镜头 | 字数 × 0.3 秒/字 |
| 最低保底 | 每镜 ≥1 秒 |
| Clip 硬约束 | 4秒 ≤ 每 Clip ≤ 15秒 |

> 用户明确要求：**时长测算必须严格按照 shots-timing.md，不凭感觉估算。**

### Step 4：生成 Prompt（video-prompt 规范）

每个 Clip 的 Prompt 必须包含：
1. **参考主体引用**：`@Image1`（首帧图片）
2. **场景描述**：描述当前 Clip 所在场景，要求保持与图片一致
3. **分镜动作描述**：按时间线写 `[00-02.5s]` + 镜头描述
4. **风格一致性说明**：要求整体风格与图片保持一致

Prompt 格式示例：
```
[00-02.5s] Wide establishing shot, terraced fields cascade down green mountains, 
villagers in colorful ethnic clothing gather near white houses. 
[02.5-05s] Medium shot, villagers smile and interact, festive atmosphere. 
[05-07.5s] Tracking shot slowly pulls back, revealing the gathering crowd. 
Style: flat 2D cartoon illustration, warm lighting, consistent ethnic characters, 
cinematic camera movement.
```

### Step 5：并行生成所有 Clip

所有 Clip **一次性并行提交**，不串行。

```bash
python3 seedance.py create \
  --image /path/to/image_N.jpg \
  --prompt "..." \
  --duration 8 \
  --ratio 16:9 \
  --model doubao-seedance-2-0-fast-260128 \
  --wait \
  --download /path/to/output_dir
```

> ⚠️ **注意**：`--duration` 参数必须是整数，浮点数（如 `7.5`）会导致 CLI 报错：`invalid int value: '7.5'`。

### Step 6：ffmpeg 拼接 + BGM 合并

```bash
# 1. 列出所有生成的 clip 文件（按顺序）
ls -v torch_festival/output/*.mp4 > clips.txt

# 2. 生成拼接文件
cat clips.txt | while read f; do echo "file '$f'"; done > concat.txt

# 3. ffmpeg 拼接
ffmpeg -f concat -safe 0 -i concat.txt -c copy concat_raw.mp4

# 4. 合并 BGM（自动延长 BGM 匹配视频总时长）
ffmpeg -i concat_raw.mp4 -i "Torch Festivalб╢╗Ё░╤╜┌б╖.mp3" -shortest -c:v copy -c:a aac output_final.mp4
```

---

## 关键教训（从实战中提取）

### 1. 图片分析不能省略
之前犯过这个错误：没有分析图片就凭旁白设计画面描述，结果与图片实际内容不符。
**正确做法**：先 vision 分析每张图，再写 prompt。

### 2. duration 参数必须是整数
`--duration 7.5` 会报错：`argument --duration: invalid int value: '7.5'`。
向上取整到最近的整数，或在 prompt 里写清楚实际需要的秒数。

### 3. 旁白按 0.3 秒/字 计算
用户确认这是正确标准，不是估算。计算后合并为 Clip 时必须满足 4-15 秒硬约束。

### 4. 并行生成，不串行
同一阶段多个生成任务，必须一次性并行提交，不串行分批。

### 5. 交付必须发实际文件
生成完成后必须将视频文件发送给用户，不能只发链接或文字描述。

---

## 工作流速查

```
已有：静态图（1.jpg~10.jpg）+ 旁白 Excel + BGM MP3

Step 1 → 分析每张图片（vision）
Step 2 → 旁白与图片匹配
Step 3 → shots-timing 计算时长
Step 4 → shots-assembly 合并 Clip（如需合并）
Step 5 → video-prompt 生成并行任务
Step 6 → Seedance 并行生成所有 Clip
Step 7 → ffmpeg 拼接 + BGM 合并
```