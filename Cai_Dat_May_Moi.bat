@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
title Drama Nhat Studio - Cai Dat Tu Dong Cho May Moi (1-Click Setup)

echo ================================================================================
echo        DRAMA NHAT STUDIO - TRINH CAI DAT TU DONG CHO MAY MOI [A -^> Z]
echo ================================================================================
echo.

if not exist "%~dp0main.py" (
    echo [LOI] Khong tim thay file he thong main.py!
    echo -^> Ban dang chay truc tiep ben trong file nen .ZIP chua giai nen.
    echo -^> Vui long GIAI NEN [Extract] toan bo thu muc ra o dia D:\ hoac C:\ roi chay lai!
    echo.
    pause
    exit /b 1
)

echo [BUOC 1/4] Dang kiem tra Python tren may tinh...
set "PYTHON_EXE="

if exist "%~dp0python_path.txt" (
    set /p SAVED_PY=<"%~dp0python_path.txt"
    if exist "!SAVED_PY!" set "PYTHON_EXE=!SAVED_PY!"
)
if defined PYTHON_EXE goto :VERIFY_PYTHON

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if defined PYTHON_EXE goto :VERIFY_PYTHON

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PYTHON_EXE goto :VERIFY_PYTHON

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if defined PYTHON_EXE goto :VERIFY_PYTHON

if exist "C:\Program Files\Python311\python.exe" set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
if defined PYTHON_EXE goto :VERIFY_PYTHON

if exist "C:\Program Files\Python312\python.exe" set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
if defined PYTHON_EXE goto :VERIFY_PYTHON

if exist "C:\Program Files\Python310\python.exe" set "PYTHON_EXE=C:\Program Files\Python310\python.exe"
if defined PYTHON_EXE goto :VERIFY_PYTHON

if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"
if defined PYTHON_EXE goto :VERIFY_PYTHON

for /f "delims=" %%P in ('where python 2^>nul') do (
    echo "%%P" | find /i "WindowsApps" >nul
    if errorlevel 1 (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)

:VERIFY_PYTHON
if not defined PYTHON_EXE goto :INSTALL_PYTHON
"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    set "PYTHON_EXE="
    goto :INSTALL_PYTHON
)
goto :PYTHON_READY

:INSTALL_PYTHON
echo [!] May tinh chua co Python 3.11. Dang tu dong tai bo cai Python 3.11.9 chinh thuc...
set "PY_INSTALLER=%TEMP%\python_3119_amd64.exe"
if exist "%PY_INSTALLER%" del /f /q "%PY_INSTALLER%" >nul 2>&1

if exist "%SystemRoot%\System32\curl.exe" (
    "%SystemRoot%\System32\curl.exe" -L --retry 3 --connect-timeout 20 -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
)

if not exist "%PY_INSTALLER%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%PY_INSTALLER%'"
)

if not exist "%PY_INSTALLER%" (
    echo [LOI] Khong the tai Python tu dong. Vui long kiem tra ket noi Internet!
    pause
    exit /b 1
)

echo [+] Dang tu dong cai dat Python 3.11.9... Vui long doi thanh tien trinh chay xong...
"%PY_INSTALLER%" /passive InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1 TargetDir="%LOCALAPPDATA%\Programs\Python\Python311"
del /f /q "%PY_INSTALLER%" >nul 2>&1

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    if exist "C:\Program Files\Python311\python.exe" set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
)

if not defined PYTHON_EXE (
    echo [LOI] Cai dat Python chua hoan tat. Vui long chay lai file Cai_Dat_May_Moi.bat!
    pause
    exit /b 1
)

:PYTHON_READY
for %%D in ("%PYTHON_EXE%") do set "PY_DIR=%%~dpD"
set "PATH=%PY_DIR%;%PY_DIR%Scripts;%~dp0bin;%PATH%"

echo [OK] Da tim thay Python tai: "%PYTHON_EXE%"
"%PYTHON_EXE%" --version
echo.

:: Chay trinh cai dat thu vien va Model AI tu dong bang Python
"%PYTHON_EXE%" "%~dp0install_setup.py"
if errorlevel 1 (
    echo.
    echo [CANH BAO] Co loi xay ra trong qua trinh tai thu vien. Vui long kiem tra mang va thu lai!
    pause
    exit /b 1
)

echo.
if exist "%~dp0Drama_Nhat_Studio.exe" (
    start "" "%~dp0Drama_Nhat_Studio.exe"
)
pause
