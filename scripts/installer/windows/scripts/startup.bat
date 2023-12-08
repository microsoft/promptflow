@echo off
setlocal

PowerShell.exe -WindowStyle hidden Start-Process -FilePath %~dp0.\pfs.bat -NoNewWindow -Wait