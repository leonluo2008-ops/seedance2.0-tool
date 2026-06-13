# 2026-06-13 删除 seedance 本地 cache 方案（设计 + 实施 plan）

> **设计 + 实施一锅出**：任务规模不大（删 5 个文件 + 改 4 个文件 + 改文档），不拆 brainstorming / plan 两份。

---

## 0. 背景与依据

### 用户信号（2026-06-13）

- "**该清除的都清除掉**，我那些历史中的快照啊，有可能很多都是错误的，要以实际的官方文档为准"
- "**MCP 的缓存是否有必要保留这个缓存？如果这个缓存会干扰任务执行，那就清理掉这个东西，不要有缓存**"
- 同意执行（用户原话："同意"）

### 官方文档依据（[volcengine.com/docs/82379/1520757](https://www.volcengine.com/docs/82379/1520757)）

火山方舟 Seedance 2.0 API **只有 2 个权威端点**：
- `POST /api/v3/contents/generations/tasks` — 提交任务
- `GET /api/v3/contents/generations/tasks/{id}` — 查单任务
- `GET /api/v3/contents/generations/tasks?page_size=N` — 列最近任务

**官方文档无任何"客户端缓存"机制**。本地 cache 是我们自己造的，且：
- ❌ 写多读少（基本没人读）
- ❌ video_url 24h TTL 过期（cache 里的 URL 24h 后就废）
- ❌ kangaroo 报告（`references/2026-06-13-kangaroo-validation.md`）证实 MCP 缓存导致状态滞后误判
- ❌ JSONL append-only 模式 = 旧条目永不更新
- ❌ 隐式持久化状态（用户看不到，agent 看不到）

### 拍板项（用户回复 `1` 全部 yes 直接开干）

1. **整体方案 OK 吗**（删除 cache 机制 + 删 2 个 MCP 工具 + 改 spike 测试 + 删物理文件 + 改文档）？
2. **删 MCP 工具 `list_recent_tasks` 和 `download_cached`** —— 同意吗？
3. **改 spike 001 e2e 测试**（list_recent_tasks 验证段改成调官方 list 端点）—— 同意吗？

### 用户追加拍板（2026-06-13 二次确认）

4. **绘本仓（picturebook-video）一起改** —— 同意吗？
   - 新开 `fix/remove-cache-2026-06-13` 分支（不碰 main 红线）
   - 改 SKILL.md（铁律 #103/#105 修订）+ `references/2026-06-13-kangaroo-validation.md`（重写翻车点 4 + 修订 4.3 段）+ `references/2026-06-13-kangaroo-100-validation.md`（翻车 4 段修订）
5. **kangaroo 报告"用户纠错链路"段删除** —— 同意吗？
   - 种子仓：删除第 81/87 行 "用户 4 轮纠错沉淀"那段（基于"CLI 走 MCP 缓存"误解）
   - 绘本仓：删除 `references/2026-06-13-kangaroo-validation.md` 翻车点 4 整节（100% 基于错误前提）+ 删除 4.3 段中"用户原话"引用

---

## 1. 设计

### 1.1 删除范围

| 类型 | 路径 | 处理 |
|---|---|---|
| 物理文件 | `~/.cache/seedance-mcp/tasks.jsonl` | `rm` 删 |
| 物理文件 | `~/.cache/seedance-mcp/` (空目录) | `rmdir` 删 |
| Python 函数 | `seedance_uploads.py::cache_task()` | 删 |
| Python 函数 | `mcp_server.py::_cache_task()` | 删 |
| 常量 | `CACHE_DIR` / `CACHE_FILE` / `CACHE_TTL_FALLBACK_SEC` | 删 |
| 常量 | `mcp_server.py::CACHE_DIR` / `CACHE_FILE` | 删 |
| MCP 工具 | `list_recent_tasks` | 删 |
| MCP 工具 | `download_cached` | 删 |
| CLI 调用 | `seedance.py` 里所有 `U.cache_task(...)` 调用 | 删 |
| MCP 调用 | `mcp_server.py` 里所有 `_cache_task(...)` 调用 | 删 |
| Spike 测试 | `spikes/003-concurrency/test_concurrent.py::test_concurrent_cache_writes` | 删（test 2） |
| 文档 | `QUICKSTART.md` §"4. 写本地缓存" 段 | 改 |
| 文档 | `README.md` §"同 prompt 重提" 段 | 改 |
| 文档 | `TROUBLESHOOTING.md` §"list_recent_tasks + download_cached" 段 | 改 |
| 文档 | `error-patterns.md` §"同 prompt 不重提" 段 | 改 |
| 文档 | `INSTALL.md` §"URL expired" 段 | 改 |
| 文档 | `SKILL.md` 相关段（多处引用 cache） | 改 |
| 文档 | `spikes/005-mcp-conductor-skill/SKILL.md` §"缓存文件绝对路径" 段 | 删 |
| 文档 | `references/2026-06-13-kangaroo-validation.md` 坑 2 段 | 重写（缓存删了，"滞后"原因消失）|
| 环境变量 | `SEEDANCE_CACHE_DIR`（mcp_server.py 默认值） | 删 |

