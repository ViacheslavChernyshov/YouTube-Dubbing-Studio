@echo off
chcp 65001 >nul 2>&1
title YouTube Dubbing Studio - Component Installation

echo =======================================================
echo Initial setup of YouTube Dubbing Studio
echo This will take a few minutes depending on your internet speed...
echo Please do not close this window!
echo =======================================================

cd /d "%~dp0"

powershell -ExecutionPolicy ByPass -NoProfile -File "%~dp0install.ps1"

if errorlevel 1 (
    echo [ERROR] Installation aborted with an error.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo Installation completed successfully! 
echo The application interface will now start...
echo =======================================================
timeout /t 3
