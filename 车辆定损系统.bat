@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ==================================================
echo   车辆定损系统 - 一键启动
echo ==================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到 .venv 虚拟环境。
    echo        请先右键运行 setup.ps1 完成环境安装。
    pause
    exit /b 1
)
if not exist "web\node_modules" (
    echo [错误] 未找到 web\node_modules。
    echo        请先在 web 目录执行 npm install。
    pause
    exit /b 1
)

rem ---------- 后端 8000 ----------
netstat -ano | findstr /C:":8000 " | findstr /C:"LISTENING" >nul
if errorlevel 1 (
    echo [1/2] 正在启动后端 http://127.0.0.1:8000 ...
    start "定损系统-后端" cmd /k ".venv\Scripts\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000"
) else (
    echo [1/2] 后端已在运行，跳过启动。
)

rem ---------- 前端 5173 ----------
netstat -ano | findstr /C:":5173 " | findstr /C:"LISTENING" >nul
if errorlevel 1 (
    echo [2/2] 正在启动前端 http://127.0.0.1:5173 ...
    start "定损系统-前端" cmd /k "cd web && npm run dev -- --host 127.0.0.1 --port 5173"
) else (
    echo [2/2] 前端已在运行，跳过启动。
)

echo.
echo 正在等待服务就绪，随后自动打开浏览器（最多 90 秒）...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(90); while((Get-Date) -lt $deadline){ $api=$false; $web=$false; try{ Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 | Out-Null; $api=$true }catch{}; try{ Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173' -TimeoutSec 2 | Out-Null; $web=$true }catch{}; if($api -and $web){ Start-Process 'http://127.0.0.1:5173'; exit 0 }; Start-Sleep -Seconds 1 }; exit 1"

if errorlevel 1 (
    echo.
    echo [提示] 服务尚未完全就绪，请查看两个服务窗口的日志。
    echo        稍后也可手动访问 http://127.0.0.1:5173
    pause
) else (
    echo.
    echo 已打开系统界面。使用完毕后，关闭“定损系统-后端”和“定损系统-前端”两个窗口即可停止服务。
    ping -n 4 127.0.0.1 >nul
)

endlocal
