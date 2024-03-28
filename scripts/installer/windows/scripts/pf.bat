@echo off
setlocal

SET PF_INSTALLER=MSI
set MAIN_EXE=%~dp0.\pfcli.exe
REM Check if the first argument is 'start'
if "%~1"=="service" (
    REM Check if the second argument is 'start'
    if "%~2"=="start" (
        cscript //nologo %~dp0.\start_pfs.vbs """%MAIN_EXE%"" pf %*"
        REM since we won't wait for vbs to finish, we need to wait for the output file to be flushed to disk
        timeout /t 5 >nul
        type "%~dp0output.txt"
    ) else (
        "%MAIN_EXE%" pf %*
    )
) else (
    "%MAIN_EXE%" pf %*
)