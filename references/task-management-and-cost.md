# 任务管理与成本意识（2026-06-05 Say 说绘本踩坑沉淀 · 必读）⭐⭐⭐

> **本节是 seedance2.0-tool 的"任务管理铁律"** —— Say 说绘本 10 Clip 批量提交踩坑后沉淀。
> **根因**：seedance.py 单任务 0.1-20 元（720P 4s 实际约 0.1-0.3 元，复杂 prompt 720P 8s 实测更高），**重提交 = 重复扣费**。**任务 ID 丢失 = 100% 灾难**。

## 0. 任务成本意识（Say 说绘本 2026-06-05 关键反馈）

**用户原话**（2026-06-05）："你知道一个任务多少钱吗？20元！！！"

**实测成本**（按 Say 说绘本 10 个 4s 16:9 任务推算）：
- 单任务 token：~87300 completion_tokens（720P 4s）
- 复杂任务：~174794 completion_tokens（720P 8s 含多镜头）
- 单任务成本：约 0.1-0.3 元（实测推算，不同模型/时长差异大）
- **批量 6 个 ≈ 0.6-1.8 元**
- **批量 10 个 ≈ 1-3 元**

**但用户说"20 元"**——可能是复杂 prompt + 1080P + 长时长（15s）组合下的成本。

**意识铁律**：
- ✅ 任何"批量提交"前**必先报总预算**给用户（不报 = 用户可能不批）
- ✅ 任何"重提交 task"前**必查 ark list 端点**看能不能用原 task 下载（不查 = 可能重复扣费）
- ❌ **不**默认重提交 —— "task ID 丢了重跑一个"是**反模式**

## 1. task ID 必存铁律（铁律 30）

**根因**（2026-06-05 Say 绘本 10 Clip 批量）：用 `for ... do ... done` 串行，每条用 `tail -1` 抓 task ID 但**没存到变量** → 6 个 task ID 全丢。

**正确做法**：

```bash
# ✅ 必用 TASK_ID=$(...) 存到变量
TASK_ID=$(python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py create \
  --ref-images /home/luo/huiben-projects/say/3.jpg \
  --prompt "..." \
  --duration 4 --ratio 16:9 --resolution 720P \
  --model doubao-seedance-2-0-fast-260128 \
  --watermark false --generate-audio true \
  --download /home/luo/huiben-projects/say/output/clip3-4s-16x9.mp4 2>&1 | grep "Task ID" | awk '{print $3}')
echo "task_id = $TASK_ID"
echo "$TASK_ID" >> /home/luo/huiben-projects/say/task_ids.txt   # 持久化兜底

# ✅ 阻塞等结果（不后台）
python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py wait $TASK_ID \
  --download /home/luo/huiben-projects/say/output/clip3-4s-16x9.mp4
```

**反模式**（已踩坑）：

```bash
# ❌ 错版 1：用 tail -1 抓 ID 不存
python3 seedance.py create ... | tail -1
# → ID 立刻丢

# ❌ 错版 2：后台 & 启动不存 PID/task ID
python3 seedance.py create ... &
# → 后台跑着，agent 不知道结果

# ❌ 错版 3：for 循环用 $() 不打印 task_id 到文件
for n in 1 2 3 4 5 6; do
  python3 seedance.py create --ref-images $n.jpg ... > /dev/null
done
# → 6 个 task_id 全丢
```

**自检**（批量提交后必跑）：

```bash
# 1. task_ids.txt 行数 == 计划任务数
wc -l task_ids.txt
# 2. 每个 ID 都能查到状态
for tid in $(cat task_ids.txt); do
  python3 seedance.py status $tid | grep -E "status"
done
# 3. 视频文件全部存在
ls -lh output/*.mp4 | wc -l
```

## 2. wait 打断后必校验（铁律 29）

**根因**（2026-06-05 Say 绘本 Clip 1 v4）：`wait` 命令被用户打断，**退出码 130 但 status 实际 succeeded**，文件**没下载到本地**。

