@echo off
REM ==========================================================================
REM  Batch Builder - build the .exe
REM
REM  Run setup.bat first. Produces build\dist\BatchBuilder\ - copy that whole
REM  folder to wherever analysts will run it from.
REM ==========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build\build.ps1"
echo.
pause
