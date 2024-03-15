@echo off
setlocal

set MAIN_EXE=%~dp0.\pfcli.exe
REM Check if the first argument is 'start'
if "%~1"=="start" (
    cscript %~dp0.\start_pfs.vbs """%MAIN_EXE%"" pfs %*"
    )
) else (
    "%MAIN_EXE%" pfs %*
)