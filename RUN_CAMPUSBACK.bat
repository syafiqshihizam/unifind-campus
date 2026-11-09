@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  set "PYCMD=python"
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set "PYCMD=py"
  ) else (
    echo Python was not found. Install Python 3 first.
    pause
    exit /b 1
  )
)
if not exist "data\campusback.db" (
  echo Preparing demo data for your first run...
  %PYCMD% seed_demo.py
)
echo.
echo CampusBack: open http://localhost:8000 in your browser
%PYCMD% server.py
pause
