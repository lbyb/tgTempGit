@echo off
setlocal
cd /d "%~dp0\.."

echo ============================================
echo  Pupdf - build Windows executable
echo ============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python launcher "py" was not found.
    echo Install Python 3.10+ from https://www.python.org/downloads/windows/
    exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
    echo [1/4] Creating isolated build environment .venv-build ...
    py -3 -m venv .venv-build
    if errorlevel 1 exit /b 1
) else (
    echo [1/4] Using existing .venv-build ...
)

echo [2/4] Installing project and build dependencies ...
call ".venv-build\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1

echo [3/4] Running tests ...
python -m pytest -q
if errorlevel 1 exit /b 1

echo [4/4] Building one-file GUI executable ...
python -m PyInstaller --noconfirm --clean pupdf.spec
if errorlevel 1 exit /b 1

echo.
echo ============================================
echo  Build complete: %CD%\dist\Pupdf.exe
echo ============================================
echo Copy Pupdf.exe into a folder containing one PDF, then double-click it.
echo You can also drag a PDF file onto Pupdf.exe.
echo.
if "%PUPDF_NO_PAUSE%"=="" pause
exit /b 0
