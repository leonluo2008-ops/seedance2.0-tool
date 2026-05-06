# Seedance2.0-tool 错误模式积累

## 已修复

| 日期 | 错误类型 | 根因 | 修复 |
|------|---------|------|------|
| 2026-05-06 | `_guess_mime()` NameError | `media_type` 未传参 | 改为 `self._guess_mime(p, media_type)` |
| 2026-05-06 | API base_url 占位符 | 重构时遗漏 | 替换为 `https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks` |

## 经验教训

- 重构时不要只动架构，API endpoint 必须同步更新
- 方法内引用的闭包变量必须作为参数传入
- 上传后端切换时要同步检查 MIME type 推断逻辑
