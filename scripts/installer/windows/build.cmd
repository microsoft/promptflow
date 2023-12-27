@echo off
SetLocal EnableDelayedExpansion

REM Double colon :: should not be used in parentheses blocks, so we use REM.
REM See https://stackoverflow.com/a/12407934/2199657
echo The promptflow version argument is: %1
set promptflow_version=%1
echo build a msi installer using local/remote cli sources and python executables. You need to have curl.exe, unzip.exe and msbuild.exe available under PATH
echo.

@REM set "PATH=%PATH%;%ProgramFiles%\Git\bin;%ProgramFiles%\Git\usr\bin;C:\Program Files (x86)\Git\bin;C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin"
@REM set "PATH=%PATH%;%ProgramFiles%\Git\bin;%ProgramFiles%\Git\usr\bin;C:\Program Files (x86)\Git\bin"

set PYTHON_VERSION=3.11.5
set PYTHON_ARCH=amd64

set WIX_DOWNLOAD_URL="https://azurecliprod.blob.core.windows.net/msi/wix310-binaries-mirror.zip"
set PYTHON_DOWNLOAD_URL="https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-%PYTHON_ARCH%.zip"

REM https://pip.pypa.io/en/stable/installation/#get-pip-py
set GET_PIP_DOWNLOAD_URL="https://bootstrap.pypa.io/get-pip.py"

REM Set up the output directory and temp. directories
echo Cleaning previous build artifacts...
set OUTPUT_DIR=%~dp0.\out
if exist %OUTPUT_DIR% rmdir /s /q %OUTPUT_DIR%
mkdir %OUTPUT_DIR%

set ARTIFACTS_DIR=%~dp0.\artifacts
mkdir %ARTIFACTS_DIR%
@REM set TEMP_SCRATCH_FOLDER=%ARTIFACTS_DIR%\cli_scratch
set BUILDING_DIR=%ARTIFACTS_DIR%\cli
set WIX_DIR=%ARTIFACTS_DIR%\wix
set PYTHON_DIR=%ARTIFACTS_DIR%\Python

REM Get the absolute directory since we pushd into different levels of subdirectories.
PUSHD %~dp0..\..\..\
SET REPO_ROOT=%CD%
POPD

REM reset working folders
if exist %BUILDING_DIR% rmdir /s /q %BUILDING_DIR%
REM rmdir always returns 0, so check folder's existence
if exist %BUILDING_DIR% (
    echo Failed to delete %BUILDING_DIR%.
    goto ERROR
)
mkdir %BUILDING_DIR%

REM ensure wix is available
if exist %WIX_DIR% (
    echo Using existing Wix at %WIX_DIR%
)
if not exist %WIX_DIR% (
    mkdir %WIX_DIR%
    pushd %WIX_DIR%
    echo Downloading Wix.
    curl --output wix-archive.zip %WIX_DOWNLOAD_URL%
    unzip wix-archive.zip
    if %errorlevel% neq 0 goto ERROR
    del wix-archive.zip
    echo Wix downloaded and extracted successfully.
    popd
)

REM ensure Python is available
if exist %PYTHON_DIR% (
    echo Using existing Python at %PYTHON_DIR%
)
if not exist %PYTHON_DIR% (
    echo Setting up Python and pip
    mkdir %PYTHON_DIR%
    pushd %PYTHON_DIR%

    echo Downloading Python
    curl --output python-archive.zip %PYTHON_DOWNLOAD_URL%
    unzip python-archive.zip
    if %errorlevel% neq 0 goto ERROR
    del python-archive.zip
    echo Python downloaded and extracted successfully

    REM Delete _pth file so that Lib\site-packages is included in sys.path
    REM https://github.com/pypa/pip/issues/4207#issuecomment-297396913
    REM https://docs.python.org/3.10/using/windows.html#finding-modules
    del python*._pth

    echo Installing pip
    curl --output get-pip.py %GET_PIP_DOWNLOAD_URL%
    %PYTHON_DIR%\python.exe get-pip.py
    del get-pip.py
    echo Pip set up successful

    dir .
    popd
)
set PYTHON_EXE=%PYTHON_DIR%\python.exe

robocopy %PYTHON_DIR% %BUILDING_DIR% /s /NFL /NDL

%BUILDING_DIR%\python.exe -m pip uninstall -y promptflow promptflow-sdk promptflow-tools

