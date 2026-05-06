# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import getpass

from promptflow._sdk._service.utils.local_user_auth import LocalUserAuthMiddleware


def _remote_user_echo_app(environ, start_response):
    start_response("200 OK", [])
    return [environ.get("REMOTE_USER", "").encode()]


def _call_middleware(remote_addr, extra_environ=None):
    environ = {"REMOTE_ADDR": remote_addr}
    if extra_environ:
        environ.update(extra_environ)

    response_status = []

    def start_response(status, headers):
        response_status.append(status)

    response_body = b"".join(LocalUserAuthMiddleware(_remote_user_echo_app)(environ, start_response)).decode()
    return response_status[0], response_body, environ


def test_loopback_request_injects_current_user():
    status, remote_user, environ = _call_middleware("127.0.0.1")

    assert status == "200 OK"
    assert remote_user == getpass.getuser()
    assert environ["REMOTE_USER"] == getpass.getuser()


def test_ipv6_loopback_request_injects_current_user():
    _, remote_user, environ = _call_middleware("::1")

    assert remote_user == getpass.getuser()
    assert environ["REMOTE_USER"] == getpass.getuser()


def test_non_loopback_request_does_not_inject_user():
    _, remote_user, environ = _call_middleware("192.0.2.10")

    assert remote_user == ""
    assert "REMOTE_USER" not in environ


def test_client_supplied_remote_user_header_is_not_trusted():
    _, remote_user, environ = _call_middleware(
        "192.0.2.10",
        {
            "HTTP_REMOTE_USER": getpass.getuser(),
            "HTTP_X_REMOTE_USER": getpass.getuser(),
        },
    )

    assert remote_user == ""
    assert "REMOTE_USER" not in environ
