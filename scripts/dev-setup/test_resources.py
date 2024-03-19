# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json

from utils import REPO_ROOT_DIR, print_yellow


def create_tracing_test_resource_template() -> None:
    working_dir = REPO_ROOT_DIR / "promptflow-tracing"
    connections_filename = "connections.json"
    connections_file_path = (working_dir / connections_filename).resolve().absolute()
    connections_template = {
        "azure_open_ai_connection": {
            "value": {
                "api_key": "aoai-api-key",
                "api_base": "aoai-api-endpoint",
                "api_version": "2023-07-01-preview",
            }
        }
    }
    with open(connections_file_path, mode="w", encoding="utf-8") as f:
        json.dump(connections_template, f, ensure_ascii=False, indent=4)

    prompt_msg = (
        f"Created test-required file {connections_filename!r} at {connections_file_path.as_posix()!r}, "
        "please update with your test resource(s)."
    )
    print_yellow(prompt_msg)


REGISTERED_TEST_RESOURCES_FUNCTIONS = {
    "promptflow-tracing": create_tracing_test_resource_template,
}
