# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from ..utils import PFSOperations, check_activity_end_telemetry


@pytest.mark.csharp
@pytest.mark.e2etest
class TestCSharp:
    def test_get_flow_yaml(self, pfs_op: PFSOperations, csharp_test_project_basic) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            flow_yaml_from_pfs = pfs_op.get_flow_yaml(flow_path=csharp_test_project_basic["flow_dir"]).data.decode(
                "utf-8"
            )
        assert flow_yaml_from_pfs == (
            "$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json\n"
            "display_name: Basic\n"
            "language: csharp\n"
            "inputs:\n"
            "  question:\n"
            "    type: string\n"
            "    default: what is promptflow?\n"
            "outputs:\n"
            "  answer:\n"
            "    type: string\n"
            "    reference: ${get_answer.output}\n"
            "nodes:\n"
            "- name: get_answer\n"
            "  type: csharp\n"
            "  source:\n"
            "    type: package\n"
            "    tool: (Basic)Basic.Flow.HelloWorld\n"
            "  inputs:\n"
            "    question: ${inputs.question}\n"
        )

    def test_get_eager_flow_yaml(self, pfs_op: PFSOperations, csharp_test_project_function_mode_basic) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            flow_yaml_from_pfs = pfs_op.get_flow_yaml(
                flow_path=csharp_test_project_function_mode_basic["flow_dir"]
            ).data.decode("utf-8")
        assert flow_yaml_from_pfs == (
            "$schema: https://azuremlschemas.azureedge.net/promptflow/latest/flow.schema.json\n"
            "\n"
            "language: csharp\n"
            "entry: (FunctionModeBasic)FunctionModeBasic.MyEntry.WritePoemReturnObjectAsync\n"
        )
