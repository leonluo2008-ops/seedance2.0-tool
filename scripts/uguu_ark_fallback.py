#!/usr/bin/env python3
"""
uguu 兜底路线（chevereto 挂了用 uguu.se + 直接 curl 调 ark API）
- 2026-06-07 Pic4 v1 跑通后 chevereto 挂了（curl 6 次全 timeout）
- 改用 uguu.se 上传图片 + 直接调 ark API（绕过 seedance.py 的 chevereto 硬编码）
- Pic4 v3 实战跑通：clip1 4s task cgt-20260607141523-mxclp seed 79679

用法：
    python3 uguu_ark_fallback.py <image_path> <prompt_file> <duration> <output_path>
    # 例：python3 uguu_ark_fallback.py 1.jpg clip1-prompt-v3.txt 4 v3-clip1-fixed.mp4
"""
import os
import sys
import json
import ssl
import urllib.request
import hashlib
import time

ctx = ssl.create_default_context()

# 加载 .env
ENV_PATH = "/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/.env"
for line in open(ENV_PATH, encoding='utf-8'):
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    os.environ.setdefault(k.strip(), v.strip())

ARK_API_KEY = os.environ['ARK_API_KEY']
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
MODEL = "doubao-seedance-2-0-fast-260128"


def upload_uguu(local_path):
    """上传到 uguu.se 拿公网 URL（multipart field 名 files[] 带方括号）"""
    file_data = open(local_path, "rb").read()
    boundary = "----hermesboundary12345"
    parts = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="files[]"; filename="{os.path.basename(local_path)}"\r\n'.encode(),
        b"Content-Type: image/jpeg\r\n\r\n",
        file_data, b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    req = urllib.request.Request(
        "https://uguu.se/upload.php", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "curl/8.0"},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=120, context=ctx)
    return json.loads(r.read())["files"][0]["url"]


def create_task(image_url, prompt, duration=4, ratio="adaptive", watermark=False, resolution="720p"):
    """直接调 ark API 创建 task（不走 seedance.py）"""
    body = {
        "model": MODEL,
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}, "role": "first_frame"},
        ],
        "duration": duration, "ratio": ratio,
        "watermark": watermark, "resolution": resolution,
    }
    req = urllib.request.Request(
        BASE_URL, data=json.dumps(body).encode('utf-8'),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {ARK_API_KEY}"},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=60, context=ctx)
    return json.loads(r.read())


def get_status(task_id):
    req = urllib.request.Request(
        f"{BASE_URL}/{task_id}",
        headers={"Authorization": f"Bearer {ARK_API_KEY}"},
    )
    r = urllib.request.urlopen(req, timeout=30, context=ctx)
    return json.loads(r.read())


def download(url, out_path):
    """下载视频（用 urllib 不用 curl，URL 跟 X-Tos-Signature 时效约 24h）"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(out_path, 'wb') as f:
        f.write(data)
    return hashlib.md5(data).hexdigest(), len(data)


def run(image, prompt_file, duration, output):
    """完整跑 1 段视频（uguu + ark API + 等待 + 下载）"""
    print(f"=== uguu_ark_fallback ===")
    print(f"  image: {image}")
    print(f"  prompt: {prompt_file}")
    print(f"  duration: {duration}s")
    print(f"  output: {output}")
    print()

    # 1. uguu 上传
    print(f"  uguu 上传...", end=" ")
    img_url = upload_uguu(image)
    print(f"OK: {img_url}")

    # 2. create task
    print(f"  ark create task...", end=" ")
    prompt = open(prompt_file, encoding='utf-8').read()
    result = create_task(img_url, prompt, duration)
    task_id = result['id']
    print(f"task_id: {task_id}")

    # 3. 等完成（最多 5 分钟）
    print(f"  等待完成...", end=" ", flush=True)
    for i in range(60):
        time.sleep(5)
        s = get_status(task_id)
        if s.get('status') == 'succeeded':
            print(f"✅ succeeded ({i*5}s)")
            video_url = s['content']['video_url']
            break
        elif s.get('status') == 'failed':
            print(f"❌ failed: {s.get('error', {})}")
            sys.exit(1)
    else:
        print(f"❌ timeout 5min")
        sys.exit(1)

    # 4. 下载
    print(f"  下载...", end=" ")
    md5, size = download(video_url, output)
    print(f"✅ {size//1024}KB md5={md5}")
    return task_id, md5, size


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("用法: python3 uguu_ark_fallback.py <image_path> <prompt_file> <duration> <output_path>")
        print("例: python3 uguu_ark_fallback.py 1.jpg clip1-prompt-v3.txt 4 v3-clip1-fixed.mp4")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
