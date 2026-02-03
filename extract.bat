@echo off
echo ================================
echo    PDF 文本提取工具 (Windows)
echo ================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.x
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查依赖
echo 检查Python依赖...
python -c "import pdfplumber, pypdf" 2>nul
if errorlevel 1 (
    echo 安装依赖中...
    pip install pdfplumber pypdf pdfminer.six
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

REM 获取PDF文件
set /p pdf_file="请输入PDF文件路径（可拖放文件到此处）: "
if "%pdf_file%"=="" (
    echo [错误] 未输入文件路径
    pause
    exit /b 1
)

REM 去掉可能的引号
set pdf_file=%pdf_file:"=%

REM 检查文件是否存在
if not exist "%pdf_file%" (
    echo [错误] 文件不存在: %pdf_file%
    pause
    exit /b 1
)

REM 提取文本
echo.
echo 开始提取: %pdf_file%
python pdf_extractor.py "%pdf_file%" --verbose

echo.
echo 按任意键退出...
pause >nul