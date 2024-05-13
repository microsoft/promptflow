# Standalone CLI

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

A standalone installation of prompt flow bypasses the need for a Python virtual environment and allows users to 
utilize the prompt flow CLI directly in their command terminal. Opt for this option when seeking a swift setup without 
concerns about dependencies or virtual environments, and when preferring the straightforward efficiency of the command line interface.

## Install

::::{tab-set}

:::{tab-item} Windows
:sync: Windows

You can use `winget`, Microsoft's Package manager for Windows, to install and manage updates for prompt flow CLI in Windows OS.

Note: winget is available by default in Windows 11 and modern versions of Windows 10. However, it may not be installed 
in older versions of Windows. See the [winget documentation](https://learn.microsoft.com/en-us/windows/package-manager/winget/) for installation instructions.


Open a command-line terminal, you can use either PowerShell or Command Prompt (cmd). Run the command below:
```Powershell
winget install -e --id Microsoft.Promptflow
```
The `-e` option is to ensure the official prompt flow package is installed. This command installs the latest version 
by default. To specify a version, add a `-v <version>` with your desired version to the command.
:::

::::

## Verify installation
To verify the installation, run the following command to check the version of prompt flow installed.

```shell
pf --version
```

## Uninstall
- If you install prompt flow CLI using winget, you can uninstall it by running the following command in your terminal:
    ```Powershell
    winget uninstall Microsoft.Promptflow
    ```

