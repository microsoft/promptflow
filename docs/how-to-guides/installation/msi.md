# Install standalone prompt flow CLI

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

The promptflow CLI provides commands to manage prompt flow resources.


## Install prompt flow CLI

::::{tab-set}

:::{tab-item} Windows Package Manager
:sync: Windows Package Manager

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

:::{tab-item} Install prompt flow using pipx
:sync: Install prompt flow using pipx
[pipx](https://pipx.pypa.io/stable/)  is a package manager for Python applications that installs them in isolated environments, 
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