# seedance2.0-tool 环境与故障排查

## Key 配置：为什么不用 bashrc

**问题**：CLI 工具（如 seedance.py）通过 Python `subprocess` 调用 curl/urllib 时，不会继承用户 shell 的环境变量（`~/.bashrc` 中的 `export` 对子进程不可见）。

**症状**：
```
Error: ARK_API_KEY environment variable is not set.
```

**常见踩坑场景**：
- 在 `~/.bashrc` 或 `~/.zshrc` 中配置了 key，以为所有命令都能读到
- 手动 `source ~/.bashrc` 后直接运行可以，但 cron/systemd/delegated agent 子进程会失败
- 某个 session 里运行正常，换一个 session 就报 `not set`

**正确做法**：在 skill 目录放置 `.env` 文件，Python 用 `python-dotenv` 加载。

```
~/.hermes/skills/seedance2.0-tool/.env
```

```bash
ARK_API_KEY=your-volcengine-ark-api-key
CHEVERETO_API_KEY=your-chevereto-api-key
```

seedance.py 的 `main()` 函数会自动向上查找并加载 `.env`：
```python
script_dir = Path(__file__).resolve().parent
for candidate in [script_dir, script_dir.parent, Path.cwd()]:
    env_path = candidate / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        break
```

## 故障排查路径

### Q: `ARK_API_KEY not set` 或 `CHEVERETO_API_KEY not set`

1. 确认 `.env` 文件存在：`ls ~/.hermes/skills/seedance2.0-tool/.env`
2. 确认文件内有正确的 key 行（无引号）：`grep ARK_API_KEY ~/.hermes/skills/seedance2.0-tool/.env`
3. 如果 key 在 bashrc 里而不在 .env 里 → 把 key 复制到 .env，删除 bashrc 中的 export 行
4. **不要**依赖 bashrc——任何通过 subprocess/HTTP 触发的 CLI 都会失败

### Q: 任务创建成功但 `status`/`wait` 报 `not set`

- create 命令在某个有环境变量的 session 里运行，key 还活着
- 后续命令在新的 subprocess 中执行，环境变量已消失
- **解决**：直接修复 .env 文件，确保 key 存在其中

### Q: `wait` 超时但任务实际已完成

**不要重新创建任务**。步骤：

```bash
# 1. 确认任务状态
python3 seedance.py status <task_id>

# 2. 如果 status 是 succeeded，直接下载
python3 seedance.py wait <task_id> --download /tmp/output
```

任务已完成时 `wait` 会立即返回，不会再次等待。

### Q: Chevereto 上传报 `403` 或 `permission denied`

- Chevereto API Key 可能过期或被重置
- 检查 key 是否和 `~/.bashrc` 中的一致
- 在 https://chevereto.aistar.work 登录后重新获取 key，更新到 `.env`

### Q: `seedance.py: command not found`

CLI 入口是 `python3 ~/.hermes/skills/seedance2.0-tool/seedance.py`，不是直接运行 `seedance.py`。如果觉得路径太长，可以设置 alias：

```bash
alias seedance='python3 ~/.hermes/skills/seedance2.0-tool/seedance.py'
```

## 通用原则：CLI Skill 的 Key 管理

任何通过 Hermes/OpenClaw spawn 的 subprocess 都无法继承父进程的 bashrc 环境变量。

| Key 存储位置 | subprocess 能否读取 | 推荐程度 |
|-------------|---------------------|---------|
| `~/.bashrc` export | ❌ 不能 | 不推荐 |
| skill 目录 `.env` | ✅ 能（python-dotenv） | **推荐** |
| 环境变量（直接 `export KEY=xxx`） | ✅ 能 | 可用，但不持久 |
| systemd service 文件 | ✅ 能（需在 service 里定义） | 仅限服务进程 |

**规则**：涉及 subprocess 调用的 skill，key 必须放在 skill 自己的 `.env` 文件中。
