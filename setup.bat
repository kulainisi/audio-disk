@echo off
chcp 65001 >nul
cd /d "%~dp0"

where git >nul 2>nul || (echo 未找到 git，请先安装：https://git-scm.com/downloads & pause & exit /b 1)
where uv >nul 2>nul || (
  echo 正在安装 uv ...
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  echo uv 安装完成，请关闭本窗口后重新双击 setup.bat
  pause & exit /b 0
)

if not exist index-tts (
  echo [1/4] 下载 IndexTTS 代码 ...
  git clone https://github.com/index-tts/index-tts.git || (echo 下载失败，请检查网络 & pause & exit /b 1)
)
cd index-tts

echo [2/4] 安装依赖（第一次需要下载约 5GB，请耐心等待）...
uv sync --extra webui --default-index "https://mirrors.aliyun.com/pypi/simple" || (echo 依赖安装失败。如果提示 CUDA 错误，请先安装 CUDA Toolkit 12.8 & pause & exit /b 1)

if not exist checkpoints\config.yaml (
  echo [3/4] 从 ModelScope 下载 IndexTTS-2.5 模型 ...
  uv run --extra webui modelscope download --model IndexTeam/IndexTTS-2.5 --local_dir checkpoints || (echo 模型下载失败，请重新运行 setup.bat & pause & exit /b 1)
)

echo [4/4] 检查显卡 ...
uv run --extra webui tools/gpu_check.py

echo.
echo 安装完成，双击 start.bat 启动。
pause
