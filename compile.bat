@echo off
REM 一键编译脚本 - 将yydb.py编译为单文件exe
REM 需要提前安装PyInstaller: pip install pyinstaller

set PYFILE=yydb.py
set EXENAME=YYDBAnalyzer
set ICONFILE=  REM 可以设置图标路径，如: set ICONFILE=icon.ico

echo 正在安装PyInstaller...
pip install pyinstaller --quiet

echo 正在编译%PYFILE%...
pyinstaller --onefile --noconsole --windowed %ICONFILE% --name %EXENAME% %PYFILE%

echo 编译完成！可执行文件在dist文件夹中
pause
