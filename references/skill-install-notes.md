# seedance2.0-tool 实测笔记

## 安装验证（2026-05-18）

### Skill 安装路径
```
~/.hermes/skills/seedance2.0-tool/
```
安装方式：复制仓库文件到 skill 目录（非 git clone，非 hermes skill add）。

### CLI 验证命令
```bash
python3 ~/.hermes/skills/seedance2.0-tool/seedance.py --help
```

### 环境变量加载问题

**症状**：`hermes` 进程调用的 Python 进程读不到 `~/.bashrc` 中的环境变量。

**原因**：`systemctl --user` 启动的 Hermes 进程是 login shell 之外的独立进程，不继承 `~/.bashrc`。

**验证方式**：
```bash
# 在 bashrc 中确认存在
grep -n "ARK_API_KEY\|CHEVERETO" ~/.bashrc

# 确认格式正确（ark- 开头，4段）
# 错误格式：314953...f591（3段省略号）
# 正确格式：ark-xxxx-xxxx-xxxx-xxxx
```

**影响**：CLI 调用 `get_api_key()` 检查环境变量，不影响 skill 注册。但实际生成视频会失败。

### ARK_API_KEY 格式验证

```bash
curl -s -X POST "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks" \
  -H "Authorization: Bearer <YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"doubao-seedance-2-0-fast-260128","content":[{"type":"text","text":"test"}],"parameters":{"duration":5}}'
```

正确 key 返回 `{"id":"cgt-..."}`；错误格式返回 `{"error":{"code":"AuthenticationError","message":"The API key format is incorrect"}}`。

### skill_view 验证
```bash
skill_view(name='seedance2.0-tool')
# readiness_status: available
# setup_needed: false
```