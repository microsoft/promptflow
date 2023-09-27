# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect
import unittest

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


class PFAzureIntegrationTestCase(unittest.TestCase):
    def __init__(self, method_name: str) -> None:
        super(PFAzureIntegrationTestCase, self).__init__(method_name)

    def setUp(self) -> None:
        super(PFAzureIntegrationTestCase, self).setUp()
