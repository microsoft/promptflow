# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import unittest


class PFAzureIntegrationTestCase(unittest.TestCase):
    def __init__(self, method_name: str) -> None:
        super(PFAzureIntegrationTestCase, self).__init__(method_name)

    def setUp(self) -> None:
        return super(PFAzureIntegrationTestCase, self).setUp()
