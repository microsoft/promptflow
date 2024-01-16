@echo off
setlocal

SET PF_INSTALLER=MSI
set MAIN_EXE=%~dp0.\pfcli.exe
"%MAIN_EXE%" pf %*