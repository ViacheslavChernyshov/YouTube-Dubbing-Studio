@echo off
chcp 65001 >nul 2>&1
title YouTube Dubbing Studio

:: Change directory to the root of the project
cd /d "%~dp0.."

set "PYTHON_EXE=%~dp0python\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Portable Python not found. Please run Start.vbs so it can install things.
    pause
    exit /b 1
)

:: Add FFmpeg shared DLLs to PATH
set "LOCAL_FFMPEG_SHARED=%~dp0..\data\tools\ffmpeg\bin"
if exist "%LOCAL_FFMPEG_SHARED%\ffmpeg.exe" (
    set "PATH=%LOCAL_FFMPEG_SHARED%;%PATH%"
)

:: Launch the app from system dir
"%PYTHON_EXE%" "%~dp0main.py"

:: If crashed, keep window open
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with error code %errorlevel%
    pause
)
