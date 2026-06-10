# 批量 Clip 交付前验证 SOP（2026-06-07 pic2 实战沉淀）

> **触发场景**：绘本 / 短视频批量跑 N 个 Clip，跑完用户**说"clip X 失败/不对"**，但**服务端 list 显示 N 个全 succeeded**——这时问题**不在 seedance**，在**"任务 ↔ 本地文件 ↔ 旁白/clip 语义" 三者没绑定**。
>
> **本文档收口**：3 步验证流程 + vision 三元组工具 + 5 个必查交付前清单。

---

## 1. 客户端报错 ≠ 服务端失败（2026-06-07 pic2 复盘 ⭐⭐）

> **用户原话（第一次踩坑）**："昨晚火山引擎的API key报错导致无法继续"——我查完发现 key 有效、8 个任务全 succeeded。
> **用户原话（第二次踩坑）**："不对，你刚才给我的是clip7视频，昨晚clip8没成功"——结果 vision 一看是**"小兔在图书馆"≠ 我以为的"may I read"** = **场景错位**不是任务失败。

**根因**：
- 子 agent D 报"API 401"→ 实际是别的退出码，但**任务已经 submitted 到 ark**
- 子 agent 报"clip8 失败"→ 实际是 ark 有这个 task + 服务端 succeeded + **只是和用户预期的"收势夕阳"内容对不上**（绘本原图本身就没画夕阳收势）

**铁律**：
- ❌ **客户端报错信了就当失败**——重复扣费
- ✅ **任何"X clip 失败"先做"服务端 30 秒核对"再下结论**：
  1. list 端点拉最近 30 个任务
  2. 按 created_at 时间窗口过滤（绘本批量跑基本是连号的，间隔 9-13 分钟/clip）
  3. 数量对得上 → 服务端 OK，问题在**本地 / 语义层**
  4. 数量对不上 → 才有可能是真失败

---

## 2. 三元组绑定铁律（task_id ↔ 本地文件 ↔ 旁白/clip 语义）

> **实测案例**（pic2 绘本 8 Clip，2026-06-06 22:03-23:24 提交）：
>
> | 本地文件 | md5 | 真实 ark task | 真实内容 | 错位？ |
> |---|---|---|---|---|
> | v1-clip1-fixed.mp4 | 20898c | drzfn | clip1 "Mama, read" | ✅ |
> | v1-clip2-fixed.mp4 | 6ce6a4 | 6xz56 | clip2 "Papa, play" | ✅ |
> | v1-clip3-fixed.mp4 | f3e63a | 48hmb | clip3 "Teacher, sing" | ✅ |
> | v1-clip4-fixed.mp4 | 3f67ae | slx57 | clip4 "Friend, share" | ✅ |
> | v1-clip5-fixed.mp4 | **6a49b4** | = ark clip6 (xnxhz) | **clip6 "may I eat"** | ❌ |
> | v1-clip6-fixed.mp4 | **fa967d** | = ark clip7 (kvj88) | **clip7 "may I read"** | ❌ |
> | v1-clip7-fixed.mp4 | **8c11ab** | = ark clip8 (bmqml) | **clip8 "Let's learn" 收势** | ❌ |
> | (v1-clip8 不存在) | — | — | — | **❌ 漏下** |
>
> **用户说"clip7 是 may I read"**—— md5 显示本地 v1-clip6-fixed.mp4 才是 may I read（ark 任务 7），**用户混淆是正常的**因为他**没看 md5 也没 vision 验证**。

**核心教训**：
- ✅ **task_id 持久化不够**——昨夜我存了 task_id 但**没和本地文件名 / 旁白 / clip 序号** 4 元绑定
- ✅ **批量交付前必做"三元组绑定"**：服务端 task (有旁白) ↔ 本地文件 (有 md5) ↔ 用户认知里的 clip 序号
- ✅ 错位的发现**必须靠 md5 + vision**，不能靠"我觉得对"——**AI 自我感觉"任务全成功了 = 交付 OK"是最大陷阱**

---

## 3. 三步验证 SOP（0 元 · 5 分钟）

### Step 1：服务端核对（30 秒）

```bash
set -a; source /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env; set +a
curl -sS -H "Authorization: Bearer $ARK_API_KEY" \
  "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks?page_size=30" \
  > /tmp/ark_tasks.json
python3 << 'EOF'
import json
from datetime import datetime, timezone, timedelta
d = json.load(open('/tmp/ark_tasks.json'))
items = sorted(d['items'], key=lambda x: x['created_at'])
# 假设批量跑在 22:00-23:30 CST
win = [it for it in items if '22:00' <= (datetime.fromtimestamp(it['created_at'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M') <= '23:30']
print(f"服务端匹配任务数 = {len(win)}（计划 8 个）")
for i, it in enumerate(win, 1):
    print(f"server_clip{i}\t{it['id']}\t{it['status']}\t{it.get('duration')}s")
EOF
```

**核对**：
- 数量 == 计划数 → 服务端 OK，继续 Step 2
- 数量 < 计划数 → 才是真漏跑，按 plan 补提（不重提已 succeeded 的）

### Step 2：md5 错位核对（1 分钟）

