@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo Identity Face Swap Studio
echo ============================================

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] .venv 가 없습니다. 먼저 install_windows.bat 를 실행하세요.
  goto :fail
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo Running environment check...
python check_environment.py
if errorlevel 1 (
  echo [ERROR] 환경 검사 실패. FFmpeg/FFprobe 또는 Python 패키지를 확인하세요.
  goto :fail
)

echo Starting Streamlit...
python -m streamlit run app.py --server.headless true --server.address 0.0.0.0 --server.port 8501
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo 실행 실패. 이 창을 닫지 말고 오류를 확인하세요.
pause
exit /b 1
