# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uuid

import pytest

from promptflow._constants import ResourceAttributeFieldName
from promptflow._trace._start_trace import _create_resource


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestStartTrace:
    def test_create_resource(self):
        session_id = str(uuid.uuid4())
        resource1 = _create_resource(session_id=session_id)
        assert resource1.attributes[ResourceAttributeFieldName.SESSION_ID] == session_id
        assert ResourceAttributeFieldName.EXPERIMENT_NAME not in resource1.attributes

        experiment = "test_experiment"
        resource2 = _create_resource(session_id=session_id, experiment=experiment)
        assert resource2.attributes[ResourceAttributeFieldName.SESSION_ID] == session_id
        assert resource2.attributes[ResourceAttributeFieldName.EXPERIMENT_NAME] == experiment
