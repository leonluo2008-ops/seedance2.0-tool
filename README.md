# Seedance 2.0 Tool

纯视频生成工具，支持多种文件托管后端。

## 功能

- 🎬 视频生成（文生视频、图生视频、视频参考、角色替换）
- 🖼️ 支持图片参考、视频参考、音频参考
- ☁️ 多种文件托管后端：Chevereto API / Nginx Docker / HTTP URL

## 安装

```bash
# 克隆仓库
git clone https://github.com/leonluo2008-ops/seedance2.0-tool.git
cd seedance2.0-tool

# 设置环境变量
export ARK_API_KEY="your-ark-api-key"
export CHEVERETO_API_KEY="your-chevereto-api-key"  # 使用 chevereto 后端时必填
```

## 快速开始

### 角色替换（使用 Chevereto 上传）

```bash
python3 seedance.py create \
  --ref-images ./角色图.png \
  --video-refs ./动作视频.mp4 \
  --prompt "使用图片1的角色，替换视频1中的角色，纯白色背景，表情自然流畅" \
  --duration 5 \
  --ratio 1:1 \
  --upload-backend chevereto \
  --wait \
  --download ./output
```

### 直接使用公网 URL（不上传）

```bash
python3 seedance.py create \
  --ref-images https://example.com/char.png \
  --video-refs https://example.com/motion.mp4 \
  --prompt "使用图片1的角色，替换视频1中的角色" \
  --duration 5 \
  --ratio 1:1 \
  --upload-backend http-url \
  --wait \
  --download ./output
```

### 使用 Nginx Docker 后端

```bash
python3 seedance.py create \
  --ref-images ./角色图.png \
  --video-refs ./动作视频.mp4 \
  --prompt "..." \
  --duration 5 \
  --ratio 1:1 \
  --upload-backend nginx-docker \
  --wait \
  --download ./output
```

## 文件托管后端

| 后端 | 说明 | 适用场景 |
|------|------|----------|
| `chevereto` | Chevereto 图床 API | **推荐**，跨平台 |
| `nginx-docker` | docker cp 到 nginx 容器 | 仅限 OpenClaw 环境 |
| `http-url` | 直接使用公网 URL | 已有公网链接 |

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `ARK_API_KEY` | ✅ | Volcengine Ark API Key |
| `CHEVERETO_API_KEY` | 仅 chevereto 后端 | Chevereto API Key |

## 命令

```bash
# 创建任务
seedance.py create [options]

# 查询状态
seedance.py status <task_id>

# 等待并下载
seedance.py wait <task_id> --download ./output
```

## License

MIT