### 1.2 MCP 工具最终清单（删 2 后剩 4）

| 工具 | 功能 | 等价 CLI |
|---|---|---|
| `generate_video` | 提交任务，返回 task_id | `seedance.py create` |
| `check_task` | 查询任务状态 | `seedance.py status` |
| `wait_and_download` | 同步等待 + 下载 | `seedance.py create --wait --download` |
| `verify_api_key` | 0 元 list 端点检测 key 有效性 | （无 CLI 等价）|

### 1.3 替代方案

需要"最近任务列表" → `mcp_seedance_check_task` + `verify_api_key` 模式不可行（只能查单个）。

**真正的方案**：MCP 加一个新工具 `list_recent_tasks_api`（调官方 list 端点），等价于 `seedance.py list --page-size N`。

但本次任务**只删 cache**，不加新工具。**理由**：绘本 agent 当前主用 `wait_and_download`（生成 + 等待 + 下载三合一），不需要"列最近"。"查历史 task_id"需求低频，遇到时直接 `seedance.py list` 或 ark REST 端点即可。

如果未来高频需要"列最近任务"，再加 MCP 工具（用官方 list 端点，不写 cache）。

---

## 2. 实施 plan（TDD 风格）

### Task 1: 物理清理 cache（5 分钟）

**步骤**:
1. 备份 cache 文件最后一次快照（防止误删）：`cp ~/.cache/seedance-mcp/tasks.jsonl /tmp/tasks.jsonl.bak-2026-06-13`
2. `rm ~/.cache/seedance-mcp/tasks.jsonl`
3. `rmdir ~/.cache/seedance-mcp`（如果空）
4. `ls -la ~/.cache/seedance-mcp/ 2>&1` 应报错"无此目录"

**验证**:
```bash
ls /home/luo/.cache/seedance-mcp/ 2>&1  # 应：No such file or directory
```

---

### Task 2: `seedance_uploads.py` 删 cache（10 分钟）

**改动**:
- 删 `cache_task()` 函数
- 删 `_ensure_cache_dir()` 函数（如有）
- 删 `parse_url_expires()` 函数（**仅 cache 用到它**，删除）
- 删 `CACHE_DIR` / `CACHE_FILE` / `CACHE_TTL_FALLBACK_SEC` 常量
- 删相关 import（`datetime` 如果只剩 cache 用）

**TDD 验证**（先写后改）:
```python
# /tmp/test_no_cache.py
import seedance_uploads as U
# 这些都应该报错
try:
    U.cache_task(...)
    assert False, "cache_task should not exist"
except AttributeError:
    pass
try:
    U.CACHE_FILE
    assert False, "CACHE_FILE should not exist"
except AttributeError:
    pass
print("✅ cache removed")
```

---

### Task 3: `seedance.py` 删 cache 调用（5 分钟）

**改动**:
- 删 `cmd_create` 里 `U.cache_task(...)` 调用（约 2 处）
- 删 `cmd_status` 里 `U.cache_task(...)` 调用（1 处）
- 删 `cmd_wait` 里 `U.cache_task(...)` 调用（如有）

**验证**:
```bash
python3 seedance.py --help  # 应能跑
python3 seedance.py status cgt-20260613114557-pfxtq  # 应能跑且返回 succeeded
python3 seedance.py list --page-size 3  # 应能跑
```

---

### Task 4: `mcp_server.py` 删 cache（15 分钟）

**改动**:
- 删 `_cache_task()` 函数
- 删 `CACHE_DIR` / `CACHE_FILE` 常量
- 删所有 `_cache_task(...)` 调用（约 3 处：`generate_video` / `check_task` / `wait_and_download`）
- 删 `list_recent_tasks` 工具（list_tools 里的 `types.Tool(...)` 块 + call_tool 里的 `elif name == "list_recent_tasks"` 分支 + `_handle_list_recent_tasks` 函数）
- 删 `download_cached` 工具（同上）
- 删 `parse_url_expires()` 函数（如果 mcp 也用）
- 删 `_ensure_cache_dir()` 函数

**TDD 验证**:
```python
# /tmp/test_mcp_no_cache.py
import sys
sys.path.insert(0, '/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/spikes/001-mcp-uguu-server')
import mcp_server
# 工具清单应剩 4 个
import asyncio
tools = asyncio.run(mcp_server.list_tools())
names = sorted([t.name for t in tools])
expected = sorted(['generate_video', 'check_task', 'wait_and_download', 'verify_api_key'])
assert names == expected, f"got {names}"
print(f"✅ MCP tools = {names}")
```

