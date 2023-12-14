# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest

import promptflow
import promptflow._sdk._mlflow as module


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestMLFlowDependencies:
    def test_mlflow_dependencies(self):
        assert module.DAG_FILE_NAME == "flow.dag.yaml"
        assert module.Flow == promptflow._sdk.entities._flow.Flow
        assert module.FlowInvoker == promptflow._sdk._serving.flow_invoker.FlowInvoker
        assert module.remove_additional_includes is not None
        assert module._merge_local_code_and_additional_includes is not None
