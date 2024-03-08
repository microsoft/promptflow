from pathlib import Path

import pytest

from promptflow._sdk.entities._chat_group._chat_group import ChatGroup
from promptflow._sdk.entities._chat_group._chat_role import ChatRole

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
FLOWS_DIR = TEST_ROOT / "test_configs/flows"


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestChatGroup:
    def test_basic_invoke(self):
        topic = "Tell me a joke"
        copilot = ChatRole(
            flow=FLOWS_DIR / "chat_group_copilot",
            role="assistant",
            name="copilot",
            inputs=dict(
                question=topic,
                model="",
                conversation_history="${parent.conversation_history}",
            ),
        )
        simulation = ChatRole(
            flow=FLOWS_DIR / "chat_group_criticizer",
            role="user",
            name="simulation",
            inputs=dict(
                topic=topic,
                persona="criticizer",
                conversation_history="${parent.conversation_history}",
            ),
        )

        chat_group = ChatGroup(
            roles=[copilot, simulation],
            max_turns=4,
            max_tokens=1000,
            max_time=1000,
            stop_signal="[stop]",
        )
        assert chat_group
        chat_group.invoke()

        # Initial group level input plus 4 turns, so 5 in total
        history = chat_group.chat_history.history
        assert len(history) == 5
        assert history[0][1]["request"] == group_input_request
        assert history[0][1]["comments"] == "I like it"
