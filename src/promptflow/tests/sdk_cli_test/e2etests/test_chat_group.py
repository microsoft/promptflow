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
        joke_master = ChatRole(flow=FLOWS_DIR / "chat_group_joke_master")
        criticizer = ChatRole(flow=FLOWS_DIR / "chat_group_criticizer")

        chat_group = ChatGroup(
            agents=[joke_master, criticizer],
            # entry_agent=joke_master,
            max_turns=4,
            max_tokens=1000,
            max_time=1000,
            inputs={
                "request": {
                    "type": str,
                    "default": "Please tell me a joke",
                    "initialize_for": joke_master.inputs.text,
                },
                "comments": {
                    "type": str,
                    "default": "I like it",
                },
            },
            outputs={
                "result": {
                    "type": str,
                    "reference": criticizer.outputs.result,
                }
            },
        )
        assert chat_group
        joke_master.set_inputs(text=criticizer.outputs.result)
        criticizer.set_inputs(
            words=joke_master.outputs.output,
            third_party_comments=chat_group.inputs.comments,
            chat_history=chat_group.chat_history,
        )

        group_input_request = "Hi, tell me a joke pls."
        chat_group.invoke(request=group_input_request)

        # Initial group level input plus 4 turns, so 5 in total
        history = chat_group.chat_history.history
        assert len(history) == 5
        assert history[0][1]["request"] == group_input_request
        assert history[0][1]["comments"] == "I like it"
