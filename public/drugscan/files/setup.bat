@echo off
REM ==========================================================================
REM  Batch Builder - setup (double-click me first)
REM
REM  This is a thin wrapper around setup.ps1. It exists because managed Windows
REM  machines often refuse to run unsigned PowerShell scripts by default;
REM  -ExecutionPolicy Bypass allows this one command through without changing
REM  any machine setting.
REM ==========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
echo.
pause