**症状**：
```bash
$ python3 seedance.py status cgt-20260605154601-dn2fr
"status": "succeeded"
"video_url": "https://ark-..."

$ ls -lh output/clip1-v4-4s.mp4
ls: 无法访问 'output/clip1-v4-4s.mp4': 没有那个文件或目录
```

**修复**（被打断后必跑）：

```bash
# 1. 先 status 确认任务已 succeeded
STATUS=$(python3 seedance.py status $TASK_ID | grep '"status"' | awk -F'"' '{print $4}')
if [ "$STATUS" = "succeeded" ]; then
  # 2. 重新 wait + download（不重创建）
  python3 seedance.py wait $TASK_ID --download ./output/clip.mp4
  # 3. 校验文件存在
  ls -lh ./output/clip.mp4 || echo "❌ 文件仍没下载"
fi
```

**铁律**：
- ✅ wait 退出码非 0 时**不直接重创建 task**（先 status 查实际状态）
- ✅ 重跑 `wait` + 同一个 `--download` 路径 = 安全的（已 succeeded 任务会立刻下载）
- ❌ 看到 wait 超时/被中断就盲重创建 = 100% 重复扣费

## 3. task ID 丢失救援 · ark REST list 端点（铁律 31）

**根因**：seedance.py 实际只有 `create/status/wait` 三个子命令（README 写的 `list` 没实现），task ID 丢失 = **官方 CLI 无法找回**。

**救命通道**（直调 ark REST 端点）：

```bash
# 1. 拿 ARK_API_KEY
source /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env

# 2. 拉最近 20 个任务
curl -sS -H "Authorization: Bearer $ARK_API_KEY" \
  "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks?page_size=20" \
  > /tmp/ark_tasks.json

# 3. python 解析 + 批量下载
python3 << 'EOF'
import json, urllib.request
d = json.load(open('/tmp/ark_tasks.json'))
# 按时间顺序映射（按 created_at 排序）
tasks = sorted(d['items'], key=lambda x: x['created_at'], reverse=True)
for i, item in enumerate(tasks[:6]):  # 取最近 6 个
    print(f"{i+1}\t{item['id']}\t{item['content'].get('video_url', 'N/A')[:80]}")
EOF
```

**拉真实 video_url 批量下载**：

```python
import json, urllib.request
d = json.load(open('/tmp/ark_tasks.json'))

# 按本次任务的图号 + 创建时间手动映射
target = {
    'cgt-20260605161930-w7zr8': 'clip4',  # 16:19:30 创建 → 对应 clip 4
    'cgt-20260605161941-k4m2x': 'clip6',
    # ... 等等，按你提交时间映射
}

for item in d['items']:
    tid = item['id']
    if tid in target:
        url = item['content']['video_url']
        out = f'./output/{target[tid]}-4s-16x9.mp4'
        urllib.request.urlretrieve(url, out)
        print(f"Downloaded {target[tid]} -> {out}")
```

**关键限制**：
- ⚠️ `page_size` 默认 10-20 → 看不到所有历史任务
- ⚠️ 必须按 `created_at` 时间窗口过滤（最近几分钟内）
- ⚠️ `video_url` 24h 过期 → **必须立刻下载**
- ⚠️ **不替代铁律 30**（仍然是首选预防）

**实测成果**（2026-06-05 Say 说绘本 10 Clip）：用 ark list 端点找回 6 个丢失的 task ID，**0 元重跑下载全部完成**。

## 4. 默认值表（绘本场景必看）