---

### Task 5: 改 spike 001 e2e 测试（10 分钟）

**改动**:
- 文件：`spikes/001-mcp-uguu-server/e2e_task5_kangaroo.py`
- 第 4 段"list_recent_tasks (本地缓存验证)" → 改成"list_api (官方 list 端点验证)"
- 调用方式：`mcp_server._handle_list_recent_tasks(args)` → 改成直接调官方 list 端点（用 `urllib`）
- 验证断言：从"cache 文件有新写入"改成"官方 API 返回真实状态"

**TDD 验证**:
```bash
# 跑 spike 001 e2e（注意会真扣费，仅在用户已确认后跑）
python3 spikes/001-mcp-uguu-server/e2e_task5_kangaroo.py
```

> 注：spike e2e 涉及真提交，本任务**不跑**（避免扣费）。只做静态检查 + import + 语法。

---

### Task 6: 改 spike 003 并发测试（5 分钟）

**改动**:
- 文件：`spikes/003-concurrency/test_concurrent.py`
- 删 `test_concurrent_cache_writes()` 函数（test 2）
- 删 main 里 test 2 的调度

**验证**:
```bash
python3 spikes/003-concurrency/test_concurrent.py --help  # 应能跑（如果有 --help）
```

---

### Task 7: 改文档（15 分钟）

**改动文件清单**:
- `QUICKSTART.md` §"4. 写本地缓存" 段 → 改写为"4. 无本地缓存，所有查询走官方 API"
- `README.md` §"同 prompt 重提" 段 → 删 list_recent_tasks 引用，改用 ark REST
- `TROUBLESHOOTING.md` §"list_recent_tasks + download_cached" 段 → 删整段，改用 ark REST 兜底
- `error-patterns.md` §"同 prompt 不重提" 段 → 删 list_recent_tasks 引用
- `INSTALL.md` §"URL expired" 段 → 删 list_recent_tasks 引用，改用 ark REST 端点（list endpoint）
- `SKILL.md`（多处提到 cache）→ 全文 grep "cache" 逐个处理
- `spikes/005-mcp-conductor-skill/SKILL.md` §"缓存文件绝对路径" 占位符 → 删
- `references/2026-06-13-kangaroo-validation.md` 坑 2 段 → 重写（缓存删了，"滞后"原因消失 → 改成"MCP 通道已重写"）

**验证**:
```bash
# 仓库内不应再有任何"cache_task" / "tasks.jsonl" / "list_recent_tasks" / "download_cached" 引用
grep -rn "cache_task\|tasks\.jsonl\|list_recent_tasks\|download_cached\|CACHE_FILE" --include="*.py" --include="*.md"
# 应：无输出（或只剩 kangaroo 报告里的历史事件描述 + SKILL.md 里的"已删除"标记）
```

---

### Task 8: 端到端验证（10 分钟）

**步骤**:
1. import 全部能跑
2. CLI 三个子命令（create/status/list/wait）能跑（不真提交 task，只验证 import + help + status 已知 task）
3. MCP server 能起 + 工具列表正确（4 个工具）
4. cache 文件确实不存在
5. kangaroo 报告里关于缓存的论断已重写

**验收清单**（用户自己跑）:
```bash
ls /home/luo/.cache/seedance-mcp/ 2>&1  # No such file or directory
cd /home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool
python3 seedance.py status cgt-20260613114557-pfxtq  # 应 succeeded
python3 seedance.py list --page-size 3  # 应出表格
python3 -c "import sys; sys.path.insert(0, 'spikes/001-mcp-uguu-server'); import mcp_server; import asyncio; print(sorted([t.name for t in asyncio.run(mcp_server.list_tools())]))"
# 应：['check_task', 'generate_video', 'verify_api_key', 'wait_and_download']
```

---

## 3. 绘本仓改动（追加 Task 9-12，独立分支操作）

### 绘本仓前置动作

```bash
cd /home/luo/.hermes/profiles/huiben/skills/creative/picturebook-video
# stash 当前未提交改动（按 fix/banana-report-2026-06-11 已有的 untracked）
git stash push -u -m "banana-report-wip-2026-06-13"
# 基于 origin/fix/banana-report-2026-06-11 开新分支
git fetch origin
git checkout -b fix/remove-cache-2026-06-13 origin/fix/banana-report-2026-06-11
```

### Task 9: 绘本仓 SKILL.md 铁律修订（20 分钟）

