@echo off
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%..\MindTask_cli.py" %*
exit /b %ERRORLEVEL%
