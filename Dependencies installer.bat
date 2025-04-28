@echo off
setlocal enabledelayedexpansion

REM Save the current script directory
set "CURDIR=%~dp0"
set "CURDIR=%CURDIR:~0,-1%"

REM Check if running as administrator
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo This script requires administrator privileges.
    echo Please run as Administrator.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed.
    echo Downloading Python 3.9.6 installer...

    REM Download Python installer (64-bit)
    powershell -Command "(New-Object Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.9.6/python-3.9.6-amd64.exe', 'python-installer.exe')" || (
        echo Failed to download Python installer.
        pause
        exit /b 1
    )

    REM Install Python silently
    echo Installing Python...
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 TargetDir="C:\Program Files\Python39" || (
        echo Failed to install Python.
        del python-installer.exe
        pause
        exit /b 1
    )

    REM Clean up
    del python-installer.exe

    REM Refresh environment variables
    set "PATH=%PATH%;C:\Program Files\Python39;C:\Program Files\Python39\Scripts"
    echo Python installed successfully.
) else (
    echo Python is already installed.
)

REM Verify Python is accessible
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not accessible after installation. Please check the installation.
    pause
    exit /b 1
)

REM Upgrade pip and install wheel
echo Upgrading pip and installing wheel...
python -m ensurepip --upgrade || (
    echo Failed to ensure pip is available.
    pause
    exit /b 1
)
python -m pip install --upgrade pip wheel || (
    echo Failed to upgrade pip or install wheel.
    pause
    exit /b 1
)

REM Install necessary Python packages
echo Installing Python packages...
pip install numpy matplotlib pillow tk pyrtlsdr pywin32 || (
    echo Failed to install Python packages.
    pause
    exit /b 1
)
echo Python packages installed successfully.

REM Set the librtlsdr directory path (relative to script location)
set "LIBRTLSDR_DIR=%CURDIR%\lib\rtl-sdr-64bit"

REM Check if the librtlsdr directory exists
if exist "%LIBRTLSDR_DIR%" (
    echo Found lib\rtl-sdr-64bit directory.

    REM Copy DLLs to C:\Windows\System32 for pyrtlsdr compatibility
    echo Copying RTL-SDR DLLs to C:\Windows\System32...
    copy "%LIBRTLSDR_DIR%\*.dll" "C:\Windows\System32" >nul || (
        echo Failed to copy RTL-SDR DLLs to C:\Windows\System32.
        pause
        exit /b 1
    )
    echo RTL-SDR DLLs copied successfully.
) else (
    echo WARNING: lib\rtl-sdr-64bit directory not found at %LIBRTLSDR_DIR%.
    echo Please ensure the directory exists with the required DLLs (librtlsdr.dll, libusb-1.0.dll).
    pause
    exit /b 1
)

echo Installation completed successfully.
pause
exit /b 0