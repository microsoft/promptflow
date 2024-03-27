@echo off
setlocal

SET PF_INSTALLER=PIP

IF EXIST "%~dp0\python.exe" (
  "%~dp0\python.exe" -m promptflow._cli._pf.entry %*
) ELSE (
  python -m promptflow._cli._pf.entry %*
)
