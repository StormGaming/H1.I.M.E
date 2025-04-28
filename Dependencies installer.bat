@echo off
setlocal enabledelayedexpansion

REM Save the current script directory
set "CURDIR=%~dp0"
set "CURDIR=%CURDIR:~0,-1%"

REM Set up logging
set "LOGFILE=%CURDIR%\install_log.txt"
echo Installation log started at %DATE% %TIME% > "%LOGFILE%"
echo. >> "%LOGFILE%"

REM Check if running as administrator
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo This script requires administrator privileges. >> "%LOGFILE%"
    echo This script requires administrator privileges.
    echo Please run as Administrator.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed. >> "%LOGFILE%"
    echo Python is not installed.
    echo Downloading Python 3.9.6 installer...

    REM Download Python installer with retry logic
    set "URL=https://www.python.org/ftp/python/3.9.6/python-3.9.6-amd64.exe"
    set "RETRIES=3"
    set "SUCCESS=0"
    for /L %%i in (1,1,%RETRIES%) do (
        if !SUCCESS! EQU 0 (
            echo Attempt %%i of %RETRIES% to download Python installer... >> "%LOGFILE%"
            powershell -Command "(New-Object Net.WebClient).DownloadFile('%URL%', 'python-installer.exe')" && set "SUCCESS=1" || (
                echo Download attempt %%i failed. >> "%LOGFILE%"
            )
        )
    )
    if !SUCCESS! EQU 0 (
        echo Failed to download Python installer after %RETRIES% attempts. >> "%LOGFILE%"
        echo Failed to download Python installer.
        pause
        exit /b 1
    )

    REM Install Python silently
    echo Installing Python... >> "%LOGFILE%"
    echo Installing Python...
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 TargetDir="C:\Program Files\Python39" || (
        echo Failed to install Python. >> "%LOGFILE%"
        echo Failed to install Python.
        del python-installer.exe
        pause
        exit /b 1
    )

    REM Clean up
    del python-installer.exe
    echo Python installed successfully. >> "%LOGFILE%"
    echo Python installed successfully.

    REM Refresh environment variables
    set "PATH=%PATH%;C:\Program Files\Python39;C:\Program Files\Python39\Scripts"
) else (
    echo Python is already installed. >> "%LOGFILE%"
    echo Python is already installed.
)

REM Verify Python is accessible
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not accessible after installation. Please check the installation. >> "%LOGFILE%"
    echo Python is not accessible after installation. Please check the installation.
    pause
    exit /b 1
)
python --version >> "%LOGFILE%"

REM Upgrade pip and install wheel
echo Upgrading pip and installing wheel... >> "%LOGFILE%"
echo Upgrading pip and installing wheel...
python -m ensurepip --upgrade || (
    echo Failed to ensure pip is available. >> "%LOGFILE%"
    echo Failed to ensure pip is available.
    pause
    exit /b 1
)
python -m pip install --upgrade pip wheel || (
    echo Failed to upgrade pip or install wheel. >> "%LOGFILE%"
    echo Failed to upgrade pip or install wheel.
    pause
    exit /b 1
)

REM Install necessary Python packages
echo Installing Python packages... >> "%LOGFILE%"
echo Installing Python packages...
pip install numpy matplotlib pillow tk pyrtlsdr pywin32 || (
    echo Failed to install Python packages. >> "%LOGFILE%"
    echo Failed to install Python packages.
    pause
    exit /b 1
)
echo Python packages installed successfully. >> "%LOGFILE%"
echo Python packages installed successfully.

REM Set the librtlsdr directory path
set "LIBRTLSDR_DIR=%CURDIR%\lib\rtl-sdr-64bit"

REM Check if the librtlsdr directory exists
if exist "%LIBRTLSDR_DIR%" (
    echo Found lib\rtl-sdr-64bit directory. >> "%LOGFILE%"
    echo Found lib\rtl-sdr-64bit directory.

    REM Copy DLLs to C:\Windows\System32
    echo Copying RTL-SDR DLLs to C:\Windows\System32... >> "%LOGFILE%"
    echo Copying RTL-SDR DLLs to C:\Windows\System32...
    copy "%LIBRTLSDR_DIR%\*.dll" "C:\Windows\System32" >nul || (
        echo Failed to copy RTL-SDR DLLs to C:\Windows\System32. >> "%LOGFILE%"
        echo Failed to copy RTL-SDR DLLs to C:\Windows\System32.
        pause