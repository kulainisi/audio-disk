@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "PIP_MIRROR=https://mirrors.aliyun.com/pypi/simple"
set "PY_MIRROR=https://registry.npmmirror.com/-/binary/python-build-standalone"

where git >nul 2>nul || (echo 未找到 git，请先安装：https://git-scm.com/downloads & pause & exit /b 1)

echo [1/5] 检查 uv（需要 0.9 或更新版本）...
call :find_uv
if not defined UV (
  echo 未找到 uv，正在安装 ...
  call :install_uv
) else (
  call :check_uv
  if errorlevel 1 (
    echo 当前 uv !UV_VER! 版本过旧，正在升级 ...
    "!UV!" self update >nul 2>nul
    call :check_uv || python -m pip install -U uv -i %PIP_MIRROR% >nul 2>nul
    call :find_uv
    call :check_uv || call :install_uv
  )
)
call :check_uv || (echo uv 升级失败。请手动安装后重试：https://docs.astral.sh/uv/getting-started/installation/ & pause & exit /b 1)
echo 使用 uv !UV_VER!：!UV!

if not exist index-tts (
  echo [2/5] 下载 IndexTTS 代码 ...
  git clone https://github.com/index-tts/index-tts.git || (echo 下载失败，请检查网络 & pause & exit /b 1)
) else (
  echo [2/5] IndexTTS 代码已存在，跳过下载
)
cd index-tts

echo [3/5] 安装 Python（版本见 .python-version）...
"!UV!" python install
if errorlevel 1 (
  echo 从 GitHub 下载 Python 失败，改用国内镜像重试 ...
  set "UV_PYTHON_INSTALL_MIRROR=%PY_MIRROR%"
  "!UV!" python install || (echo Python 安装失败，请检查网络后重新运行 setup.bat & pause & exit /b 1)
)

echo [4/5] 安装依赖（第一次需要下载约 5GB，请耐心等待）...
"!UV!" sync --extra webui --default-index "%PIP_MIRROR%" || (echo 依赖安装失败。如果提示 CUDA 错误，请先安装 CUDA Toolkit 12.8 & pause & exit /b 1)

if not exist checkpoints\config.yaml (
  echo [5/5] 从 ModelScope 下载 IndexTTS-2.5 模型 ...
  "!UV!" run --extra webui modelscope download --model IndexTeam/IndexTTS-2.5 --local_dir checkpoints || (echo 模型下载失败，请重新运行 setup.bat & pause & exit /b 1)
) else (
  echo [5/5] 模型已存在，跳过下载
)

echo.
echo 检查显卡 ...
"!UV!" run --extra webui tools/gpu_check.py

echo.
echo 安装完成，双击 start.bat 启动。
pause
exit /b 0

rem ---- 查找 uv：优先使用官方安装器装到 %USERPROFILE%\.local\bin 的版本 ----
:find_uv
set "UV="
if exist "%USERPROFILE%\.local\bin\uv.exe" (set "UV=%USERPROFILE%\.local\bin\uv.exe" & exit /b 0)
for /f "delims=" %%p in ('where uv 2^>nul') do if not defined UV set "UV=%%p"
exit /b 0

rem ---- 检查 uv 版本是否不低于 0.9，结果放在 errorlevel ----
:check_uv
set "UV_VER="
if not defined UV exit /b 1
for /f "tokens=2" %%v in ('call "!UV!" --version 2^>nul') do set "UV_VER=%%v"
if not defined UV_VER exit /b 1
for /f "tokens=1,2 delims=." %%a in ("!UV_VER!") do (set "UV_MAJOR=%%a" & set "UV_MINOR=%%b")
if !UV_MAJOR! GTR 0 exit /b 0
if !UV_MINOR! GEQ 9 exit /b 0
exit /b 1

rem ---- 用官方安装器安装最新 uv ----
:install_uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 python -m pip install -U uv -i %PIP_MIRROR%
call :find_uv
exit /b 0
