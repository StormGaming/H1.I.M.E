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
    echo Checking for Python 3.11.9 installer in lib\python...

    REM Check for Python installer in lib\python
    set "INSTALLER_PATH=%CURDIR%\lib\python\python-3.11.9-amd64.exe"
    if not exist "!INSTALLER_PATH!" (
        echo Python 3.11.9 installer not found at !INSTALLER_PATH!. >> "%LOGFILE%"
        echo Python 3.11.9 installer not found in lib\python.
        echo Please place python-3.11.9-amd64.exe in the lib\python folder.
        echo Download it from: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
        pause
        exit /b 1
    )
    echo Found Python 3.11.9 installer at !INSTALLER_PATH!. >> "%LOGFILE%"
    echo Found Python 3.11.9 installer.

    REM Install Python silently with detailed logging
    echo Installing Python... >> "%LOGFILE%"
    echo Installing Python...
    start /wait "" "!INSTALLER_PATH!" /quiet InstallAllUsers=1 PrependPath=1 TargetDir="C:\Program Files\Python311" > "%LOGFILE%.python_install.log" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo Failed to install Python. Check %LOGFILE%.python_install.log for details. >> "%LOGFILE%"
        echo Failed to install Python. Check the log file for details.
        echo Installer path: !INSTALLER_PATH!
        echo Please ensure the installer is valid and not corrupted.
        echo Download a fresh copy from: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
        pause
        exit /b 1
    )

    REM Refresh environment variables for the current session
    echo Refreshing environment variables... >> "%LOGFILE%"
    echo Refreshing environment variables...
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "PATH=%%B"
    set "PATH=%PATH%;C:\Program Files\Python311;C:\Program Files\Python311\Scripts"
    setx PATH "%PATH%" >nul 2>&1

    REM Brief delay to ensure installer completion
    ping 127.0.0.1 -n 3 >nul

    REM No cleanup needed since we're not downloading
    echo Python installed successfully. >> "%LOGFILE%"
    echo Python installed successfully.
) else (
    echo Python is already installed. >> "%LOGFILE%"
    echo Python is already installed.
)

REM Verify Python is accessible
echo Verifying Python installation... >> "%LOGFILE%"
if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" --version >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo Python is installed but not accessible. Please check the installation. >> "%LOGFILE%"
        echo Python is installed but not accessible. Please check the installation.
        pause
        exit /b 1
    )
    echo Python is accessible at C:\Program Files\Python311\python.exe. >> "%LOGFILE%"
) else (
    echo Python executable not found at C:\Program Files\Python311\python.exe. >> "%LOGFILE%"
    echo Python executable not found. Please check the installation.
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
set "PYTHON_SCRIPTS=C:\Program Files\Python311\Scripts"

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
pause
exit /b 0