@echo off
echo ========================================
echo GLM Usage Monitor - Install
echo ========================================
echo.

echo [1/2] Installing Python dependencies (using China mirror)...
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple flask flask-cors playwright PyGithub python-dotenv
if %errorlevel% neq 0 (
    echo Failed to install dependencies!
    echo Please make sure Python is installed correctly.
    pause
    exit /b 1
)

echo.
echo [2/2] Installing Playwright dependencies...
python -m playwright install-deps
echo Skipping browser download (will use Edge)

echo.
echo ========================================
echo Install completed!
echo Run start.bat to launch the program
echo ========================================
pause
