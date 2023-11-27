# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import os
import sys

import waitress
import yaml

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR, PF_SERVICE_PORT_FILE
from promptflow._sdk._service.app import create_app
from promptflow._sdk._service.utils.utils import get_random_port, is_port_in_use
from promptflow._sdk._utils import read_write_by_user
from promptflow._version import VERSION
from promptflow.exceptions import UserErrorException


def main():
    if "USER_AGENT" in os.environ:
        user_agent = f"{os.environ['USER_AGENT']} local_pfs/{VERSION}"
    else:
        user_agent = f"local_pfs/{VERSION}"
    os.environ["USER_AGENT"] = user_agent
    command_args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="pfs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Prompt Flow Service",
    )

    parser.add_argument("-p", "--port", type=int, help="port of the promptflow service")

    args = parser.parse_args(command_args)
    port = args.port
    app, _ = create_app()

    if port and is_port_in_use(port):
        app.logger.warning(f"Service port {port} is used.")
        raise UserErrorException(f"Service port {port} is used.")
    if not port:
        (HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE).touch(mode=read_write_by_user(), exist_ok=True)
        with open(HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE, "r") as f:
            service_config = yaml.safe_load(f) or {}
            port = service_config.get("service", {}).get("port", None)
        if not port:
            with open(HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE, "w") as f:
                # Set random port to ~/.promptflow/pf.yaml
                port = get_random_port()
                service_config["service"] = service_config.get("service", {})
                service_config["service"]["port"] = port
                yaml.dump(service_config, f)

    if is_port_in_use(port):
        app.logger.warning(f"Service port {port} is used.")
        raise UserErrorException(f"Service port {port} is used.")
    # Set host to localhost, only allow request from localhost.
    app.logger.info(f"Start Prompt Flow Service on http://localhost:{port}")
    waitress.serve(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
