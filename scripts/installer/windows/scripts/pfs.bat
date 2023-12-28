@echo off
setlocal

IF EXIST "%~dp0\python.exe" (
  "%~dp0\python.exe" -m promptflow._sdk._service.entry %*
) ELSE (
  echo Failed to load python executable.
  exit /b 1
)