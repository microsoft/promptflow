from pathlib import Path

import pytest

from promptflow._sdk.entities._chat_group._chat_group import ChatGroup
from promptflow._sdk.entities._chat_group._chat_role import ChatRole

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
FLOWS_DIR = TEST_ROOT / "test_configs/flows"


@pytest.mark.sdk_test
@pytest.mark.e2etest
@pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
class TestChatGroup:
    def test_chat_group_basic_invoke(self):
        question = "What's the most beautiful thing in the world?"
        ground_truth = "The world itself."

        copilot = ChatRole(
            flow=FLOWS_DIR / "chat_group_copilot",
            role="assistant",
            inputs=dict(
                question=question,
                model="gpt-3.5-turbo",
                conversation_history="${parent.conversation_history}",
            ),
        )
        simulation = ChatRole(
            flow=FLOWS_DIR / "chat_group_simulation",
            role="user",
            inputs=dict(
                question=question,
                ground_truth=ground_truth,
                conversation_history="${parent.conversation_history}",
            ),
        )

        chat_group = ChatGroup(
            roles=[copilot, simulation],
            max_turns=4,
            max_tokens=1000,
            max_time=1000,
            stop_signal="[STOP]",
        )
        chat_group.invoke()

        # history has 4 records
        history = chat_group.conversation_history
        assert len(history) == 4
        assert history[0][0] == history[2][0] == copilot.role
        assert history[1][0] == history[3][0] == simulation.role