| 参数 | 默认 | 绘本场景必设 | 理由 |
|---|---|---|---|
| `--watermark` | `true`（带 AI 水印）| **`false`** | 绘本是给家长/孩子看的，水印 = 产品缺陷（2026-06-03 Ok 好的绘本踩坑）|
| `--generate-audio` | `true` | **`true`** | 绘本 ≠ 全静音，需要拟声/环境音（2026-06-02 Red 绘本踩坑）|
| `--duration` | 5s | **4-10s** | 4s 硬下限，10s 体验最佳 |
| `--ratio` | 16:9 | **16:9** | 短视频平台标准（用户原话"视频比例默认 16:9"）|
| `--resolution` | 720P | 720P | 1080P 慢且贵，720P 够用 |
| `--model` | `doubao-seedance-2-0-fast-260128` | 同左 | fast 比标准快 5x |

**反模式**：
- ❌ 用 seedance.py 默认值跑绘本 → 水印 + 比例错 + 时长错（4 件事全错）
- ❌ 不查绘本原图比例（绘本 1920×1200 = 16:10，但视频模型自动适配 16:9，**不需裁切**）—— 用户原话"你不用看原图，视频模型会自动处理"

## 5. 交付必发实际文件

**用户原话**（picturebook-video skill §9.1）："我先自己下载拼接，不需要你拼接"——绘本场景**默认不主动拼片**。

**铁律**：
- ✅ 视频生成后**必须**通过对话渠道发实际文件（`MEDIA:/path/to/file.mp4` 或 send_message）
- ❌ 只发链接或文字描述"已完成"= 任务失败（用户看不到视频）
- ✅ 单测门 SOP：跑 1 个 Clip → 发飞书 → 等用户确认 → 再批量

## 6. 单测门 SOP（参考 picturebook-video 沉淀）

```
Phase 8 启动
  ↓
【单测】选 1 个 Clip（推荐 Clip 1，开场最具代表性）
  ↓ TASK_ID=$(...) 存 + wait 阻塞 + 校验文件
  ↓ vision 自评（4 项）+ 发飞书给用户
  ↓ 用户确认「效果 OK，可以继续」
  ↓
【批量】剩余 N-1 个 Clip 并行提交（每个用独立 TASK_ID + 文件名）
  ↓ wait 每个 + 校验文件
  ↓ 发飞书交付
```

**单测重点看 5 项**（AI/人分工）：
1. 风格锁定 → ✅ AI vision 可查
2. 镜头运镜 → ✅ AI vision 可查
3. 收势 → ✅ AI vision 可查
4. 无穿帮/崩坏 → ✅ AI vision 可查
5. **音效**（有无朗读/有无 BGM/有无卡点/不抢戏）→ ❌ **必须人耳听**（vision_analyze 不支持 mp4 音频）

## 8. 错位铁律 · 三元组绑定（2026-06-07 pic2 绘本 8 Clip 实战 · 必读）⭐⭐⭐

> **触发场景**：用户说"clip X 失败/不对"，但服务端全部 succeeded。**真问题不是任务失败，是本地文件错位/漏下**。
>
> **根因**：子 agent D 跑完用 `--download ./v1-clipN-fixed.mp4` 默认按"我跑的序号"命名，**没把 task_id ↔ 本地文件 ↔ 旁白/clip 语义**三者绑定校验。
>
> **昨夜实战**（pic2 绘本 8 Clip / `cgt-20260606220322` ~ `cgt-20260606232433`）：
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
> | (v1-clip8 不存在) | — | — | **❌ 漏下 clip5 n67qf** |
>
> 用户表里报"clip8 API 401 失败"——**实际 8 个全 succeeded**（包括 `cgt-20260606232433-bmqml` 收势视频），问题在下载阶段漏了 1 错位 3，agent 误报成 401。

### 8.1 客户端报错 ≠ 服务端没跑成

> **2026-06-07 pic2 实战反直觉点**：用户报告"API 401" → 服务端 8 个任务**全 succeeded** → 真问题在下载阶段错位。
>
> **常见混淆**：
> - ❌ 客户端 401 → 服务端 0 任务（昨夜反例：服务端 8 个全活）
> - ❌ 客户端 timeout → 服务端任务卡死（实际 90% 情况下服务端继续跑完）
> - ❌ 客户端 `failed` → 服务端 status=failed（**必须先 `status <task_id>` 确认**）
>
> **铁律**：**任何客户端报错**（401/timeout/failed/连接 reset）→ **第一时间查 ark list 端点**（video_url 24h 内可救）→ **再决定**是救回还是重跑。

