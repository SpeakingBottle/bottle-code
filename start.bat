@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal

REM ============================================================
REM  Bottle Code 网页版 · 一键启动脚本（⑤）
REM  用法：
REM     start.bat                -> 默认接真实 API（anthropic，需 .env 配好 key）
REM     start.bat mock           -> 离线可跑，无需 key
REM     start.bat openai         -> 后端接 OpenAI 兼容接口
REM  效果：后端和前端各开一个窗口；前端 http://localhost:5173
REM ============================================================

set PROVIDER=anthropic
if not "%~1"=="" set PROVIDER=%~1

REM ---- 环境自检：.venv 要存在，否则给出初始化命令 ----
if not exist ".venv\Scripts\python.exe" (
  echo [start] 未找到 .venv。请先创建并装依赖，然后重跑：
  echo         python -m venv .venv
  echo         .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

REM ---- 后端依赖：缺 fastapi/uvicorn 就装一下（已装则秒过）----
.venv\Scripts\python.exe -c "import fastapi, uvicorn, dotenv" >nul 2>&1
if errorlevel 1 (
  echo [start] 安装后端依赖...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)

REM ---- 前端依赖：没有 node_modules 就装一下 ----
if not exist "web\node_modules" (
  echo [start] 安装前端依赖 npm install...
  pushd web
  call npm install
  popd
)

REM ---- 各开一个窗口拉起后端和前端 ----
echo [start] 后端：%PROVIDER% 模式，http://127.0.0.1:8000
start "bottle-code-backend" cmd /k ".venv\Scripts\python.exe web\server.py --provider %PROVIDER% --port 8000"

echo [start] 前端：http://localhost:5173
start "bottle-code-web" cmd /k "cd web && npm run dev"

echo.
echo [start] 已在两个窗口分别启动。浏览器打开 http://localhost:5173 即可对话；
echo [start] 后端直连测试页在 http://127.0.0.1:8000/test.html 。
echo [start] 关掉对应窗口即退出，无需 Ctrl-C。
endlocal
exit /b 0
