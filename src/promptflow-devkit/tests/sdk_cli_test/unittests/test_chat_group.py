import pytest
from _constants import PROMPTFLOW_ROOT
from pytest_mock import MockFixture

from promptflow._sdk._errors import ChatGroupError, ChatRoleError
from promptflow._sdk.entities._chat_group._chat_group import ChatGroup
from promptflow._sdk.entities._chat_group._chat_role import ChatRole

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
FLOWS_DIR = TEST_ROOT / "test_configs/flows"


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestChatGroup:
    def test_chat_role_creation_error(self):
        with pytest.raises(ChatRoleError, match=r"Failed to create chat role"):
            ChatRole(flow=FLOWS_DIR / "non_existing_flow", role="assistant")

    def test_chat_role_invoke_error(self):
        copilot = ChatRole(
            flow=FLOWS_DIR / "chat_group_copilot",
            role="assistant",
            name="copilot",
            inputs=dict(
                question="Tell me a joke",
                model="gpt-3.5-turbo",
                conversation_history="${parent.conversation_history}",
            ),
        )
        with pytest.raises(ChatRoleError, match=r"Chat role invoke does not accept positional arguments"):
            copilot.invoke(1)

    def test_chat_group_invalid_parameters(self, mocker: MockFixture):
        mocker.patch.object(ChatRole, "_build_role_io", return_value=({}, {}))
        copilot = ChatRole(flow=FLOWS_DIR / "chat_group_copilot", role="assistant")
        simulation = ChatRole(flow=FLOWS_DIR / "chat_group_simulation", role="user")
        simulation_1 = ChatRole(flow=FLOWS_DIR / "chat_group_simulation", role="user")
        entry = ChatRole(flow=FLOWS_DIR / "hello-world", role="user2")

        # entry role is not in role list
        with pytest.raises(ChatGroupError, match=r"Entry role .*? is not in roles list"):
            ChatGroup(roles=[copilot, simulation], entry_role=entry)

        # invalid roles passed in
        with pytest.raises(ChatGroupError, match="Agents should be a non-empty list of ChatRole"):
            ChatGroup(roles=[1, True])

        # duplicate roles
        with pytest.raises(ChatGroupError, match="Duplicate roles are not allowed"):
            ChatGroup(roles=[simulation, simulation_1])

        # invalid parameters
        with pytest.raises(ChatGroupError, match="should be an integer"):
            ChatGroup(roles=[copilot, simulation], max_turns="4")
        with pytest.raises(ChatGroupError, match="should be an integer"):
            ChatGroup(roles=[copilot, simulation], max_tokens="1000")
        with pytest.raises(ChatGroupError, match="should be an integer"):
            ChatGroup(roles=[copilot, simulation], max_time="1000")

    def test_chat_role_flow_dag_file(self):
        copilot = ChatRole(
            flow="flow.dag.yaml",
            role="assistant",
            name="copilot",
            working_dir=FLOWS_DIR / "chat_group_copilot",
        )
        assert copilot._flow_definition is not None
