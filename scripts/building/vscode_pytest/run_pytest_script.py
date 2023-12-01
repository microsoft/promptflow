# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import os
import pathlib
import socket
import sys

import pytest

script_dir = pathlib.Path(__file__).parent.parent
sys.path.append(os.fspath(script_dir))
sys.path.append(os.fspath(script_dir / "lib" / "python"))
from testing_tools import process_json_util

# This script handles running pytest via pytest.main(). It is called via run in the
# pytest execution adapter and gets the test_ids to run via stdin and the rest of the
# args through sys.argv. It then runs pytest.main() with the args and test_ids.

if __name__ == "__main__":
    # Add the root directory to the path so that we can import the plugin.
    directory_path = pathlib.Path(__file__).parent.parent
    sys.path.append(os.fspath(directory_path))
    sys.path.insert(0, os.getcwd())
    # Get the rest of the args to run with pytest.
    args = sys.argv[1:]
    run_test_ids_port = os.environ.get("RUN_TEST_IDS_PORT")
    run_test_ids_port_int = (
        int(run_test_ids_port) if run_test_ids_port is not None else 0
    )
    test_ids_from_buffer = []
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("localhost", run_test_ids_port_int))
        print(f"CLIENT: Server listening on port {run_test_ids_port_int}...")
        buffer = b""

        while True:
            # Receive the data from the client
            data = client_socket.recv(1024 * 1024)
            if not data:
                break

            # Append the received data to the buffer
            buffer += data

            try:
                # Try to parse the buffer as JSON
                test_ids_from_buffer = process_json_util.process_rpc_json(
                    buffer.decode("utf-8")
                )
                # Clear the buffer as complete JSON object is received
                buffer = b""

                # Process the JSON data
                print(f"Received JSON data: {test_ids_from_buffer}")
                break
            except json.JSONDecodeError:
                # JSON decoding error, the complete JSON object is not yet received
                continue
    except socket.error as e:
        print(f"Error: Could not connect to runTestIdsPort: {e}")
        print("Error: Could not connect to runTestIdsPort")
    try:
        if test_ids_from_buffer:
            arg_array = ["-p", "vscode_pytest"] + args + test_ids_from_buffer
            pytest.main(arg_array)
    except json.JSONDecodeError:
        print("Error: Could not parse test ids from stdin")
