# Building the Windows MSI Installer

This document provides instructions on creating the MSI installer.

## Option1: Building with Github Actions
Trigger the [workflow](https://github.com/microsoft/promptflow/actions/workflows/build_msi_installer.yml) manually.


## Option2: Local Building
### Prerequisites

1. Turn on the '.NET Framework 3.5' Windows Feature (required for WIX Toolset).
2. Install 'Microsoft Build Tools 2015'.
    https://www.microsoft.com/download/details.aspx?id=48159
3. You need to have curl.exe, unzip.exe and msbuild.exe available under PATH.
4. Install 'WIX Toolset build tools' following the instructions below.
   - Enter the directory where the README is located (`cd scripts/installer/windows`), `mkdir wix` and `cd wix`.
   - `curl --output wix-archive.zip  https://azurecliprod.blob.core.windows.net/msi/wix310-binaries-mirror.zip`
   - `unzip wix-archive.zip` and `del wix-archive.zip`
5. We recommend creating a clean virtual Python environment and installing all dependencies using src/promptflow/setup.py.
   - `python -m venv venv`
   - `venv\Scripts\activate`
   - `pip install promptflow[azure,executable,azureml-serving,executor-service] promptflow-tools`


### Building
1. Update the version number `$(env.CLI_VERSION)` and `$(env.FILE_VERSION)` in `product.wxs`, `promptflow.wixproj` and `version_info.txt`.
2. `cd scripts/installer/windows/scripts` and run `python generate_dependency.py`.
3. run `pyinstaller promptflow.spec`.
4. `cd scripts/installer/windows` and Run `msbuild /t:rebuild /p:Configuration=Release /p:Platform=x64 promptflow.wixproj`.
5. The unsigned MSI will be in the `scripts/installer/windows/out` folder.

## Notes
- If you encounter "Access is denied" error when running promptflow. Please follow the [link](https://learn.microsoft.com/en-us/microsoft-365/security/defender-endpoint/attack-surface-reduction-rules-deployment-implement?view=o365-worldwide#customize-attack-surface-reduction-rules) to add the executable to the Windows Defender Attack Surface Reduction (ASR) rule.
Or you can add promptflow installation folder to the Windows Defender exclusion list.