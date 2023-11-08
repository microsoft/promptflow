# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import stat
import sys

import waitress
import yaml

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR, SERVICE_CONFIG_FILE
from promptflow._sdk._service.app import create_app
from promptflow._sdk._service.utils import get_random_port, is_port_in_use
from promptflow.exceptions import UserErrorException


def main():
    command_args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="pfs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Prompt Flow Service",
    )

    parser.add_argument("-p", "--port", type=int, help="port of the promptflow service")
    args = parser.parse_args(command_args)
    port = args.port

    if port and is_port_in_use():
        raise UserErrorException(f"Service port {port} is used.")
    if not port:
        # Read and write permission for user.
        mode = stat.S_IRUSR | stat.S_IWUSR
        (HOME_PROMPT_FLOW_DIR / SERVICE_CONFIG_FILE).touch(mode=mode, exist_ok=True)
        with open(HOME_PROMPT_FLOW_DIR / SERVICE_CONFIG_FILE, "r") as f:
            service_config = yaml.safe_load(f)
            port = service_config.get("service", {}).get("port", None)

    app = create_app()
    # Set host to localhost, only allow request from localhost.
    waitress(app, host="127.0.0.1", port=port or get_random_port())


if __name__ == "__main__":
    main()