**改动**:
- 铁律 #103（L740）：
  - 保留现象描述"MCP 提交瞬间挂 = 任务假死"——这是事实
  - 删除 ② 段提到 `mcp_seedance_list_recent_tasks` 看 `cached_at` + `local_path` —— 工具要删了
  - 改成：用 `seedance.py list --page-size 10` 看相邻任务状态分布
- 铁律 #105（L817）**整条删除**——核心论断"查询 seedance 任务 = 必走兜底 `seedance.py status` 直调 ark API · 禁只信 MCP 缓存"虽然 CLI 走 ark API 这部分**对**，但"MCP 缓存不可信"这层已无意义（缓存都不存在了）。铁律 #105 的存在前提消失。
  - 替换为："**查询 seedance 任务 = 必走 `seedance.py status <task_id>` 直调 ark API**（实测 2026-06-13 CLI 直连 ark API，详见 seedance2.0-tool 历史 commit）"
- 顶部 Kangaroo 索引段（L704）"④ MCP 缓存不可信（铁律 #105）" → 改成"④ 已删除铁律 #105（基于 MCP 缓存前提，已无意义）"

### Task 10: 绘本仓 `references/2026-06-13-kangaroo-validation.md` 重写（30 分钟）

**改动**:
- 翻车点 4 整节（L76-93）**删除**——100% 基于"CLI 走 MCP 缓存"误解
- 4.3 段（L164-169）"查询必走兜底" 修订：
  - 保留核心："**查询必走兜底 `seedance.py status <task_id>` 直调 ark API**"
  - 删除"不信 MCP 缓存（`mcp_seedance_list_recent_tasks` / `mcp_seedance_check_task`）" —— 缓存删了
  - 删除"用户原话"引用 —— 用户已表态删除"用户纠错链路"
- 第 89 行"不信 MCP 缓存" → 改成"信 CLI 直连 ark API"
- 第 132 行 "9 条新铁律摘要" 中的 #105 行 → 改为已删除
- 第 141 行铁律表里的 #105 → 删除
- 第 168/214/220 行 cache 引用 → 改写
- 章节结构从"4 大翻车点 + 4.3 查询必走兜底"变成"3 大翻车点"（删除翻车点 4 后）

### Task 11: 绘本仓 `references/2026-06-13-kangaroo-100-validation.md` 修订（10 分钟）

**改动**:
- 翻车 4 段（L90-108）保留现象（"MCP 提交瞬间挂掉 = 任务假死"是真的发生）
- 修订第 94 行"Clip 4 实际早就 succeeded（33 分钟前），但 MCP 缓存没更新所以查不到" → 改成事实版："Clip 4 实际早就 succeeded（33 分钟前），但当时 kangaroo agent 没用 `seedance.py status` 走官方 ark API 验证"

### Task 12: 绘本仓 stash pop（5 分钟）

**改动**:
- `git stash pop` 恢复 banana report wip（如果用户要求）
- 本任务**不**自动 pop，stash 留给用户在所有改动合并后自己决定

### 绘本仓 commit + push

```bash
git add SKILL.md references/2026-06-13-kangaroo-validation.md references/2026-06-13-kangaroo-100-validation.md
git commit -m "fix(kangaroo): 删除 cache 相关铁律/翻车点（cache 已废）"
git push origin fix/remove-cache-2026-06-13
```

---

## 4. 不动的东西

- **官方 ark API**——不碰
- **已生成的 mp4 文件**——绘本仓里那些，物理文件不碰
- **kangaroo 报告"用户纠错链路"段**——按用户 2026-06-13 拍板**删除**（基于错误前提的叙事，不是独立历史事件）

---

## 5. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 删 cache 后 MCP 绘本 agent 工作流挂 | 中 | 高 | spike 001 改 e2e 测试 + 不真提交，仅静态校验；绘本仓如挂了单独修 |
| kangaroo 报告改写触发其他 agent 误读 | 低 | 低 | 报告原文不动，仅坑 2 段改写，加 PATCH 注释 |
| README/INSTALL 改写漏掉某处引用 | 中 | 中 | Task 7 末尾 grep 全仓库验证 |
| `~/.cache/seedance-mcp/` 被别的进程重新创建 | 低 | 低 | 仅删文件 + 空目录，不动 .cache 父目录 |
| 用户后悔要回 cache | 低 | 中 | 物理文件先备份到 `/tmp/tasks.jsonl.bak-2026-06-13`，可手工恢复 |
| 绘本仓删铁律 #105 后旧 agent 找不到"信 CLI 走 ark"这条规则 | 中 | 中 | 铁律 #105 替换为等价段（"信 CLI 直连 ark API"），功能上等价 |
| 绘本仓 stash 改动丢失 | 低 | 中 | stash push 用 `-u` + 描述名 + 不自动 pop，留给用户自己控制 |