### 8.2 三元组绑定 SOP（批量跑完必做 · 5 分钟 · 0 元）

```bash
set -a; source /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env; set +a

# === Step 1: 拉 ark list 端点 ===
curl -sS -H "Authorization: Bearer $ARK_API_KEY" \
  "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks?page_size=30" \
  > /tmp/ark_tasks.json

# === Step 2: 按本次任务的提交时间窗口过滤 + 编号 ===
python3 << 'EOF'
import json
from datetime import datetime, timezone, timedelta
d = json.load(open('/tmp/ark_tasks.json'))
items = sorted(d['items'], key=lambda x: x['created_at'])

# 改这里：本次任务的提交窗口（CST 时间字符串）
WIN_START = "22:00"
WIN_END   = "23:30"

in_win = [it for it in items
          if WIN_START <= (datetime.fromtimestamp(it['created_at'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M') <= WIN_END]

print(f"匹配到 {len(in_win)} 条任务（应为 N）")
print()
print("idx\ttask_id\tcreated_at(CST)\tduration\tvideo_url_prefix")
for i, it in enumerate(in_win, 1):
    cst = (datetime.fromtimestamp(it['created_at'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M:%S')
    print(f"{i}\t{it['id']}\t{cst}\t{it.get('duration')}\t{it['content']['video_url'][:50]}")
EOF

# === Step 3: 下载全部到 /tmp（按服务端顺序） ===
mkdir -p /tmp/ark_batch
python3 << 'EOF'
import json, subprocess
from datetime import datetime, timezone, timedelta
d = json.load(open('/tmp/ark_tasks.json'))
items = sorted(d['items'], key=lambda x: x['created_at'])
in_win = [it for it in items
          if "22:00" <= (datetime.fromtimestamp(it['created_at'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M') <= "23:30"]
for i, it in enumerate(in_win, 1):
    url = it['content']['video_url']
    out = f"/tmp/ark_batch/server_clip{i}.mp4"
    r = subprocess.run(['curl', '-sS', '-L', '-o', out, url], capture_output=True, text=True)
    print(f"server_clip{i} -> {out}  exit={r.returncode}")
EOF

# === Step 4: md5 交叉对比，本地 vs 服务端 ===
md5sum /tmp/ark_batch/server_clip*.mp4 /home/luo/huiben-projects/20260606-pic2/v1-clip*-fixed.mp4 | sort
```

**看结果**：
- 每个本地文件 md5 都**有且仅有 1 个** `server_clipN.mp4` 匹配 → ✅ 对得齐
- 匹配错位（如本地 v1-clip5 = server_clip6）→ ❌ 错位，按 server_clip 顺序覆盖命名
- 本地有文件但服务端无匹配 → ❌ 漏下或被覆盖，从 `/tmp/ark_batch/` 拉回来
- 服务端有文件但本地无 → ❌ 漏下，把 `/tmp/ark_batch/server_clipN.mp4` 复制到 `v1-clipN-fixed.mp4`

### 8.3 防错位铁律（写入代码模板）

**铁律 30 升级版**（task_id 持久化**必须包含绑定信息**）：

```bash
# ❌ 老版（昨夜反例：只存 ID，没绑定文件）
echo "$TASK_ID" >> task_ids.txt

# ✅ 新版（一行一组：task_id\tclip_idx\tlocal_path\t旁白摘要）
echo -e "${TASK_ID}\tclip${N}\t./v1-clip${N}-fixed.mp4\t${旁白}" >> task_ids.tsv
```

**交付前自检**（5 分钟 0 元，**必跑**）：

