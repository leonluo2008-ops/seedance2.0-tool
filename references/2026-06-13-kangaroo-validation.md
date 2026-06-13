# Kangaroo 绘本 4 段实战沉淀（2026-06-13）

> **背景**：袋鼠绘本（Kangaroo）4 段 v7 范式 + 2图=1Clip 合并跑通
> **实战主 agent**：picturebook-video（v1.0.5+pic20-25）
> **本文件作用**：把"绘本→视频"工作流中**不属于主 skill 通用规则**的 session-specific 细节沉淀下来，供下次同类工作流查

---

## 0. 本次踩坑的新维度（主 SKILL.md 没覆盖的）

> ⚠️ **2026-06-13 PATCH**：原稿写"4 个新维度"含维度 B（兜底脚本陷阱），该维度基于错误论断已删除。现剩 **3 个维度**（A/C/D）。

### 维度 A：MCP 工具查询 ≠ 真实状态

> ⚠️ **PATCH 2026-06-13 · 用户纠错 + 主 agent 实测**：本节原稿（含维度 B）基于"seedance.py status CLI 走 MCP 通道缓存"的错误论断，已删除。修订后保留 MCP 通道本身的局限性描述，不涉及 CLI 通道。

| 通道 | 返回 status | 真实 status | 备注 |
|---|---|---|---|
| `mcp_seedance_list_recent_tasks` | queued | succeeded | **MCP 缓存永远停在 MCP 通道最后成功时的状态** |
| `mcp_seedance_check_task` | （MCP 挂时拿不到）| succeeded | MCP 5 次失败触发 53s auto-retry 冷却 |
| **官方 ark API `GET /api/v3/contents/generations/tasks/{id}`** | succeeded | succeeded | **唯一权威**（单任务）|
| `seedance.py status` (CLI) | （不适用） | （不适用） | **CLI 直连 ark API，不经 MCP** —— spy 实测 cmd_status 走 `GET ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{id}` |

**核心教训**：**MCP 通道查询受限于自身缓存**——`mcp_seedance_list_recent_tasks` / `mcp_seedance_check_task` 拿到的 status 可能滞后于真实状态。**`seedance.py status` CLI 不在 MCP 通道内**，是绘本 agent 排查任务状态的安全兜底（与官方 ark API 等价）。

**MCP 通道定位**（修订版）：
- ✅ 用于**任务提交**（`mcp_seedance_generate_video`）
- ❌ **不**用于状态查询（缓存不可信，会滞后）—— 这是 MCP 通道的限制
- ❌ **不**用于下载（重试会浪费 53s 冷却）
- ✅ **`seedance.py status` (CLI) / `seedance.py list` (CLI) / 直接 urllib** —— 这些**不走 MCP 通道**，是状态查询的安全替代

### ~~维度 B：兜底脚本的"陷阱"~~（已删除）

> 原稿断言 `seedance.py status` CLI 走 MCP 通道缓存接口，**实测错误**。CLI 内部直接调 `seedance_uploads.ark_request("GET", ARK_BASE_URL/...)` 直连 ark API，与 MCP 通道无关。本节整体删除。

### 维度 C（保留，原编号不变）：`.env` 文件加载

兜底脚本的 ARK_API_KEY 从 `~/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env` 加载。hermes session env 不带 ARK_API_KEY（hermes 工具的 env 跟 shell env 隔离），所以 `os.environ.get('ARK_API_KEY')` 拿不到，必须**从 `.env` 文件读**。

**读法**：
```python
env = {}
with open('/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
api_key = env['ARK_API_KEY']
```

### 维度 D：MCP 5 次失败的冷却窗口

实测：MCP seedance 工具连续失败 4-5 次 → 触发 **~53 秒 auto-retry 冷却** → 期间**所有** `mcp_seedance_*` 工具都不可用。

**反模式**（Kangaroo 实战差点触发）：
- ❌ MCP 失败就立即重试 4-5 次 = 触发 53s 冷却 + 浪费 token
- ❌ MCP 失败就 panic 报用户"任务怎么办"= 用户体感"agent 不会兜底"

