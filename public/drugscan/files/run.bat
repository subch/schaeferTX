@echo off
REM ==========================================================================
REM  Batch Builder - run from source, without building an .exe
REM
REM  Useful for testing on the lab network before you package anything. Opens
REM  your browser automatically. Close this window to stop the application.
REM ==========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
echo.
pause