```bash
# 1. task_ids.tsv 行数 == 计划任务数
wc -l task_ids.tsv

# 2. 每个 task_id 都能在 ark list 里查到
while IFS=$'\t' read -r tid clip_idx path 旁白; do
  status=$(curl -sS -H "Authorization: Bearer $ARK_API_KEY" \
    "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/$tid" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
  echo "$clip_idx $tid $status"
done < task_ids.tsv

# 3. 每个 path 文件都存在 + 大小 > 0
while IFS=$'\t' read -r tid clip_idx path 旁白; do
  [ -s "$path" ] && echo "✅ $clip_idx $path" || echo "❌ $clip_idx $path 缺失"
done < task_ids.tsv

# 4. 跑三元组 SOP（§8.2）做最终 md5 交叉对比
```

### 8.4 错位发生后的 0 元修复

**不要重跑任务**（重复扣费），按 SOP 把错位文件重新对齐：

```bash
# 例：昨夜 v1-clip5 实际是 server_clip6，v1-clip8 漏下
# 修复步骤：
cp /tmp/ark_batch/server_clip5.mp4 ./v1-clip5-fixed.mp4   # 把 server_clip5 放回 v1-clip5
cp /tmp/ark_batch/server_clip6.mp4 ./v1-clip6-fixed.mp4
cp /tmp/ark_batch/server_clip7.mp4 ./v1-clip7-fixed.mp4
cp /tmp/ark_batch/server_clip8.mp4 ./v1-clip8-fixed.mp4
# 验证
md5sum ./v1-clip*-fixed.mp4 /tmp/ark_batch/server_clip*.mp4 | sort
# → 每对同名 file1 / file2 md5 一致 = ✅
```

### 8.5 反模式（必避）

- ❌ **凭印象对文件名** —— 昨夜就是反例，v1-clip5 实际是 clip6 内容
- ❌ **用文件大小判断对错** —— 6s 视频可能 1.5M / 2.2M / 12M 都有（取决于 prompt 复杂度）
- ❌ **task_id 存了 = 安全** —— 昨夜 task_id 全部在 task_ids.txt 里（7 个 + 1 个漏），但**没和本地文件绑定**一样错
- ❌ **客户端报错直接信** —— 必先 list 端点核对

## 9. 自检清单升级（v2）

**5 必避**（在原 4 必避基础上 + 1）：

- ❌ `for ... do ... done` 串行 + `tail -1` 抓 ID 不存变量
- ❌ 后台 `&` 启动不存 PID/task ID
- ❌ wait 被打断就盲重创建（**先 status 查实际状态**——可能已 succeeded）
- ❌ task ID 丢了直接重提交（**先查 ark list 端点救回**——video_url 24h 有效，0 元重跑）
- ❌ **客户端报错就当服务端没跑成**（**必先 list 端点核对**——2026-06-07 pic2 实战：客户端报"API 401"但服务端 8 个全 succeeded）

**4 必查**（在原 3 必查基础上 + 1）：

- ✅ 批量提交后：`wc -l task_ids.txt` == 计划任务数
- ✅ 每个 task 跑完 `wait` 后：`ls -lh` 校验文件存在
- ✅ 交付前：所有 task `status` 都 succeeded（不是 failed / 不是 pending）
- ✅ **三元组绑定校验**：本地文件 md5 ↔ ark list video_url ↔ clip 序号 三者对得上（防错位/漏下）

**4 个必避**：
- ❌ `for ... do ... done` 串行 + `tail -1` 抓 ID 不存
- ❌ 后台 `&` 启动不存 PID/task ID
- ❌ wait 被打断就盲重创建（先 status 查实际状态）
- ❌ task ID 丢了直接重提交（先查 ark list 端点救回）

**3 个必查**：
- ✅ 批量提交后：`wc -l task_ids.txt` == 计划任务数
- ✅ 每个 task 跑完 `wait` 后：`ls -lh` 校验文件存在
- ✅ 交付前：所有 task `status` 都 succeeded（不是 failed / 不是 pending）

---