```bash
# 下载全部到 /tmp/identify/
mkdir -p /tmp/identify
python3 << 'EOF'
import json, subprocess
d = json.load(open('/tmp/ark_tasks.json'))
items = sorted(d['items'], key=lambda x: x['created_at'])
from datetime import datetime, timezone, timedelta
win = [it for it in items if '22:00' <= (datetime.fromtimestamp(it['created_at'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M') <= '23:30']
for i, it in enumerate(win, 1):
    url = it['content']['video_url']
    out = f"/tmp/identify/server_{i}_{it['id'].split('-')[-1]}.mp4"
    subprocess.run(['curl', '-sS', '-L', '-o', out, url])
EOF

# 算两边 md5
md5sum /tmp/identify/*.mp4 /home/luo/<project>/v1-clip*-fixed.mp4 2>/dev/null | sort
```

**核对**：
- 每个本地 `v1-clipN-fixed.mp4` 的 md5 必须能在 `/tmp/identify/server_N.mp4` 里找到匹配
- 不匹配 → 错位 / 漏下
- 漏下 → 重新按 server_clipN 顺序 cp 覆盖

### Step 3：vision 语义核对（3 分钟 · 防"场景错位"）

> **本步是 pic2 教训的核心**——md5 对齐 ≠ 语义对位。绘本原图本身可能**和旁白没对位**（玩具房当 eat、餐桌当 read、书店当收势）。

```bash
# 抽每条视频的 t=0.5s 帧（场景建立瞬间）
mkdir -p /tmp/identify/frames
for f in /tmp/identify/server_*.mp4; do
  base=$(basename "$f" .mp4)
  ffmpeg -y -ss 0.5 -i "$f" -frames:v 1 -q:v 2 "/tmp/identify/frames/${base}_t0.5.jpg" 2>/dev/null
done
```

**然后用 vision_analyze 抽帧（用 native vision，不用 vision_analyze 外部工具）**——问 4 件事：
1. 室内还是室外
2. 有几个角色 / 什么颜色
3. 有没有大人在场
4. 顶部有没有 "Please" / "请" 字

**核对**：
- 8 张 vision 描述对应 8 句旁白 → ✅ 全部对位
- 有 X 张 vision 描述和旁白不匹配 → **绘本原图本身有错**（不是 seedance 的锅），**主 agent 应该先看原图再决策是否重提任务**

---

## 4. 绘本原图错位的根因 + 修复（pic2 教训 ⭐）

> **pic2 教训**：绘本 8 张原图本身**和旁白没对位**——
> - task6 xnxhz = 玩具房（应为 eat 餐桌）❌
> - task7 kvj88 = 餐桌（应为 read 看书的场景）❌
> - task8 bmqml = 书店（应为收势夕阳爱心）❌
>
> **根因**（主 agent 拍脑袋错配）：
> - 绘本 C 子 agent（storyboard-design）按"通用兔子+场景"模板生成 8 张图
> - 主 agent 拍脑袋把"小兔+场景"对上"May I... / Let's learn" 8 句旁白
> - **没做原图 vision 验证**就进 D 子 agent 跑任务
> - 等用户看视频才发现错位，**8 个任务全成功 + 8 个视频全错位 = 100% 错位交付**

**修复**（绘本项目启动前必跑）：
1. ✅ 绘本原图生成后**必做 vision 验证**（每张图 + 旁白 + 故事弧线对位）
2. ✅ 主 agent 派活前**必查"原图-旁白对位表"**（用 table 显式 8 行 N 列）
3. ✅ 错位**必须重画原图**而不是改 prompt——prompt 救不了场景错位
4. ❌ "我看到了图大概对了" —— **vision 看到 ≠ 旁白对位**，**vision + 旁白双校验**才是

---

## 5. 交付前 5 必查清单（pic2 实战 0 元保险）

| # | 必查 | 怎么查 | 失败后果 |
|---|---|---|---|
| 1 | **服务端任务数 == 计划数** | list 端点按时间窗口过滤 | 漏跑 / 误删 |
| 2 | **所有任务 status == succeeded** | list 端点 status 字段 | 失败任务混入 |
| 3 | **本地文件存在 + 大小正常** | `ls -lh v1-clip*.mp4` | 下载中断 |
| 4 | **md5 三元组绑定对齐** | 见 §3 Step 2 | 错位交付（pic2 教训）|
| 5 | **vision 语义对位** | 见 §3 Step 3 | 场景错位（pic2 教训）|

**反模式**：
- ❌ "8 个任务都 succeeded = 交付 OK" —— pic2 反例
- ❌ "md5 对了 = 没问题" —— 语义对位要 vision 验
- ❌ "我看一眼视频画面" —— **AI 自我感觉 = 最大陷阱**，**用户视角 + vision 抽帧**才是真

---

## 6. 复用：vision_analyze 抽帧 prompt 模板

> 每次批量交付前，用这个 prompt 模板问 vision。

```
这是绘本的一帧画面。请描述：
(1) 主场景是室内还是室外
(2) 有几个小兔子/什么颜色
(3) 有没有大人在场（如兔妈妈/兔爸爸/老师/朋友）
(4) 顶部有没有彩色英文 "Please" 和中文 "请" 字
用 1-2 句简短回答。
```

**触发模式**（vision_analyze 已配置 native vision patch，2026-06-07）：
- ✅ **直接传图给当前 model**（不调 mcp_zai_analyze_image，丢像素）
- 一次一批 4-8 张并行 vision_analyze
- 输出用 table 汇总
