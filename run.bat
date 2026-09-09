@echo off
REM ForgeMind one-cmd wrapper - bypasses ExecutionPolicy for double-click
powershell -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
pause