## 10. 批量并发调度（3 并发上限 + 异步等待模板）⭐ 2026-06-10 Hamster 8 段绘本实战沉淀

> **触发场景**：绘本 8 段 / 漫剧 N 段 / 任何"批量跑 N 个 Clip"场景。**走串行 = 浪费时间**（绘本 8 段 18 分钟 vs 并发 7 分钟）。
> **本节是"调度模式"而非红线**——违反不翻车，但**慢**。用户 2026-06-10 原话："**seedance 可以并发 3 个任务**"。

### 10.1 并发上限

| API 限制 | 值 | 来源 |
|---|---|---|
| **单用户最大并发任务数** | **3** | seedance 官方 API 限制（用户确认） |
| **绘本单批建议并发数** | **3**（与官方上限对齐） | Hamster 8 段实战 3+2 拆分验证 |
| **超出上限** | API 拒绝（429 / 任务排队延迟）| 实测 |

**绘本 N 段拆分算法**：
```python
batches = [clips[i:i+3] for i in range(0, len(clips), 3)]
# 例：8 段 → [[1,2,3], [4,5,6], [7,8]] = 3 批
# 例：5 段 → [[1,2,3], [4,5]] = 2 批
```

### 10.2 异步等待可执行模板（execute_code + subprocess.Popen）⭐⭐⭐

> **反模式 1**（最早我写的串行版）：`subprocess.run(... timeout=600)` —— 一个跑完才跑下一个 = 串行 = 慢
> **反模式 2**：`subprocess.Popen(...) + sleep` —— 不知道何时完成 = race condition
> **正解**：`subprocess.Popen` 启动 N 个进程 → `communicate()` **异步等所有** = 真并发

**完整可执行模板**（Pic10 Hamster 8 段实战验证）：

```python
import subprocess
import time
import os

# Step 1: 准备 clips 数据
CLIPS = [
    {'n': 4, 'img': '/path/4.jpg', 'duration': 6},
    {'n': 5, 'img': '/path/5.jpg', 'duration': 6},
    {'n': 6, 'img': '/path/6.jpg', 'duration': 7},
    # 7, 8 走第 2 批（3 并发上限）
]

# Step 2: 错开 1 秒提交（避免 API 抖动）+ 用独立 download 路径
procs = []
for clip in CLIPS:
    n = clip['n']
    with open(f'/path/clip{n}-prompt.txt', 'r') as f:
        prompt = f.read().strip()
    output = f'/path/clip{n}.mp4'  # 独立路径（红线！同路径会互相覆盖）
    cmd = ['python3', 'seedance.py', 'create',
        '--ref-images', clip['img'],
        '--prompt', prompt,
        '--model', 'doubao-seedance-2-0-fast-260128',
        '--ratio', '16:9', '--duration', str(clip['duration']),
        '--resolution', '720P',
        '--watermark', 'false', '--generate-audio', 'true',
        '--wait', '--download', output]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, cwd='/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool')
    procs.append((n, p, time.time()))
    time.sleep(1)  # 错开 1 秒避免 API 抖动

# Step 3: 异步等待所有任务完成（不等任何一个先完成）
results = []
for n, p, t0 in procs:
    try:
        stdout, stderr = p.communicate(timeout=600)  # 单任务最长等 10 分钟
    except subprocess.TimeoutExpired:
        p.kill()
        stdout, stderr = p.communicate()
    elapsed = time.time() - t0
    # 解析 task_id + seed + tokens
    task_id = seed = tokens = None
    for line in stdout.split('\n'):
        if 'Task ID:' in line:
            task_id = line.split('Task ID:')[1].strip()
        if '"seed":' in line:
            try: seed = int(line.split('"seed":')[1].split(',')[0].strip())
            except: pass
        if '"total_tokens":' in line:
            try: tokens = int(line.split('"total_tokens":')[1].split('}')[0].strip())
            except: pass
    out_path = f'/path/clip{n}.mp4'
    exists = os.path.exists(out_path)
    size = os.path.getsize(out_path) if exists else 0
    print(f"clip{n}: {task_id} seed={seed} tokens={tokens} 用时={elapsed:.1f}s 文件={size//1024}KB {'✅' if exists else '❌'}")
    if not exists or p.returncode != 0:
        print(f"  STDERR: {stderr[-500:]}")
    results.append({'n': n, 'task_id': task_id, 'seed': seed, 'tokens': tokens,
                    'elapsed': elapsed, 'size_kb': size//1024, 'exists': exists, 'returncode': p.returncode})
```

