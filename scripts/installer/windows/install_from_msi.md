# Install prompt flow MSI installer on Windows
Prompt flow is a suite of development tools designed to streamline the end-to-end development 
cycle of LLM-based AI applications, that can be installed locally on Windows computers.

For Windows, the prompt flow is installed via an MSI, which gives you access to the CLI 
through the Windows Command Prompt (CMD) or PowerShell.

## Install or update

The MSI distributable is used for installing or updating the prompt flow on Windows. 
You don't need to uninstall current versions before using the MSI installer because 
the MSI updates any existing version.

::::{tab-set}
:::{tab-item} Microsoft Installer (MSI)
:sync: Microsoft Installer (MSI)
### Latest version

Download and install the latest release of the prompt flow. 
When the installer asks if it can make changes to your computer, select the "Yes" box.

> [Latest release of the promptflow (64-bit)](https://aka.ms/installpromptflowwindowsx64)
)


### Specific version

If you prefer, you can download a specific version of the promptflow by using a URL. 
To download the MSI installer for a specific version, change the version segment in URL
https://promptflowartifact.blob.core.windows.net/msi-installer/promptflow-<version>.msi
:::

:::{tab-item} Microsoft Installer (MSI) with PowerShell
:sync: Microsoft Installer (MSI) with PowerShell

### PowerShell

To install the prompt flow using PowerShell, start PowerShell and 
run the following command:

   ```PowerShell
   $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri https://aka.ms/installpromptflowwindowsx64 -OutFile .\promptflow.msi; Start-Process msiexec.exe -Wait -ArgumentList '/I promptflow.msi /quiet'; Remove-Item .\promptflow.msi
   ```

This will download and install the latest 64-bit installer of the prompt flow for Windows.

To install a specific version, replace the `-Uri` argument with the URL like below. 
Here is an example of using the 64-bit installer of the promptflow version 1.0.0 in PowerShell:

   ```PowerShell
   $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri https://promptflowartifact.blob.core.windows.net/msi-installer/promptflow-1.0.0.msi -OutFile .\promptflow.msi; Start-Process msiexec.exe -Wait -ArgumentList '/I promptflow.msi /quiet'; Remove-Item .\promptflow.msi
   ```
:::

::::



## Run the prompt flow

You can now run the prompt flow with the `pf` or `pfazure` command from either Windows Command Prompt or PowerShell.


## Upgrade the prompt flow
Beginning with version 1.4.0, the prompt flow provides an in-tool command to upgrade to the latest version.

```commandline
pf upgrade
```
For prompt flow versions prior to 1.4.0, upgrade by reinstalling as described in Install the prompt flow.

## Uninstall
You uninstall the prompt flow from the Windows "Apps and Features" list. To uninstall:

| Platform | Instructions |
|---|---|
| Windows 11 | Start > Settings > Apps > Installed apps |
| Windows 10 | Start > Settings > System > Apps & Features |
| Windows 8 and Windows 7 | Start > Control Panel > Programs > Uninstall a program |

Once on this screen type __promptflow_ into the program search bar. 
The program to uninstall is listed as __promptflow (64-bit)__. 
Select this application, then select the `Uninstall` button.

## FAQ

### Where is the prompt flow installed?
In Windows, the 64-bit prompt flow installs in `C:\Users\**\AppData\Local\Apps\promptflow` by default. 


### What version of the prompt flow is installed?

Type `pf --version` in a terminal window to know what version of the prompt flow is installed. 
Your output looks like this:

```output
promptflow                       x.x.x

Executable '***\python.exe'
Python (Windows) 3.*.* | packaged by conda-forge | *
```