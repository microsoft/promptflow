# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect
import os
import re

from vcr.request import Request

TEST_RUN_LIVE = "PROMPT_FLOW_TEST_RUN_LIVE"
SKIP_LIVE_RECORDING = "PROMPT_FLOW_SKIP_LIVE_RECORDING"

REGISTERED_FIXTURES = [
    "ml_client",
    "remote_client",
    "pf",
    "remote_web_classification_data",
    "runtime",
    "ml_client_with_acr_access",
    # test_arm_connection_operations.py & test_connection_operations.py
    "connection_ops",
]


def is_live() -> bool:
    return os.environ.get(TEST_RUN_LIVE, None) == "true"


def is_live_and_not_recording() -> bool:
    return is_live() and os.environ.get(SKIP_LIVE_RECORDING, None) == "true"


class SanitizedValues:
    SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000000"
    RESOURCE_GROUP_NAME = "00000"
    WORKSPACE_NAME = "00000"


def fixture_provider(testcase_func):
    # pytest fixture does not work with unittest.TestCase, except for autouse fixtures
    # use this decorator to inject fixtures so that the experience is consistent with pytest
    # reference: https://pytest.org/en/latest/how-to/unittest.html
    @functools.wraps(testcase_func)
    def wrapper(test_class_instance):
        injected_params = {}
        params = inspect.signature(testcase_func).parameters
        for name, param in params.items():
            if name not in REGISTERED_FIXTURES:
                injected_params[name] = param
            else:
                injected_params[name] = getattr(test_class_instance, name)
        testcase_func(**injected_params)

    return wrapper


def sanitize_azure_workspace_triad(val: str) -> str:
    sanitized_sub = re.sub(
        "/(subscriptions)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        r"/\1/{}".format("00000000-0000-0000-0000-000000000000"),
        val,
        flags=re.IGNORECASE,
    )
    # for regex pattern for resource group name and workspace name, refer from:
    # https://learn.microsoft.com/en-us/rest/api/resources/resource-groups/create-or-update?tabs=HTTP
    sanitized_rg = re.sub(
        r"/(resourceGroups)/[-\w\._\(\)]+",
        r"/\1/{}".format("00000"),
        sanitized_sub,
        flags=re.IGNORECASE,
    )
    sanitized_ws = re.sub(
        r"/(workspaces)/[-\w\._\(\)]+/",
        r"/\1/{}/".format("00000"),
        sanitized_rg,
        flags=re.IGNORECASE,
    )
    return sanitized_ws


def _is_json_payload(headers: dict, key: str) -> bool:
    if not headers:
        return False
    content_type = headers.get(key)
    if not content_type:
        return False
    # content-type can be an array, e.g. ["application/json; charset=utf-8"]
    content_type = content_type[0] if isinstance(content_type, list) else content_type
    content_type = content_type.split(";")[0].lower()
    return "application/json" in content_type


def is_json_payload_request(request: Request) -> bool:
    headers = request.headers
    return _is_json_payload(headers, key="Content-Type")


def is_json_payload_response(response: dict) -> bool:
    headers = response.get("headers")
    # PFAzureIntegrationTestCase will lower keys in response headers
    return _is_json_payload(headers, key="content-type")
