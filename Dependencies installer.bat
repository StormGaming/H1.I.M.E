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

REM Set the librtlsdr source and target directory paths
set "LIBRTLSDR_SRC=%CURDIR%\lib\rtl-sdr-64bit"
set "LIBRTLSDR_DEST=C:\Program Files\librtlsdr"
set "PYTHON_SCRIPTS=C:\Program Files\Python39\Scripts"

REM Check if the source librtlsdr directory exists
if exist "%LIBRTLSDR_SRC%" (
    echo Found lib\rtl-sdr-64bit directory at %LIBRTLSDR_SRC%. >> "%LOGFILE%"
    echo Found lib\rtl-sdr-64bit directory.

    REM Verify required DLLs exist
    set "DLLS=librtlsdr.dll libusb-1.0.dll"
    set "MISSING_DLLS="
    for %%d in (%DLLS%) do (
        if not exist "%LIBRTLSDR_SRC%\%%d" (
            set "MISSING_DLLS=!MISSING_DLLS! %%d"
        )
    )
    if not "!MISSING_DLLS!"=="" (
        echo Missing required DLLs in %LIBRTLSDR_SRC%:%MISSING_DLLS%. >> "%LOGFILE%"
        echo Missing required DLLs:%MISSING_DLLS%.
        echo Please ensure librtlsdr.dll and libusb-1.0.dll are in lib\rtl-sdr-64bit.
        pause
        exit /b 1
    )

    REM Create and copy DLLs to C:\Program Files\librtlsdr
    echo Creating and copying RTL-SDR DLLs to %LIBRTLSDR_DEST%... >> "%LOGFILE%"
    echo Creating and copying RTL-SDR DLLs to %LIBRTLSDR_DEST%...
    if not exist "%LIBRTLSDR_DEST%" mkdir "%LIBRTLSDR_DEST%" || (
        echo Failed to create %LIBRTLSDR_DEST%. >> "%LOGFILE%"
        echo Failed to create %LIBRTLSDR_DEST%.
        pause
        exit /b 1
    )
    copy "%LIBRTLSDR_SRC%\*.dll" "%LIBRTLSDR_DEST%" >nul || (
        echo Failed to copy RTL-SDR DLLs to %LIBRTLSDR_DEST%. >> "%LOGFILE%"
        echo Failed to copy RTL-SDR DLLs to %LIBRTLSDR_DEST%.
        pause
        exit /b 1
    )

    REM Copy DLLs to C:\Windows\System32 as a fallback
    echo Copying RTL-SDR DLLs to C:\Windows\System32... >> "%LOGFILE%"
    echo Copying RTL-SDR DLLs to C:\Windows\System32...
    copy "%LIBRTLSDR_SRC%\*.dll" "C:\Windows\System32" >nul || (
        echo Failed to copy RTL-SDR DLLs to C:\Windows\System32. >> "%LOGFILE%"
        echo Failed to copy RTL-SDR DLLs to C:\Windows\System32.
        pause
        exit /b 1
    )

    REM Copy DLLs to Python Scripts folder as a fallback
    if exist "%PYTHON_SCRIPTS%" (
        echo Copying RTL-SDR DLLs to %PYTHON_SCRIPTS%... >> "%LOGFILE%"
        echo Copying RTL-SDR DLLs to Python Scripts folder...
        copy "%LIBRTLSDR_SRC%\*.dll" "%PYTHON_SCRIPTS%" >nul || (
            echo Failed to copy RTL-SDR DLLs to %PYTHON_SCRIPTS%. >> "%LOGFILE%"
            echo Failed to copy RTL-SDR DLLs to Python Scripts folder.
            pause
            exit /b 1
        )
    ) else (
        echo WARNING: Python Scripts folder %PYTHON_SCRIPTS% not found. Skipping copy. >> "%LOGFILE%"
        echo WARNING: Python Scripts folder not found.
    )

    REM Add C:\Program Files\librtlsdr to system PATH
    echo Checking system PATH for %LIBRTLSDR_DEST%... >> "%LOGFILE%"
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "currentPath=%%B"
    echo !currentPath! | find /I "%LIBRTLSDR_DEST%" >nul
    if %ERRORLEVEL% NEQ 0 (
        echo Adding %LIBRTLSDR_DEST% to system PATH... >> "%LOGFILE%"
        echo Adding %LIBRTLSDR_DEST% to system PATH...
        setx /M PATH "!currentPath!;%LIBRTLSDR_DEST%" || (
            echo Failed to update system PATH with %LIBRTLSDR_DEST%. >> "%LOGFILE%"
            echo Failed to update system PATH.
            pause
            exit /b 1
        )
    ) else (
        echo %LIBRTLSDR_DEST% already in system PATH. >> "%LOGFILE%"
        echo %LIBRTLSDR_DEST% already in system PATH.
    )

    echo RTL-SDR DLLs setup completed. >> "%LOGFILE%"
    echo RTL-SDR DLLs setup completed.
) else (
    echo ERROR: lib\rtl-sdr-64bit directory not found at %LIBRTLSDR_SRC%. >> "%LOGFILE%"
    echo ERROR: lib\rtl-sdr-64bit directory not found.
    echo Please ensure the directory exists with librtlsdr.dll and libusb-1.0.dll.
    pause
    exit /b 1
)

echo. >> "%LOGFILE%"
echo Installation completed successfully. >> "%LOGFILE%"
echo Installation completed successfully.
echo If the program still fails with 'failed to import librtlsdr', try:
echo 1. Copying %LIBRTLSDR_SRC%\*.dll to the same folder as H1IME.py.
echo 2. Rebooting your system to refresh the PATH.
echo 3. Verifying %LIBRTLSDR_DEST% and C:\Windows\System32 contain librtlsdr.dll and libusb-1.0.dll.
echo 4. Running 'python -c "from rtlsdr import RtlSdr"' to test pyrtlsdr.
pause
exit /b 0