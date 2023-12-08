@echo off
setlocal

set MAIN_EXE=%~dp0.\pfcli.exe
start /B "" "%MAIN_EXE%" pfs %*