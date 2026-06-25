@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo MangaAnimatorPrep development executable build
echo Repository root: %CD%
echo.

if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment: .venv
    call ".venv\Scripts\activate.bat"
) else (
    echo No .venv found; using system Python.
)

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python was not found. Install Python 3.14+ or create .venv in this repository.
        pause
        exit /b 1
    )
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)

echo Verifying project dependencies...
%PYTHON% -m pip check
if errorlevel 1 (
    echo.
    echo ERROR: Dependency check failed. Install dependencies first:
    echo   %PYTHON% -m pip install -r requirements.txt
    pause
    exit /b 1
)

%PYTHON% "scripts\check_runtime.py"
if errorlevel 1 (
    echo.
    echo ERROR: Runtime dependencies are missing. Install dependencies first:
    echo   %PYTHON% -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Verifying PyInstaller...
%PYTHON% -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo PyInstaller is not installed. Installing build dependency...
    %PYTHON% -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

echo.
echo Cleaning previous development build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist\MangaAnimatorPrep.exe" del /q "dist\MangaAnimatorPrep.exe"

echo.
echo Building dist\MangaAnimatorPrep.exe ...
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --console ^
    --name MangaAnimatorPrep ^
    --paths "%CD%" ^
    --collect-all PySide6 ^
    --collect-submodules MangaAnimatorPrep ^
    --collect-submodules onnxruntime ^
    --hidden-import cv2 ^
    --hidden-import PIL.Image ^
    "MangaAnimatorPrep\gui_entry.py"

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

if not exist "dist\MangaAnimatorPrep.exe" (
    echo.
    echo ERROR: Build completed but dist\MangaAnimatorPrep.exe was not found.
    pause
    exit /b 1
)

echo.
echo Build complete:
echo   %CD%\dist\MangaAnimatorPrep.exe
echo.
echo Launching the executable for a local smoke test...
"%CD%\dist\MangaAnimatorPrep.exe"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ERROR: Executable exited with code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

endlocal
