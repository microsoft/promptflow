# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import getpass

_LOOPBACK_REMOTE_ADDRS = {"127.0.0.1", "::1"}


class LocalUserAuthMiddleware:
    """Inject the current OS user for local PFS loopback requests."""

    def __init__(self, wsgi_app):
        self._wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # Strip any client-supplied identity headers to prevent spoofing.
        environ.pop("HTTP_REMOTE_USER", None)
        environ.pop("HTTP_X_REMOTE_USER", None)

        if environ.get("REMOTE_ADDR") in _LOOPBACK_REMOTE_ADDRS:
            environ["REMOTE_USER"] = getpass.getuser()
        return self._wsgi_app(environ, start_response)
