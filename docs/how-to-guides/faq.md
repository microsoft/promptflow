# Frequency asked questions (FAQ)

## General ##

### Stable vs experimental

Prompt flow provides both stable and experimental features in the same SDK.

|Feature status | Description | 
|----------------|----------------|
Stable features	| **Production ready** <br/><br/> These features are recommended for most use cases and production environments. They are updated less frequently then experimental features.|
Experimental features | **Developmental**  <br/><br/> These features are newly developed capabilities & updates that may not be ready or fully tested for production usage. While the features are typically functional, they can include some breaking changes. Experimental features are used to iron out SDK breaking bugs, and will only receive updates for the duration of the testing period. Experimental features are also referred to as features that are in **preview**. <br/> As the name indicates, the experimental (preview) features are for experimenting and is **not considered bug free or stable**. For this reason, we only recommend experimental features to advanced users who wish to try out early versions of capabilities and updates, and intend to participate in the reporting of bugs and glitches.

## Troubleshooting ##

### Connection creation failed with StoreConnectionEncryptionKeyError

```
Connection creation failed with StoreConnectionEncryptionKeyError: System keyring backend service not found in your operating system. See https://pypi.org/project/keyring/ to install requirement for different operating system, or 'pip install keyrings.alt' to use the third-party backend.
```

This error raised due to keyring can't find an available backend to store keys.
For example [macOs Keychain](https://en.wikipedia.org/wiki/Keychain_%28software%29) and [Windows Credential Locker](https://learn.microsoft.com/en-us/windows/uwp/security/credential-locker)
are valid keyring backends.

To resolve this issue, install the third-party keyring backend or write your own keyring backend, for example:
`pip install keyrings.alt`

For more detail about keyring third-party backend, please refer to 'Third-Party Backends' in [keyring](https://pypi.org/project/keyring/).

### Pf visualize show error: "tcgetpgrp failed: Not a tty"

If you are using WSL, this is a known issue for `webbrowser` under WSL; see [this issue](https://github.com/python/cpython/issues/89752) for more information. Please try to upgrade your WSL to 22.04 or later, this issue should be resolved.

If you are still facing this issue with WSL 22.04 or later, or you are not even using WSL, please open an issue to us.

### The tool installed by package is not visible in the tool list in VSCode Extension

In VSCode Extension, if you find that you have installed the tool package via `pip install [tool-package-name]` but you can't see the tool in the tool list as below:

![The tool list in VScode extension](../media/how-to-guides/vscode-tool-list.png)

You may need to reload the window of VSCode Extension to clean previous cache. Bring up the command palette by pressing `Ctrl+Ship+P`, type and choose the `Developer: Reload Webviews` command to reload. Waiting for a moment, then you can see that the tool list has been refreshed and the installed tools are visible.

