@echo off
setlocal

REM Remove __pycache__
echo The promptflow installation folder: %1
set promptflow_folder=%1

echo remove pycache
for /d /r %promptflow_folder%\Lib\site-packages\ %%d in (__pycache__) do (
    if exist %%d rmdir /s /q "%%d"
)