### 10.3 实战数据（Pic10 Hamster 8 段并发 vs 串行预估）

| 调度模式 | 总耗时 | 时间效率 | 备注 |
|---|---|---|---|
| **串行预估** | ~18 分钟（5 × 223s 平均）| 100% | 假设 5 个 clip 都按 5s 算 |
| **3+2 并发实测** | **7 分 18 秒**（223s + 213s）| **节省 11 分钟** | 第 1 批 3 个 / 第 2 批 2 个 |
| 节省比例 | — | **~60% 时间节省** | 绘本 8 段级以上的批量场景必走并发 |

### 10.4 ⚠️ 3 个红线（并发场景必避）

> 这 3 条是 2026-06-10 Hamster 并发实战发现的"看起来没问题但会翻车"的陷阱：

1. **❌ `--download` 路径冲突**（最致命）
   - 所有任务传同一个 `--download /path/output` → 全部写入 `/path/output`（无扩展名）= 互相覆盖
   - 修复：**每个任务用独立文件名** `--download /path/clip1.mp4` / `--download /path/clip2.mp4`
   - 详见 SKILL.md "⚠️ 重要：`--download` 是「完整文件路径」" 红线

2. **❌ 错开时间 < 1 秒**
   - 3 个任务同毫秒级提交 → API 端可能触发频率限制（429 / 任务延迟）
   - 修复：`time.sleep(1)` 错开 1 秒（实测稳定）

3. **❌ execute_code 单次 timeout 太短**
   - `subprocess.run(..., timeout=300)` 串行超时 = 任务跑超过 5 分钟就 false alarm
   - `subprocess.Popen` + `communicate(timeout=600)` 单任务 10 分钟上限 = 安全
   - 绘本 7s 1080P 实测 4-8 分钟；14s 复杂 prompt 实测 15-25 分钟

### 10.5 task_id 持久化（并发场景版）

并发跑多个任务时，**每个任务 ID 必须独立持久化**（不能靠 stdout 打印追）：

```python
# 启动时创建 task_ids 跟踪文件
TRACKER = '/path/task_ids.tsv'
import json
with open(TRACKER, 'w') as f:
    f.write('task_id\tclip_idx\tlocal_path\tcreated_at\tseed\ttokens\tsize_kb\n')

# 每个任务完成后追加一行
for r in results:
    with open(TRACKER, 'a') as f:
        f.write(f"{r['task_id']}\tclip{r['n']}\t/path/clip{r['n']}.mp4\t"
                f"{time.strftime('%H:%M:%S')}\t{r['seed']}\t{r['tokens']}\t{r['size_kb']}\n")
```

**触发场景**：
- 任何"批量跑 N 个 Clip"前（绘本 N 段 / 漫剧 N 段 / 多角度产品图 / 同主题多版本）
- 用户明确说"批量" / "全部" / "所有 Clip" 时
- 单测门 SOP（§6）跑完 1 个 Clip 用户确认后，进入批量阶段时

**反模式**（必避）：
- ❌ 走 `for ... subprocess.run` 串行 = 浪费时间（绘本 8 段从 7 分钟变 18 分钟）
- ❌ 走 `subprocess.Popen + os.wait` 没存 task_id = 任务 ID 丢失（违反 §1 铁律 30）
- ❌ 走 `nohup &` 后台 = 失去控制（违反 §1 铁律 30 + §2 铁律 29）
