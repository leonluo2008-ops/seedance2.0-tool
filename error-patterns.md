# Seedance2.0-tool 错误模式积累

## 已修复

| 日期 | 错误类型 | 根因 | 修复 |
|------|---------|------|------|
| 2026-05-06 | `_guess_mime()` NameError | `media_type` 未传参 | 改为 `self._guess_mime(p, media_type)` |
| 2026-05-06 | API base_url 占位符 | 重构时遗漏 | 替换为 `https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks` |
| 2026-05-06 | Chevereto HOST=localhost | 重构时错误 | 改为 `https://chevereto.aistar.work/api/1/upload` |
| 2026-05-06 | `requests` 被 Cloudflare 拦截 | urllib/requests 被 Cloudflare ASN block | 改用 curl subprocess（与 Seedance2-skill 验证一致） |
| 2026-05-06 | 视频 MIME type 推断不准确 | `mimetypes.guess_type()` 对 mp4 不稳定 | 显式指定 `type=video/mp4` |
| 2026-05-06 | 保留 nginx-docker 和 http-url 后端 | 多后端架构不再需要 | 删除，只保留 Chevereto（唯一图床） |

## 经验教训

- 重构时不要只动架构，API endpoint 必须同步更新
- 方法内引用的闭包变量必须作为参数传入
- 上传后端切换时要同步检查 MIME type 推断逻辑
- Chevereto 上传必须用 curl subprocess，`requests`/`urllib` 会被 Cloudflare ASN block
- 视频上传必须显式指定 `type=video/mp4`，mimetypes 模块对 mp4 判断不稳定
- 多后端架构如果只有一端实际使用，应删除简化代码
