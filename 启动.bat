@echo off
chcp 65001 >nul
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未检测到 Python，请先安装 Python 3.10+，安装时勾选 "Add Python to PATH"。
  pause
  exit /b 1
)

if not exist .venv (
  echo 首次运行：正在创建 Python 虚拟环境（约半分钟）...
  python -m venv .venv
)

call .venv\Scripts\activate.bat

python -c "import fastapi" >nul 2>nul
if errorlevel 1 (
  echo 正在安装依赖（首次约 1-2 分钟）...
  pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo ======== 选课助手已启动 ========
echo 浏览器访问  http://localhost:8000
echo 局域网分享  http://本机IP:8000（同一 WiFi 下的同学可直接访问）
echo 关闭服务：直接关闭本窗口
echo ================================
start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