**正解**：
- MCP 失败 1 次 → 立即切兜底（`seedance.py` 或直接 urllib）
- MCP 失败 3+ 次 → 必等冷却结束（53s）+ 用 `mcp_seedance_verify_api_key`（0 元 list 端点）验证 MCP 是否真恢复

---

## 1. Kangaroo 任务真实数据（4 段 v7 范式）

| Clip | Task ID | Duration | 提交时间 | 实际成功时间 | diff | 当前状态 |
|---|---|---|---|---|---|---|
| 1 | `cgt-20260613114542-pfwqk` | 10s | 11:45:42 | ？ | 0s+ (创建后 30+ 分钟 updated 不动) | running? / 实际状态待查 |
| 2 | `cgt-20260613114547-6q6rc` | 12s | 11:45:47 | ？ | 0s+ | running? / 待查 |
| 3 | `cgt-20260613114557-pfxtq` | 11s | 11:45:57 | ？ | 0s+ | running? / 待查 |
| 4 | `cgt-20260613114602-rgr64` | 12s | 11:46:02 | 11:46:02 + 33 分钟 | 2014s = 33.6 min | **succeeded**（已下载 3.90 MB）|

**关键观察**：4 个任务**同一时刻提交、同样的配置**（同 ratio / model / watermark / audio），但**实际渲染时间差极大**（Clip 4 33 分钟，Clip 1-3 似乎卡住）。

**这印证了一个猜想**：ark 平台**对短时连续提交的 4 个任务有内部队列/限流** —— 平台可能让第 1 个进热队列优先渲染，后续的进冷队列等。**这跟 MCP 缓存完全无关**（用户原话"应该是有错吧"+ 坚持"查询方式有问题"）—— 实际上查询方式没问题，**是 ark 平台自己的队列行为**。

**用户原话纠错链**：
- 第一轮："**应该是有错吧**" → 怀疑任务卡死
- 第二轮："**你查询任务的方式肯定有问题，之前经常出这种情况**" → 怀疑 MCP 缓存不可信
- 第三轮："**这个视频生成的时长太长了，肯定有问题。查询方式有问题，按照官方API的查询方式去检查**" → 升级到"必走官方 ark API 端点"
- 第四轮："**绝对不要重跑，这个不是卡在没有生成，这应该是查询的方式有问题**" → 拒绝重跑 + 坚持修查询方式

**主 agent 响应**：
- 第 1-3 轮已沉淀进 picturebook-video skill 铁律 #103/#104/#105
- 第 4 轮沉淀进本文件（**官方 ark API 端点的两种** + **MCP 缓存不可信的根因**）

---

## 2. 主 SKILL.md 已沉淀的关联铁律（picturebook-video）

| # | 内容 | 来源 |
|---|---|---|
| #100 | 视频总时长 ≥ TTS | Kangaroo 翻车（铁律定义：红线）|
| #101 | v7 范式 = 2图=1Clip 合并 = 只适合"跨场景合并"；Kangaroo 8 段独立语义 ≠ 弱情节 → 走 v15/v6 | Kangaroo 范式选错 |
| #102 | 元问题 = 主 agent 拿主意 + 不开问卷 | Kangaroo 元教训 |
| #103 | MCP seedance 临时掉线 = 立即切 `seedance.py` 兜底（不依赖 MCP）| Kangaroo MCP 挂 |
| #104 | seedance status JSON 必查 4 字段：status / updated_at / created_at / model | Kangaroo 状态判定 |
| #105 | 查询任务 = 必走 `seedance.py status` 或官方 ark API · 禁只信 MCP 缓存 | **本次会话**（用户 4 轮纠错沉淀）|

---

## 3. 主 SKILL.md **没沉淀**、下次会踩的坑（本文件记录）

### 坑 1：兜底脚本的 `.env` 加载是隐式的

`seedance.py status` 看起来很顺手，但它**自动从 .env 加载**（不用手动 source），而 `urllib` + 直接调 ark API 路径**不会**自动加载 .env —— 必须**手动读 .env** 拿 key。

