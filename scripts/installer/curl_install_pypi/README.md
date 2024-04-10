# Curl Install Script Information

The scripts in this directory are used for installing through curl and they point to the packages on PyPI.

## Install or update promptflow

curl https://promptflowartifact.blob.core.windows.net/linux-install-scripts/install | bash

The script can also be downloaded and run locally. You may have to restart your shell in order for the changes to take effect.

## Uninstall promptflow

Uninstall the promptflow by directly deleting the files from the location chosen at the time of installation.

1. Remove the installed CLI files.

   ```bash
   # The default install/executable location is the user's home directory ($HOME).
   rm -r $HOME/lib/promptflow
   ```

2. Modify your `$HOME/.bash_profile` or `$HOME/.bashrc` file to remove the following line:

   ```text
   export PATH=$PATH:$HOME/lib/promptflow/bin
   ```

3. If using `bash` or `zsh`, reload your shell's command cache.

   ```bash
   hash -r
   ```