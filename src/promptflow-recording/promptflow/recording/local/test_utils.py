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
    from promptflow._sdk._constants import PF_SERVICE_HOST
    from promptflow._sdk._service.utils.utils import get_pfs_port

    port = str(get_pfs_port())
    if platform.system() == "Windows":
        _start_background_service_on_windows(port)
    else:
        _start_background_service_on_unix(port)
    time.sleep(20)  # we need some seconds to start the service
    response = requests.get(f"http://{PF_SERVICE_HOST}:{port}/heartbeat")
    assert response.status_code == 200, "prompt flow service is not healthy via /heartbeat"
    return port
