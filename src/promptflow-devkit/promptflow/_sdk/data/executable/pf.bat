@echo off
setlocal


set MAIN_EXE=%~dp0.\app.exe
REM Check if the first argument is 'start'
if "%~1"=="service" (
    REM Check if the second argument is 'start'
    if "%~2"=="start" (
        cscript //nologo %~dp0.\start_pfs.vbs """%MAIN_EXE%"" pf %*"
    ) else (
        "%MAIN_EXE%" pf %*
    )
) else (
    "%MAIN_EXE%" pf %*
)
