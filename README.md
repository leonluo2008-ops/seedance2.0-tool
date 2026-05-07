# Seedance 2.0 Tool

纯视频生成工具，调用 Volcengine Seedance 2.0 API 生成视频。

## 核心功能

- 🎬 调用 Seedance 2.0 模型生成视频
- 🖼️ 支持图片参考、视频参考、音频参考
- ✍️ 支持文生视频、图片生视频、动作模仿等多种模式
- ☁️ 本地文件自动上传 Chevereto 图床（公网可访问）

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

# 必填：Chevereto 图床 API Key（上传本地文件用）
export CHEVERETO_API_KEY="your-chevereto-api-key"
```

### 3. 生成视频

```bash
# 动作模仿（图片 + 视频参考）⭐
python3 seedance.py create \
  --ref-images ./character.png \
  --video-refs ./motion.mp4 \
  --prompt "@Image1's character mimics @Video1's action choreography, pure white background" \
  --duration 5 \
  --ratio 16:9 \
  --wait \
  --download ./output

# 文生视频
python3 seedance.py create \
  --prompt "宇航员在太空中行走，漂浮感，电影质感" \
  --duration 5 \
  --ratio 16:9 \
  --wait
```

## 主要参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--prompt` / `-p` | 文字提示词 | - |
| `--ref-images` | 参考图片（角色参考） | - |
| `--video-refs` | 参考视频（本地文件自动上传） | - |
| `--image` / `-i` | 首帧图片 | - |
| `--audio` | 参考音频 | - |
| `--model` / `-m` | 模型 ID（Fast/高质量） | `doubao-seedance-2-0-fast-260128`（默认） |
| `--duration` / `-d` | 时长（秒，4-15） | `5` |
| `--ratio` | 画幅（16:9/4:3/1:1/3:4/9:16/21:9/adaptive） | `16:9` |
| `--resolution` / `-r` | 分辨率（480p/720p/1080p） | `720p` |
| `--seed` | 随机种子（-1=随机） | `-1` |
| `--watermark` | 添加水印 | `true` |
| `--service-tier` | 服务层级（default/flex） | `default` |
| `--wait` / `-w` | 等待生成完成 | - |
| `--download` | 下载目录 | - |

## 命令

```bash
python3 seedance.py create [options]   # 创建任务
python3 seedance.py status <task_id>   # 查询状态
python3 seedance.py wait <task_id>     # 等待完成
python3 seedance.py list [--status succeeded]  # 列出任务
python3 seedance.py delete <task_id>   # 删除任务
```

## License

MIT