if %promptflow_version% == "" (
    echo Building promptflow from local sources...
    set PROMPTFLOW_CLI_SRC=%REPO_ROOT%\src\promptflow
    pushd %PROMPTFLOW_CLI_SRC%
    set PIP_DEBUG=true
    %BUILDING_DIR%\python.exe -m pip install --no-warn-script-location --requirement .\dev_requirements.txt
    echo pip list Before
    %BUILDING_DIR%\python.exe -m pip list
    %BUILDING_DIR%\python.exe .\setup.py bdist_wheel

    for /f %%i in ('dir /b .\dist\*.whl') do (
        echo Processing file: %%i
        set PACKAGE=./dist/%%i[azure,executable,pfs,azureml-serving]
        echo %PACKAGE%
    )

    %BUILDING_DIR%\python.exe -m pip install !PACKAGE!
    echo pip freeze After
    %BUILDING_DIR%\python.exe -m  pip freeze
    popd

    set PROMPTFLOW_TOOL_CLI_SRC=%REPO_ROOT%\src\promptflow-tools
    pushd %PROMPTFLOW_TOOL_CLI_SRC%
    set PIP_DEBUG=true
    %BUILDING_DIR%\python.exe .\setup.py bdist_wheel
    for /f %%i in ('dir /b .\dist\*.whl') do (
        echo Processing file: %%i
        set PACKAGE=./dist/%%i
        echo %PACKAGE%
    )
    %BUILDING_DIR%\python.exe -m pip install !PACKAGE!
    echo pip freeze After
    pip freeze
    popd
) else (
    echo Building promptflow from PyPI...
    %BUILDING_DIR%\python.exe -m pip install --no-warn-script-location --no-cache-dir promptflow[azure,executable,pfs,azureml-serving]==%promptflow_version%
    %BUILDING_DIR%\python.exe -m pip install --no-warn-script-location --no-cache-dir promptflow-tools
)


REM Check pf can be executed. This also prints the Python version.
pushd %BUILDING_DIR%\Scripts
pf --version
if %errorlevel% neq 0 goto ERROR
popd

pushd %BUILDING_DIR%
@REM %BUILDING_DIR%\python.exe %~dp0\compact_aaz.py
%BUILDING_DIR%\python.exe %~dp0\patch_models_v2.py
@REM %BUILDING_DIR%\python.exe %~dp0\trim_sdk.py
popd

REM Remove pywin32 help file to reduce size.
del %BUILDING_DIR%\Lib\site-packages\PyWin32.chm

@REM echo Creating the wbin (Windows binaries) folder that will be added to the path...
@REM mkdir %BUILDING_DIR%\wbin
copy %BUILDING_DIR%\Scripts\pf.exe %BUILDING_DIR%\
copy %BUILDING_DIR%\Scripts\pfazure.exe %BUILDING_DIR%
copy %BUILDING_DIR%\Scripts\pfs.exe %BUILDING_DIR%
if %errorlevel% neq 0 goto ERROR
copy %REPO_ROOT%\scripts\installer\windows\resources\CLI_LICENSE.rtf %BUILDING_DIR%
copy %REPO_ROOT%\src\promptflow\NOTICE.txt %BUILDING_DIR%

REM Remove .py and only deploy .pyc files
pushd %BUILDING_DIR%\Lib\site-packages
for /f %%f in ('dir /b /s *.pyc') do (
    set PARENT_DIR=%%~df%%~pf..
    echo !PARENT_DIR! | findstr /C:\Lib\site-packages\pip\ 1>nul
    if !errorlevel! neq  0 (
        echo !PARENT_DIR! | findstr /C:\Lib\site-packages\promptflow\ 1>nul
        if !errorlevel! neq  0 (
            REM Only take the file name without 'pyc' extension: e.g., (same below) __init__.cpython-310
            set FILENAME=%%~nf
            REM Truncate the '.cpython-310' postfix which is 12 chars long: __init__
            REM https://stackoverflow.com/a/636391/2199657
            set BASE_FILENAME=!FILENAME:~0,-12!
            REM __init__.pyc
            set pyc=!BASE_FILENAME!.pyc
            REM Delete ..\__init__.py
            del !PARENT_DIR!\!BASE_FILENAME!.py
            REM Copy to ..\__init__.pyc
            copy %%~f !PARENT_DIR!\!pyc! >nul
            REM Delete __init__.pyc
            del %%~f
        ) ELSE (
            echo --SKIP !PARENT_DIR! under promptflow
        )
    ) ELSE (
        echo --SKIP !PARENT_DIR! under pip
    )
)
popd

REM Remove __pycache__
echo remove pycache
for /d /r %BUILDING_DIR%\Lib\site-packages\ %%d in (__pycache__) do (
    if exist %%d rmdir /s /q "%%d"
)

REM Remove dist-info
echo remove dist-info
pushd %BUILDING_DIR%\Lib\site-packages
for /d %%d in ("azure*.dist-info") do (
    if exist %%d rmdir /s /q "%%d"
)
if %errorlevel% neq 0 goto ERROR
popd

echo %OUTPUT_DIR%

goto END

:ERROR
echo Error occurred, please check the output for details.
exit /b 1

:END
exit /b 0
popd
