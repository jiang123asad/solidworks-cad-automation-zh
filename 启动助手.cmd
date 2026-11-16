@echo off
setlocal
title SolidWorks Chinese Assistant
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -X utf8 -B "%~dp0scripts\cad_assistant.py" menu
  goto done
)
py -3 -c "import sys;sys.exit(sys.version_info < (3,9))" >nul 2>&1
if not errorlevel 1 (
  py -3 -X utf8 -B "%~dp0scripts\cad_assistant.py" menu
  goto done
)
python -c "import sys;sys.exit(sys.version_info < (3,9))" >nul 2>&1
if not errorlevel 1 (
  python -X utf8 -B "%~dp0scripts\cad_assistant.py" menu
  goto done
)
echo Python 3.9+ was not found. Install Windows Python, then retry.
echo Read INSTALL.md for setup instructions.
:done
pause
endlocal
