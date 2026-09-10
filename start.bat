@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal

REM ============================================================
REM  Bottle Code Web - one-click launcher
REM  Usage:
REM    start.bat                -> real API (anthropic, needs .env key)
REM    start.bat mock           -> offline, no key needed
REM    start.bat openai         -> OpenAI-compatible backend
REM  Result: backend + frontend each open a window; frontend at http://localhost:5173
REM
REM  NOTE: keep this file ASCII-only AND CRLF line endings. cmd.exe reads
REM  batch files with the system OEM code page (936 on Chinese Windows);
REM  any non-ASCII bytes (e.g. UTF-8 Chinese comments) get misparsed and
REM  can execute comment lines as commands, creating garbage files. LF-only
REM  endings also break cmd's if (...) block parsing. And never put literal
REM  parentheses inside a block's echo line - cmd treats the first ')' as
REM  the block end and errors on whatever follows. Chinese usage notes live
REM  in README.md instead.
REM ============================================================

set PROVIDER=anthropic
if not "%~1"=="" set PROVIDER=%~1

REM ---- Env check: .venv must exist, otherwise show init commands ----
if not exist ".venv\Scripts\python.exe" (
  echo [start] .venv not found. Create it and install deps first, then rerun:
  echo         python -m venv .venv
  echo         .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

REM ---- Backend deps: install fastapi/uvicorn if missing (fast if already installed) ----
.venv\Scripts\python.exe -c "import fastapi, uvicorn, dotenv" >nul 2>&1
if errorlevel 1 (
  echo [start] Installing backend dependencies...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)

REM ---- Frontend deps: npm install if node_modules missing ----
if not exist "web\node_modules" (
  echo [start] Installing frontend dependencies: npm install...
  pushd web
  call npm install
  popd
)

REM ---- Launch backend and frontend in separate windows ----
echo [start] Backend: %PROVIDER% mode, http://127.0.0.1:8000
start "bottle-code-backend" cmd /k ".venv\Scripts\python.exe web\server.py --provider %PROVIDER% --port 8000"

echo [start] Frontend: http://localhost:5173
start "bottle-code-web" cmd /k "cd web && npm run dev"

echo.
echo [start] Started in two windows. Open http://localhost:5173 to chat;
echo [start] Backend test page at http://127.0.0.1:8000/test.html .
echo [start] Close the windows to exit, no Ctrl-C needed.
endlocal
exit /b 0
