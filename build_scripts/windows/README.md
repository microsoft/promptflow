Building the Windows MSI Installer
========================

This document provides instructions on creating the MSI installer.

Prerequisites
-------------

1. Turn on the '.NET Framework 3.5' Windows Feature (required for WIX Toolset).
2. Install 'Microsoft Build Tools 2015'.
    https://www.microsoft.com/download/details.aspx?id=48159
3. You need to have curl.exe, unzip.exe and msbuild.exe available under PATH.
4. Install 'WIX Toolset build tools' following the instructions below.
   - Enter the directory where the README is located (`cd build_scripts/windows`), `mkdir wix` and `cd wix`.
   - `curl --output wix-archive.zip  https://azurecliprod.blob.core.windows.net/msi/wix310-binaries-mirror.zip`
   - `unzip wix-archive.zip` and `del wix-archive.zip`
5. We recommend creating a clean virtual Python environment and installing all dependencies using src/promptflow/setup.py.
   - `python -m venv venv`
   - `venv\Scripts\activate`
   - `pip install promptflow[azure,executable] promptflow-tools`


Building
--------
1. `cd build_scripts/windows/scripts` and run `pyinstaller promptflow.spec`.
2. `cd build_scripts/windows` and Run `msbuild /t:rebuild /p:Configuration=Release /p:Platform=x64 promptflow.wixproj`.
3. The unsigned MSI will be in the `build_scripts/windows/out` folder.