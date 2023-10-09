# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect

REGISTERED_FIXTURES = [
    "ml_client",
    "remote_client",
    "pf",
    "remote_web_classification_data",
    "runtime",
    "ml_client_with_acr_access",
]


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


def is_json_payload_response(response: dict) -> bool:
    headers = response.get("headers")
    if headers:
        # PFAzureIntegrationTestCase will lower keys in response headers
        content_type = headers.get("content-type")
        if content_type:
            return "application/json" in content_type
    return False
