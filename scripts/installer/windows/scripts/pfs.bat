@REM @echo off
@REM setlocal
@REM
@REM set MAIN_EXE=%~dp0.\pfcli.exe
@REM "%MAIN_EXE%" pfs %*

@echo off
setlocal

set MAIN_EXE=%~dp0.\pfcli.exe

REM Check if the first argument is 'start'
if "%~1"=="start" (
    cscript start_pfs.vbs """%MAIN_EXE%"" pfs %*"
    )
) else (
    "%MAIN_EXE%" pfs %*
)