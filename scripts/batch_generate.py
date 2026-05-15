#!/usr/bin/env python3
"""
批量视频生成脚本
读取目录下的所有 .json spec 文件，依次执行生成任务。

用法：
    python3 scripts/batch_generate.py <spec_dir> [--output <output_dir>] [--wait]

示例：
    python3 scripts/batch_generate.py tmp/batch_jobs/ --wait
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SEEDANCE_PY = SKILL_DIR / "seedance.py"


def load_dotenv():
    """加载环境变量"""
    for candidate in [SKILL_DIR, SKILL_DIR.parent, Path.cwd()]:
        env_path = candidate / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
            break


def run_single_spec(spec_path: Path, output_base: Path, wait: bool) -> dict:
    """执行单个 spec 文件，返回结果"""
    with open(spec_path) as f:
        spec = json.load(f)

    # 构建 seedance.py 命令参数
    cmd = ["python3", str(SEEDANCE_PY), "create"]
    
    # prompt
    if spec.get("prompt"):
        cmd += ["--prompt", spec["prompt"]]
    
    # model
    cmd += ["--model", spec.get("model", "doubao-seedance-2-0-fast-260128")]
    
    # duration
    cmd += ["--duration", str(spec.get("duration", 5))]
    
    # ratio
    cmd += ["--ratio", spec.get("ratio", "16:9")]
    
    # resolution
    cmd += ["--resolution", spec.get("resolution", "480p")]
    
    # ref_images
    for img in spec.get("ref_images", []):
        cmd += ["--ref-images", img]
    
    # video_refs
    for vid in spec.get("video_refs", []):
        cmd += ["--video-refs", vid]
    
    # audio
    for aud in spec.get("audio", []):
        cmd += ["--audio", aud]
    
    # output_name 用于结果文件名
    output_name = spec.get("output_name", spec_path.stem)
    
    if wait:
        cmd.append("--wait")
    
    cmd.append("--force")

    print(f"\n{'='*60}")
    print(f"执行: {spec_path.name}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*60}")

    result = {
        "spec_file": str(spec_path),
        "spec": spec,
        "cmd": " ".join(cmd),
        "status": "running",
        "task_id": None,
        "error": None,
        "output": None,
    }

    try:
        # 执行命令（不使用 shell，避免转义问题）
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(SKILL_DIR),
            env={**os.environ, **os.environ}  # 继承当前环境变量
        )
        
        if proc.returncode != 0:
            result["status"] = "failed"
            result["error"] = proc.stderr
            result["output"] = proc.stdout
            return result
        
        output = proc.stdout
        
        # 解析 task_id
        for line in output.split("\n"):
            if "Task ID:" in line or "task_id" in line.lower():
                task_id = line.split("Task ID:")[-1].strip()
                if not task_id:
                    # 尝试从 "Task created: xxx" 格式提取
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p.lower() in ("id:", "task_id:", "task"):
                            task_id = parts[i + 1] if i + 1 < len(parts) else None
                result["task_id"] = task_id
                break
        
        result["output"] = output
        
        # 如果需要等待，轮询任务状态
        if wait and result["task_id"]:
            print(f"等待任务完成: {result['task_id']}")
            # 简单等待后查询（实际应该轮询）
            time.sleep(5)
            status_cmd = ["python3", str(SEEDANCE_PY), "status", result["task_id"]]
            status_proc = subprocess.run(
                status_cmd,
                capture_output=True,
                text=True,
                cwd=str(SKILL_DIR)
            )
            result["status_output"] = status_proc.stdout
        
        result["status"] = "submitted"
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="批量视频生成脚本")
    parser.add_argument("spec_dir", help="包含 .json spec 文件的目录")
    parser.add_argument("--output", "-o", default=None, help="结果输出目录（默认与 spec_dir 相同）")
    parser.add_argument("--wait", "-w", action="store_true", help="等待每个任务完成")
    parser.add_argument("--dry-run", "-n", action="store_true", help="仅打印命令，不执行")
    
    args = parser.parse_args()
    
    spec_dir = Path(args.spec_dir)
    if not spec_dir.exists():
        print(f"错误: 目录不存在: {spec_dir}")
        sys.exit(1)
    
    output_dir = Path(args.output) if args.output else spec_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载环境变量
    load_dotenv()
    
    # 查找所有 .json 文件（排除 .result.json）
    spec_files = sorted(spec_dir.glob("*.json"))
    spec_files = [f for f in spec_files if not f.name.endswith(".result.json")]
    
    if not spec_files:
        print(f"警告: 目录 {spec_dir} 中没有找到 .json spec 文件")
        sys.exit(0)
    
    print(f"找到 {len(spec_files)} 个 spec 文件")
    print(f"Spec 目录: {spec_dir}")
    print(f"输出目录: {output_dir}")
    
    results = []
    
    for spec_file in spec_files:
        result = run_single_spec(spec_file, output_dir, args.wait)
        results.append(result)
        
        # 保存结果
        result_file = output_dir / f"{spec_file.stem}.result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存: {result_file}")
    
    # 汇总报告
    print(f"\n{'='*60}")
    print(f"批量执行完成: {len(results)} 个任务")
    print(f"{'='*60}")
    
    summary = {"total": len(results), "submitted": 0, "failed": 0, "error": 0}
    for r in results:
        summary[r.get("status", "unknown")] = summary.get(r.get("status", "unknown"), 0) + 1
        if r.get("task_id"):
            summary["submitted"] += 1
        elif r.get("error"):
            summary["failed"] += 1
    
    print(f"提交成功: {summary['submitted']}")
    print(f"失败: {summary['failed']}")
    
    # 保存汇总
    summary_file = output_dir / "batch_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    
    print(f"\n汇总已保存: {summary_file}")


if __name__ == "__main__":
    main()
