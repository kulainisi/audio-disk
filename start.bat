@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist index-tts\checkpoints\config.yaml (echo 还没有安装，请先双击 setup.bat & pause & exit /b 1)
set "UV=uv"
if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
rem 首次运行会从 HuggingFace 下载几个小模型，国内用镜像更快
if not defined HF_ENDPOINT set HF_ENDPOINT=https://hf-mirror.com
echo 正在加载模型，大约需要 1-2 分钟，加载完成后会自动打开浏览器 ...
"%UV%" run --project index-tts --extra webui python server.py --open %*
pause
