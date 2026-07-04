@echo off
chcp 65001 >nul
REM ─────────────────────────────────────────────────────────────
REM  DiskScanner 打包脚本
REM  使用 PyInstaller 将 tkinter_gui.py 打包为单文件可执行程序
REM ─────────────────────────────────────────────────────────────

echo.
echo  ============================================
echo   DiskScanner 打包工具
echo  ============================================
echo.

REM 切换到脚本所在目录（即项目根目录）
cd /d "%~dp0"

REM 检测 Python 命令（优先使用 py 启动器）
where py >nul 2>&1
if not errorlevel 1 (
    set PYTHON=py
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set PYTHON=python
    ) else (
        echo  [错误] 未找到 Python，请先安装 Python 3.8+ 并加入 PATH
        pause
        exit /b 1
    )
)

REM 检查 / 安装 PyInstaller
%PYTHON% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  [信息] 未检测到 PyInstaller，正在安装...
    %PYTHON% -m pip install pyinstaller
    if errorlevel 1 (
        echo  [错误] PyInstaller 安装失败
        pause
        exit /b 1
    )
)

echo.
echo  [信息] 开始打包...
echo.

REM 清理旧的构建目录
if exist "dist\DiskScanner.exe" del "dist\DiskScanner.exe"

REM 执行打包（使用 spec 文件，不生成额外确认提示）
%PYTHON% -m PyInstaller DiskScanner.spec --noconfirm

if errorlevel 1 (
    echo.
    echo  [错误] 打包失败，请检查上方错误信息
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   打包成功！
echo   输出文件: dist\DiskScanner.exe
echo  ============================================
echo.

pause
