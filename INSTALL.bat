@echo off
setlocal
title British Voice - Installer
cd /d "%~dp0"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol='Tls12';"
echo ================================================
echo   British Voice - one-click installer
echo   Please wait, this takes 5-10 minutes...
echo ================================================
echo.

rem ---------- 1. Python 3.11 (the app's own copy) ----------
set "PY="
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%ProgramFiles%\Python311\python.exe" set "PY=%ProgramFiles%\Python311\python.exe"
if defined PY goto have_python
echo [1/4] Downloading Python 3.11...
%PS% "Invoke-WebRequest https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile '%TEMP%\python-setup.exe'"
echo [1/4] Installing Python 3.11...
"%TEMP%\python-setup.exe" /quiet InstallAllUsers=0 PrependPath=0 Include_tcltk=1 Include_test=0 Include_launcher=0
set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not exist "%PY%" (
  echo.
  echo Python install failed. Check your internet and run INSTALL.bat again.
  pause
  exit /b 1
)
:have_python
echo [1/4] Python OK.

rem ---------- 2. App libraries ----------
echo [2/4] Installing British Voice (this is the slow part)...
if not exist ".venv\Scripts\python.exe" "%PY%" -m venv .venv
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Check your internet and run INSTALL.bat again.
  pause
  exit /b 1
)

rem ---------- 3. Desktop shortcut ----------
echo [3/4] Creating "British Voice" shortcut on your Desktop...
%PS% "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\British Voice.lnk'); $s.TargetPath='%~dp0.venv\Scripts\pythonw.exe'; $s.Arguments='\"%~dp0app.py\"'; $s.WorkingDirectory='%~dp0'; $s.Save()"

rem ---------- 4. Virtual microphone (VB-Cable) ----------
%PS% "if (Get-PnpDevice -FriendlyName '*VB-Audio Virtual Cable*' -ErrorAction SilentlyContinue) {exit 0} else {exit 1}"
if not errorlevel 1 (
  echo [4/4] Virtual microphone already installed.
  goto done
)
echo [4/4] Downloading the free virtual microphone (VB-Cable)...
%PS% "try { Invoke-WebRequest https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip -OutFile '%TEMP%\vbcable.zip'; Expand-Archive -Force '%TEMP%\vbcable.zip' '%TEMP%\vbcable' } catch {}"
if not exist "%TEMP%\vbcable\VBCABLE_Setup_x64.exe" (
  echo.
  echo   Could not download it automatically. The website will open now:
  echo   Download, unzip, right-click VBCABLE_Setup_x64.exe,
  echo   "Run as administrator", then click "Install Driver".
  start https://vb-audio.com/Cable/
  set NEED_RESTART=1
  goto done
)
echo.
echo   A window will open: click YES, then click "Install Driver".
echo.
%PS% "Start-Process '%TEMP%\vbcable\VBCABLE_Setup_x64.exe' -Verb RunAs -Wait"
set NEED_RESTART=1

:done
echo.
echo ================================================
echo   ALL DONE!
if defined NEED_RESTART echo   - RESTART your PC now.
echo   - Then open "British Voice" from your Desktop.
echo ================================================
pause