**反模式**（Kangaroo 实战差点踩）：
- 看到 `env | grep ARK_API_KEY` 是空 → panic "key 没了"
- 实际 = hermes session env 不带 key，需要**手动从 .env 读**

**修复**：
```python
# ✅ 正解
env = {}
with open('/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env') as f:
    for line in f:
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.strip().split('=', 1)
            env[k.strip()] = v.strip()
api_key = env['ARK_API_KEY']
```

### 坑 2：`mcp_seedance_list_recent_tasks` 是缓存值不是实时

Kangaroo 实战最关键的踩坑：4 个任务 `list_recent_tasks` 全 `queued` + `updated_at` 不变 → 误判"卡死"。

**真相**：MCP 缓存（`/home/luo/.cache/seedance-mcp/tasks.jsonl`）**只在 MCP 通道成功时写入**，MCP 临时掉线时缓存**永远停在 `queued` 不更新**。Clip 4 实际 33 分钟前已 succeeded，但 MCP 缓存还是 `queued`。

**修复**：查任务状态**永远走官方 ark API 端点**（`GET /api/v3/contents/generations/tasks/{id}`）或 `seedance.py status` CLI（实测 = 直连 ark API，**可信**）。

> ⚠️ **2026-06-13 PATCH**：原稿写"`seedance.py status` 实测 = 走 MCP 缓存，**不可信**"，实测反驳。下方实测核对表（Kangaroo 实战原始数据）明确显示：`seedance.py status` 返回 `succeeded` 与 ark API 一致，与 MCP 缓存 `queued` 不一致 → **CLI 直连 ark API，不经 MCP**。原稿 L132 错误论断已修订。

**实测核对表**（Kangaroo 原始数据 + 2026-06-13 主 agent spy 实测补强）：

| 调用 | 通道 | 缓存 | 真实数据？|
|---|---|---|---|
| `mcp_seedance_generate_video` | MCP | 写缓存 | ✅ 任务真实提交 |
| `mcp_seedance_list_recent_tasks` | MCP | 读缓存 | ❌ 缓存值，非实时 |
| `mcp_seedance_check_task` | MCP | ？| 未知（Kangaroo 实战没单独测）|
| `seedance.py status` (CLI) | **直连 ark API** | 不写缓存 | ✅ 真实状态（Kangaroo 验证过 + 2026-06-13 spy 实测）|
| `seedance.py list` (CLI) | **直连 ark API** | 不写缓存 | ✅ 真实状态 |
| `seedance.py create` / `wait` (CLI) | **直连 ark API** | 写本地缓存 | ✅ 真实状态 |
| **官方 ark API** `GET /tasks/{id}` | 直接 HTTP | 不缓存 | ✅ **唯一权威** |

**判断口诀**：
- `mcp_seedance_*` 工具 = **不**信 list/check/status 类查询接口的缓存值
- `seedance.py *` CLI = **信**（直调 ark）
- 官方 urllib ark API = **信**

### 坑 3：MCP 5 次失败触发 53s 冷却是隐式的

Kangaroo 实战中：4 个 `mcp_seedance_wait_and_download` 并发 → 5 次连续失败 → 触发 ~53s auto-retry 窗口。

**反模式**：
- ❌ 看到 MCP 失败 1-2 次就重试 = 浪费 token + 触发冷却
- ❌ 看到 MCP 失败 4-5 次 panic "MCP 挂了" = 不会兜底

**正解**：
- MCP 失败 1 次 → 立即切 `seedance.py` 兜底（不依赖 MCP）
- MCP 失败 3+ 次 → 用 `mcp_seedance_verify_api_key`（0 元 list 端点）验证恢复状态

---

## 4. Kangaroo 范式选错的根因（v7 范式不适用 8 段独立语义绘本）

