# Frequency asked questions (FAQ)

## Troubleshooting ##

### Connection creation failed with StoreConnectionEncryptionKeyError

```
Connection creation failed with StoreConnectionEncryptionKeyError: System keyring backend service not found in your operating system. See https://pypi.org/project/keyring/ to install requirement for different operating system, or 'pip install keyrings.alt' to use the third-party backend.
```

Install the third-party key-ring backend.
`pip install keyrings.alt`

### Pf visualize show error: "tcgetpgrp failed: Not a tty"

WIP

