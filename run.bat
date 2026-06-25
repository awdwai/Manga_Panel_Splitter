@echo off
setlocal

cd /d "%~dp0"

echo MangaAnimatorPrep launcher
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

echo Verifying Python dependencies...
%PYTHON% -m pip check
if errorlevel 1 (
    echo.
    echo ERROR: Dependency check failed. Run:
    echo   %PYTHON% -m pip install -r requirements.txt
    pause
    exit /b 1
)

%PYTHON% -c "import importlib.util, sys; required=('cv2','numpy','PIL','pydantic','rich','PySide6','tqdm','psutil','onnxruntime','torch','torchvision','MangaAnimatorPrep'); missing=[m for m in required if importlib.util.find_spec(m) is None]; print('Missing required Python modules: '+', '.join(missing)) if missing else print('Required runtime dependencies found.'); sys.exit(1 if missing else 0)"
if errorlevel 1 (
    echo.
    echo ERROR: Required GUI dependencies are missing. Run:
    echo   %PYTHON% -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo Launching MangaAnimatorPrep GUI...
%PYTHON% -m MangaAnimatorPrep.main gui
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ERROR: MangaAnimatorPrep exited with code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

endlocal
