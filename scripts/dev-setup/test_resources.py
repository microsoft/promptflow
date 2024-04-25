# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import shutil
from pathlib import Path

from utils import REPO_ROOT_DIR, print_yellow


def _prompt_user_for_test_resources(path: Path) -> None:
    prompt_msg = (
        f"Created test-required file {path.name!r} at {path.as_posix()!r}, "
        "please update with your test resource(s)."
    )
    print_yellow(prompt_msg)


def create_tracing_test_resource_template() -> None:
    working_dir = REPO_ROOT_DIR / "src" / "promptflow-tracing"
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
    _prompt_user_for_test_resources(connections_file_path)


def create_evals_test_resource_template() -> None:
    working_dir = REPO_ROOT_DIR / "src" / "promptflow-evals"
    connections_filename = "connections.json"
    connections_file_path = (working_dir / connections_filename).resolve().absolute()
    connections_template = {
        "azure_openai_model_config": {
            "value": {
                "azure_endpoint": "aoai-api-endpoint",
                "api_key": "aoai-api-key",
                "api_version": "2023-07-01-preview",
                "azure_deployment": "aoai-deployment"
            },
        },
        "azure_ai_project_scope": {
            "value": {
                "subscription_id": "subscription-id",
                "resource_group_name": "resource-group-name",
                "project_name": "project-name"
            }
        }
    }
    with open(connections_file_path, mode="w", encoding="utf-8") as f:
        json.dump(connections_template, f, ensure_ascii=False, indent=4)
    _prompt_user_for_test_resources(connections_file_path)


def create_tools_test_resource_template() -> None:
    working_dir = REPO_ROOT_DIR / "src" / "promptflow-tools"
    example_file_path = (working_dir / "connections.json.example").resolve().absolute()
    target_file_path = (working_dir / "connections.json").resolve().absolute()
    shutil.copy(example_file_path, target_file_path)
    _prompt_user_for_test_resources(target_file_path)


REGISTERED_TEST_RESOURCES_FUNCTIONS = {
    "promptflow-tracing": create_tracing_test_resource_template,
    "promptflow-tools": create_tools_test_resource_template,
    "promptflow-evals": create_evals_test_resource_template,
}
