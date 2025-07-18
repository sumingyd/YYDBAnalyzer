@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM 一键编译脚本 - 将yydb.py编译为单文件exe
REM 需要提前安装PyInstaller: pip install pyinstaller

set PYFILE=yydb.py
set EXENAME=YYDBAnalyzer
set ICONFILE=

echo 正在检查PyInstaller安装...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [错误] PyInstaller安装失败
    pause
    exit /b 1
)

echo 正在清理旧编译文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo 正在编译 %PYFILE%...
pyinstaller --onefile --noconsole --windowed --name %EXENAME% %PYFILE%
if errorlevel 1 (
    echo [错误] 编译失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo 编译成功！可执行文件已生成在 dist 目录
echo 文件路径: %cd%\dist\%EXENAME%.exe
echo ========================================
echo.

REM 自动打开输出目录
start "" "dist"

pause
