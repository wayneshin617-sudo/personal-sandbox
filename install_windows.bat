@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo Identity Face Swap Studio - Windows install
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] python 실행 파일을 PATH에서 찾지 못했습니다.
  echo Python 3.10 또는 3.11^(3.12도 동작^)을 설치하세요: https://www.python.org/downloads/
  goto :fail
)

for /f "tokens=2 delims= " %%v in ('python -c "import sys; print(sys.version)"') do (
  echo Python: %%v
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.10 이상이 필요합니다.
  goto :fail
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] venv 생성 실패
    goto :fail
  )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing pinned requirements...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] requirements 설치 실패. 버전 충돌 로그를 확인하세요.
  goto :fail
)

echo.
echo --- GPU / CUDA ---
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  echo nvidia-smi 없음: CPU 모드로 설치를 유지합니다.
) else (
  nvidia-smi
  echo CUDA GPU가 있으면 선택적으로 onnxruntime-gpu를 설치할 수 있습니다.
  echo   .venv\Scripts\pip uninstall -y onnxruntime
  echo   .venv\Scripts\pip install onnxruntime-gpu==1.20.1
)

echo.
echo --- FFmpeg / FFprobe ---
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [WARN] ffmpeg 없음. https://www.gyan.dev/ffmpeg/builds/ 또는 winget install Gyan.FFmpeg
) else (
  ffmpeg -version | more +0
)
where ffprobe >nul 2>nul
if errorlevel 1 (
  echo [WARN] ffprobe 없음. FFmpeg 전체 빌드를 PATH에 넣으세요.
) else (
  ffprobe -version | more +0
)

echo.
echo --- Models ---
".venv\Scripts\python.exe" -c "from src.model_manager import download_models; download_models(); print('models ready')"
if errorlevel 1 (
  echo [WARN] 자동 모델 다운로드 실패. models\README.md 의 수동 경로를 사용하세요.
  echo 모델이 없으면 얼굴 교체는 비활성화되며 단순 합성으로 대체되지 않습니다.
)

echo.
echo --- Environment check ---
".venv\Scripts\python.exe" check_environment.py
if errorlevel 1 (
  echo [WARN] 환경 검사에서 경고/오류가 있었습니다. 위 로그를 확인하세요.
)

echo.
echo Install finished.
pause
exit /b 0

:fail
echo.
echo Install failed. 창을 닫지 않고 오류를 확인하세요.
pause
exit /b 1
