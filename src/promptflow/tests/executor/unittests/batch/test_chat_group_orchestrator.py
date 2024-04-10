import os.path
import pytest
from tempfile import mkdtemp
from pathlib import Path

from typing import List, Mapping, Any
from ...utils import get_yaml_file, get_flow_folder
from promptflow.contracts.run_info import Status
from promptflow.executor._result import LineResult
from promptflow._utils.utils import dump_list_to_jsonl
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow._sdk.entities._chat_group._chat_role import ChatRole
from promptflow._orchestrator._chat_group_orchestrator import ChatGroupOrchestrator
from promptflow._orchestrator._errors import (
    MissingConversationHistoryExpression,
    MultipleConversationHistoryInputsMapping,
    InvalidChatRoleCount,
    UsingReservedRoleKey,
    InvalidMaxTurnValue
)
from .test_result import get_flow_run_info, get_node_run_infos


def get_chat_role(role, flow_file=None):
    return ChatRole(flow=os.path.normpath(flow_file), role=role, stop_signal=None)


def get_conversation_history(empty: bool) -> List[Mapping[str, Any]]:
    if empty:
        return []
    conversation_history: List[Mapping[str, Any]] = []
    conversation_history.append({"role": "user", "question": "question0", "others" : "others0"})
    return conversation_history


def get_line_result(output, node_dict):
    return LineResult(
        output=output,
        aggregation_inputs={},
        run_info=get_flow_run_info(status_dict=node_dict , index=0),
        node_run_infos=get_node_run_infos(node_dict=node_dict, index=0, api_calls=None, system_metrics=None),
    )


