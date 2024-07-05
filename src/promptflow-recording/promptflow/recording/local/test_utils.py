# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import platform
import time

import requests


def invoke_prompt_flow_service() -> str:
    # invoke prompt flow service as a standby service
    # so use some private APIs, instead of existing API
    # then this port won't be recorded in pf.config
    from promptflow._cli._pf._service import _start_background_service_on_unix, _start_background_service_on_windows
    from promptflow._sdk._service.utils.utils import get_pfs_host, get_pfs_host_after_check_wildcard, get_pfs_port

    service_host = get_pfs_host()
    host = get_pfs_host_after_check_wildcard(service_host)
    port = str(get_pfs_port(host))
    if platform.system() == "Windows":
        _start_background_service_on_windows(port, service_host)
    else:
        _start_background_service_on_unix(port, service_host)
    time.sleep(20)  # we need some seconds to start the service
    response = requests.get(f"http://{host}:{port}/heartbeat")
    assert response.status_code == 200, "prompt flow service is not healthy via /heartbeat"
    return port, host
