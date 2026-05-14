@echo off
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%setup_MindTask_db.py" %*
exit /b %ERRORLEVEL%
