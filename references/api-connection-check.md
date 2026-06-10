# API Key 连接验证（不发视频 · 0 元）

> **触发场景**：用户问"检查 K 是否有效" / "验证连接" / "API 是不是挂了" / 启动时 sanity check。
> **核心原则**：**不调用 create**（避免 0.1-20 元扣费 + 1-5 分钟浪费），用 REST API 廉价端点（30 秒内 0 元）验证。

---

## 0. 为什么需要这个（2026-06-07 用户原话）

> "昨晚火山引擎的 API key 报错导致无法继续，我想请你用命令行检查一下，确认这个 K 是否有效。单独的调用不需要生成视频，就是看连接是否正常。"

**关键洞察**：用户**明确说"不需要生成视频"**——意味着不能用 `seedance.py create`（每次 0.1-20 元）。但 skill 当前 SKILL.md 里**完全没有"只验证连接不发视频"的方法**——只有 create/status/wait 三个子命令，验证会扣费。

---

## 1. 三种 0 元验证方法（按推荐度排序）

### 方法 A（推荐）：list 任务端点（1 次 API call · 30 秒内）

**原理**：用 list 任务的 REST API 端点，带上 `ARK_API_KEY` → 服务端只校验 key 有效性 + 返回空列表（没任务）或最近的任务。**不创建任何任务，0 元扣费。**

```bash
# 1. 加载 key（hermes 沙盒 HOME 错位 → 必须用绝对路径）
source /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env

# 2. 调 list 端点
curl -sS -H "Authorization: Bearer $ARK_API_KEY" \
  "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks?page_size=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ K 有效' if 'items' in d else f'❌ {d}')"
```

**判定**：
- `items` 字段存在（哪怕空）→ ✅ K 有效 + 服务端可达
- `{"error": {"code": "...", "message": "Authentication failed"}}` → ❌ K 无效
- HTTP 401 → ❌ K 无效
- HTTP 5xx / connection timeout → ⚠️ 服务端问题（不是 K 问题）

**实际案例**（2026-06-07）：`curl` 一次 2 秒返回 `{"items": [], "total": 0}` → 用户确认 K 有效，**全程 0 元**。

---

### 方法 B（次选）：get 单个 task（用已知 task_id · 30 秒内）

**原理**：用 `status <task_id>` 验证 key 有效性。需要至少一个已知的 task_id（从历史任务找）。

```bash
source /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env
TASK_ID="cgt-20260607151501-fmw5v"  # 任意已知 ID
python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py status $TASK_ID
```

**判定**：
- 输出 `succeeded` / `failed` / `running` → ✅ K 有效
- 输出 `Authentication failed` → ❌ K 无效

**缺点**：需要先有 task_id（如果用户**从没跑过**，方法 A 更合适）。

---

### 方法 C（不推荐）：最小 create（4s 1 个 clip · 0.1-0.5 元）

**仅当方法 A/B 都失败**才用。**用户明确说"不需要生成视频"**——**不要主动用方法 C**。

```bash
# 仅作 debug 兜底
python3 /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/seedance.py create \
  --prompt "test connection" --duration 4 --ratio 16:9 \
  --watermark false --generate-audio false \
  --wait 2>&1 | tail -20
```

**反模式**：
- ❌ 默认用方法 C（浪费钱 + 违反用户"不需要生成视频"指令）
- ❌ 用方法 A 时把 `page_size=1` 改成 `page_size=20`（多余数据，触发反爬虫）
- ❌ 不 source `.env` 直接跑 → `ARK_API_KEY not set` 误报

---

## 2. 完整验证脚本（粘贴即用）

```bash
#!/bin/bash
# verify-ark-key.sh —— 30 秒 0 元验证 K 是否有效
# 用法：bash verify-ark-key.sh
# 输出：✅ K 有效 / ❌ K 无效 / ⚠️ 服务端问题

set -e
ENV_FILE="/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env"

# 1. 检查 .env 存在
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ .env 不存在: $ENV_FILE"
  exit 1
fi

# 2. 加载 key
set -a
source "$ENV_FILE"
set +a

if [ -z "$ARK_API_KEY" ]; then
  echo "❌ ARK_API_KEY 未设置（.env 文件可能为空）"
  exit 1
fi

# 3. 调 list 端点
RESP=$(curl -sS -w "\nHTTP_CODE:%{http_code}" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks?page_size=1" \
  2>&1)

HTTP_CODE=$(echo "$RESP" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESP" | grep -v "HTTP_CODE:")

# 4. 判定
if [ "$HTTP_CODE" = "200" ]; then
  ITEM_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('items',[])))" 2>/dev/null || echo "?")
  echo "✅ K 有效 · HTTP 200 · 任务数: $ITEM_COUNT"
elif [ "$HTTP_CODE" = "401" ]; then
  echo "❌ K 无效 · HTTP 401 · 请检查火山方舟控制台重新生成 key"
elif [ "$HTTP_CODE" = "403" ]; then
  echo "❌ K 无权限 · HTTP 403 · key 可能过期或被禁用"
elif [ -z "$HTTP_CODE" ]; then
  echo "⚠️ 服务端无响应（连接失败/超时）· 不是 K 问题"
else
  echo "⚠️ HTTP $HTTP_CODE · 详情: $BODY"
fi
```

**实测**（2026-06-07 用户最初问的场景）：bash 跑通 → 5 秒内输出 `✅ K 有效 · HTTP 200 · 任务数: 0`。

---

## 3. 与 SKILL.md 主流程的衔接

**不要**在用户问"验证连接"时自动跑 create。**流程**：

```
用户: "检查 K 是否有效"
   ↓
主 agent 必读本 reference（避免误用 create）
   ↓
跑方法 A（list 端点）= 0 元 30 秒
   ↓
返回判定 + 报告
```

**反模式**：
- ❌ 用户问"验证 K" → 直接 `seedance.py create ... --wait` → 0.5 元浪费 + 5 分钟
- ❌ 用户问"验证 K" → 报"你的 .env 存在性 = K 有效"（错！文件存在 ≠ key 有效）
- ❌ 用户问"验证 K" → 用 `printenv ARK_API_KEY`（泄露 key 字符到终端 + 飞书消息）

---

## 4. 关联文档

- **`SKILL.md` §"Key 找不到的排查路径"**：查 `.env` 存在性 + 内容（**不是**验 K 有效性）
- **`SKILL.md` §"任务管理铁律"**：list 端点的"任务 ID 救援"用途（不同场景，但同端点）
- **`references/audio-bugs-and-hosting.md`**：4 个已知 bug 修复（连接性问题先排查这 4 个）
- **`github-pr-workflow` §"Token 完整扫描清单"**：7 个位置找 token（如果用户报错"key 找不到"）
