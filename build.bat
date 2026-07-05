@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo ============================================================
echo   DiskScanner PyQt5 打包工具 (build.bat)
echo ============================================================
echo.

REM ── 切换到脚本所在目录 ──────────────────────────────────────
cd /d "%~dp0"

REM ── 从 .env 文件读取 Python 路径 ────────────────────────────
if not exist ".env" (
    echo [错误] 未找到 .env 配置文件，请创建 .env 并设置 PYTHON=...
    pause
    exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%K in (".env") do (
    set "line=%%K"
    if not "!line:~0,1!"=="#" (
        if /I "%%K"=="PYTHON" set "PYTHON=%%L"
    )
)

if not defined PYTHON (
    echo [错误] .env 文件中未找到 PYTHON 配置项
    echo        请在 .env 文件中添加: PYTHON=你的python路径
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo [错误] 未找到 Python: %PYTHON%
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('"%PYTHON%" --version 2^>^&1') do set PYVER=%%v
echo Python 版本: %PYVER%
echo Python 路径: %PYTHON%
echo.

REM ── 安装 / 升级依赖 ─────────────────────────────────────────
echo [1/4] 检查并安装依赖...
"%PYTHON%" -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [错误] 安装依赖失败，请检查网络连接或 requirements.txt。
    pause
    exit /b 1
)

echo [2/4] 检查并安装 PyInstaller...
"%PYTHON%" -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo       正在安装 PyInstaller...
    "%PYTHON%" -m pip install pyinstaller --quiet
    if %errorlevel% neq 0 (
        echo [错误] 安装 PyInstaller 失败。
        pause
        exit /b 1
    )
)
echo       PyInstaller 已就绪。
echo.

REM ── 清理旧的构建产物 ─────────────────────────────────────────
echo [3/4] 清理旧的构建产物...
if exist "build"    ( rmdir /s /q build    && echo       已删除 build\  )
if exist "dist"     ( rmdir /s /q dist     && echo       已删除 dist\   )
if exist "__pycache__" ( rmdir /s /q __pycache__ >nul 2>&1 )
if exist "ui\__pycache__" ( rmdir /s /q ui\__pycache__ >nul 2>&1 )
echo       清理完成。
echo.

REM ── 构建可执行文件 ───────────────────────────────────────────
echo [4/4] 开始打包 DiskScanner...
echo.

REM 构建 PyInstaller 命令
set PYI_CMD="%PYTHON%" -m PyInstaller --name=DiskScanner --windowed --onefile --noconfirm --clean

if exist "icon.ico" (
    set PYI_CMD=%PYI_CMD% --icon=icon.ico
    echo       使用图标: icon.ico
) else (
    echo       未找到 icon.ico，使用默认图标。
)

REM 入口文件
set PYI_CMD=%PYI_CMD% pyqt_gui.py

echo       命令: %PYI_CMD%
echo.
echo -----------------------------------------------------------

%PYI_CMD%

if %errorlevel% neq 0 (
    echo.
    echo [错误] 打包失败，请查看上方日志排查问题。
    pause
    exit /b 1
)

echo -----------------------------------------------------------
echo.

REM ── 输出结果 ─────────────────────────────────────────────────
if exist "dist\DiskScanner.exe" (
    for %%F in ("dist\DiskScanner.exe") do set FILESIZE=%%~zF
    set /a SIZE_MB=%FILESIZE% / 1048576
    echo [成功] 可执行文件已生成!
    echo.
    echo   路径: dist\DiskScanner.exe
    echo   大小: 约 %SIZE_MB% MB
    echo.
    echo 可直接运行 dist\DiskScanner.exe 启动应用。
) else (
    echo [警告] dist\DiskScanner.exe 未找到，请检查打包日志。
)

echo.
pause
endlocal
