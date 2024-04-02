import pytest
from ...utils import get_yaml_file, get_flow_folder
from promptflow._sdk.entities._chat_group._chat_role import ChatRole
from promptflow._orchestrator._chat_group_orchestrator import ChatGroupOrchestrator
from promptflow._orchestrator._errors import (
    MissingConversationHistoryExpression,
    MultipleConversationHistoryInputsMapping,
    InvalidChatRoleCount
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
        orchestrator = ChatGroupOrchestrator([simulation_role, simulation_role])
        with pytest.raises(error_code) as e:
            orchestrator._process_batch_inputs(inputs=[])
        assert error_message in str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

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
            ChatGroupOrchestrator([simulation_role])
        assert error_message in str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))