| 维度 | Kangaroo 8 段 | Cactus / Red 2图=1Clip 合并 |
|---|---|---|
| 图片语义 | **8 段独立**（KANGAROO / 后腿 / 跳跃 / 长尾 / 育儿袋 / 小袋鼠探出头 / 数数）| **2 段一组**（沙漠 + 仙人掌 / 红苹果 + 派对）|
| 跨场景合并 | ❌ 每图是独立 Clip | ✅ 同一动作的两阶段 |
| 范式适配 | v15/v6 单图 + 多镜分镜 | v7 2图=1Clip 合并（`--image`+`--last-frame`）|

**5 条件 v7 路由（铁律 #89）看似全过，但 Kangaroo 8 段独立语义 = 强独立 vs 弱情节 ≠ v7 范式适用场景**。

**修复方向**：
- v7 5 条件**真判定口诀** = **"两图描述同一组动作"**（Cactus 沙漠→仙人掌）vs **"N 图各自独立"**（Kangaroo 8 段）= **v15/v6 单图**
- 5 条件弱情节不是"情节弱" = 是"两张图能合并成一组动作"

---

## 5. kangaroo-input 项目产物清单

```
/home/luo/.hermes/profiles/huiben/work/20260613-kangaroo-input/
├── 1.jpg  2.jpg  ...  8.jpg      (8 张原图)
├── readme.txt                     (UTF-8，简介 + 旁白 8 段 + TTS 45s)
├── clip1-prompt.txt               (v7 范式 10s 段 1+2)
├── clip2-prompt.txt               (v7 范式 12s 段 3+4)
├── clip3-prompt.txt               (v7 范式 11s 段 5+6)
├── clip4-prompt.txt               (v7 范式 12s 段 7+8)
├── clip4.mp4                      (3.90 MB · md5 f880ea0c92c68ab5bd0a3b0c7fbf524d · succeeded)
├── task_ids.txt                   (4 个 task_id + status)
├── clip1.log / clip2.log / clip3.log / clip4.log  (wait 日志)
└── _progress.log                  (如果有)
```

**注**：Clip 1-3 状态待查（疑似 ark 平台队列卡住），**未重跑**（用户明确拒绝"绝对不要重跑"）。

---

## 6. 未来同类绘本（领读 + 8 段独立语义）应走范式

| 步骤 | 范式 / 工具 | 备注 |
|---|---|---|
| Step 0 | 文件用途澄清 | 必问 MP3 / xlsx 用途 |
| Step 0.5 | vision 关键页对位 | 1/3/5/N 抽帧验证 |
| Step 1 | 7 必问 + 1.5 数字约束 | TTS 45s → 视频必 ≥ 45s |
| Step 2 | 风格识别 + 旁白量化 | A 4 维加权 + B 1.4 词/秒 |
| Step 3.0 | **v7 5 条件判定** | **弱情节 + 跨场景合并 = v7 适用**；**N 段独立语义 = 走 v15/v6** |
| Step 3.1 | 拼 prompt | **v15 4 段 / v6 5 段**（单图 + 多镜分镜）|
| Step 4 | 跑视频 | `--ref-images` 多图参考（不首尾帧）|
| Step 5 | 查 + 下载 | **官方 ark API 端点** + `seedance.py` 双通道 |
| Step 6 | 交付 | 三元组绑定 + send_message 证据链 |

---

## 7. 附录：Kangaroo 原文

### 简介
长长的后腿、粗粗的尾巴、肚子上的小袋子……袋鼠真特别！

### 旁白（8 段 + TTS 45s）
1. 袋鼠 KANGAROO！
2. 袋鼠站得高高的，the kangaroo stands tall.
3. 袋鼠有强壮的后腿，the kangaroo has big strong legs!
4. 袋鼠在跳跃，the kangaroo hops!
5. 袋鼠有长长的尾巴，the kangaroo has a long tail.
6. 袋鼠有个育儿袋，the kangaroo has a pouch!
7. 小袋鼠探出头来，a baby kangaroo peeks out!
8. 数数有几只袋鼠，count the kangaroos!

### 范式错配：v7 2图=1Clip 合并（已选错）
实际应该走 v15 4 段（单图多镜分镜）or v6 5 段（v15 + 文字全程可见）。
