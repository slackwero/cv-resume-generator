@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
rem Keep a failed start's message on screen after a double-click.
rem GitHub Actions sets CI, and a pause would hang the job.
if errorlevel 1 if not defined CI pause
