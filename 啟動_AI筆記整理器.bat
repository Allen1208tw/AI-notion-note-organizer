@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if exist ".venv\Scripts\python.exe" goto use_venv
where py > nul 2>&1
if not errorlevel 1 goto use_py
goto use_python

:use_venv
".venv\Scripts\python.exe" launcher.py %*
goto finished

:use_py
py -3 launcher.py %*
goto finished

:use_python
python launcher.py %*

:finished
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" goto end

echo.
echo 啟動失敗。請查看上方訊息，修正後再重新開啟。
pause

:end
endlocal & exit /b %EXIT_CODE%
