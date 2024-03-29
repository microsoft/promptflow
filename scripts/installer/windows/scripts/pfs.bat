@echo off
setlocal

set MAIN_EXE=%~dp0.\pfcli.exe
REM Check if the first argument is 'start'
if "%~1"=="start" (
    cscript //nologo %~dp0.\start_pfs.vbs """%MAIN_EXE%"" pfs %*"
@REM since we won't wait for vbs to finish, we need to wait for the output file to be flushed to disk
    timeout /t 5 >nul
    type "%~dp0output.txt"
) else (
    "%MAIN_EXE%" pfs %*
)