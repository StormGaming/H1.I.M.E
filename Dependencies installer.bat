@echo off
setlocal

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

REM Install necessary packages
pip install numpy matplotlib pillow tk pyrtlsdr pywin32

echo Installation complete.
pause