@pytest.mark.unittest
class TestChatGroupOrchestrator:

    @pytest.mark.parametrize(
        "inputs_mapping, error_code, error_message",
        [
            (
                {
                    "topic": "${data.topic}", "ground_truth": "${data.ground_truth}"
                },
                MissingConversationHistoryExpression,
                "Cannot find conversation expression mapping for chat role: user. name: simulator "
                "Please mapping ${parent.conversation_history} for a flow input."
            ),
            (
                {
                    "topic": "${data.topic}",
                    "ground_truth": "${data.ground_truth}",
                    "history": "${parent.conversation_history}",
                    "conversation_history": "${parent.conversation_history}",
                },
                MultipleConversationHistoryInputsMapping,
                "chat role: user. name: simulator only accepts 1 inputs mapping for ${parent.conversation_history}",
            )
        ],
    )
    def test_process_chat_roles_inputs_with_invalid_inputs_mapping(self, inputs_mapping, error_code, error_message):
        simulation_role = ChatRole(
            flow=get_yaml_file("chat_group/cloud_batch_runs/chat_group_simulation"),
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder("chat_group/cloud_batch_runs/chat_group_simulation"),
            connections=None,
            inputs_mapping=inputs_mapping
        )
        orchestrator = ChatGroupOrchestrator([simulation_role, simulation_role], 3)
        with pytest.raises(error_code) as e:
            orchestrator._process_batch_inputs(inputs=[])
        assert error_message in str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    def test_process_chat_roles_inputs(self):
        simulation_role = ChatRole(
            flow=get_yaml_file("chat_group/cloud_batch_runs/chat_group_simulation"),
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder("chat_group/cloud_batch_runs/chat_group_simulation"),
            connections=None,
            inputs_mapping={
                    "topic": "${data.topic}",
                    "ground_truth": "${data.ground_truth}",
                    "conversation_history": "${parent.conversation_history}",
                }
        )
        data = [
            {"ground_truth": "apple", "topic": "fruit"},
            {"ground_truth": "football", "topic": "sport"},
        ]
        data_file = Path(mkdtemp()) / "data.jsonl"
        dump_list_to_jsonl(data_file, data)
        input_dirs = {"data": data_file}
        inputs = BatchInputsProcessor("", {}).process_batch_inputs_without_inputs_mapping(input_dirs)
        orchestrator = ChatGroupOrchestrator([simulation_role, simulation_role], 3)
        batch_inputs = orchestrator._process_batch_inputs(inputs[0])
        assert len(batch_inputs) == 2
        for i, input in enumerate(batch_inputs):
            assert isinstance(input, dict)
            assert "line_number" in input, f"line_number is not in {i}th input {input}"
            assert "conversation_history" in input, f"conversation_history is not in {i}th output {input}"

    @pytest.mark.parametrize(
        "error_code, error_message",
        [
            (
                InvalidChatRoleCount,
                "Invalid chat group role count: 1. Please define 2 chat group roles at least."
            )
        ],
    )
    def test_process_chat_roles_inputs_with_invalid_chat_role_count(self, error_code, error_message):
        simulation_role = ChatRole(
            flow=get_yaml_file("chat_group/cloud_batch_runs/chat_group_simulation"),
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder("chat_group/cloud_batch_runs/chat_group_simulation"),
            connections=None,
            inputs_mapping={"topic": "${data.topic}", "ground_truth": "${data.ground_truth}"}
        )
        with pytest.raises(error_code) as e:
            ChatGroupOrchestrator([simulation_role], 3)
        assert error_message in str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize(
        "error_code, error_message",
        [
            (
                    InvalidMaxTurnValue,
                    "Invalid max_turn value for chat group run: 0. Please assign max_turn at least 1."
            )
        ],
    )
    def test_process_chat_roles_inputs_with_invalid_max_turn_count(self, error_code, error_message):
        simulation_role = ChatRole(
            flow=get_yaml_file("chat_group/cloud_batch_runs/chat_group_simulation"),
            role="user",
            name="simulator",
            stop_signal="[STOP]",
            working_dir=get_flow_folder("chat_group/cloud_batch_runs/chat_group_simulation"),
            connections=None,
            inputs_mapping={"topic": "${data.topic}", "ground_truth": "${data.ground_truth}"}
        )
        with pytest.raises(error_code) as e:
            ChatGroupOrchestrator([simulation_role, simulation_role])
        assert error_message in str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize(
        "chat_role, conversation_history",
        [
            (
                    get_chat_role(role="user", flow_file=get_yaml_file("hello-world")),
                    get_conversation_history(empty=True)
            ),
            (
                    get_chat_role(role="assistant", flow_file=get_yaml_file("hello-world")),
                    get_conversation_history(empty=False)
            )
        ],
    )
    def test_process_flow_outputs(self, chat_role, conversation_history):
        line_result = get_line_result(
            output={"question": "question0", "others": "others0"},
            node_dict={"node_0": Status.Failed, "node_1": Status.Completed, "node_2": Status.Completed}
        )
        orchestrator = ChatGroupOrchestrator(
            [
                get_chat_role(role="user", flow_file=get_yaml_file("hello-world")),
                chat_role
            ],
            3
        )
        conversation_history_len = len(conversation_history)
        outputs = {}
        orchestrator._process_flow_outputs(0, chat_role, line_result, conversation_history, outputs, {})
        cur_conversation_history_len = len(conversation_history)

        assert cur_conversation_history_len == conversation_history_len + 1
        current_line = conversation_history[-1]
        assert current_line["role"] == chat_role.role == outputs[0]["role"]
        assert current_line["question"] == "question0" == outputs[0]["question"]
        assert current_line["others"] == "others0" == outputs[0]["others"]

    @pytest.mark.parametrize(
        "error_code, error_message",
        [
            (
                    UsingReservedRoleKey,
                    "chat role output use reserved key role"
            )
        ],
    )
    def test_process_flow_outputs_with_reserved_key(self, error_code, error_message):
        line_result = get_line_result(
            output={"question": "question0", "role": "reserved"},
            node_dict={"node_0": Status.Failed, "node_1": Status.Completed, "node_2": Status.Completed}
        )
        conversation_history = get_conversation_history(empty=True)
        chat_role = get_chat_role(role="user", flow_file=get_yaml_file("hello-world"))
        orchestrator = ChatGroupOrchestrator([chat_role, chat_role], 3)
        outputs = {}
        with pytest.raises(error_code) as e:
            orchestrator._process_flow_outputs(0, chat_role, line_result, conversation_history, outputs, {})
        assert error_message in str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))
