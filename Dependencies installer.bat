@echo off
setlocal enabledelayedexpansion

REM Save the current script directory
set "CURDIR=%~dp0"
set "CURDIR=%CURDIR:~0,-1%" 

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed.
    echo Downloading and installing Python...

    REM Download the Python installer (64-bit)
    powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.9.6/python-3.9.6-amd64.exe -OutFile python-installer.exe"

    REM Install Python silently
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1

    REM Clean up
    del python-installer.exe

    REM Refresh environment variables
    set "PATH=%PATH%;C:\Program Files\Python39\Scripts;C:\Program Files\Python39"
)

REM Upgrade pip
python -m ensurepip
python -m pip install --upgrade pip

REM Install necessary Python packages
pip install numpy matplotlib pillow tk pyrtlsdr pywin32

REM Set the librtlsdr directory path (relative to script location)
set "LIBRTLSDR_DIR=%CURDIR%\lib\rtl-sdr-64bit"

REM Check if that directory exists
if exist "%LIBRTLSDR_DIR%" (
    echo Found lib\rtl-sdr-64bit directory.

    REM Fetch current system PATH
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "currentPath=%%B"

    REM Check if the path is already included
    echo !currentPath! | find /I "%LIBRTLSDR_DIR%" >nul
    if %ERRORLEVEL% NEQ 0 (
        echo Adding lib\rtl-sdr-64bit directory to system PATH...
        setx /M PATH "!currentPath!;%LIBRTLSDR_DIR%"
    ) else (
        echo lib\rtl-sdr-64bit path already exists in system PATH.
    )
) else (
    echo WARNING: lib\rtl-sdr-64bit directory not found. Skipping PATH update.
)

echo Installation complete.
pause
