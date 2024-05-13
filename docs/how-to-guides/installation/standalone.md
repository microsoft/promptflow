# Standlone CLI

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

A standalone installation of prompt flow bypasses the need for a Python virtual environment and allows users to 
utilize the prompt flow CLI directly in their command terminal. Opt for this option when seeking a swift setup without 
concerns about dependencies or virtual environments, and when preferring the straightforward efficiency of the command line interface.

## Install prompt flow CLI

::::{tab-set}

:::{tab-item} Windows
:sync: Windows

You can use winget, Microsoft's Package manager for Windows, to install and manage updates for prompt flow CLI in Windows OS.
:::{admonition} Note
Note: winget is available by default in Windows 11 and modern versions of Windows 10. However, it may not be installed 
in older versions of Windows. See the [winget documentation](https://learn.microsoft.com/en-us/windows/package-manager/winget/) for installation instructions.
:::

Open a command-line terminal, you can use either PowerShell or Command Prompt (cmd). Run the command below:
```Powershell
winget install -e --id Microsoft.Promptflow
```
The `-e` option is to ensure the official prompt flow package is installed. This command installs the latest version 
by default. To specify a version, add a `-v <version>` with your desired version to the command.
:::

:::{tab-item} Linux/MAC
:sync: Linux/MAC
[pipx](https://pipx.pypa.io/stable/) is a package manager for Python applications that installs them in isolated environments, 
providing a clean separation from your system Python packages. It creates executable binaries for each application, making them easily accessible from the command line.

To install prompt flow CLI using pipx, simply run the following command in your terminal:
```shell
pipx install promptflow
```
This command will download and install prompt flow along with its dependencies in an isolated environment. Once installed, you can use the promptflow command directly 
from your terminal to start developing and executing workflows with ease.
:::

::::

## Verify installation
To verify the installation, run the following command to check the version of prompt flow installed.

```shell
pf --version
```

## Uninstall
- If you install prompt flow CLI using winget, you can uninstallit from the Windows "Apps and Features" list. To uninstall:
    
    | Platform | Instructions |
    |---|---|
    | Windows 11 | Start > Settings > Apps > Installed apps |
    | Windows 10 | Start > Settings > System > Apps & Features |
    
    Once on this screen type __promptflow__ into the program search bar. The program to uninstall is listed as __promptflow(64bit)__. Select this application, then select the `Uninstall` button.
- If you install prompt flow CLI using pipx, you can uninstall it by running the following command in your terminal:
    ```shell
    pipx uninstall promptflow
    ```

:::

