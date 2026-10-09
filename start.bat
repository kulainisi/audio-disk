@echo off
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>nul || (echo 未找到 Node.js，请先从 https://nodejs.org 安装 LTS 版本 & pause & exit /b 1)
if not exist .env (copy .env.example .env >nul & echo 已生成 .env，请用记事本填写 API Key 后重新运行 & notepad .env & exit /b 0)
start "" http://localhost:3000
node server.js
pause
