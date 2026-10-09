#!/usr/bin/env bash
# Linux 安装脚本：下载 IndexTTS 代码、安装依赖、下载 IndexTTS-2.5 模型
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null || pip install -U uv
[ -d index-tts ] || git clone https://github.com/index-tts/index-tts.git
cd index-tts
uv sync --extra webui --default-index "${PIP_INDEX:-https://mirrors.aliyun.com/pypi/simple}"
[ -f checkpoints/config.yaml ] || uv run --extra webui modelscope download --model IndexTeam/IndexTTS-2.5 --local_dir checkpoints
uv run --extra webui tools/gpu_check.py
echo "安装完成，运行 ./start.sh 启动"
