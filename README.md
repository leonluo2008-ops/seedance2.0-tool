# Seedance 2.0 Tool

纯视频生成工具，调用 Volcengine Seedance 2.0 API，支持多种文件托管后端。

## 核心功能

- 🎬 调用 Seedance 2.0 模型生成视频
- 🖼️ 支持图片参考、视频参考、音频参考
- ☁️ 支持多种文件托管后端（Chevereto / Nginx Docker / HTTP URL）

## 快速开始

### 1. 安装

```bash
git clone https://github.com/leonluo2008-ops/seedance2.0-tool.git
cd seedance2.0-tool
```

### 2. 配置环境变量

```bash
# 必填：Volcengine Ark API Key
export ARK_API_KEY="your-ark-api-key"

# 使用 Chevereto 后端时必填：图床 API Key
export CHEVERETO_API_KEY="your-chevereto-api-key"
```

### 3. 生成视频

```bash
python3 seedance.py create \
  --ref-images ./character.png \
  --video-refs ./motion.mp4 \
  --prompt "使用图片1的角色，替换视频1中的角色，纯白色背景" \
  --duration 5 \
  --ratio 1:1 \
  --upload-backend chevereto \
  --wait \
  --download ./output
```

## 文件托管后端

| 后端 | 说明 | 适用场景 |
|------|------|----------|
| `chevereto` | Chevereto 图床 API（推荐） | **跨平台使用** |
| `nginx-docker` | docker cp 到 nginx 容器 | 仅限本地 OpenClaw 环境 |
| `http-url` | 直接使用公网 URL | 已有公网链接 |

### Chevereto 图床服务

本工具使用 Chevereto 作为默认图床后端。

**使用流程：**
1. 向图床服务提供者获取 API Key
2. 设置环境变量 `CHEVERETO_API_KEY`
3. 使用 `--upload-backend chevereto` 即可自动上传

**自建图床（可选）：**
1. 安装 Chevereto（支持 Docker）
2. 在设置中启用 API 功能并获取 API Key
3. 确保图床可通过公网访问
4. 将 API Key 提供给工具使用者

## 命令说明

```bash
# 创建视频生成任务
seedance.py create [options]

# 查询任务状态
seedance.py status <task_id>

# 等待任务完成并下载
seedance.py wait <task_id> --download ./output
```

## 主要参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--ref-images` | 参考图片路径或 URL | - |
| `--video-refs` | 参考视频路径或 URL | - |
| `--prompt` | 提示词 | - |
| `--model` | 模型 ID | doubao-seedance-2-0-fast-260128 |
| `--duration` | 视频时长（秒） | 5 |
| `--ratio` | 画幅 | 1:1 |
| `--upload-backend` | 文件托管后端 | chevereto |
| `--wait` | 等待生成完成 | False |
| `--download` | 下载保存路径 | - |

## License

MIT
